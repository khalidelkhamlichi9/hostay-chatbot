# auth.py

import logging

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from config import get_settings

logger = logging.getLogger(__name__)

security = HTTPBearer()
ALGORITHM = "HS256"


def decode_jwt(token: str):
    settings = get_settings()
    options = {
        "verify_signature": True,
        "verify_exp": True,
        "verify_aud": bool(settings.jwt_audience),
        "verify_iss": bool(settings.jwt_issuer),
        "verify_sub": False,
    }
    decode_kw: dict = {
        "algorithms": [ALGORITHM],
        "options": options,
    }
    if settings.jwt_audience:
        decode_kw["audience"] = settings.jwt_audience
    if settings.jwt_issuer:
        decode_kw["issuer"] = settings.jwt_issuer

    try:
        payload = jwt.decode(token, settings.jwt_secret, **decode_kw)
        return {
            "user_hashId": payload.get("user_hashId"),
            "role": payload.get("role"),
            "reservation_hashId": payload.get("reservation_hashId"),
        }
    except JWTError as e:
        logger.error("JWT decode error: %s", e)
        return None


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    payload = decode_jwt(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")
    payload["token"] = token
    return payload
