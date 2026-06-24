"""SQLite-lagring for konversationer och meddelanden.

Enkel persistens sa flera samtal sparas mellan omstarter. Vi lagrar bara
user-/assistant-turernas innehall (plus ev. kallcitat for assistenten) -
verktygsanrop kors om vid varje ny fraga, sa de behover inte sparas.
"""
from __future__ import annotations

import datetime
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
            CREATE TABLE IF NOT EXISTS users (
                id            TEXT PRIMARY KEY,
                email         TEXT NOT NULL UNIQUE COLLATE NOCASE,
                password_hash TEXT NOT NULL,
                is_admin      INTEGER NOT NULL DEFAULT 0,
                created_at    REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS conversations (
                id          TEXT PRIMARY KEY,
                title       TEXT NOT NULL,
                created_at  REAL NOT NULL,
                updated_at  REAL NOT NULL,
                model       TEXT,
                provider    TEXT,
                user_id     TEXT REFERENCES users(id) ON DELETE CASCADE
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
            CREATE TABLE IF NOT EXISTS usage (
                id                TEXT PRIMARY KEY,
                conversation_id   TEXT,
                message_id        TEXT,
                model             TEXT NOT NULL,
                prompt_tokens     INTEGER NOT NULL,
                completion_tokens INTEGER NOT NULL,
                created_at        REAL NOT NULL,
                provider          TEXT,
                latency_ms        INTEGER
            );
            CREATE INDEX IF NOT EXISTS idx_usage_created ON usage(created_at);
            CREATE INDEX IF NOT EXISTS idx_usage_conv ON usage(conversation_id);
            """
        )
        # Migrering for aldre databaser: lagg till kolumner som saknas.
        existing = {row["name"] for row in conn.execute("PRAGMA table_info(usage)")}
        if "provider" not in existing:
            conn.execute("ALTER TABLE usage ADD COLUMN provider TEXT")
        if "latency_ms" not in existing:
            conn.execute("ALTER TABLE usage ADD COLUMN latency_ms INTEGER")
        conv_cols = {row["name"] for row in conn.execute("PRAGMA table_info(conversations)")}
        if "model" not in conv_cols:
            conn.execute("ALTER TABLE conversations ADD COLUMN model TEXT")
        if "provider" not in conv_cols:
            conn.execute("ALTER TABLE conversations ADD COLUMN provider TEXT")
        if "user_id" not in conv_cols:
            # Aldre DB: samtalen saknar agare. Kolumnen laggs till har; befintliga
            # samtal knyts till bootstrap-adminen i ensure_bootstrap_admin().
            conn.execute("ALTER TABLE conversations ADD COLUMN user_id TEXT")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_conv_user ON conversations(user_id, updated_at)")
        # Backfill: samtal skapade innan kolumnerna fanns saknar model/provider.
        # Harled dem fran den FORSTA usage-raden for samtalet (den som startade
        # det), sa aven gamla trader far en tooltip. Idempotent (rakar bara NULL).
        conn.execute(
            """
            UPDATE conversations SET
                model = (
                    SELECT model FROM usage u
                    WHERE u.conversation_id = conversations.id
                    ORDER BY u.created_at LIMIT 1
                ),
                provider = (
                    SELECT COALESCE(provider, 'grunden') FROM usage u
                    WHERE u.conversation_id = conversations.id
                    ORDER BY u.created_at LIMIT 1
                )
            WHERE model IS NULL
              AND EXISTS (SELECT 1 FROM usage u WHERE u.conversation_id = conversations.id)
            """
        )


def list_conversations(user_id: str) -> list[dict]:
    """Lista en anvandares egna samtal (nyast forst)."""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT id, title, updated_at, model, provider FROM conversations "
            "WHERE user_id = ? ORDER BY updated_at DESC",
            (user_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def create_conversation(
    title: str, user_id: str, model: str | None = None, provider: str | None = None
) -> str:
    """Skapa ett samtal agt av user_id. model/provider lagras for den leverantor
    som STARTADE samtalet, sa sidopanelen kan visa det i tooltip aven om man
    byter sen."""
    conv_id = uuid.uuid4().hex
    now = time.time()
    with _connect() as conn:
        conn.execute(
            "INSERT INTO conversations (id, title, created_at, updated_at, model, provider, user_id) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (conv_id, title.strip()[:80] or "Nytt samtal", now, now, model, provider, user_id),
        )
    return conv_id


def conversation_owned_by(conv_id: str, user_id: str) -> bool:
    """True om samtalet finns OCH agas av user_id. Gar att anvanda bade for
    atkomstkontroll och for att avgora om ett samtals-id ska ateranvandas."""
    with _connect() as conn:
        row = conn.execute(
            "SELECT 1 FROM conversations WHERE id = ? AND user_id = ?",
            (conv_id, user_id),
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


# --------------------------------------------------------------------------- #
#  Anvandare (inloggning)
# --------------------------------------------------------------------------- #
def count_users() -> int:
    with _connect() as conn:
        return conn.execute("SELECT COUNT(*) AS n FROM users").fetchone()["n"]


def create_user(email: str, password_hash: str, is_admin: bool) -> str:
    """Skapa en anvandare. Kastar sqlite3.IntegrityError om e-posten redan finns."""
    user_id = uuid.uuid4().hex
    with _connect() as conn:
        conn.execute(
            "INSERT INTO users (id, email, password_hash, is_admin, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (user_id, email.strip(), password_hash, 1 if is_admin else 0, time.time()),
        )
    return user_id


def get_user_by_email(email: str) -> dict | None:
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE email = ?", (email.strip(),)
        ).fetchone()
    return dict(row) if row else None


def get_user(user_id: str) -> dict | None:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    return dict(row) if row else None


def list_users() -> list[dict]:
    """Alla anvandare (utan losenordshash) for admin-vyn."""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT id, email, is_admin, created_at FROM users ORDER BY created_at"
        ).fetchall()
    return [{**dict(r), "is_admin": bool(r["is_admin"])} for r in rows]


def set_admin(user_id: str, is_admin: bool) -> None:
    with _connect() as conn:
        conn.execute(
            "UPDATE users SET is_admin = ? WHERE id = ?", (1 if is_admin else 0, user_id)
        )


def set_password(user_id: str, password_hash: str) -> None:
    with _connect() as conn:
        conn.execute(
            "UPDATE users SET password_hash = ? WHERE id = ?", (password_hash, user_id)
        )


def delete_user(user_id: str) -> None:
    """Ta bort en anvandare. Samtalen foljer med (ON DELETE CASCADE)."""
    with _connect() as conn:
        conn.execute("DELETE FROM users WHERE id = ?", (user_id,))


def admin_count() -> int:
    """Antal admins - sa vi aldrig tar bort/degraderar den sista adminen."""
    with _connect() as conn:
        return conn.execute(
            "SELECT COUNT(*) AS n FROM users WHERE is_admin = 1"
        ).fetchone()["n"]


def assign_orphan_conversations(user_id: str) -> int:
    """Knyt alla agarlosa samtal (user_id IS NULL) till user_id. Korrigerar
    befintliga samtal fran tiden innan inloggning fanns. Returnerar antal."""
    with _connect() as conn:
        cur = conn.execute(
            "UPDATE conversations SET user_id = ? WHERE user_id IS NULL", (user_id,)
        )
        return cur.rowcount


# --------------------------------------------------------------------------- #
#  Token-anvandning (for Driftinfo)
# --------------------------------------------------------------------------- #
def record_usage(
    conversation_id: str | None,
    message_id: str | None,
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    provider: str | None = None,
    latency_ms: int | None = None,
) -> None:
    """Spara token-forbrukningen (och svarstid) for en avslutad fraga."""
    if not (prompt_tokens or completion_tokens):
        return  # inget att spara (t.ex. om API:t inte returnerade usage)
    with _connect() as conn:
        conn.execute(
            "INSERT INTO usage (id, conversation_id, message_id, model, "
            "prompt_tokens, completion_tokens, created_at, provider, latency_ms) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                uuid.uuid4().hex,
                conversation_id,
                message_id,
                model,
                int(prompt_tokens),
                int(completion_tokens),
                time.time(),
                provider,
                int(latency_ms) if latency_ms is not None else None,
            ),
        )


def usage_summary(provider: str | None = None) -> dict:
    """Aggregerad token-anvandning for EN leverantor: senaste fraga, senaste
    trad, idag, totalt. Bara rader som korts mot `provider` raknas, sa
    Driftinfo speglar enbart den valda leverantoren. Rader utan provider raknas
    som 'grunden' (gamla rader fran innan kolumnen fanns)."""
    prov = provider or "grunden"
    midnight = (
        datetime.datetime.now()
        .replace(hour=0, minute=0, second=0, microsecond=0)
        .timestamp()
    )
    with _connect() as conn:
        last = conn.execute(
            "SELECT conversation_id, message_id, latency_ms FROM usage "
            "WHERE COALESCE(provider, 'grunden') = ? ORDER BY created_at DESC LIMIT 1",
            (prov,),
        ).fetchone()
        last_conv_id = last["conversation_id"] if last else None
        last_msg_id = last["message_id"] if last else None
        last_latency_ms = last["latency_ms"] if last else None

        def agg(cond: str, params: tuple) -> dict:
            # Leverantorsfiltret ligger alltid forst; ev. extra villkor laggs pa.
            where = "WHERE COALESCE(provider, 'grunden') = ?" + (f" AND {cond}" if cond else "")
            args = (prov,) + params
            row = conn.execute(
                "SELECT COALESCE(SUM(prompt_tokens), 0) AS p, "
                "COALESCE(SUM(completion_tokens), 0) AS c, COUNT(*) AS n "
                f"FROM usage {where}",
                args,
            ).fetchone()
            # Gruppera per (provider, model) sa kostnaden kan rakna i ratt valuta.
            groups = conn.execute(
                "SELECT COALESCE(provider, 'grunden') AS provider, model, "
                "COALESCE(SUM(prompt_tokens), 0) AS p, "
                "COALESCE(SUM(completion_tokens), 0) AS c "
                f"FROM usage {where} GROUP BY provider, model",
                args,
            ).fetchall()
            return {
                "prompt_tokens": row["p"],
                "completion_tokens": row["c"],
                "total_tokens": row["p"] + row["c"],
                "requests": row["n"],
                "by_model": [
                    {
                        "provider": g["provider"],
                        "model": g["model"],
                        "prompt_tokens": g["p"],
                        "completion_tokens": g["c"],
                    }
                    for g in groups
                ],
            }

        last_message = agg("message_id = ?", (last_msg_id,)) if last_msg_id else agg("0", ())
        last_conversation = (
            agg("conversation_id = ?", (last_conv_id,)) if last_conv_id else agg("0", ())
        )
        today = agg("created_at >= ?", (midnight,))
        total = agg("", ())

        title = None
        if last_conv_id:
            trow = conn.execute(
                "SELECT title FROM conversations WHERE id = ?", (last_conv_id,)
            ).fetchone()
            title = trow["title"] if trow else None

    last_conversation["conversation_title"] = title
    return {
        "last_message": last_message,
        "last_conversation": last_conversation,
        "today": today,
        "total": total,
        "last_latency_ms": last_latency_ms,
    }


def reset_usage() -> None:
    """Nollstall all token-/kostnadsstatistik (Driftinfo). Sjalva samtalen lamnas
    ororda - bara usage-tabellen toms."""
    with _connect() as conn:
        conn.execute("DELETE FROM usage")
