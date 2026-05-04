# database.py - Gestion SQLite complète (Conversations + Admin + RAG Chunks)
import sqlite3
import os
from datetime import datetime
from typing import List, Dict, Optional, Any
import logging

logger = logging.getLogger(__name__)

# Path absolu
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hostay_chatbot.db")


# =========================================================
# 🛠️ INITIALIZATION FUNCTIONS
# =========================================================
def init_admin_tables():
    """Créer les tables Admin (Prompts, RAG Chunks) et insérer les prompts par défaut"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 3️⃣ Table Prompts (Admin)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS prompts (
            role TEXT PRIMARY KEY,
            system_prompt TEXT NOT NULL
        )
    """)

    # 4️⃣ Table RAG Chunks (Admin)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS rag_chunks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            doc_id TEXT NOT NULL,
            title TEXT,
            content TEXT NOT NULL,
            tags TEXT DEFAULT ''
        )
    """)

    # 🔽 Insert default prompts si vides
    default_prompts = [
        ("guest", "Tu es l'assistant IA officiel de Hostay. Tu parles à un voyageur/guest. Réponds de manière utile, concise et courtoise."),
        ("owner", "Tu es l'assistant IA officiel de Hostay. Tu parles à un propriétaire. Focus sur la gestion, les revenus, et la technique."),
        ("concierge", "Tu es l'assistant IA officiel de Hostay. Tu parles à un concierge. Priorise les procédures, la logistique et l'urgence.")
    ]

    for role, prompt in default_prompts:
        cursor.execute("INSERT OR IGNORE INTO prompts (role, system_prompt) VALUES (?, ?)", (role, prompt))

    conn.commit()
    conn.close()
    logger.info("✅ Admin tables (prompts & rag_chunks) initialized.")


def init_db():
    """Créer toutes les tables et initialiser la base de données"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 1️⃣ Table Sessions
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id TEXT PRIMARY KEY,
            timestamp TEXT NOT NULL,
            user_role TEXT NOT NULL,
            language TEXT NOT NULL,
            urgency_level TEXT DEFAULT 'Normal',
            urgency_type TEXT
        )
    """)

    # 1.5️⃣ Table Messages
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            FOREIGN KEY(session_id) REFERENCES sessions(id) ON DELETE CASCADE
        )
    """)

    # Keep old conversations table for backup/reference if needed
    cursor.execute("""
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

    # 2️⃣ Table Feedback
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id INTEGER,
            rating INTEGER,
            comment TEXT,
            timestamp TEXT,
            FOREIGN KEY (conversation_id) REFERENCES conversations(id)
        )
    """)

    conn.commit()
    conn.close()
    logger.info("✅ Core tables (conversations & feedback) initialized.")

    # 🔽 Appel automatique des tables admin
    init_admin_tables()
    logger.info(f"✅ Database fully initialized: {DB_PATH}")


# =========================================================
# 📝 CONVERSATIONS & SESSIONS
# =========================================================
import uuid

def create_session(user_role: str, language: str, urgency: Any) -> str:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    session_id = str(uuid.uuid4())
    timestamp = datetime.now().isoformat()
    
    urgency_level = "Normal"
    urgency_type = None
    
    if urgency:
        if isinstance(urgency, dict):
            urgency_level = str(urgency.get("level", "Normal"))
            urgency_type = urgency.get("type")
            if urgency_type: urgency_type = str(urgency_type)
        elif isinstance(urgency, str):
            urgency_level = urgency
        else:
            urgency_level = str(urgency)
            
    cursor.execute("""
        INSERT INTO sessions (id, timestamp, user_role, language, urgency_level, urgency_type)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (session_id, timestamp, str(user_role), str(language), urgency_level, urgency_type))
    
    conn.commit()
    conn.close()
    return session_id


def add_message(session_id: str, role: str, content: str) -> int:
    """Ajoute un message à une session (role = 'user' ou 'assistant')"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    timestamp = datetime.now().isoformat()
    
    cursor.execute("""
        INSERT INTO messages (session_id, role, content, timestamp)
        VALUES (?, ?, ?, ?)
    """, (session_id, role, content, timestamp))
    
    msg_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return msg_id


def get_session_messages(session_id: str) -> List[Dict]:
    """Récupère l'historique des messages pour une session"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM messages WHERE session_id = ? ORDER BY timestamp ASC", (session_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_session(session_id: str) -> Optional[Dict]:
    """Récupérer une session spécifique"""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM sessions WHERE id = ?", (session_id,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None
    except Exception as e:
        logger.error(f"❌ Database error: {e}")
        return None


# =========================================================
# 📊 ADMIN & ANALYTICS
# =========================================================
def get_prompt(role: str) -> str:
    """Récupère le prompt système pour un rôle donné"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT system_prompt FROM prompts WHERE role = ?", (role,))
    res = cursor.fetchone()
    conn.close()
    return res[0] if res else ""


def save_prompt(role: str, prompt: str):
    """Sauvegarde ou met à jour un prompt système"""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("INSERT OR REPLACE INTO prompts (role, system_prompt) VALUES (?, ?)", (role, prompt))
    conn.commit()
    conn.close()


def get_analytics() -> dict:
    """Retourne les statistiques globales des sessions/messages"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    total = cursor.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
    by_role = dict(cursor.execute("SELECT user_role, COUNT(*) FROM sessions GROUP BY user_role").fetchall())
    by_lang = dict(cursor.execute("SELECT language, COUNT(*) FROM sessions GROUP BY language").fetchall())
    by_urgency = dict(cursor.execute("SELECT urgency_level, COUNT(*) FROM sessions GROUP BY urgency_level").fetchall())
    
    conn.close()
    return {
        "total": total,
        "by_role": by_role,
        "by_lang": by_lang,
        "by_urgency": by_urgency
    }


def get_all_sessions(limit: int = 50) -> List[Dict]:
    """Liste les dernières sessions"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM sessions ORDER BY timestamp DESC LIMIT ?", (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_session(session_id: str):
    """Supprime une session et ses messages en cascade"""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
    conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
    conn.commit()
    conn.close()


def update_message(message_id: int, new_content: str):
    """Met à jour le contenu d'un message spécifique"""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("UPDATE messages SET content = ? WHERE id = ?", (new_content, message_id))
    conn.commit()
    conn.close()


def delete_message(message_id: int):
    """Supprime un message spécifique"""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("DELETE FROM messages WHERE id = ?", (message_id,))
    conn.commit()
    conn.close()


# =========================================================
# 📚 RAG CHUNKS MANAGEMENT (Admin)
# =========================================================
def get_all_chunks() -> List[Dict]:
    """Récupère tous les chunks stockés en DB"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM rag_chunks ORDER BY id DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def add_chunk(doc_id: str, title: str, content: str, tags: str = "") -> int:
    """Ajoute un chunk manuellement ou via upload"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO rag_chunks (doc_id, title, content, tags) VALUES (?, ?, ?, ?)", 
                   (doc_id, title, content, tags))
    cid = cursor.lastrowid
    conn.commit()
    conn.close()
    return cid


def update_chunk(cid: int, title: str, content: str, tags: str):
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "UPDATE rag_chunks SET title = ?, content = ?, tags = ? WHERE id = ?",
        (title, content, tags, cid)
    )
    conn.commit()
    conn.close()


def delete_chunk(cid: int):
    """Supprime un chunk"""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("DELETE FROM rag_chunks WHERE id = ?", (cid,))
    conn.commit()
    conn.close()