"""Loads agent definitions from agents/*.yaml. One YAML file = one business agent."""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

BASE_DIR = Path(__file__).resolve().parent.parent
AGENTS_DIR = Path(os.getenv("AGENTS_DIR", BASE_DIR / "agents"))
KNOWLEDGE_DIR = Path(os.getenv("KNOWLEDGE_DIR", BASE_DIR / "knowledge"))


class HttpTool(BaseModel):
    """A business API the agent may call (CRM, booking system, order DB, webhook...)."""
    name: str
    description: str
    method: str = "GET"
    url: str  # may contain {param} placeholders and ${ENV_VAR} references
    headers: dict[str, str] = Field(default_factory=dict)
    parameters: dict[str, Any] = Field(default_factory=dict)  # JSON-schema "properties"
    required: list[str] = Field(default_factory=list)


class AgentConfig(BaseModel):
    id: str
    name: str
    business: str = ""
    domain: str = "general"
    description: str = ""
    greeting: str = "Hi! How can I help you today?"
    system_prompt: str
    provider: str | None = None  # anthropic | openai | mock ; falls back to LLM_PROVIDER
    model: str | None = None
    temperature: float = 0.3
    max_tokens: int = 1024
    knowledge: str | None = None  # folder name under knowledge/
    builtin_tools: list[str] = Field(default_factory=lambda: ["knowledge_search", "web_lookup", "calculator", "current_time",
                                                            "save_lead", "request_booking"])
    answer_mode: str = "open"  # open: answers any question; business: only questions about the business
    http_tools: list[HttpTool] = Field(default_factory=list)
    theme_color: str = "#2563eb"
    suggested_questions: list[str] = Field(default_factory=list)


_ENV = re.compile(r"\$\{([A-Z0-9_]+)\}")


def expand_env(value: str) -> str:
    return _ENV.sub(lambda m: os.getenv(m.group(1), ""), value)


def load_agents(directory: Path = AGENTS_DIR) -> dict[str, AgentConfig]:
    agents: dict[str, AgentConfig] = {}
    for path in sorted(directory.glob("*.y*ml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        data.setdefault("id", path.stem)
        cfg = AgentConfig(**data)
        agents[cfg.id] = cfg
    return agents
