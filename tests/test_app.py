import json
import os

os.environ["LLM_PROVIDER"] = "mock"
os.environ["API_KEYS"] = "test-key"
os.environ["PUBLIC_AGENTS"] = "acme-support,bella-bistro,santo"
os.environ["RATE_LIMIT_PER_MIN"] = "1000"
import tempfile
os.environ["DATABASE_PATH"] = os.path.join(tempfile.mkdtemp(), "test.db")

import httpx
import pytest
from fastapi.testclient import TestClient

from app import llm
from app.main import app, AGENTS
from app.knowledge import get_kb

client = TestClient(app)
KEY = {"X-API-Key": "test-key"}


def test_health_and_list():
    assert client.get("/health").json()["status"] == "ok"
    ids = {a["id"] for a in client.get("/api/agents").json()}
    assert {"acme-support", "bella-bistro", "hr-helpdesk", "santo"} <= ids


def test_ui_and_widget_served():
    assert "Santo" in client.get("/").text
    assert "attachShadow" in client.get("/widget.js").text


def test_knowledge_search_ranks_relevant_chunk():
    hits = get_kb("acme-support").search("how many days to return an item for refund")
    assert hits and "30 days" in hits[0]["text"]


def test_public_chat_and_session_memory():
    r = client.post("/api/agents/acme-support/chat", json={"message": "What is the warranty on tents?"})
    assert r.status_code == 200, r.text
    j = r.json()
    assert "2-year" in j["reply"] and j["tool_calls"][0]["tool"] == "knowledge_search"
    r2 = client.post("/api/agents/acme-support/chat", json={"message": "thanks", "session_id": j["session_id"]})
    assert r2.json()["session_id"] == j["session_id"]


def test_private_agent_requires_key():
    assert client.post("/api/agents/hr-helpdesk/chat", json={"message": "PTO?"}).status_code == 401
    r = client.post("/api/agents/hr-helpdesk/chat", json={"message": "How many PTO days?"}, headers=KEY)
    assert r.status_code == 200 and "20 PTO days" in r.json()["reply"]


def test_unknown_agent_404():
    assert client.post("/api/agents/nope/chat", json={"message": "hi"}, headers=KEY).status_code == 404


def test_mcp_flow():
    rpc = lambda m, p=None, i=1: client.post("/mcp", json={"jsonrpc": "2.0", "id": i, "method": m, "params": p or {}}, headers=KEY).json()
    assert client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"}).status_code == 401
    assert rpc("initialize", {"protocolVersion": "2025-06-18"})["result"]["serverInfo"]["name"] == "santo"
    assert client.post("/mcp", json={"jsonrpc": "2.0", "method": "notifications/initialized"}, headers=KEY).status_code == 202
    names = [t["name"] for t in rpc("tools/list")["result"]["tools"]]
    assert "ask_bella_bistro" in names
    out = rpc("tools/call", {"name": "ask_bella_bistro", "arguments": {"message": "vegan options?"}})
    assert "marinara" in out["result"]["content"][0]["text"].lower()
    assert rpc("bogus")["error"]["code"] == -32601


def _patch_transport(monkeypatch, handler):
    real = httpx.AsyncClient
    monkeypatch.setattr(llm.httpx, "AsyncClient", lambda **kw: real(transport=httpx.MockTransport(handler), **kw))


@pytest.mark.anyio
async def test_anthropic_tool_loop(monkeypatch):
    calls = []

    def handler(req):
        body = json.loads(req.content)
        calls.append(body)
        if len(calls) == 1:
            assert any(t["name"] == "knowledge_search" for t in body["tools"])
            return httpx.Response(200, json={"content": [{"type": "tool_use", "id": "t1", "name": "knowledge_search",
                                                          "input": {"query": "shipping"}}]})
        assert body["messages"][-1]["content"][0]["type"] == "tool_result"
        return httpx.Response(200, json={"content": [{"type": "text", "text": "Ships in 3-5 days."}]})

    _patch_transport(monkeypatch, handler)
    agent = AGENTS["acme-support"].model_copy(update={"provider": "anthropic"})
    res = await llm.run_agent(agent, [], "How long is shipping?")
    assert res.reply == "Ships in 3-5 days." and res.tool_calls[0]["tool"] == "knowledge_search"


@pytest.mark.anyio
async def test_openai_tool_loop(monkeypatch):
    n = {"i": 0}

    def handler(req):
        n["i"] += 1
        if n["i"] == 1:
            return httpx.Response(200, json={"choices": [{"message": {"content": None, "tool_calls": [
                {"id": "c1", "type": "function", "function": {"name": "current_time", "arguments": "{}"}}]}}]})
        assert json.loads(req.content)["messages"][-1]["role"] == "tool"
        return httpx.Response(200, json={"choices": [{"message": {"content": "It's Tuesday."}}]})

    _patch_transport(monkeypatch, handler)
    agent = AGENTS["hr-helpdesk"].model_copy(update={"provider": "openai"})
    res = await llm.run_agent(agent, [], "What day is it?")
    assert res.reply == "It's Tuesday."


@pytest.fixture
def anyio_backend():
    return "asyncio"


# ---------------------------------------------------------------- full-stack additions
def test_pages_served():
    for path, text in [("/", "Meet Santo. Your customers get answers"), ("/builder", "Build an agent"), ("/console", "Console"), ("/admin", "Dashboard")]:
        r = client.get(path)
        assert r.status_code == 200 and text in r.text, path
    assert client.get("/static/img/logo.svg").status_code == 200
    assert client.get("/favicon.ico").headers["content-type"].startswith("image/svg")


def test_leads_validation_and_admin_list():
    assert client.post("/api/leads", json={"email": "not-an-email"}).status_code == 422
    r = client.post("/api/leads", json={"email": "Owner@Shop.com", "company": "Shop", "plan": "studio"})
    assert r.status_code == 201
    assert client.get("/api/admin/leads").status_code == 401
    leads = client.get("/api/admin/leads", headers=KEY).json()
    assert any(l["email"] == "owner@shop.com" for l in leads)


def test_builder_create_chat_delete():
    body = {"id": "sunrise-dental", "name": "Front desk", "business": "Sunrise Dental", "domain": "dental clinic",
            "system_prompt": "You are the front desk.", "theme_color": "#6F82D6",
            "knowledge_text": "# Insurance\nWe accept Delta Dental and Cigna.\n\n# Hours\nMon-Thu 8am-5pm.",
            "suggested_questions": ["Do you take Cigna?", ""]}
    assert client.post("/api/admin/agents", json=body).status_code == 401
    assert client.post("/api/admin/agents", json={**body, "id": "Bad ID!"}, headers=KEY).status_code == 422
    r = client.post("/api/admin/agents", json=body, headers=KEY)
    assert r.status_code == 201 and r.json()["mcp_tool"] == "ask_sunrise_dental"
    assert client.post("/api/admin/agents", json=body, headers=KEY).status_code == 409
    chat = client.post("/api/agents/sunrise-dental/chat", json={"message": "Do you accept Cigna insurance?"}, headers=KEY).json()
    assert "Cigna" in chat["reply"]
    assert client.get("/api/agents/sunrise-dental").json()["suggested_questions"] == ["Do you take Cigna?"]
    assert client.delete("/api/admin/agents/sunrise-dental", headers=KEY).status_code == 200
    assert client.get("/api/agents/sunrise-dental").status_code == 404
    import shutil
    from app.config import KNOWLEDGE_DIR
    shutil.rmtree(KNOWLEDGE_DIR / "sunrise-dental", ignore_errors=True)


def test_stats_count_conversations():
    client.post("/api/agents/acme-support/chat", json={"message": "shipping time?"})
    s = client.get("/api/admin/stats", headers=KEY).json()
    assert s["totals"]["messages"] >= 1 and any(a["agent_id"] == "acme-support" for a in s["per_agent"])


def test_santo_agent_answers_product_questions():
    a = client.get("/api/agents/santo").json()
    assert a["name"] == "Santo" and "I'm Santo" in a["greeting"]
    r = client.post("/api/agents/santo/chat", json={"message": "How much does it cost?"}).json()
    assert "not announced" in r["reply"] and "$" not in r["reply"]


# ---------------------------------------------------------------- keyless AI
def test_health_reports_no_key_needed():
    h = client.get("/health").json()
    assert h["api_key_required"] is False and h["ai_engine"] == "local"


@pytest.mark.anyio
async def test_ollama_engine_needs_no_key_and_books(monkeypatch):
    from app import db as dbm
    monkeypatch.setenv("OLLAMA_URL", "http://ollama:11434")
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    seen = {"n": 0}

    def handler(req):
        assert str(req.url) == "http://ollama:11434/v1/chat/completions"
        assert "authorization" not in req.headers and "api-key" not in req.headers
        body = json.loads(req.content)
        assert body["model"] == "qwen2.5:3b" and any(t["function"]["name"] == "request_booking" for t in body["tools"])
        seen["n"] += 1
        if seen["n"] == 1:
            return httpx.Response(200, json={"choices": [{"message": {"content": "", "tool_calls": [
                {"id": "b1", "type": "function", "function": {"name": "request_booking", "arguments": json.dumps(
                    {"name": "Asha", "contact": "555-0101", "date": "Friday", "time": "19:00", "party_size": 4})}}]}}]})
        return httpx.Response(200, json={"choices": [{"message": {"content": "Booked! We'll confirm soon."}}]})

    _patch_transport(monkeypatch, handler)
    res = await llm.run_agent(AGENTS["bella-bistro"], [], "Table for 4 Friday 7pm, Asha 555-0101", "sess-1")
    assert res.provider == "ollama" and res.reply.startswith("Booked")
    b = dbm.list_bookings()[0]
    assert b["name"] == "Asha" and b["party_size"] == 4 and b["session_id"] == "sess-1"


@pytest.mark.anyio
async def test_falls_back_to_builtin_engine_when_model_server_down(monkeypatch):
    monkeypatch.setenv("OLLAMA_URL", "http://ollama:11434")
    monkeypatch.delenv("LLM_PROVIDER", raising=False)

    def handler(req):
        raise httpx.ConnectError("connection refused")

    _patch_transport(monkeypatch, handler)
    res = await llm.run_agent(AGENTS["acme-support"], [], "What is your return policy?")
    assert res.provider == "local" and "30 days" in res.reply and res.tool_calls[0]["tool"] == "fallback"


def test_builtin_engine_captures_leads_and_bookings():
    sid = client.post("/api/agents/bella-bistro/chat", json={"message": "Hi"}).json()["session_id"]
    r = client.post("/api/agents/bella-bistro/chat", json={"message": "I want to book a table", "session_id": sid}).json()
    assert "date and time" in r["reply"]
    r = client.post("/api/agents/bella-bistro/chat", json={"message": "Ravi, Saturday 8pm, 3 people, ravi@mail.com", "session_id": sid}).json()
    assert "booking request" in r["reply"]
    assert any(b["contact"] == "ravi@mail.com" for b in client.get("/api/admin/bookings", headers=KEY).json())
    r = client.post("/api/agents/acme-support/chat", json={"message": "Please call me about bulk orders: 214-555-0199"}).json()
    assert "passed your details" in r["reply"]
    leads = client.get("/api/admin/leads", headers=KEY).json()
    assert any(l["source"] == "agent:acme-support" and "214-555-0199" in l["email"] for l in leads)


@pytest.mark.anyio
async def test_semantic_search_uses_local_embeddings(monkeypatch):
    from app import knowledge as kn
    monkeypatch.setenv("OLLAMA_URL", "http://ollama:11434")

    async def fake_embed(texts):  # "refund" query should land on the Returns chunk by meaning
        return [[1.0, 0.0] if ("Returns" in t or "money back" in t) else [0.0, 1.0] for t in texts]

    monkeypatch.setattr(kn, "_embed", fake_embed)
    kb = kn.KnowledgeBase(kn.KNOWLEDGE_DIR / "acme-support")
    hits = await kb.hybrid_search("can I get my money back", k=1)
    assert hits and hits[0]["heading"] == "Returns"


def test_seo_files_and_industry_pages():
    assert "Sitemap:" in client.get("/robots.txt").text
    sm = client.get("/sitemap.xml").text
    assert "/for/restaurants" in sm and "/for/law-firms" in sm
    p = client.get("/for/restaurants")
    assert p.status_code == 200 and "AI Chatbot for Restaurants" in p.text and '"FAQPage"' in p.text
    assert client.get("/for/nope").status_code == 404
    home = client.get("/").text
    assert '"SoftwareApplication"' in home and 'id="pricing"' not in home and "$49" not in home


# ---------------------------------------------------------------- answers every question
def _patch_web(monkeypatch, handler):
    from app import tools as tl
    real = httpx.AsyncClient
    monkeypatch.setattr(tl.httpx, "AsyncClient", lambda **kw: real(transport=httpx.MockTransport(handler), **kw))


def test_general_question_answered_without_key(monkeypatch):
    def handler(req):
        if "duckduckgo" in req.url.host:
            return httpx.Response(200, json={"Answer": "", "AbstractText": ""})
        if "w/api.php" in str(req.url):
            assert "photosynthesis" in req.url.params["srsearch"].lower()
            return httpx.Response(200, json={"query": {"search": [{"title": "Photosynthesis"}]}})
        return httpx.Response(200, json={"extract": "Photosynthesis is the process plants use to turn light into chemical energy. It releases oxygen. More text. Even more."})
    _patch_web(monkeypatch, handler)
    r = client.post("/api/agents/bella-bistro/chat", json={"message": "What is photosynthesis?"}).json()
    assert r["reply"].startswith("Photosynthesis is the process") and "Wikipedia" in r["reply"]


def test_duckduckgo_instant_answer(monkeypatch):
    _patch_web(monkeypatch, lambda req: httpx.Response(200, json={"AbstractText": "Canberra is the capital city of Australia.", "AbstractURL": "https://en.wikipedia.org/wiki/Canberra"}))
    r = client.post("/api/agents/santo/chat", json={"message": "What is the capital of Australia?"}).json()
    assert "Canberra" in r["reply"]


def test_math_and_time_answered():
    assert "36" in client.post("/api/agents/santo/chat", json={"message": "what is 15% of 240"}).json()["reply"]
    assert "529.2" in client.post("/api/agents/santo/chat", json={"message": "(49*12)*0.9"}).json()["reply"]
    assert "UTC" in client.post("/api/agents/santo/chat", json={"message": "What time is it?"}).json()["reply"]


def test_business_questions_still_use_own_documents(monkeypatch):
    _patch_web(monkeypatch, lambda req: (_ for _ in ()).throw(AssertionError("must not search the web")))
    r = client.post("/api/agents/acme-support/chat", json={"message": "What is your return policy?"}).json()
    assert "30 days" in r["reply"]


def test_open_mode_prompt_and_tools():
    a = AGENTS["santo"]
    assert "Answer EVERY question" in llm._system(a)
    names = [t["name"] for t in __import__("app.tools", fromlist=["tool_specs"]).tool_specs(a)]
    assert {"web_lookup", "calculator", "knowledge_search", "save_lead", "request_booking"} <= set(names)
    strict = a.model_copy(update={"answer_mode": "business"})
    assert "Politely decline" in llm._system(strict)
    assert "web_lookup" not in [t["name"] for t in __import__("app.tools", fromlist=["tool_specs"]).tool_specs(strict)]


def test_page_scripts_have_no_syntax_errors(tmp_path):
    import re, shutil, subprocess
    node = shutil.which("node")
    if not node:
        pytest.skip("node not installed")
    from app.config import BASE_DIR
    for name in ["index.html", "builder.html", "admin.html", "console.html"]:
        for i, js in enumerate(re.findall(r"<script>(.*?)</script>", (BASE_DIR / "static" / name).read_text(), re.S)):
            f = tmp_path / f"{name}.{i}.js"; f.write_text(js)
            r = subprocess.run([node, "--check", str(f)], capture_output=True, text=True)
            assert r.returncode == 0, f"{name} script {i}: {r.stderr[:300]}"
    assert subprocess.run([node, "--check", str(BASE_DIR / "static" / "widget.js")]).returncode == 0
