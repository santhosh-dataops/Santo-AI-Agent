"""Zero-dependency knowledge base: drop .md/.txt files into knowledge/<agent>/ and they
become searchable with BM25. Swap for a vector DB (pgvector, Qdrant...) later if needed."""
from __future__ import annotations

import logging
import math
import os
import re
from collections import Counter
from functools import lru_cache
from pathlib import Path

import httpx

from .config import KNOWLEDGE_DIR

log = logging.getLogger("santo.knowledge")
EMBED_MODEL = os.getenv("EMBED_MODEL", "nomic-embed-text")


async def _embed(texts: list[str]) -> list[list[float]] | None:
    """Embeddings from the local Ollama server (free, no key). None if unavailable."""
    url = os.getenv("OLLAMA_URL")
    if not url or not texts:
        return None
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.post(url.rstrip("/") + "/api/embed", json={"model": EMBED_MODEL, "input": texts})
            r.raise_for_status()
            return r.json().get("embeddings")
    except Exception as exc:
        log.info("Embeddings unavailable (%s); using keyword search", exc)
        return None


def _cos(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na, nb = math.sqrt(sum(x * x for x in a)), math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0

_TOKEN = re.compile(r"[a-z0-9]+")
_STOP = set("a an and are as at be by for from has have how i in is it of on or our the to we what when where which who why with you your can do does".split())


def _stem(t: str) -> str:
    """Light plural/verb folding so "costs" matches "cost" and "restaurants" matches "restaurant"."""
    if len(t) > 5 and t.endswith("ing"):
        return t[:-3]
    if len(t) > 3 and t.endswith("s") and not t.endswith("ss"):
        return t[:-1]
    return t


def _tokens(text: str) -> list[str]:
    return [_stem(t) for t in _TOKEN.findall(text.lower()) if t not in _STOP]


# Everyday words customers use -> words businesses write. Helps keyword search when the
# semantic model isn't running.
_SYNONYMS = {
    "money": ["refund", "return"], "refund": ["return", "refund"], "send": ["return", "ship"],
    "cost": ["price", "pricing", "fee"], "price": ["cost", "pricing"], "much": ["price", "cost"], "charge": ["fee", "price"],
    "open": ["hour"], "close": ["hour"], "time": ["hour"], "when": ["hour"],
    "deliver": ["shipping", "ship"], "delivery": ["shipping", "ship"], "arrive": ["shipping", "ship"],
    "broken": ["warranty", "defect"], "guarantee": ["warranty"], "damaged": ["warranty", "claim"],
    "vegetarian": ["vegan"], "allergy": ["allergen"], "gluten": ["allergen"],
    "insurance": ["insurance"], "leave": ["pto"], "vacation": ["pto"], "holiday": ["pto"], "salary": ["payroll", "payday"], "paid": ["payroll", "payday"],
    "park": ["parking"], "where": ["location"], "address": ["location"],
}


def _expand(tokens: list[str]) -> list[str]:
    out = list(tokens)
    for t in tokens:
        out += [_stem(x) for x in _SYNONYMS.get(t, [])]
    return out


def _chunk(text: str, source: str, max_chars: int = 900) -> list[dict]:
    chunks, buf, heading = [], "", ""
    for block in re.split(r"\n\s*\n", text):
        block = block.strip()
        if not block:
            continue
        is_heading = block.startswith("#")
        if buf and (is_heading or len(buf) + len(block) > max_chars):
            chunks.append({"source": source, "heading": heading, "text": buf.strip()})
            buf = ""
        if is_heading:
            heading = block.splitlines()[0].lstrip("# ").strip()
        buf += block + "\n\n"
    if buf.strip():
        chunks.append({"source": source, "heading": heading, "text": buf.strip()})
    return chunks


class KnowledgeBase:
    def __init__(self, folder: Path):
        self.chunks: list[dict] = []
        if folder.is_dir():
            for f in sorted(folder.rglob("*")):
                if f.suffix.lower() in {".md", ".txt"}:
                    self.chunks += _chunk(f.read_text(encoding="utf-8"), f.name)
        self._tf = [Counter(_tokens(c["heading"] + " " + c["text"])) for c in self.chunks]
        self._len = [sum(tf.values()) for tf in self._tf]
        self._avg = (sum(self._len) / len(self._len)) if self._len else 1
        df = Counter(t for tf in self._tf for t in tf)
        n = len(self.chunks)
        self._idf = {t: math.log(1 + (n - d + 0.5) / (d + 0.5)) for t, d in df.items()}

    async def hybrid_search(self, query: str, k: int = 3) -> list[dict]:
        """Meaning-based search (local embeddings) blended with keyword search. Falls back to keywords."""
        keyword = self.search(query, k=max(k, 6))
        if not self.chunks:
            return keyword[:k]
        if getattr(self, "_vecs", None) is None:
            self._vecs = await _embed([f"{c['heading']}\n{c['text']}" for c in self.chunks]) or []
        if not self._vecs:
            return keyword[:k]
        qv = await _embed([query])
        if not qv:
            return keyword[:k]
        kw = {id(h["text"]): h["score"] for h in keyword}
        top_kw = max(kw.values(), default=1) or 1
        scored = []
        for i, c in enumerate(self.chunks):
            sem = _cos(qv[0], self._vecs[i])
            bm = next((h["score"] for h in keyword if h["text"] == c["text"]), 0) / top_kw
            scored.append((0.7 * sem + 0.3 * bm, i))
        scored.sort(reverse=True)
        return [dict(self.chunks[i], score=round(sc, 3)) for sc, i in scored[:k] if sc > 0.25]

    def search(self, query: str, k: int = 3) -> list[dict]:
        q = _expand(_tokens(query))
        k1, b = 1.5, 0.75
        scored = []
        base = set(_tokens(query)) or set(q)
        for i, tf in enumerate(self._tf):
            s = 0.0
            hit = len([t for t in base if t in tf or any(_stem(x) in tf for x in _SYNONYMS.get(t, []))])
            for t in q:
                if t in tf:
                    f = tf[t]
                    s += self._idf[t] * f * (k1 + 1) / (f + k1 * (1 - b + b * self._len[i] / self._avg))
            if s > 0:
                scored.append((s, i, hit / max(1, len(base))))
        scored.sort(reverse=True)
        return [dict(self.chunks[i], score=round(s, 3), coverage=round(c, 2)) for s, i, c in scored[:k]]


@lru_cache(maxsize=64)
def get_kb(name: str | None) -> KnowledgeBase:
    return KnowledgeBase(KNOWLEDGE_DIR / name) if name else KnowledgeBase(Path("/nonexistent"))
