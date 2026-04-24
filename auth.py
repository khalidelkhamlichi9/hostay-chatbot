# auth.py

from jose import jwt, JWTError
from fastapi import Header, HTTPException
import os

SECRET_KEY = os.getenv("JWT_SECRET", "secret")
ALGORITHM = "HS256"


# -----------------------------
# 🔓 Decode JWT only
# -----------------------------
def decode_jwt(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])

        return {
            "user_hashId": payload.get("user_hashId"),
            "role": payload.get("role"),
            "reservation_hashId": payload.get("reservation_hashId")
        }

    except JWTError:
        return None


# -----------------------------
# 🔐 FastAPI dependency
# -----------------------------
def get_current_user(authorization: str = Header(None)):
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing token")

    # Remove "Bearer "
    token = authorization.replace("Bearer ", "")

    payload = decode_jwt(token)

    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")

    return payload