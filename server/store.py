"""SQLite-lagring for konversationer och meddelanden.

Enkel persistens sa flera samtal sparas mellan omstarter. Vi lagrar bara
user-/assistant-turernas innehall (plus ev. kallcitat for assistenten) -
verktygsanrop kors om vid varje ny fraga, sa de behover inte sparas.
"""
from __future__ import annotations

import json
import os
import sqlite3
import time
import uuid

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "app.db")


def _connect() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    with _connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS conversations (
                id          TEXT PRIMARY KEY,
                title       TEXT NOT NULL,
                created_at  REAL NOT NULL,
                updated_at  REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS messages (
                id              TEXT PRIMARY KEY,
                conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
                role            TEXT NOT NULL,
                content         TEXT NOT NULL,
                citations       TEXT,
                created_at      REAL NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_messages_conv ON messages(conversation_id, created_at);
            """
        )


def list_conversations() -> list[dict]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT id, title, updated_at FROM conversations ORDER BY updated_at DESC"
        ).fetchall()
    return [dict(r) for r in rows]


def create_conversation(title: str) -> str:
    conv_id = uuid.uuid4().hex
    now = time.time()
    with _connect() as conn:
        conn.execute(
            "INSERT INTO conversations (id, title, created_at, updated_at) VALUES (?, ?, ?, ?)",
            (conv_id, title.strip()[:80] or "Nytt samtal", now, now),
        )
    return conv_id


def conversation_exists(conv_id: str) -> bool:
    with _connect() as conn:
        row = conn.execute(
            "SELECT 1 FROM conversations WHERE id = ?", (conv_id,)
        ).fetchone()
    return row is not None


def rename_conversation(conv_id: str, title: str) -> None:
    with _connect() as conn:
        conn.execute(
            "UPDATE conversations SET title = ? WHERE id = ?",
            (title.strip()[:80] or "Nytt samtal", conv_id),
        )


def delete_conversation(conv_id: str) -> None:
    with _connect() as conn:
        conn.execute("DELETE FROM conversations WHERE id = ?", (conv_id,))


def get_messages(conv_id: str) -> list[dict]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT id, role, content, citations, created_at FROM messages "
            "WHERE conversation_id = ? ORDER BY created_at",
            (conv_id,),
        ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["citations"] = json.loads(d["citations"]) if d["citations"] else []
        out.append(d)
    return out


def add_message(conv_id: str, role: str, content: str, citations: list | None = None) -> str:
    msg_id = uuid.uuid4().hex
    now = time.time()
    with _connect() as conn:
        conn.execute(
            "INSERT INTO messages (id, conversation_id, role, content, citations, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (msg_id, conv_id, role, content, json.dumps(citations or [], ensure_ascii=False), now),
        )
        conn.execute(
            "UPDATE conversations SET updated_at = ? WHERE id = ?", (now, conv_id)
        )
    return msg_id
