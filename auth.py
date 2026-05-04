# auth.py

from jose import jwt, JWTError
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import os
from dotenv import load_dotenv

load_dotenv()
SECRET_KEY = os.getenv("JWT_SECRET", "secret")
ALGORITHM = "HS256"


# -----------------------------
# 🔓 Decode JWT only
# -----------------------------
def decode_jwt(token: str):
    try:
        options = {
            "verify_aud": False,
            "verify_iss": False,
            "verify_sub": False
        }
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM], options=options)

        return {
            "user_hashId": payload.get("user_hashId"),
            "role": payload.get("role"),
            "reservation_hashId": payload.get("reservation_hashId")
        }

    except JWTError as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"JWT Decode Error: {e}")
        return None


# -----------------------------
# 🔐 FastAPI dependency
# -----------------------------
security = HTTPBearer()

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials

    payload = decode_jwt(token)

    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")

    payload["token"] = token
    return payload