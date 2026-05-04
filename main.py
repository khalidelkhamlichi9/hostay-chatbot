# main.py - Hostay Chatbot (Clean Architecture)

import os
import logging
from dotenv import load_dotenv

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s'
)
logger = logging.getLogger(__name__)

from fastapi import FastAPI, Depends, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from contextlib import asynccontextmanager

import jwt

import database
from auth import get_current_user
from chatbot import get_answer
from admin_routes import router as admin_router
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

# Load env
load_dotenv()

# =========================
# APP & INIT DB
# =========================
@asynccontextmanager
async def lifespan(app: FastAPI):
    database.init_db()
    logger.info("✅ Database initialized")
    yield

limiter = Limiter(key_func=get_remote_address)
app = FastAPI(lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.router.redirect_slashes = False

# Templates & Static
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

# Secret
SECRET = os.getenv("JWT_SECRET")
if not SECRET:
    raise RuntimeError("Missing JWT_SECRET — server cannot start")


from typing import Optional

# =========================
# MODELS
# =========================
class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None


# =========================
# ADMIN ROUTER
# =========================
app.include_router(admin_router)


# =========================
# FAVICON
# =========================
@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return RedirectResponse(
        url="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>🤖</text></svg>"
    )


# =========================
# MAIN CHAT API (JWT PROTECTED)
# =========================
@app.post("/chat")
@limiter.limit("20/minute")
async def chat(request: Request, req: ChatRequest, user=Depends(get_current_user)):
    """
    Secure chatbot endpoint with JWT user context
    """
    result = await get_answer(req.message, user["role"], req.session_id, user.get("token"))

    return {
        "user": user,
        "reply": result["reply"],
        "saved": result.get("saved", False),
        "session_id": result.get("session_id")
    }


# =========================
# FRONTEND PAGE
# =========================
@app.get("/", response_class=HTMLResponse)
async def chat_page(request: Request):
    return templates.TemplateResponse("chat.html", {
        "request": request,
        "title": "Hostay Chatbot"
    })