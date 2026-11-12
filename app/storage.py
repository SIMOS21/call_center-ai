"""Persistent operational state of *our* support platform (not fake responses)."""
from __future__ import annotations
import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from app.config import path_env

SCHEMA = """
CREATE TABLE IF NOT EXISTS http_requests (
 request_id TEXT PRIMARY KEY, route TEXT NOT NULL, method TEXT NOT NULL,
 status INTEGER NOT NULL, duration_ms REAL NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS interactions (
 request_id TEXT PRIMARY KEY, calls INTEGER NOT NULL, iterations INTEGER NOT NULL,
 duration_ms REAL NOT NULL, escalation INTEGER NOT NULL, confirmation INTEGER NOT NULL,
 model TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS tickets (
 id TEXT PRIMARY KEY, customer_id TEXT NOT NULL, order_id TEXT,
 category TEXT NOT NULL, description TEXT NOT NULL,
 status TEXT NOT NULL DEFAULT 'open', created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS approvals (
 id TEXT PRIMARY KEY, customer_id TEXT NOT NULL, kind TEXT NOT NULL,
 arguments_json TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending',
 created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS audit_events (
 id TEXT PRIMARY KEY, request_id TEXT NOT NULL,
 tool_name TEXT NOT NULL, category TEXT NOT NULL,
 success INTEGER NOT NULL, duration_ms REAL NOT NULL,
 error_type TEXT, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS historical_olist_orders (
 order_id TEXT PRIMARY KEY, customer_id TEXT NOT NULL,
 status TEXT, purchase_at TEXT, delivered_at TEXT);
"""


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def conn():
    db = path_env("DB_FILE", "data/commerceops.sqlite3")
    db.parent.mkdir(parents=True, exist_ok=True)
    cx = sqlite3.connect(db)
    cx.row_factory = sqlite3.Row
    cx.executescript(SCHEMA)
    try:
        with cx:
            yield cx
    finally:
        cx.close()


def create_ticket(customer_id: str, category: str, description: str, order_id: str | None = None) -> dict:
    ticket_id = "tic_" + uuid.uuid4().hex[:16]
    with conn() as cx:
        cx.execute("INSERT INTO tickets (id,customer_id,order_id,category,description,created_at) VALUES (?,?,?,?,?,?)",
                   (ticket_id, customer_id, order_id, category, description[:3000], now()))
    return {"ticket_id": ticket_id, "status": "open", "category": category}


def get_tickets(customer_id: str) -> list[dict]:
    with conn() as cx:
        return [dict(r) for r in cx.execute("SELECT * FROM tickets WHERE customer_id=? ORDER BY created_at DESC LIMIT 50", (customer_id,))]


def create_approval(customer_id: str, kind: str, arguments: dict) -> dict:
    approval_id = "appr_" + uuid.uuid4().hex
    with conn() as cx:
        cx.execute("INSERT INTO approvals (id,customer_id,kind,arguments_json,created_at) VALUES (?,?,?,?,?)",
                   (approval_id, customer_id, kind, json.dumps(arguments), now()))
    return {"approval_id": approval_id, "status": "pending_confirmation", "kind": kind}


def get_approval(approval_id: str, customer_id: str) -> dict | None:
    with conn() as cx:
        row = cx.execute("SELECT * FROM approvals WHERE id=? AND customer_id=?", (approval_id, customer_id)).fetchone()
    return dict(row) if row else None


def mark_approval(approval_id: str, customer_id: str) -> bool:
    with conn() as cx:
        cur = cx.execute("UPDATE approvals SET status='confirmed' WHERE id=? AND customer_id=? AND status='pending'",
                         (approval_id, customer_id))
        return cur.rowcount == 1


def audit(request_id: str, tool: str, category: str, success: bool, duration_ms: float, error_type: str | None = None) -> None:
    # Never store user arguments, JWTs, prompt content, or full outputs here.
    with conn() as cx:
        cx.execute("INSERT INTO audit_events VALUES (?,?,?,?,?,?,?,?)",
                   (uuid.uuid4().hex, request_id, tool, category, int(success), duration_ms, error_type, now()))


def metrics() -> dict:
    with conn() as cx:
        row = cx.execute("SELECT COUNT(*) calls, COALESCE(AVG(duration_ms),0) avg_ms, COALESCE(SUM(1-success),0) failed FROM audit_events").fetchone()
        q = cx.execute("SELECT duration_ms FROM audit_events ORDER BY duration_ms").fetchall()
        requests = cx.execute("SELECT COUNT(*), COALESCE(AVG(duration_ms),0), COALESCE(SUM(status>=400),0) FROM http_requests").fetchone()
        http_lat = [r[0] for r in cx.execute("SELECT duration_ms FROM http_requests ORDER BY duration_ms")]
    lat = [r[0] for r in q]
    return {"tool_calls": row[0], "tool_latency_mean_ms": round(row[1], 2), "tool_errors": row[2],
            "http_requests": requests[0], "http_errors": requests[2], "http_latency_mean_ms": round(requests[1], 2),
            "http_latency_p95_ms": http_lat[int(.95*(len(http_lat)-1))] if http_lat else 0,
            "tool_success_rate": (row[0]-row[2])/row[0] if row[0] else None,
            "tool_latency_p95_ms": lat[min(len(lat)-1, int(.95 * (len(lat)-1)))] if lat else 0}


def interaction(request_id, calls, iterations, duration_ms, escalation, confirmation, model):
    with conn() as cx:
        cx.execute("INSERT OR REPLACE INTO interactions VALUES (?,?,?,?,?,?,?,?)",
                   (request_id, calls, iterations, duration_ms, int(escalation), int(confirmation), model, now()))


def http_request(request_id, route, method, status, duration_ms):
    with conn() as cx:
        cx.execute("INSERT INTO http_requests VALUES (?,?,?,?,?,?)",
                   (request_id, route, method, status, duration_ms, now()))
