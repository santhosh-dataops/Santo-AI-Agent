"""SQLite storage for leads (sign-ups/contact) and conversation logs.
Zero setup; the file lives in DATA_DIR. Point DATABASE_PATH at a mounted volume in production."""
from __future__ import annotations

import json
import os
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path

from .config import BASE_DIR

DB_PATH = Path(os.getenv("DATABASE_PATH", Path(os.getenv("DATA_DIR", BASE_DIR / "data")) / "santo.db"))
_lock = threading.Lock()

SCHEMA = """
CREATE TABLE IF NOT EXISTS leads (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  email TEXT NOT NULL, name TEXT, company TEXT, plan TEXT, message TEXT, source TEXT,
  created_at TEXT DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS conversations (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  agent_id TEXT NOT NULL, session_id TEXT NOT NULL, user_message TEXT, reply TEXT,
  tools TEXT, provider TEXT, created_at TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS ix_conv_agent ON conversations(agent_id, created_at);
CREATE TABLE IF NOT EXISTS bookings (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  agent_id TEXT NOT NULL, session_id TEXT, name TEXT, contact TEXT, date TEXT, time TEXT,
  party_size INTEGER, details TEXT, status TEXT DEFAULT 'pending',
  created_at TEXT DEFAULT (datetime('now'))
);
"""


@contextmanager
def conn():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _lock:
        c = sqlite3.connect(DB_PATH)
        c.row_factory = sqlite3.Row
        try:
            yield c
            c.commit()
        finally:
            c.close()


def init() -> None:
    with conn() as c:
        c.executescript(SCHEMA)


def add_lead(email: str, name: str = "", company: str = "", plan: str = "", message: str = "",
             source: str = "") -> int:
    with conn() as c:
        cur = c.execute("INSERT INTO leads(email,name,company,plan,message,source) VALUES (?,?,?,?,?,?)",
                        (email, name, company, plan, message, source))
        return cur.lastrowid


def list_leads(limit: int = 200) -> list[dict]:
    with conn() as c:
        return [dict(r) for r in c.execute("SELECT * FROM leads ORDER BY id DESC LIMIT ?", (limit,))]


def add_booking(agent_id: str, session_id: str, name: str, contact: str, date: str, time: str,
                party_size, details: str) -> int:
    try:
        party_size = int(party_size) if party_size not in (None, "") else None
    except (TypeError, ValueError):
        party_size = None
    with conn() as c:
        return c.execute("INSERT INTO bookings(agent_id,session_id,name,contact,date,time,party_size,details) "
                         "VALUES (?,?,?,?,?,?,?,?)",
                         (agent_id, session_id, name, contact, date, time, party_size, details)).lastrowid


def list_bookings(limit: int = 200) -> list[dict]:
    with conn() as c:
        return [dict(r) for r in c.execute("SELECT * FROM bookings ORDER BY id DESC LIMIT ?", (limit,))]


def set_booking_status(booking_id: int, status: str) -> bool:
    with conn() as c:
        return c.execute("UPDATE bookings SET status=? WHERE id=?", (status, booking_id)).rowcount > 0


def log_conversation(agent_id: str, session_id: str, user_message: str, reply: str,
                     tools: list, provider: str) -> None:
    with conn() as c:
        c.execute("INSERT INTO conversations(agent_id,session_id,user_message,reply,tools,provider) "
                  "VALUES (?,?,?,?,?,?)",
                  (agent_id, session_id, user_message, reply, json.dumps([t.get("tool") for t in tools]), provider))


def recent_conversations(agent_id: str | None = None, limit: int = 50) -> list[dict]:
    q, args = "SELECT * FROM conversations", []
    if agent_id:
        q, args = q + " WHERE agent_id=?", [agent_id]
    with conn() as c:
        return [dict(r) for r in c.execute(q + " ORDER BY id DESC LIMIT ?", (*args, limit))]


def stats() -> dict:
    with conn() as c:
        per_agent = [dict(r) for r in c.execute(
            "SELECT agent_id, COUNT(*) AS messages, COUNT(DISTINCT session_id) AS conversations, "
            "MAX(created_at) AS last_active FROM conversations GROUP BY agent_id ORDER BY messages DESC")]
        daily = [dict(r) for r in c.execute(
            "SELECT date(created_at) AS day, COUNT(*) AS messages FROM conversations "
            "WHERE created_at >= datetime('now','-13 days') GROUP BY day ORDER BY day")]
        totals = dict(c.execute(
            "SELECT (SELECT COUNT(*) FROM conversations) AS messages, "
            "(SELECT COUNT(DISTINCT agent_id||session_id) FROM conversations) AS conversations, "
            "(SELECT COUNT(*) FROM leads) AS leads, "
            "(SELECT COUNT(*) FROM bookings) AS bookings").fetchone())
    return {"totals": totals, "per_agent": per_agent, "daily": daily}
