"""Tool registry. Each agent gets built-in tools plus any HTTP tools declared in its YAML."""
from __future__ import annotations

import ast
import contextvars
import json
import operator
import os
import re
from datetime import datetime, timezone
from typing import Any

import httpx

from .config import AgentConfig, expand_env
from . import db
from .knowledge import get_kb

CURRENT_SESSION: contextvars.ContextVar[str] = contextvars.ContextVar("santo_session", default="")


def tool_specs(agent: AgentConfig) -> list[dict]:
    """Provider-neutral tool specs: {name, description, input_schema}."""
    specs: list[dict] = []
    if "knowledge_search" in agent.builtin_tools and agent.knowledge:
        specs.append({
            "name": "knowledge_search",
            "description": f"Search {agent.business or agent.name}'s knowledge base (policies, FAQs, "
                           "product/service info). Use before answering factual questions about the business.",
            "input_schema": {"type": "object", "properties": {
                "query": {"type": "string", "description": "What to look up"}}, "required": ["query"]},
        })
    if "web_lookup" in agent.builtin_tools and agent.answer_mode == "open":
        specs.append({
            "name": "web_lookup",
            "description": "Look up general facts from Wikipedia and DuckDuckGo (free, no key): people, places, "
                           "history, science, definitions, how things work. Use for general questions you are "
                           "unsure about. Never use it for this business's own prices or policies.",
            "input_schema": {"type": "object", "properties": {
                "query": {"type": "string", "description": "Short topic, e.g. 'capital of Australia'"}},
                "required": ["query"]},
        })
    if "calculator" in agent.builtin_tools:
        specs.append({
            "name": "calculator",
            "description": "Exact arithmetic: + - * / ** %, parentheses, and 'X% of Y'. Use for any math.",
            "input_schema": {"type": "object", "properties": {
                "expression": {"type": "string", "description": "e.g. '(49*12)*0.9' or '15% of 240'"}},
                "required": ["expression"]},
        })
    if "current_time" in agent.builtin_tools:
        specs.append({
            "name": "current_time",
            "description": "Get the current UTC date and time.",
            "input_schema": {"type": "object", "properties": {}},
        })
    if "save_lead" in agent.builtin_tools:
        specs.append({
            "name": "save_lead",
            "description": "Save a customer's contact details so the business can follow up. Use when someone "
                           "shares an email or phone number, asks for a quote or call back, or a question needs a person.",
            "input_schema": {"type": "object", "properties": {
                "name": {"type": "string"}, "contact": {"type": "string", "description": "Email or phone"},
                "need": {"type": "string", "description": "What they want, in one sentence"}},
                "required": ["contact", "need"]},
        })
    if "request_booking" in agent.builtin_tools:
        specs.append({
            "name": "request_booking",
            "description": "Send a booking request (table, appointment, viewing, consultation) to the business. "
                           "Collect name, date, time, party size if relevant, and a phone or email first, "
                           "confirm them with the customer, then call this.",
            "input_schema": {"type": "object", "properties": {
                "name": {"type": "string"}, "contact": {"type": "string"},
                "date": {"type": "string"}, "time": {"type": "string"},
                "party_size": {"type": "integer"}, "details": {"type": "string"}},
                "required": ["contact"]},
        })
    for t in agent.http_tools:
        specs.append({
            "name": t.name,
            "description": t.description,
            "input_schema": {"type": "object", "properties": t.parameters, "required": t.required},
        })
    return specs


async def run_tool(agent: AgentConfig, name: str, args: dict[str, Any], session: str = "") -> str:
    try:
        if name == "save_lead":
            contact = str(args.get("contact", "")).strip()
            if not contact:
                return "Ask the customer for an email or phone number first."
            email = contact if "@" in contact else ""
            db.add_lead(email=email or contact, name=str(args.get("name", ""))[:120], company="",
                        plan="", message=f"[phone: {contact}] " * (not email) + str(args.get("need", ""))[:2000],
                        source=f"agent:{agent.id}")
            return "Saved. Tell the customer the team will contact them soon."
        if name == "request_booking":
            contact = str(args.get("contact", "")).strip()
            if not contact:
                return "Ask the customer for a phone number or email before booking."
            bid = db.add_booking(agent.id, session or CURRENT_SESSION.get(), str(args.get("name", ""))[:120], contact[:200],
                                 str(args.get("date", ""))[:40], str(args.get("time", ""))[:40],
                                 args.get("party_size"), str(args.get("details", ""))[:2000])
            return f"Booking request #{bid} sent to the business. Tell the customer it is pending confirmation."
        if name == "knowledge_search":
            hits = await get_kb(agent.knowledge).hybrid_search(args.get("query", ""), k=3)
            if not hits:
                return "No matching information found in the knowledge base."
            return "\n\n---\n\n".join(f"[{h['source']} > {h['heading']}]\n{h['text']}" for h in hits)
        if name == "web_lookup":
            return await web_lookup(str(args.get("query", "")))
        if name == "calculator":
            return calculate(str(args.get("expression", "")))
        if name == "current_time":
            return datetime.now(timezone.utc).strftime("%A %Y-%m-%d %H:%M UTC")
        for t in agent.http_tools:
            if t.name == name:
                return await _call_http(t, args)
        return f"Unknown tool: {name}"
    except Exception as exc:  # never crash the conversation on a tool failure
        return f"Tool '{name}' failed: {exc}"


async def _call_http(t, args: dict[str, Any]) -> str:
    url = expand_env(t.url)
    path_args = {k: v for k, v in args.items() if "{" + k + "}" in url}
    url = url.format(**path_args) if path_args else url
    rest = {k: v for k, v in args.items() if k not in path_args}
    headers = {k: expand_env(v) for k, v in t.headers.items()}
    async with httpx.AsyncClient(timeout=20) as client:
        if t.method.upper() in {"GET", "DELETE"}:
            r = await client.request(t.method.upper(), url, params=rest, headers=headers)
        else:
            r = await client.request(t.method.upper(), url, json=rest, headers=headers)
    body = r.text[:4000]
    try:
        body = json.dumps(r.json())[:4000]
    except ValueError:
        pass
    return f"HTTP {r.status_code}: {body}"


# ---------------------------------------------------------------- free general-knowledge lookup
_UA = {"User-Agent": os.getenv("LOOKUP_USER_AGENT", "SantoAssistant/1.0 (https://heysanto.ai; hello@heysanto.ai)")}
_Q_NOISE = re.compile(r"^(what|who|where|when|why|how|which)( is| are| was| were| does| do| did)?( the| a| an)?\s+|"
                      r"^(tell me about|explain|define|meaning of)\s+|\?$", re.I)


def _topic(q: str) -> str:
    t = q.strip()
    for _ in range(2):
        t = _Q_NOISE.sub("", t).strip()
    return t or q


async def web_lookup(query: str) -> str:
    """DuckDuckGo instant answers + Wikipedia summaries. No API key. Returns a short factual passage."""
    query = query.strip()
    if not query:
        return "No query given."
    async with httpx.AsyncClient(timeout=8, headers=_UA, follow_redirects=True) as client:
        try:
            r = await client.get("https://api.duckduckgo.com/", params={"q": query, "format": "json", "no_html": 1, "skip_disambig": 1})
            d = r.json()
            ans = d.get("Answer") or d.get("AbstractText") or d.get("Definition")
            if ans:
                src = d.get("AbstractURL") or d.get("DefinitionURL") or "DuckDuckGo"
                return f"{ans}\n(Source: {src})"
        except Exception:
            pass
        try:
            topic = _topic(query)
            r = await client.get("https://en.wikipedia.org/w/api.php", params={
                "action": "query", "list": "search", "srsearch": topic, "srlimit": 1, "format": "json"})
            hits = r.json().get("query", {}).get("search", [])
            if hits:
                title = hits[0]["title"]
                r = await client.get("https://en.wikipedia.org/api/rest_v1/page/summary/" + title.replace(" ", "_"))
                extract = r.json().get("extract", "")
                if extract:
                    sentences = re.split(r"(?<=[.!?])\s+", extract)
                    return " ".join(sentences[:3]) + f"\n(Source: Wikipedia, {title})"
        except Exception as exc:
            return f"Lookup failed: {exc}"
    return "No reliable information found."


# ---------------------------------------------------------------- safe calculator
_OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv,
        ast.Pow: operator.pow, ast.Mod: operator.mod, ast.FloorDiv: operator.floordiv,
        ast.USub: operator.neg, ast.UAdd: operator.pos}


def _eval(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
        left, right = _eval(node.left), _eval(node.right)
        if isinstance(node.op, ast.Pow) and abs(right) > 100:
            raise ValueError("exponent too large")
        return _OPS[type(node.op)](left, right)
    if isinstance(node, ast.UnaryOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_eval(node.operand))
    raise ValueError("unsupported expression")


def calculate(expr: str) -> str:
    e = expr.lower().replace("x", "*").replace("×", "*").replace("÷", "/").replace("^", "**").replace(",", "")
    e = re.sub(r"(\d+(?:\.\d+)?)\s*%\s*of\s*(\d+(?:\.\d+)?)", r"(\1/100*\2)", e)
    e = re.sub(r"(\d+(?:\.\d+)?)\s*%", r"(\1/100)", e)
    e = re.sub(r"[^0-9+\-*/().% ]", "", e).strip()
    if not e:
        return "No arithmetic found."
    try:
        v = _eval(ast.parse(e, mode="eval").body)
    except ZeroDivisionError:
        return "Can't divide by zero."
    except Exception:
        return "I couldn't work that out. Try a simpler expression."
    v = round(v, 10)
    return f"{int(v):,}" if float(v).is_integer() else f"{v:,.4f}".rstrip("0").rstrip(".")
