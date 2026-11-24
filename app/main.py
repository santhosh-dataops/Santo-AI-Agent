"""Santo - a deployable, config-driven AI agent platform for any business or domain.

Surfaces:
  /                         marketing site with live demo
  /builder                  no-code agent builder
  /console                  chat console (all agents)
  /admin                    dashboard: usage, leads, conversations
  /widget.js                embeddable chat bubble for any website
  /api/agents               list agents               (REST, OpenAPI docs at /docs)
  /api/agents/{id}/chat     chat with an agent
  /mcp                      MCP server (JSON-RPC over HTTP) so other AI agents can call yours
  /health                   health check
"""
from __future__ import annotations

import os
import re
import time
import uuid
from collections import defaultdict, deque
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles
import yaml
from pydantic import BaseModel, Field, field_validator

from . import db
from .config import AGENTS_DIR, BASE_DIR, KNOWLEDGE_DIR, AgentConfig, load_agents
from . import seo
from .knowledge import get_kb
from .llm import resolve_provider, run_agent

VERSION = "1.0.0"
STATIC = BASE_DIR / "static"
API_KEYS = {k.strip() for k in os.getenv("API_KEYS", "").split(",") if k.strip()}
PUBLIC_AGENTS = {a.strip() for a in os.getenv("PUBLIC_AGENTS", "*").split(",") if a.strip()}
SESSION_TTL = int(os.getenv("SESSION_TTL_SECONDS", "3600"))
MAX_HISTORY = int(os.getenv("MAX_HISTORY_MESSAGES", "20"))
RATE_LIMIT = int(os.getenv("RATE_LIMIT_PER_MIN", "30"))

app = FastAPI(title="Santo API", version=VERSION,
              description="Config-driven AI agents for any business. Add a YAML file in agents/ or use /builder.")
app.add_middleware(CORSMiddleware, allow_origins=os.getenv("CORS_ORIGINS", "*").split(","),
                   allow_methods=["*"], allow_headers=["*"])
app.mount("/static", StaticFiles(directory=STATIC), name="static")

AGENTS: dict[str, AgentConfig] = load_agents()
SESSIONS: dict[str, dict] = {}          # swap for Redis in multi-instance deployments
HITS: dict[str, deque] = defaultdict(deque)
db.init()


# ------------------------------------------------------------------ helpers
def _key_from(request: Request) -> str | None:
    auth = request.headers.get("authorization", "")
    return auth[7:].strip() if auth.lower().startswith("bearer ") else request.headers.get("x-api-key")


def require_key(request: Request) -> None:
    if API_KEYS and _key_from(request) not in API_KEYS:
        raise HTTPException(401, "Missing or invalid API key")


def chat_auth(agent_id: str, request: Request) -> None:
    """Public website widgets may chat without a key if the agent is listed in PUBLIC_AGENTS."""
    if "*" in PUBLIC_AGENTS or agent_id in PUBLIC_AGENTS:
        return
    require_key(request)


def rate_limit(request: Request) -> None:
    ip = request.headers.get("x-forwarded-for", request.client.host if request.client else "?").split(",")[0]
    now, q = time.time(), HITS[ip]
    while q and now - q[0] > 60:
        q.popleft()
    if len(q) >= RATE_LIMIT:
        raise HTTPException(429, "Too many requests, slow down.")
    q.append(now)


def get_agent(agent_id: str) -> AgentConfig:
    if agent_id not in AGENTS:
        raise HTTPException(404, f"Agent '{agent_id}' not found. Available: {', '.join(AGENTS)}")
    return AGENTS[agent_id]


def _history(session_id: str) -> list[dict]:
    now = time.time()
    for sid in [s for s, v in SESSIONS.items() if now - v["ts"] > SESSION_TTL]:
        SESSIONS.pop(sid, None)
    return SESSIONS.get(session_id, {}).get("messages", [])


async def _chat(agent: AgentConfig, message: str, session_id: str | None) -> dict:
    sid = session_id or uuid.uuid4().hex
    history = _history(f"{agent.id}:{sid}")
    try:
        result = await run_agent(agent, history, message, sid)
    except Exception as exc:
        raise HTTPException(502, f"LLM provider error: {exc}") from exc
    msgs = [*history, {"role": "user", "content": message}, {"role": "assistant", "content": result.reply}]
    SESSIONS[f"{agent.id}:{sid}"] = {"messages": msgs[-MAX_HISTORY:], "ts": time.time()}
    try:
        db.log_conversation(agent.id, sid, message, result.reply, result.tool_calls, result.provider)
    except Exception:  # logging must never break a chat
        pass
    return {"agent_id": agent.id, "session_id": sid, "reply": result.reply,
            "tool_calls": result.tool_calls, "provider": result.provider, "model": result.model}


def _public(a: AgentConfig) -> dict:
    return {"id": a.id, "name": a.name, "business": a.business, "domain": a.domain,
            "description": a.description, "greeting": a.greeting, "theme_color": a.theme_color,
            "suggested_questions": a.suggested_questions}


# ------------------------------------------------------------------ REST API
class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=8000)
    session_id: str | None = Field(None, description="Reuse to keep conversation memory")


@app.get("/health")
def health():
    engine = resolve_provider(next(iter(AGENTS.values()))) if AGENTS else ("local", "santo-local")
    return {"status": "ok", "version": VERSION, "agents": len(AGENTS),
            "ai_engine": engine[0], "model": engine[1], "api_key_required": False}


@app.get("/api/agents")
def list_agents():
    return [_public(a) for a in AGENTS.values()]


@app.get("/api/agents/{agent_id}")
def agent_detail(agent_id: str):
    return _public(get_agent(agent_id))


@app.post("/api/agents/{agent_id}/chat", dependencies=[Depends(rate_limit)])
async def chat(agent_id: str, body: ChatRequest, request: Request):
    chat_auth(agent_id, request)
    return await _chat(get_agent(agent_id), body.message, body.session_id)


@app.delete("/api/agents/{agent_id}/sessions/{session_id}")
def end_session(agent_id: str, session_id: str, request: Request):
    chat_auth(agent_id, request)
    SESSIONS.pop(f"{agent_id}:{session_id}", None)
    return {"ok": True}


@app.post("/api/admin/reload", dependencies=[Depends(require_key)])
def reload_agents():
    """Re-read agents/*.yaml and knowledge/ without restarting."""
    global AGENTS
    AGENTS = load_agents()
    get_kb.cache_clear()
    return {"reloaded": list(AGENTS)}


@app.get("/api/admin/status", dependencies=[Depends(require_key)])
def status():
    return {aid: {"provider_model": resolve_provider(a), "knowledge_chunks": len(get_kb(a.knowledge).chunks),
                  "http_tools": [t.name for t in a.http_tools]} for aid, a in AGENTS.items()}


@app.get("/api/admin/stats", dependencies=[Depends(require_key)])
def admin_stats():
    return {**db.stats(), "agents": len(AGENTS)}


@app.get("/api/admin/leads", dependencies=[Depends(require_key)])
def admin_leads():
    return db.list_leads()


@app.get("/api/admin/bookings", dependencies=[Depends(require_key)])
def admin_bookings():
    return db.list_bookings()


class BookingStatus(BaseModel):
    status: str = Field(..., pattern="^(pending|confirmed|declined|done)$")


@app.patch("/api/admin/bookings/{booking_id}", dependencies=[Depends(require_key)])
def update_booking(booking_id: int, body: BookingStatus):
    if not db.set_booking_status(booking_id, body.status):
        raise HTTPException(404, "Booking not found")
    return {"id": booking_id, "status": body.status}


@app.get("/api/admin/conversations", dependencies=[Depends(require_key)])
def admin_conversations(agent_id: str | None = None, limit: int = 50):
    return db.recent_conversations(agent_id, min(limit, 500))


# ------------------------------------------------------------------ leads (public)
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class LeadRequest(BaseModel):
    email: str = Field(..., max_length=200)
    name: str = Field("", max_length=120)
    company: str = Field("", max_length=160)
    plan: str = Field("", max_length=40)
    message: str = Field("", max_length=4000)
    source: str = Field("", max_length=60)

    @field_validator("email")
    @classmethod
    def valid_email(cls, v: str) -> str:
        v = v.strip()
        if not _EMAIL.match(v):
            raise ValueError("Enter a valid email address, like name@company.com")
        return v.lower()


@app.post("/api/leads", status_code=201, dependencies=[Depends(rate_limit)])
def create_lead(body: LeadRequest):
    lead_id = db.add_lead(**body.model_dump())
    return {"id": lead_id, "ok": True}


# ------------------------------------------------------------------ agent builder
_SLUG = re.compile(r"^[a-z0-9][a-z0-9-]{1,40}$")


class BuildAgentRequest(BaseModel):
    id: str = Field(..., description="URL-safe id, e.g. 'sunrise-dental'")
    name: str = Field(..., max_length=80)
    business: str = Field("", max_length=120)
    domain: str = Field("general", max_length=60)
    description: str = Field("", max_length=300)
    greeting: str = Field("Hi! How can I help you today?", max_length=300)
    system_prompt: str = Field(..., max_length=8000)
    theme_color: str = Field("#4F46E5", pattern=r"^#[0-9a-fA-F]{6}$")
    answer_mode: str = Field("open", pattern="^(open|business)$")
    suggested_questions: list[str] = Field(default_factory=list, max_length=6)
    knowledge_text: str = Field("", max_length=200_000, description="FAQs, policies, prices... as plain text/markdown")
    overwrite: bool = False

    @field_validator("id")
    @classmethod
    def valid_id(cls, v: str) -> str:
        v = v.strip().lower()
        if not _SLUG.match(v):
            raise ValueError("Use 2-41 lowercase letters, numbers or dashes, like sunrise-dental")
        return v


@app.post("/api/admin/agents", status_code=201, dependencies=[Depends(require_key)])
def build_agent(body: BuildAgentRequest):
    path = AGENTS_DIR / f"{body.id}.yaml"
    if path.exists() and not body.overwrite:
        raise HTTPException(409, f"An agent with id '{body.id}' already exists. Pick another id or allow overwrite.")
    data = body.model_dump(exclude={"knowledge_text", "overwrite"})
    data["suggested_questions"] = [q for q in data["suggested_questions"] if q.strip()]
    if body.knowledge_text.strip():
        folder = KNOWLEDGE_DIR / body.id
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "knowledge.md").write_text(body.knowledge_text, encoding="utf-8")
        data["knowledge"] = body.id
    AgentConfig(**data)  # validate before writing
    AGENTS_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
    reload_agents()
    return {"created": body.id, "chat_url": f"/console?agent={body.id}",
            "api": f"/api/agents/{body.id}/chat", "mcp_tool": f"ask_{body.id.replace('-', '_')}"}


@app.delete("/api/admin/agents/{agent_id}", dependencies=[Depends(require_key)])
def delete_agent(agent_id: str):
    path = AGENTS_DIR / f"{agent_id}.yaml"
    if not path.exists():
        raise HTTPException(404, f"Agent '{agent_id}' not found")
    path.unlink()
    reload_agents()
    return {"deleted": agent_id}


# ------------------------------------------------------------------ MCP server
MCP_PROTOCOL = "2025-06-18"


def _mcp_tools() -> list[dict]:
    return [{
        "name": f"ask_{a.id.replace('-', '_')}",
        "description": f"Ask the {a.name} agent ({a.business or a.domain}). {a.description}".strip(),
        "inputSchema": {"type": "object", "properties": {
            "message": {"type": "string", "description": "Question or instruction for the agent"},
            "session_id": {"type": "string", "description": "Optional: reuse for multi-turn memory"}},
            "required": ["message"]},
    } for a in AGENTS.values()]


@app.post("/mcp", dependencies=[Depends(require_key)])
async def mcp(request: Request):
    """Minimal MCP (Streamable HTTP, JSON responses). Connect from Claude, Cursor, or any MCP client."""
    msg = await request.json()
    if isinstance(msg, list):
        return JSONResponse([r for r in [await _mcp_handle(m) for m in msg] if r])
    resp = await _mcp_handle(msg)
    return JSONResponse(resp) if resp else Response(status_code=202)


async def _mcp_handle(msg: dict) -> dict | None:
    mid, method, params = msg.get("id"), msg.get("method", ""), msg.get("params") or {}
    if mid is None:  # notification
        return None

    def ok(result):
        return {"jsonrpc": "2.0", "id": mid, "result": result}

    if method == "initialize":
        return ok({"protocolVersion": params.get("protocolVersion", MCP_PROTOCOL),
                   "capabilities": {"tools": {"listChanged": False}},
                   "serverInfo": {"name": "santo", "version": VERSION}})
    if method == "ping":
        return ok({})
    if method == "tools/list":
        return ok({"tools": _mcp_tools()})
    if method == "tools/call":
        name, args = params.get("name", ""), params.get("arguments") or {}
        agent = next((a for a in AGENTS.values() if f"ask_{a.id.replace('-', '_')}" == name), None)
        if not agent:
            return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32602, "message": f"Unknown tool {name}"}}
        try:
            out = await _chat(agent, str(args.get("message", "")), args.get("session_id"))
            text = f"{out['reply']}\n\n[session_id: {out['session_id']}]"
            return ok({"content": [{"type": "text", "text": text}], "isError": False})
        except HTTPException as exc:
            return ok({"content": [{"type": "text", "text": str(exc.detail)}], "isError": True})
    return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": f"Method not found: {method}"}}


@app.get("/mcp")
def mcp_get():
    return Response(status_code=405, headers={"Allow": "POST"})


# ------------------------------------------------------------------ web pages
def _page(name: str):
    return FileResponse(STATIC / name, media_type="text/html")


@app.get("/", include_in_schema=False)
def home():
    return _page("index.html")


@app.get("/builder", include_in_schema=False)
def builder_page():
    return _page("builder.html")


@app.get("/console", include_in_schema=False)
def console_page():
    return _page("console.html")


@app.get("/admin", include_in_schema=False)
def admin_page():
    return _page("admin.html")


@app.get("/robots.txt", include_in_schema=False)
def robots():
    return PlainTextResponse(seo.robots_txt())


@app.get("/sitemap.xml", include_in_schema=False)
def sitemap():
    return Response(seo.sitemap_xml(), media_type="application/xml")


@app.get("/for/{slug}", include_in_schema=False)
def industry(slug: str):
    page = seo.industry_page(slug)
    if not page:
        raise HTTPException(404, "Page not found")
    return HTMLResponse(page)


@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    return FileResponse(STATIC / "img" / "favicon.svg", media_type="image/svg+xml")


@app.get("/widget.js", include_in_schema=False)
def widget():
    return FileResponse(STATIC / "widget.js", media_type="application/javascript")
