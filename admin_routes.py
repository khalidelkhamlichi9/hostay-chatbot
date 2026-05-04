# admin_routes.py - Routes Admin pour Hostay Chatbot
from fastapi import APIRouter, Request, Form, UploadFile, File, HTTPException, Cookie, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import database
import uuid
import PyPDF2
import docx
from io import BytesIO
import nltk
from nltk.tokenize import sent_tokenize
from llm_client import translate_to_english
import re
from jose import jwt, JWTError
from fastapi.responses import RedirectResponse

# Télécharger les données NLTK si nécessaires
nltk.download('punkt', quiet=True)
nltk.download('punkt_tab', quiet=True)

router = APIRouter()
templates = Jinja2Templates(directory="templates")

import os

ADMIN_USER = os.getenv("ADMIN_USER")
ADMIN_PASS = os.getenv("ADMIN_PASS")
SECRET = os.getenv("JWT_SECRET")

if not all([ADMIN_USER, ADMIN_PASS, SECRET]):
    raise RuntimeError("Missing ADMIN_USER, ADMIN_PASS, JWT_SECRET variables")

def require_admin(admin_token: str = Cookie(default=None)):
    if not admin_token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = jwt.decode(admin_token, SECRET, algorithms=["HS256"])
        if payload.get("role") != "admin":
            raise HTTPException(status_code=403, detail="Access denied")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
# ==========================================
# 🧹 PREPROCESSING
# ==========================================
def clean_text(text: str) -> str:
    """
    Nettoyage du texte avant traduction
    """
    if not text:
        return ""

    text = re.sub(r'\s+', ' ', text)  # espaces multiples
    text = text.replace('\n', ' ').replace('\r', ' ')
    
    return text.strip()

# ==========================================
# 📊 DASHBOARD
# ==========================================
@router.get("/admin", response_class=HTMLResponse)
async def admin_dashboard(request: Request, _=Depends(require_admin)):
    analytics = database.get_analytics()
    return templates.TemplateResponse("admin/dashboard.html", {"request": request, "analytics": analytics})

# ==========================================
# ⚙️ PROMPTS
# ==========================================
@router.get("/admin/prompts", response_class=HTMLResponse)
async def get_prompts(request: Request, _=Depends(require_admin)):
    prompts = {
        "guest": database.get_prompt("guest"),
        "owner": database.get_prompt("owner"),
        "concierge": database.get_prompt("concierge")
    }
    return templates.TemplateResponse("admin/prompts.html", {"request": request, "prompts": prompts})

@router.post("/admin/prompts", response_class=HTMLResponse)
async def save_prompts(request: Request,
                       guest: str = Form(...),
                       owner: str = Form(...),
                       concierge: str = Form(...),
                       _=Depends(require_admin)):
    database.save_prompt("guest", guest)
    database.save_prompt("owner", owner)
    database.save_prompt("concierge", concierge)
    return templates.TemplateResponse("admin/prompts.html", {
        "request": request,
        "prompts": {"guest": guest, "owner": owner, "concierge": concierge},
        "msg": "✅ Prompts sauvegardés avec succès!"
    })

# ==========================================
# 💬 CONVERSATIONS / SESSIONS
# ==========================================
@router.get("/admin/conversations", response_class=HTMLResponse)
async def list_conversations(request: Request, _=Depends(require_admin)):
    sessions = database.get_all_sessions()
    return templates.TemplateResponse("admin/conversations.html", {"request": request, "sessions": sessions})

@router.get("/admin/conversations/{session_id}", response_class=HTMLResponse)
async def view_session(request: Request, session_id: str, _=Depends(require_admin)):
    session = database.get_session(session_id)
    messages = database.get_session_messages(session_id)
    return templates.TemplateResponse("admin/session_detail.html", {
        "request": request, 
        "session": session, 
        "messages": messages
    })

@router.post("/admin/conversations/delete")
async def delete_convo(session_id: str = Form(...), _=Depends(require_admin)):
    database.delete_session(session_id)
    return {"status": "ok"}

@router.post("/admin/messages/edit")
async def edit_message(msg_id: int = Form(...), content: str = Form(...), _=Depends(require_admin)):
    database.update_message(msg_id, content)
    return {"status": "ok"}
@router.get("/admin/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("admin/login.html", {
        "request": request
    })


@router.post("/admin/login")
async def admin_login(
    username: str = Form(...),
    password: str = Form(...)
):
    if username != ADMIN_USER or password != ADMIN_PASS:
        return {"error": "wrong credentials"}

    token = jwt.encode({"role": "admin"}, SECRET, algorithm="HS256")

    response = RedirectResponse("/admin", status_code=302)
    response.set_cookie("admin_token", token, httponly=True)

    return response
# ==========================================
# 📚 RAG CHUNKS
# ==========================================
@router.get("/admin/rag", response_class=HTMLResponse)
async def rag_manager(request: Request, _=Depends(require_admin)):
    chunks = database.get_all_chunks()
    return templates.TemplateResponse("admin/rag.html", {"request": request, "chunks": chunks})

# ✅ AJOUT MANUEL AVEC CLEAN + TRADUCTION
@router.post("/admin/rag/add_chunk")
async def add_chunk_manual(
    doc_id: str = Form("manual"),
    title: str = Form("..."),
    content: str = Form(...),
    tags: str = Form(""),
    _=Depends(require_admin)
):
    cleaned = clean_text(content)
    translated = translate_to_english(cleaned)

    cid = database.add_chunk(
        doc_id,
        title,
        translated,
        tags + ",en"
    )

    return {"status": "ok", "id": cid}

@router.post("/admin/rag/delete_chunk")
async def delete_chunk_manual(cid: int = Form(...), _=Depends(require_admin)):
    database.delete_chunk(cid)
    return {"status": "ok"}

# ✅ EDIT AVEC CLEAN + TRADUCTION
@router.post("/admin/rag/edit_chunk")
async def edit_chunk(
    cid: int = Form(...),
    title: str = Form(...),
    content: str = Form(...),
    tags: str = Form(""),
    _=Depends(require_admin)
):
    cleaned = clean_text(content)
    translated = translate_to_english(cleaned)

    database.update_chunk(cid, title, translated, tags + ",en")
    return {"status": "ok"}

# ✅ UPLOAD COMPLET (CLEAN → TRANSLATE → TOKENIZE)
@router.post("/admin/rag/upload")
async def upload_doc(file: UploadFile = File(...), _=Depends(require_admin)):
    """Upload & Auto-Chunking (TXT, MD, PDF, DOCX)"""

    MAX_UPLOAD_SIZE = 10 * 1024 * 1024  # 10 MB
    allowed_extensions = ['.txt', '.md', '.pdf', '.doc', '.docx']
    file_ext = '.' + file.filename.split('.')[-1].lower()

    if file_ext not in allowed_extensions:
        raise HTTPException(status_code=400, detail="Fichiers acceptés: .txt, .md, .pdf, .doc, .docx")

    content = ""

    try:
        file_data = await file.read()
        if len(file_data) > MAX_UPLOAD_SIZE:
            raise HTTPException(status_code=413, detail="File too large (max 10MB)")

        # 1️⃣ Extraction
        if file_ext == '.pdf':
            pdf_reader = PyPDF2.PdfReader(BytesIO(file_data))
            for page in pdf_reader.pages:
                content += page.extract_text() + "\n"

        elif file_ext in ['.doc', '.docx']:
            doc = docx.Document(BytesIO(file_data))
            for paragraph in doc.paragraphs:
                content += paragraph.text + "\n"

        else:
            content = file_data.decode("utf-8")

        # 2️⃣ CLEAN
        cleaned = clean_text(content)

        # 3️⃣ TRANSLATE (1 seul appel 🔥)
        translated_full = translate_to_english(cleaned)

        # 4️⃣ TOKENIZE
        sentences = sent_tokenize(translated_full)

        doc_id = f"upload_{uuid.uuid4().hex[:6]}"
        chunks_added = 0

        for sent in sentences:
            clean = sent.strip()

            if len(clean) > 10:
                database.add_chunk(
                    doc_id=doc_id,
                    title=file.filename.replace(file_ext, ''),
                    content=clean,
                    tags=f"auto,{file_ext.replace('.','')},en"
                )
                chunks_added += 1

        return {
            "status": "ok",
            "chunks_added": chunks_added,
            "filename": file.filename
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur de lecture: {str(e)}")