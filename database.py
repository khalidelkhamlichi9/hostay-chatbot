# database.py - Gestion SQLite complète (Conversations + Admin + RAG Chunks)
import sqlite3
import os
from datetime import datetime
from typing import List, Dict, Optional, Any

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
    print("✅ Admin tables (prompts & rag_chunks) initialized.")


def init_db():
    """Créer toutes les tables et initialiser la base de données"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 1️⃣ Table Conversations
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
    print("✅ Core tables (conversations & feedback) initialized.")

    # 🔽 Appel automatique des tables admin
    init_admin_tables()
    print(f"✅ Database fully initialized: {DB_PATH}")


# =========================================================
# 📝 CONVERSATIONS
# =========================================================
def save_conversation(user_role: str, message: str, reply: str, 
                     language: str, urgency: Any) -> int:
    """Sauvegarde une conversation (gère dict, str, ou None pour urgency)"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
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
            INSERT INTO conversations (timestamp, user_role, message, reply, language, urgency_level, urgency_type)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (timestamp, str(user_role), str(message), str(reply), str(language), urgency_level, urgency_type))
        
        conversation_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        print(f"✅ Saved conversation ID: {conversation_id}")
        return conversation_id
        
    except Exception as e:
        print(f"❌ Database error: {e}")
        import traceback
        print(traceback.format_exc())
        return -1


def get_conversation_by_id(conv_id: int) -> Optional[Dict]:
    """Récupérer une conversation spécifique"""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM conversations WHERE id = ?", (conv_id,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None
    except Exception as e:
        print(f"❌ Database error: {e}")
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
    """Retourne les statistiques globales des conversations"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    total = cursor.execute("SELECT COUNT(*) FROM conversations").fetchone()[0]
    by_role = dict(cursor.execute("SELECT user_role, COUNT(*) FROM conversations GROUP BY user_role").fetchall())
    by_lang = dict(cursor.execute("SELECT language, COUNT(*) FROM conversations GROUP BY language").fetchall())
    by_urgency = dict(cursor.execute("SELECT urgency_level, COUNT(*) FROM conversations GROUP BY urgency_level").fetchall())
    
    conn.close()
    return {
        "total": total,
        "by_role": by_role,
        "by_lang": by_lang,
        "by_urgency": by_urgency
    }


def get_all_conversations(limit: int = 50) -> List[Dict]:
    """Liste les dernières conversations"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM conversations ORDER BY timestamp DESC LIMIT ?", (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_conversation(conv_id: int):
    """Supprime une conversation"""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("DELETE FROM conversations WHERE id = ?", (conv_id,))
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