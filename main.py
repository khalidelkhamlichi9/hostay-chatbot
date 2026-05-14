# main.py - Hostay Chatbot (Clean Architecture)

import logging
import os
from typing import Optional

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger(__name__)

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Form, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

import database
from admin_security import CSRF_COOKIE_ADMIN
from admin_routes import router as admin_router
from auth import get_current_user
from cache import cache
from chatbot import get_answer
from config import get_settings
from rate_limit import limiter
from rag_engine_v2 import init_rag_kb
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        return response


class AttachAdminCSRFCookieMiddleware(BaseHTTPMiddleware):
    """Sets admin CSRF cookie when require_admin created a new token."""

    async def dispatch(self, request, call_next):
        response = await call_next(request)
        if getattr(request.state, "admin_set_csrf_cookie", False):
            s = get_settings()
            response.set_cookie(
                CSRF_COOKIE_ADMIN,
                request.state.admin_csrf_token,
                httponly=True,
                secure=s.cookie_secure,
                samesite="lax",
                max_age=86400,
                path="/admin",
            )
        return response


@asynccontextmanager
async def lifespan(app: FastAPI):
    get_settings()
    database.init_db()
    logger.info("Database initialized")
    if os.getenv("SKIP_RAG_INIT", "").lower() not in ("1", "true", "yes"):
        init_rag_kb()
        logger.info("RAG knowledge base initialized")
    else:
        logger.info("SKIP_RAG_INIT set — skipping RAG KB load")
    await cache.connect()
    try:
        yield
    finally:
        await cache.close()
        logger.info("Shutdown complete")


s = get_settings()
app = FastAPI(
    lifespan=lifespan,
    docs_url="/docs" if s.enable_openapi else None,
    redoc_url="/redoc" if s.enable_openapi else None,
    openapi_url="/openapi.json" if s.enable_openapi else None,
)

_origins = [
    "https://hostayapp.com",
    "https://m4.hostayapp.com",
]
if s.cors_extra_origins.strip():
    _origins.extend([o.strip() for o in s.cors_extra_origins.split(",") if o.strip()])

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_origin_regex=r"https://.*\.hostayapp\.com",
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept"],
)

if s.trusted_hosts.strip():
    _hosts = [h.strip() for h in s.trusted_hosts.split(",") if h.strip()]
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=_hosts)

app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(AttachAdminCSRFCookieMiddleware)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.router.redirect_slashes = False

templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    session_id: Optional[str] = None


app.include_router(admin_router)


@app.get("/live", include_in_schema=False)
async def live():
    return JSONResponse({"status": "live"})


@app.get("/health", include_in_schema=False)
@app.get("/ready", include_in_schema=False)
async def health():
    db_ok = False
    try:
        conn = database.connect_db(timeout=2.0)
        conn.execute("SELECT 1")
        conn.close()
        db_ok = True
    except Exception as e:
        logger.warning("health: database check failed: %s", e)

    redis_ok = False
    if cache.redis is not None:
        try:
            await cache.redis.ping()
            redis_ok = True
        except Exception as e:
            logger.warning("health: redis ping failed: %s", e)

    if not db_ok:
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "database": False,
                "redis": redis_ok,
            },
        )
    return JSONResponse(
        status_code=200,
        content={
            "status": "ok",
            "database": True,
            "redis": redis_ok,
        },
    )


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return RedirectResponse(
        url="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>🤖</text></svg>"
    )


@app.post("/chat")
@limiter.limit("20/minute")
async def chat(request: Request, req: ChatRequest, user=Depends(get_current_user)):
    result = await get_answer(req.message, user["role"], req.session_id, user.get("token"))
    return {
        "user": user,
        "reply": result["reply"],
        "saved": result.get("saved", False),
        "session_id": result.get("session_id"),
    }


@app.post("/chat-form", response_class=HTMLResponse)
@limiter.limit("20/minute")
async def chat_form(
    request: Request,
    message: str = Form(...),
    role: str = Form("guest"),
    session_id: Optional[str] = Form(default=None),
):
    result = await get_answer(message, role, session_id or None, token=None)
    return templates.TemplateResponse(
        request,
        "chat.html",
        {
            "title": "Hostay Chatbot",
            "message": message,
            "reply": result["reply"],
            "session_id": result.get("session_id"),
            "language": result.get("language", ""),
            "role": role,
        },
    )


@app.get("/", response_class=HTMLResponse)
async def chat_page(request: Request):
    return templates.TemplateResponse(
        request,
        "chat.html",
        {"title": "Hostay Chatbot"},
    )
