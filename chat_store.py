import sqlite3
import json
import os
from datetime import datetime
from nova_logging import get_logger

logger = get_logger("chat_store")

DB_PATH = os.getenv("NOVA_CHAT_DB", "nova_chat.db")


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def _init_db():
    """Create tables if they don't exist."""
    conn = _get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS sessions (
            id TEXT PRIMARY KEY,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT,
            name TEXT,
            tool_call_id TEXT,
            tool_calls_json TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id);
    """)
    conn.commit()
    conn.close()


# Initialize on import
_init_db()


def save_message(session_id: str, role: str, content: str = None,
                 name: str = None, tool_call_id: str = None, tool_calls=None):
    """Save a single message to the database."""
    conn = _get_conn()
    now = datetime.utcnow().isoformat()

    # Upsert session
    conn.execute(
        "INSERT INTO sessions (id, created_at, updated_at) VALUES (?, ?, ?) "
        "ON CONFLICT(id) DO UPDATE SET updated_at = ?",
        (session_id, now, now, now),
    )

    tool_calls_json = json.dumps(tool_calls) if tool_calls else None
    conn.execute(
        "INSERT INTO messages (session_id, role, content, name, tool_call_id, tool_calls_json, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (session_id, role, content, name, tool_call_id, tool_calls_json, now),
    )
    conn.commit()
    conn.close()


def load_session(session_id: str) -> list:
    """Load all messages for a session, returning OpenAI-compatible dicts."""
    conn = _get_conn()
    rows = conn.execute(
        "SELECT role, content, name, tool_call_id, tool_calls_json FROM messages "
        "WHERE session_id = ? ORDER BY id",
        (session_id,),
    ).fetchall()
    conn.close()

    messages = []
    for row in rows:
        msg = {"role": row["role"]}
        if row["content"] is not None:
            msg["content"] = row["content"]
        if row["name"]:
            msg["name"] = row["name"]
        if row["tool_call_id"]:
            msg["tool_call_id"] = row["tool_call_id"]
        if row["tool_calls_json"]:
            msg["tool_calls"] = json.loads(row["tool_calls_json"])
        messages.append(msg)
    return messages


def list_sessions() -> list:
    """Return a list of all sessions with metadata."""
    conn = _get_conn()
    rows = conn.execute(
        "SELECT s.id, s.created_at, s.updated_at, "
        "(SELECT content FROM messages WHERE session_id = s.id AND role = 'user' ORDER BY id LIMIT 1) as first_message, "
        "(SELECT COUNT(*) FROM messages WHERE session_id = s.id) as message_count "
        "FROM sessions s ORDER BY s.updated_at DESC",
    ).fetchall()
    conn.close()
    return [
        {
            "id": row["id"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "preview": (row["first_message"] or "")[:80],
            "message_count": row["message_count"],
        }
        for row in rows
    ]


def delete_session(session_id: str) -> bool:
    """Delete a session and all its messages."""
    conn = _get_conn()
    conn.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
    result = conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
    conn.commit()
    deleted = result.rowcount > 0
    conn.close()
    return deleted
