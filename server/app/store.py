"""SQLite persistence for events, enrolled faces and settings."""
import json
import sqlite3
import threading
import time
from typing import Any, Optional

from .config import settings

_lock = threading.Lock()
_conn: Optional[sqlite3.Connection] = None


def _get_conn() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        import os
        os.makedirs(settings.DATA_DIR, exist_ok=True)
        _conn = sqlite3.connect(settings.DB_PATH, check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        _conn.execute("PRAGMA journal_mode=WAL")
        _init_schema(_conn)
    return _conn


def _init_schema(c: sqlite3.Connection) -> None:
    c.executescript(
        """
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts REAL NOT NULL,
            kind TEXT NOT NULL,              -- person | face | motion | doorbell
            confidence REAL DEFAULT 0,
            label TEXT DEFAULT '',
            snapshot TEXT DEFAULT '',
            boxes_json TEXT DEFAULT '[]'
        );
        CREATE INDEX IF NOT EXISTS idx_events_ts ON events(ts DESC);

        CREATE TABLE IF NOT EXISTS faces (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            embedding TEXT NOT NULL,         -- JSON list of 128 floats
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL
        );

        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        );
        """
    )
    c.commit()


def _row_to_dict(row: sqlite3.Row) -> dict:
    d = dict(row)
    if "boxes_json" in d:
        d["boxes"] = json.loads(d.pop("boxes_json") or "[]")
    return d


# ------------------------------------------------------------------ events
def add_event(kind: str, confidence: float = 0.0, label: str = "",
              snapshot: str = "", boxes: Optional[list] = None) -> int:
    with _lock:
        c = _get_conn()
        cur = c.execute(
            "INSERT INTO events (ts, kind, confidence, label, snapshot, boxes_json)"
            " VALUES (?,?,?,?,?,?)",
            (time.time(), kind, confidence, label, snapshot,
             json.dumps(boxes or [])),
        )
        c.commit()
        return int(cur.lastrowid)


def list_events(limit: int = 100, offset: int = 0,
                kind: Optional[str] = None) -> list[dict]:
    with _lock:
        c = _get_conn()
        if kind:
            rows = c.execute(
                "SELECT * FROM events WHERE kind=? ORDER BY ts DESC LIMIT ? OFFSET ?",
                (kind, limit, offset)).fetchall()
        else:
            rows = c.execute(
                "SELECT * FROM events ORDER BY ts DESC LIMIT ? OFFSET ?",
                (limit, offset)).fetchall()
    return [_row_to_dict(r) for r in rows]


def delete_event(event_id: int) -> None:
    with _lock:
        c = _get_conn()
        c.execute("DELETE FROM events WHERE id=?", (event_id,))
        c.commit()


def clear_events() -> None:
    with _lock:
        c = _get_conn()
        c.execute("DELETE FROM events")
        c.commit()


# ------------------------------------------------------------------ faces
def upsert_face(name: str, embedding: list[float]) -> None:
    now = time.time()
    with _lock:
        c = _get_conn()
        c.execute(
            "INSERT INTO faces (name, embedding, created_at, updated_at)"
            " VALUES (?,?,?,?)"
            " ON CONFLICT(name) DO UPDATE SET embedding=excluded.embedding,"
            " updated_at=excluded.updated_at",
            (name, json.dumps(embedding), now, now))
        c.commit()


def list_faces() -> list[dict]:
    with _lock:
        c = _get_conn()
        rows = c.execute("SELECT id, name, created_at, updated_at FROM faces"
                         " ORDER BY name").fetchall()
    return [dict(r) for r in rows]


def get_face_embeddings() -> dict[str, list[float]]:
    with _lock:
        c = _get_conn()
        rows = c.execute("SELECT name, embedding FROM faces").fetchall()
    return {r["name"]: json.loads(r["embedding"]) for r in rows}


def delete_face(name: str) -> bool:
    with _lock:
        c = _get_conn()
        cur = c.execute("DELETE FROM faces WHERE name=?", (name,))
        c.commit()
        return cur.rowcount > 0


# ------------------------------------------------------------------ settings
def get_setting(key: str, default: str = "") -> str:
    with _lock:
        c = _get_conn()
        row = c.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return row["value"] if row else default


def set_setting(key: str, value: str) -> None:
    with _lock:
        c = _get_conn()
        c.execute("INSERT INTO settings (key,value) VALUES (?,?)"
                  " ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                  (key, str(value)))
        c.commit()


def get_all_settings() -> dict[str, str]:
    with _lock:
        c = _get_conn()
        rows = c.execute("SELECT key, value FROM settings").fetchall()
    return {r["key"]: r["value"] for r in rows}
