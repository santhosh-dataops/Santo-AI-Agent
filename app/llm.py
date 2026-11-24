"""AI engines with a tool-calling loop. Plain HTTP, no vendor SDKs.

Santo needs NO API key. Engines, in the order they are picked automatically:
  ollama    - DEFAULT. Open-source model (Qwen 2.5, Llama 3, Mistral...) running on your own
              server via Ollama. No key, no per-message cost.      (OLLAMA_URL, OLLAMA_MODEL)
  local     - Built-in offline engine: knowledge search + lead/booking capture, no model at all.
              Used when no model server is reachable, so the site never goes silent.
  anthropic / openai - optional paid clouds, only if you choose to add a key.
"""
from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass, field

import httpx

from .config import AgentConfig
from .tools import CURRENT_SESSION, run_tool, tool_specs

MAX_TOOL_ROUNDS = int(os.getenv("MAX_TOOL_ROUNDS", "6"))
log = logging.getLogger("santo.ai")


@dataclass
class AgentResult:
    reply: str
    tool_calls: list[dict] = field(default_factory=list)
    provider: str = ""
    model: str = ""


def resolve_provider(agent: AgentConfig) -> tuple[str, str]:
    provider = (agent.provider or os.getenv("LLM_PROVIDER") or "").lower()
    if provider == "mock":
        provider = "local"
    if not provider:
        provider = ("ollama" if os.getenv("OLLAMA_URL") else
                    "anthropic" if os.getenv("ANTHROPIC_API_KEY") else
                    "openai" if os.getenv("OPENAI_API_KEY") else "local")
    defaults = {"ollama": os.getenv("OLLAMA_MODEL", "qwen2.5:3b"),
                "anthropic": os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5-5"),
                "openai": os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
                "local": "santo-local"}
    return provider, agent.model or defaults.get(provider, "santo-local")


def _system(agent: AgentConfig) -> str:
    who = (f"{agent.system_prompt.strip()}\n\n"
           f"You are '{agent.name}' for {agent.business or 'this business'} (domain: {agent.domain}).")
    if agent.answer_mode == "open":
        rules = ("Answer EVERY question helpfully, whatever the topic: the business, general knowledge, advice, "
                 "math, writing, explanations or small talk.\n"
                 "- For anything about this business (prices, hours, policies, products, services), search the "
                 "knowledge base first and use only what it says. Never invent business facts; if they're missing, "
                 "say so and offer to take the customer's contact details for the team.\n"
                 "- For general questions, answer from your own knowledge. Use web_lookup for facts you are unsure "
                 "of, and calculator for math.\n"
                 "- Reply in the language the customer writes in. Be clear and concise.")
    else:
        rules = ("Only help with questions about this business. Use your tools to look up facts instead of "
                 "guessing. If the information is not available, say so and offer to connect the user with a human. "
                 "Politely decline unrelated topics.")
    return f"{who}\n\n{rules}"


async def run_agent(agent: AgentConfig, history: list[dict], user_message: str, session_id: str = "") -> AgentResult:
    CURRENT_SESSION.set(session_id)
    provider, model = resolve_provider(agent)
    messages = [*history, {"role": "user", "content": user_message}]
    try:
        if provider == "ollama":
            base = os.getenv("OLLAMA_URL", "http://localhost:11434").rstrip("/") + "/v1"
            return await _openai(agent, model, messages, base=base, key=None, label="ollama")
        if provider == "anthropic":
            return await _anthropic(agent, model, messages)
        if provider == "openai":
            return await _openai(agent, model, messages)
    except Exception as exc:  # model server down or busy: never leave the customer without an answer
        log.warning("AI engine %s failed (%s); answering with the built-in engine", provider, exc)
        result = await _local(agent, "santo-local", messages)
        result.tool_calls.insert(0, {"tool": "fallback", "input": {"from": provider}, "output": str(exc)[:200]})
        return result
    return await _local(agent, model, messages)


# ---------------------------------------------------------------- Anthropic
async def _anthropic(agent: AgentConfig, model: str, messages: list[dict]) -> AgentResult:
    url = os.getenv("ANTHROPIC_BASE_URL", "https://api.anthropic.com") + "/v1/messages"
    headers = {"x-api-key": os.getenv("ANTHROPIC_API_KEY", ""), "anthropic-version": "2023-06-01",
               "content-type": "application/json"}
    tools = tool_specs(agent)
    msgs = [dict(m) for m in messages]
    log_: list[dict] = []
    async with httpx.AsyncClient(timeout=120) as client:
        for _ in range(MAX_TOOL_ROUNDS):
            payload = {"model": model, "max_tokens": agent.max_tokens, "temperature": agent.temperature,
                       "system": _system(agent), "messages": msgs}
            if tools:
                payload["tools"] = tools
            r = await client.post(url, headers=headers, json=payload)
            r.raise_for_status()
            data = r.json()
            blocks = data.get("content", [])
            uses = [b for b in blocks if b.get("type") == "tool_use"]
            if not uses:
                text = "".join(b.get("text", "") for b in blocks if b.get("type") == "text")
                return AgentResult(text.strip(), log_, "anthropic", model)
            msgs.append({"role": "assistant", "content": blocks})
            results = []
            for u in uses:
                out = await run_tool(agent, u["name"], u.get("input") or {}, session=_session(messages))
                log_.append({"tool": u["name"], "input": u.get("input"), "output": out[:500]})
                results.append({"type": "tool_result", "tool_use_id": u["id"], "content": out})
            msgs.append({"role": "user", "content": results})
    return AgentResult("Sorry, I couldn't finish that request. Please try rephrasing.", log_, "anthropic", model)


# ---------------------------------------------------------------- OpenAI-compatible
_DEFAULT = object()


async def _openai(agent: AgentConfig, model: str, messages: list[dict], base: str | None = None,
                  key=_DEFAULT, label: str = "openai") -> AgentResult:
    base = (base or os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")).rstrip("/")
    url = base + "/chat/completions"
    key = os.getenv("OPENAI_API_KEY", "") if key is _DEFAULT else key
    headers = {"content-type": "application/json"}
    if key and os.getenv("OPENAI_AUTH_HEADER", "bearer").lower() == "api-key":  # Azure OpenAI style
        headers["api-key"] = key
    elif key:
        headers["authorization"] = f"Bearer {key}"
    if label == "openai" and os.getenv("OPENAI_API_VERSION"):  # Azure: ?api-version=...
        url += f"?api-version={os.getenv('OPENAI_API_VERSION')}"
    tools = [{"type": "function", "function": {"name": t["name"], "description": t["description"],
                                                "parameters": t["input_schema"]}} for t in tool_specs(agent)]
    msgs = [{"role": "system", "content": _system(agent)}, *[dict(m) for m in messages]]
    log_: list[dict] = []
    async with httpx.AsyncClient(timeout=float(os.getenv("AI_TIMEOUT_SECONDS", "120"))) as client:
        for _ in range(MAX_TOOL_ROUNDS):
            payload = {"model": model, "messages": msgs, "temperature": agent.temperature,
                       "max_tokens": agent.max_tokens}
            if tools:
                payload["tools"] = tools
            r = await client.post(url, headers=headers, json=payload)
            r.raise_for_status()
            msg = r.json()["choices"][0]["message"]
            calls = msg.get("tool_calls") or []
            if not calls:
                return AgentResult((msg.get("content") or "").strip(), log_, label, model)
            msgs.append({"role": "assistant", "content": msg.get("content"), "tool_calls": calls})
            for c in calls:
                fn = c["function"]
                try:
                    args = json.loads(fn.get("arguments") or "{}")
                except json.JSONDecodeError:
                    args = {}
                out = await run_tool(agent, fn["name"], args, session=_session(messages))
                log_.append({"tool": fn["name"], "input": args, "output": out[:500]})
                msgs.append({"role": "tool", "tool_call_id": c.get("id", fn["name"]), "content": out})
    return AgentResult("Sorry, I couldn't finish that request. Please try rephrasing.", log_, label, model)


def _session(messages: list[dict]) -> str:
    return CURRENT_SESSION.get()


# ---------------------------------------------------------------- Built-in local engine (no model)
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_PHONE = re.compile(r"(?:\+?\d[\d\s().-]{7,}\d)")
_BOOK = re.compile(r"\b(book|booking|reserve|reservation|appointment|table for|schedule|viewing|consultation)\b", re.I)
_WHEN = re.compile(r"\b(today|tomorrow|tonight|mon|tue|wed|thu|fri|sat|sun)[a-z]*\b|\b\d{1,2}(:\d{2})?\s?(am|pm)\b|\b\d{1,2}/\d{1,2}\b", re.I)
_MATH = re.compile(r"(\d[\d,.]*\s*([-+*/x×÷^]|\*\*)\s*\(?\d)|(\d+(\.\d+)?\s*%\s*of\s*\d)", re.I)
_TIME = re.compile(r"\b(what('?s| is) the (time|date)|what time is it|today'?s date|what day is (it|today))\b", re.I)
_HELLO = re.compile(r"^\s*(hi|hello|hey|good (morning|afternoon|evening)|namaste)\b[\s!.]*$", re.I)
_THANKS = re.compile(r"^\s*(thanks|thank you|thx|great|ok|okay|cool)\b[\s!.]*$", re.I)


async def _local(agent: AgentConfig, model: str, messages: list[dict]) -> AgentResult:
    """Keyless, model-free engine. Understands greetings, bookings and contact details, and answers
    everything else from the agent's own documents. Runs anywhere, even on free hosting."""
    q = messages[-1]["content"]
    sess = _session(messages)
    log_: list[dict] = []
    tools = set(agent.builtin_tools)
    contact = (_EMAIL.search(q) or _PHONE.search(q))
    recent = [m.get("content", "") for m in messages[-5:-1] if isinstance(m.get("content"), str)]
    booking_context = _BOOK.search(q) or any(_BOOK.search(t) or "date and time" in t for t in recent)

    async def tool(name, args):
        out = await run_tool(agent, name, args, session=sess)
        log_.append({"tool": name, "input": args, "output": out[:500]})
        return out

    if _HELLO.match(q):
        return AgentResult(agent.greeting, log_, "local", model)
    if _THANKS.match(q):
        return AgentResult("You're welcome! Is there anything else I can help with?", log_, "local", model)
    if booking_context and contact and _WHEN.search(q) and "request_booking" in tools:
        await tool("request_booking", {"details": q, "contact": contact.group(0)})
        return AgentResult("Thank you! I've sent your booking request to the team. They'll confirm with you "
                           f"at {contact.group(0)} shortly.", log_, "local", model)
    if contact and "save_lead" in tools:
        await tool("save_lead", {"contact": contact.group(0), "need": q})
        return AgentResult(f"Thanks! I've passed your details to the team and someone will reach you at "
                           f"{contact.group(0)} soon. Anything else I can answer meanwhile?", log_, "local", model)
    if _BOOK.search(q) and "request_booking" in tools:
        return AgentResult("I'd be happy to arrange that. Please send me, in one message, your name, the date "
                           "and time you'd like, how many people (if relevant), and a phone number or email.",
                           log_, "local", model)
    if _TIME.search(q) and "current_time" in tools:
        out = await tool("current_time", {})
        return AgentResult(f"It's {out}.", log_, "local", model)
    if _MATH.search(q) and "calculator" in tools:
        out = await tool("calculator", {"expression": q})
        if out[:1].isdigit() or out.startswith("-"):
            return AgentResult(f"That comes to {out}.", log_, "local", model)

    # Business knowledge first, but only when it really matches the question.
    if agent.knowledge and "knowledge_search" in tools:
        from .knowledge import get_kb
        hits = get_kb(agent.knowledge).search(q, k=1)
        strong = hits and (hits[0]["coverage"] >= 0.5 or hits[0]["score"] >= 3.0)
        if strong or agent.answer_mode != "open":
            out = await tool("knowledge_search", {"query": q})
            if not out.startswith("No matching"):
                best = out.split("\n\n---\n\n")[0]
                lines = [l for l in best.splitlines()[1:] if l.strip() and not l.lstrip().startswith("#")]
                return AgentResult(" ".join(lines)[:700] or best[:700], log_, "local", model)

    # Any other question: free general-knowledge lookup.
    if agent.answer_mode == "open" and "web_lookup" in tools:
        out = await tool("web_lookup", {"query": q})
        if not out.startswith(("No reliable", "Lookup failed", "No query")):
            return AgentResult(out, log_, "local", model)
        if agent.knowledge and "knowledge_search" in tools:  # weak match is better than nothing
            out = await tool("knowledge_search", {"query": q})
            if not out.startswith("No matching"):
                best = out.split("\n\n---\n\n")[0]
                lines = [l for l in best.splitlines()[1:] if l.strip() and not l.lstrip().startswith("#")]
                return AgentResult(" ".join(lines)[:700], log_, "local", model)
    return AgentResult("I couldn't find a reliable answer to that. If you share your email or phone number, I'll "
                       "pass your question to the team and they'll get back to you.", log_, "local", model)
