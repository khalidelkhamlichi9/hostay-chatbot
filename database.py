import logging
import os
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

DEFAULT_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hostay_chatbot.db")
DB_PATH = os.getenv("CHATBOT_DB_PATH", DEFAULT_DB_PATH)
DB_DIR = os.path.dirname(DB_PATH)
if DB_DIR:
    os.makedirs(DB_DIR, exist_ok=True)


def connect_db(timeout: float = 10.0) -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=timeout)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=30000")
    return conn


@contextmanager
def get_db(timeout: float = 10.0):
    """Context manager: open connection, commit on success, rollback on error, always close."""
    conn = connect_db(timeout)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# =========================================================
# INITIALIZATION
# =========================================================
def init_admin_tables():
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS prompts (
                role TEXT PRIMARY KEY,
                system_prompt TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS rag_chunks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                doc_id TEXT NOT NULL,
                title TEXT,
                content TEXT NOT NULL,
                tags TEXT DEFAULT ''
            )
        """)
        default_prompts = [
            ("guest", "Tu es l'assistant IA officiel de Hostay. Tu parles à un voyageur/guest. Réponds de manière utile, concise et courtoise."),
            ("owner", "Tu es l'assistant IA officiel de Hostay. Tu parles à un propriétaire. Focus sur la gestion, les revenus, et la technique."),
            ("concierge", "Tu es l'assistant IA officiel de Hostay. Tu parles à un concierge. Priorise les procédures, la logistique et l'urgence.")
        ]
        for role, prompt in default_prompts:
            conn.execute("INSERT OR IGNORE INTO prompts (role, system_prompt) VALUES (?, ?)", (role, prompt))
    logger.info("Admin tables (prompts & rag_chunks) initialized.")


def init_db():
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                timestamp TEXT NOT NULL,
                user_role TEXT NOT NULL,
                language TEXT NOT NULL,
                urgency_level TEXT DEFAULT 'Normal',
                urgency_type TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                FOREIGN KEY(session_id) REFERENCES sessions(id) ON DELETE CASCADE
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                user_role TEXT NOT NULL,
                message TEXT NOT NULL,
                reply TEXT NOT NULL,
                language TEXT NOT NULL,
                urgency_level TEXT DEFAULT 'Normal',
                urgency_type TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id INTEGER,
                rating INTEGER,
                comment TEXT,
                timestamp TEXT,
                FOREIGN KEY (conversation_id) REFERENCES conversations(id)
            )
        """)
    logger.info("Core tables initialized.")
    init_admin_tables()
    logger.info("Database fully initialized: %s", DB_PATH)


# =========================================================
# CONVERSATIONS & SESSIONS
# =========================================================
def create_session(user_role: str, language: str, urgency: Any) -> str:
    urgency_level = "Normal"
    urgency_type = None
    if urgency:
        if isinstance(urgency, dict):
            urgency_level = str(urgency.get("level", "Normal"))
            urgency_type = urgency.get("type")
            if urgency_type:
                urgency_type = str(urgency_type)
        elif isinstance(urgency, str):
            urgency_level = urgency
        else:
            urgency_level = str(urgency)

    session_id = str(uuid.uuid4())
    with get_db() as conn:
        conn.execute(
            "INSERT INTO sessions (id, timestamp, user_role, language, urgency_level, urgency_type) VALUES (?, ?, ?, ?, ?, ?)",
            (session_id, datetime.now().isoformat(), str(user_role), str(language), urgency_level, urgency_type),
        )
    return session_id


def add_message(session_id: str, role: str, content: str) -> int:
    with get_db() as conn:
        cursor = conn.execute(
            "INSERT INTO messages (session_id, role, content, timestamp) VALUES (?, ?, ?, ?)",
            (session_id, role, content, datetime.now().isoformat()),
        )
        return cursor.lastrowid


def get_session_messages(session_id: str) -> List[Dict]:
    with get_db() as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM messages WHERE session_id = ? ORDER BY timestamp ASC", (session_id,)
        ).fetchall()
    return [dict(row) for row in rows]


def get_session(session_id: str) -> Optional[Dict]:
    try:
        with get_db() as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
        return dict(row) if row else None
    except Exception as e:
        logger.error("Database error in get_session: %s", e)
        return None


# =========================================================
# ADMIN & ANALYTICS
# =========================================================
def get_prompt(role: str) -> str:
    with get_db() as conn:
        res = conn.execute("SELECT system_prompt FROM prompts WHERE role = ?", (role,)).fetchone()
    return res[0] if res else ""


def save_prompt(role: str, prompt: str):
    with get_db() as conn:
        conn.execute("INSERT OR REPLACE INTO prompts (role, system_prompt) VALUES (?, ?)", (role, prompt))


def get_analytics() -> dict:
    with get_db() as conn:
        total = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
        by_role = dict(conn.execute("SELECT user_role, COUNT(*) FROM sessions GROUP BY user_role").fetchall())
        by_lang = dict(conn.execute("SELECT language, COUNT(*) FROM sessions GROUP BY language").fetchall())
        by_urgency = dict(conn.execute("SELECT urgency_level, COUNT(*) FROM sessions GROUP BY urgency_level").fetchall())
    return {"total": total, "by_role": by_role, "by_lang": by_lang, "by_urgency": by_urgency}


def get_all_sessions(limit: int = 50) -> List[Dict]:
    with get_db() as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM sessions ORDER BY timestamp DESC LIMIT ?", (limit,)).fetchall()
    return [dict(r) for r in rows]


def delete_session(session_id: str):
    with get_db() as conn:
        conn.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
        conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))


def update_message(message_id: int, new_content: str):
    with get_db() as conn:
        conn.execute("UPDATE messages SET content = ? WHERE id = ?", (new_content, message_id))


def delete_message(message_id: int):
    with get_db() as conn:
        conn.execute("DELETE FROM messages WHERE id = ?", (message_id,))


# =========================================================
# RAG CHUNKS MANAGEMENT
# =========================================================
def get_all_chunks() -> List[Dict]:
    with get_db() as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM rag_chunks ORDER BY id DESC").fetchall()
    return [dict(r) for r in rows]


def add_chunk(doc_id: str, title: str, content: str, tags: str = "") -> int:
    with get_db() as conn:
        cursor = conn.execute(
            "INSERT INTO rag_chunks (doc_id, title, content, tags) VALUES (?, ?, ?, ?)",
            (doc_id, title, content, tags),
        )
        return cursor.lastrowid


def update_chunk(cid: int, title: str, content: str, tags: str):
    with get_db() as conn:
        conn.execute(
            "UPDATE rag_chunks SET title = ?, content = ?, tags = ? WHERE id = ?",
            (title, content, tags, cid),
        )


def delete_chunk(cid: int):
    with get_db() as conn:
        conn.execute("DELETE FROM rag_chunks WHERE id = ?", (cid,))
