# admin_routes.py - Admin routes (CSRF, bcrypt password, async LLM)

import asyncio
import logging
import os
import re
import uuid
from datetime import datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path

import docx
import nltk
import PyPDF2
from fastapi import APIRouter, Cookie, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from jose import JWTError, jwt
from nltk.tokenize import sent_tokenize

import database
from admin_security import (
    CSRF_COOKIE_ADMIN,
    CSRF_COOKIE_LOGIN,
    ensure_admin_csrf,
    new_login_csrf,
    verify_admin_csrf,
    verify_admin_password,
    verify_login_csrf,
)
from cache import cache
from config import get_settings
from llm_client import translate_to_english_async
from rag_engine_v2 import reload_rag_kb
from rate_limit import limiter

logger = logging.getLogger(__name__)

nltk.download("punkt", quiet=True)
nltk.download("punkt_tab", quiet=True)

router = APIRouter()
templates = Jinja2Templates(directory="templates")


def _tctx(request: Request, **kwargs):
    return {
        **kwargs,
        "csrf_token": getattr(request.state, "admin_csrf_token", "") or "",
    }


async def require_admin(request: Request, admin_token: str | None = Cookie(default=None)):
    settings = get_settings()
    if not admin_token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = jwt.decode(admin_token, settings.jwt_secret, algorithms=["HS256"])
        if payload.get("role") != "admin":
            raise HTTPException(status_code=403, detail="Access denied")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
    ensure_admin_csrf(request)
    return True


def clean_text(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"\s+", " ", text)
    text = text.replace("\n", " ").replace("\r", " ")
    return text.strip()


# ==========================================
# 📊 DASHBOARD
# ==========================================
@router.get("/admin", response_class=HTMLResponse)
async def admin_dashboard(request: Request, _=Depends(require_admin)):
    analytics = database.get_analytics()
    top_role = "-"
    roles = analytics.get("by_role", {})
    if roles:
        top_role = max(roles, key=roles.get).capitalize()
    top_lang = "-"
    langs = analytics.get("by_lang", {})
    if langs:
        top_lang = max(langs, key=langs.get)

    return templates.TemplateResponse(
        request,
        "admin/dashboard.html",
        _tctx(
            request,
            analytics=analytics,
            top_role=top_role,
            top_lang=top_lang,
        ),
    )


@router.get("/admin/cache", response_class=HTMLResponse)
async def cache_manager(request: Request, _=Depends(require_admin)):
    redis_status = "Connected" if cache.redis else "Disconnected"
    redis_info = {}
    if cache.redis:
        try:
            info = await cache.redis.info()
            redis_info = {
                "version": info.get("redis_version"),
                "memory": info.get("used_memory_human"),
                "key_count": await cache.redis.dbsize(),
                "uptime": info.get("uptime_in_seconds"),
                "clients": info.get("connected_clients"),
            }
        except Exception:
            redis_status = "Error"

    return templates.TemplateResponse(
        request,
        "admin/cache.html",
        _tctx(request, cache={"status": redis_status, "info": redis_info}),
    )


@router.post("/admin/cache/clear")
async def clear_cache(
    request: Request,
    csrf_token: str = Form(...),
    _=Depends(require_admin),
):
    verify_admin_csrf(request, csrf_token)
    await cache.clear()
    return RedirectResponse("/admin/cache", status_code=302)


# ==========================================
# ⚙️ PROMPTS
# ==========================================
@router.get("/admin/prompts", response_class=HTMLResponse)
async def get_prompts(request: Request, _=Depends(require_admin)):
    prompts = {
        "guest": database.get_prompt("guest"),
        "owner": database.get_prompt("owner"),
        "concierge": database.get_prompt("concierge"),
    }
    return templates.TemplateResponse(request, "admin/prompts.html", _tctx(request, prompts=prompts))


@router.post("/admin/prompts", response_class=HTMLResponse)
async def save_prompts(
    request: Request,
    guest: str = Form(...),
    owner: str = Form(...),
    concierge: str = Form(...),
    csrf_token: str = Form(...),
    _=Depends(require_admin),
):
    verify_admin_csrf(request, csrf_token)
    database.save_prompt("guest", guest)
    database.save_prompt("owner", owner)
    database.save_prompt("concierge", concierge)
    return templates.TemplateResponse(
        request,
        "admin/prompts.html",
        _tctx(
            request,
            prompts={"guest": guest, "owner": owner, "concierge": concierge},
            msg="✅ Prompts sauvegardés avec succès!",
        ),
    )


# ==========================================
# 💬 CONVERSATIONS / SESSIONS
# ==========================================
@router.get("/admin/conversations", response_class=HTMLResponse)
async def list_conversations(request: Request, _=Depends(require_admin)):
    sessions = database.get_all_sessions()
    return templates.TemplateResponse(
        request, "admin/conversations.html", _tctx(request, sessions=sessions)
    )


@router.get("/admin/conversations/{session_id}", response_class=HTMLResponse)
async def view_session(request: Request, session_id: str, _=Depends(require_admin)):
    session = database.get_session(session_id)
    messages = database.get_session_messages(session_id)
    return templates.TemplateResponse(
        request,
        "admin/session_detail.html",
        _tctx(request, session=session, messages=messages),
    )


@router.post("/admin/conversations/delete")
async def delete_convo(
    request: Request,
    session_id: str = Form(...),
    csrf_token: str = Form(...),
    _=Depends(require_admin),
):
    verify_admin_csrf(request, csrf_token)
    database.delete_session(session_id)
    return {"status": "ok"}


@router.post("/admin/messages/edit")
async def edit_message(
    request: Request,
    msg_id: int = Form(...),
    content: str = Form(...),
    csrf_token: str = Form(...),
    _=Depends(require_admin),
):
    verify_admin_csrf(request, csrf_token)
    database.update_message(msg_id, content)
    return {"status": "ok"}


@router.get("/admin/login", response_class=HTMLResponse)
async def login_page(request: Request):
    settings = get_settings()
    token = new_login_csrf()
    resp = templates.TemplateResponse(
        request, "admin/login.html", {"csrf_token": token}
    )
    resp.set_cookie(
        CSRF_COOKIE_LOGIN,
        token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        max_age=600,
        path="/admin",
    )
    return resp


@router.post("/admin/login")
@limiter.limit("10/minute")
async def admin_login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    csrf_token: str = Form(...),
):
    verify_login_csrf(request, csrf_token)
    settings = get_settings()
    if username != settings.admin_user or not verify_admin_password(password, settings):
        return {"error": "wrong credentials"}

    token = jwt.encode(
        {"role": "admin", "exp": datetime.now(timezone.utc) + timedelta(hours=8)},
        settings.jwt_secret,
        algorithm="HS256",
    )
    admin_csrf = new_login_csrf()

    response = RedirectResponse("/admin", status_code=302)
    response.set_cookie(
        "admin_token",
        token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        max_age=86400,
        path="/admin",
    )
    response.set_cookie(
        CSRF_COOKIE_ADMIN,
        admin_csrf,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        max_age=86400,
        path="/admin",
    )
    response.delete_cookie(CSRF_COOKIE_LOGIN, path="/admin")
    return response


# ==========================================
# 📚 RAG CHUNKS
# ==========================================
@router.get("/admin/rag", response_class=HTMLResponse)
async def rag_manager(request: Request, _=Depends(require_admin)):
    chunks = database.get_all_chunks()
    return templates.TemplateResponse(request, "admin/rag.html", _tctx(request, chunks=chunks))


@router.post("/admin/rag/add_chunk")
async def add_chunk_manual(
    request: Request,
    doc_id: str = Form("manual"),
    title: str = Form("..."),
    content: str = Form(...),
    tags: str = Form(""),
    csrf_token: str = Form(...),
    _=Depends(require_admin),
):
    verify_admin_csrf(request, csrf_token)
    cleaned = clean_text(content)
    translated = await translate_to_english_async(cleaned)
    cid = database.add_chunk(doc_id, title, translated, tags + ",en")
    await asyncio.to_thread(reload_rag_kb)
    return {"status": "ok", "id": cid}


@router.post("/admin/rag/delete_chunk")
async def delete_chunk_manual(
    request: Request,
    cid: int = Form(...),
    csrf_token: str = Form(...),
    _=Depends(require_admin),
):
    verify_admin_csrf(request, csrf_token)
    database.delete_chunk(cid)
    await asyncio.to_thread(reload_rag_kb)
    return {"status": "ok"}


@router.post("/admin/rag/edit_chunk")
async def edit_chunk(
    request: Request,
    cid: int = Form(...),
    title: str = Form(...),
    content: str = Form(...),
    tags: str = Form(""),
    csrf_token: str = Form(...),
    _=Depends(require_admin),
):
    verify_admin_csrf(request, csrf_token)
    cleaned = clean_text(content)
    translated = await translate_to_english_async(cleaned)
    database.update_chunk(cid, title, translated, tags + ",en")
    await asyncio.to_thread(reload_rag_kb)
    return {"status": "ok"}


@router.post("/admin/rag/upload")
async def upload_doc(
    request: Request,
    file: UploadFile = File(...),
    csrf_token: str = Form(...),
    _=Depends(require_admin),
):
    verify_admin_csrf(request, csrf_token)
    MAX_UPLOAD_SIZE = 10 * 1024 * 1024
    allowed_extensions = {".txt", ".md", ".pdf", ".doc", ".docx"}
    file_ext = Path(file.filename or "").suffix.lower()

    if not file_ext or file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail="Fichiers acceptés: .txt, .md, .pdf, .doc, .docx",
        )

    content = ""

    try:
        file_data = await file.read()
        if len(file_data) > MAX_UPLOAD_SIZE:
            raise HTTPException(status_code=413, detail="File too large (max 10MB)")

        if file_ext == ".pdf":
            pdf_reader = PyPDF2.PdfReader(BytesIO(file_data))
            for page in pdf_reader.pages:
                content += page.extract_text() + "\n"
        elif file_ext in [".doc", ".docx"]:
            doc = docx.Document(BytesIO(file_data))
            for paragraph in doc.paragraphs:
                content += paragraph.text + "\n"
        else:
            content = file_data.decode("utf-8")

        cleaned = clean_text(content)
        translated_full = await translate_to_english_async(cleaned)
        sentences = sent_tokenize(translated_full)
        doc_id = f"upload_{uuid.uuid4().hex[:6]}"
        chunks_added = 0

        for sent in sentences:
            clean = sent.strip()
            if len(clean) > 10:
                database.add_chunk(
                    doc_id=doc_id,
                    title=file.filename.replace(file_ext, ""),
                    content=clean,
                    tags=f"auto,{file_ext.replace('.', '')},en",
                )
                chunks_added += 1

        await asyncio.to_thread(reload_rag_kb)
        return {
            "status": "ok",
            "chunks_added": chunks_added,
            "filename": file.filename,
        }

    except HTTPException:
        raise
    except Exception:
        logger.exception("RAG upload failed")
        if get_settings().is_production():
            raise HTTPException(
                status_code=500, detail="Erreur de traitement du fichier"
            ) from None
        raise HTTPException(
            status_code=500, detail="Erreur de lecture du fichier"
        ) from None
