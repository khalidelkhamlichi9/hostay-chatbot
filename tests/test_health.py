"""Smoke tests — set env before any app imports (DB_PATH is read at import time)."""

import os
import tempfile

_fd, _db_path = tempfile.mkstemp(suffix=".db")
os.close(_fd)
os.environ["CHATBOT_DB_PATH"] = _db_path
os.environ["ENVIRONMENT"] = "development"
os.environ["JWT_SECRET"] = "012345678901234567890123456"
os.environ["ADMIN_USER"] = "testadmin"
os.environ["ADMIN_PASS"] = "testpass"
os.environ["DEEPSEEK_API_KEY"] = ""
os.environ["SKIP_RAG_INIT"] = "1"

from config import get_settings  # noqa: E402

get_settings.cache_clear()

from fastapi.testclient import TestClient  # noqa: E402

from main import app  # noqa: E402


def test_live():
    client = TestClient(app)
    r = client.get("/live")
    assert r.status_code == 200
    assert r.json().get("status") == "live"


def test_health():
    client = TestClient(app)
    r = client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data.get("database") is True


def test_chat_requires_auth():
    client = TestClient(app)
    r = client.post("/chat", json={"message": "hello"})
    assert r.status_code in (401, 403)
