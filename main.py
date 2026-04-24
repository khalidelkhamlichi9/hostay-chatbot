# main.py - Hostay Chatbot (Clean Architecture)

import os
from dotenv import load_dotenv

from fastapi import FastAPI, Depends, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

import jwt

import database
from auth import get_current_user
from chatbot import get_answer
from admin_routes import router as admin_router

# Load env
load_dotenv()

# App
app = FastAPI()
app.router.redirect_slashes = False

# Templates & Static
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

# Secret
SECRET = os.getenv("JWT_SECRET", "MYSECRET")

# =========================
# INIT DB
# =========================
@app.on_event("startup")
async def startup_event():
    database.init_db()
    print("✅ Database initialized")


# =========================
# MODELS
# =========================
class ChatRequest(BaseModel):
    message: str


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
# AUTH - DEMO LOGIN
# =========================
@app.post("/login")
def login():
    user = {
        "user_hashId": "demo_123",
        "role": "guest",
        "reservation_hashId": "res_456"
    }

    token = jwt.encode(user, SECRET, algorithm="HS256")

    return {"access_token": token}


# =========================
# MAIN CHAT API (JWT PROTECTED)
# =========================
@app.post("/chat")
def chat(req: ChatRequest, user=Depends(get_current_user)):
    """
    Secure chatbot endpoint with JWT user context
    """

    result = get_answer(req.message, user["role"])

    return {
        "user": user,
        "reply": result["reply"],
        "saved": result.get("saved", False),
        "conversation_id": result.get("conversation_id", -1)
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


# =========================
# FORM CHAT (NO POSTMAN)
# =========================
@app.post("/chat-form", response_class=HTMLResponse)
async def chat_form(
    request: Request,
    message: str = Form(...),
    role: str = Form("guest")
):
    """
    Simple HTML testing endpoint
    """

    user = {
        "user_hashId": "demo_123",
        "role": role,
        "reservation_hashId": "res_456"
    }

    result = get_answer(message, role)

    return templates.TemplateResponse("chat.html", {
        "request": request,
        "title": "Hostay Chatbot",
        "message": message,
        "reply": result["reply"],
        "language": result.get("language", "en"),
        "conversation_id": result.get("conversation_id", -1),
        "role": role
    })