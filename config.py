"""Centralised settings (validated at startup)."""

import logging
import os
import secrets
from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

_JWT_SECRET_FILENAME = ".jwt_secret"


def _jwt_secret_data_dir(chatbot_db_path: str | None) -> Path:
    if chatbot_db_path:
        return Path(chatbot_db_path).resolve().parent
    default_db = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hostay_chatbot.db")
    return Path(default_db).resolve().parent


def _resolve_jwt_secret(raw: str, data_dir: Path) -> str:
    if raw and raw.strip():
        return raw.strip()

    secret_file = data_dir / _JWT_SECRET_FILENAME
    if secret_file.is_file():
        stored = secret_file.read_text(encoding="utf-8").strip()
        if len(stored) >= 24:
            return stored

    generated = secrets.token_urlsafe(32)
    data_dir.mkdir(parents=True, exist_ok=True)
    secret_file.write_text(generated, encoding="utf-8")
    try:
        secret_file.chmod(0o600)
    except OSError:
        pass
    logger.warning(
        "JWT_SECRET is empty; generated a persistent secret at %s. "
        "Set JWT_SECRET in your env file to use your own value.",
        secret_file,
    )
    return generated


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    environment: str = Field(default="production", alias="ENVIRONMENT")

    jwt_secret: str = Field(default="", alias="JWT_SECRET")
    jwt_issuer: str | None = Field(default=None, alias="JWT_ISSUER")
    jwt_audience: str | None = Field(default=None, alias="JWT_AUDIENCE")

    admin_user: str = Field(..., alias="ADMIN_USER")
    admin_pass: str | None = Field(default=None, alias="ADMIN_PASS")
    admin_pass_hash: str | None = Field(default=None, alias="ADMIN_PASS_HASH")

    deepseek_api_key: str = Field(default="", alias="DEEPSEEK_API_KEY")
    deepseek_api_url: str = Field(
        default="https://api.deepseek.com/chat/completions",
        alias="DEEPSEEK_API_URL",
    )
    deepseek_model: str = Field(default="deepseek-chat", alias="DEEPSEEK_MODEL")

    hostay_backend_url: str = Field(
        default="https://api.hostayapp.com",
        alias="HOSTAY_BACKEND_URL",
    )

    chatbot_db_path: str | None = Field(default=None, alias="CHATBOT_DB_PATH")

    redis_host: str = Field(default="localhost", alias="REDIS_HOST")
    redis_port: int = Field(default=6379, alias="REDIS_PORT")
    redis_db: int = Field(default=0, alias="REDIS_DB")
    redis_password: str | None = Field(default=None, alias="REDIS_PASSWORD")
    redis_ssl: bool = Field(default=False, alias="REDIS_SSL")

    cookie_secure: bool = Field(default=False, alias="COOKIE_SECURE")
    cors_extra_origins: str = Field(default="", alias="CORS_EXTRA_ORIGINS")
    trusted_hosts: str = Field(default="", alias="TRUSTED_HOSTS")
    enable_openapi: bool = Field(default=False, alias="ENABLE_OPENAPI")

    @field_validator("cookie_secure", "redis_ssl", "enable_openapi", mode="before")
    @classmethod
    def _coerce_bool(cls, v):
        if isinstance(v, bool):
            return v
        if v is None:
            return False
        return str(v).lower() in ("1", "true", "yes", "on")

    @field_validator("admin_pass", "admin_pass_hash", mode="before")
    @classmethod
    def _empty_str_to_none(cls, v):
        if v is None:
            return None
        if isinstance(v, str) and not v.strip():
            return None
        return v

    @model_validator(mode="after")
    def _production_rules(self) -> "Settings":
        data_dir = _jwt_secret_data_dir(self.chatbot_db_path)
        resolved = _resolve_jwt_secret(self.jwt_secret, data_dir)
        object.__setattr__(self, "jwt_secret", resolved)

        is_prod = self.environment.lower() in ("production", "prod")
        if is_prod and len(self.jwt_secret) < 24:
            raise ValueError("JWT_SECRET must be at least 24 characters in production")
        if not self.admin_pass:
            raise ValueError("Set ADMIN_PASS in your env file")
        return self

    def is_production(self) -> bool:
        return self.environment.lower() in ("production", "prod")


@lru_cache
def get_settings() -> Settings:
    return Settings()
