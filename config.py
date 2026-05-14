"""Centralised settings (validated at startup)."""

from functools import lru_cache

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    environment: str = Field(default="production", alias="ENVIRONMENT")

    jwt_secret: str = Field(..., alias="JWT_SECRET")
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

    @field_validator("jwt_secret")
    @classmethod
    def _jwt_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("JWT_SECRET is required")
        return v

    @model_validator(mode="after")
    def _production_rules(self) -> "Settings":
        env = self.environment.lower()
        is_prod = env in ("production", "prod")
        if is_prod and len(self.jwt_secret) < 24:
            raise ValueError("JWT_SECRET must be at least 24 characters in production")
        if not self.admin_pass_hash and not self.admin_pass:
            raise ValueError("Set ADMIN_PASS_HASH (bcrypt) or ADMIN_PASS (development only)")
        if is_prod and not self.admin_pass_hash:
            raise ValueError(
                "Production requires ADMIN_PASS_HASH (bcrypt). "
                "Generate a hash in Python: from passlib.hash import bcrypt; print(bcrypt.hash('YOUR_PASSWORD'))"
            )
        return self

    def is_production(self) -> bool:
        return self.environment.lower() in ("production", "prod")


@lru_cache
def get_settings() -> Settings:
    return Settings()
