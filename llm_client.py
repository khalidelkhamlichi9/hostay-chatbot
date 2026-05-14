# llm_client.py - DeepSeek LLM Client (httpx, retries, safe logging)

from __future__ import annotations

import asyncio
import logging
import random
from typing import Any

import httpx

from config import get_settings

logger = logging.getLogger(__name__)

_MAX_BODY_LOG = 120


def _safe_error_snippet(status: int, text: str, production: bool) -> str:
    if production:
        return f"status={status}"
    t = (text or "").replace("\n", " ")[:_MAX_BODY_LOG]
    return f"status={status} body_prefix={t!r}"


def get_deepseek_api_key() -> str:
    return get_settings().deepseek_api_key


def get_deepseek_headers(api_key: str | None = None) -> dict[str, str]:
    resolved = api_key or get_deepseek_api_key()
    return {
        "Authorization": f"Bearer {resolved}",
        "Content-Type": "application/json",
    }


def build_chat_payload(
    messages: list[dict[str, Any]],
    max_tokens: int = 1024,
    temperature: float = 0.7,
) -> dict[str, Any]:
    s = get_settings()
    return {
        "model": s.deepseek_model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }


async def _post_deepseek_async(
    payload: dict[str, Any],
    headers: dict[str, str],
) -> httpx.Response:
    s = get_settings()
    production = s.is_production()
    timeout = httpx.Timeout(60.0, connect=10.0)
    limits = httpx.Limits(max_keepalive_connections=5, max_connections=10)

    last_exc: Exception | None = None
    for attempt in range(3):
        try:
            async with httpx.AsyncClient(timeout=timeout, limits=limits) as client:
                r = await client.post(s.deepseek_api_url, headers=headers, json=payload)
            if r.status_code == 200:
                return r
            if r.status_code in (429, 500, 502, 503, 504) and attempt < 2:
                wait = (2**attempt) + random.uniform(0, 0.5)
                logger.warning(
                    "DeepSeek retryable HTTP %s (attempt %s), sleeping %.1fs — %s",
                    r.status_code,
                    attempt + 1,
                    wait,
                    _safe_error_snippet(r.status_code, r.text, production),
                )
                await asyncio.sleep(wait)
                continue
            logger.error(
                "DeepSeek HTTP error: %s",
                _safe_error_snippet(r.status_code, r.text, production),
            )
            return r
        except (httpx.TimeoutException, httpx.ConnectError, httpx.NetworkError) as e:
            last_exc = e
            if attempt < 2:
                wait = (2**attempt) + random.uniform(0, 0.5)
                logger.warning("DeepSeek transport error (attempt %s): %s", attempt + 1, e)
                await asyncio.sleep(wait)
                continue
            logger.error("DeepSeek transport failed after retries: %s", e)
            raise
    if last_exc:
        raise last_exc
    raise RuntimeError("DeepSeek request failed")


def _post_deepseek_sync(payload: dict[str, Any], headers: dict[str, str]) -> httpx.Response:
    s = get_settings()
    production = s.is_production()
    timeout = httpx.Timeout(60.0, connect=10.0)
    last_exc: Exception | None = None
    for attempt in range(3):
        try:
            with httpx.Client(timeout=timeout) as client:
                r = client.post(s.deepseek_api_url, headers=headers, json=payload)
            if r.status_code == 200:
                return r
            if r.status_code in (429, 500, 502, 503, 504) and attempt < 2:
                wait = (2**attempt) + random.uniform(0, 0.5)
                logger.warning(
                    "DeepSeek sync retryable %s, sleeping %.1fs — %s",
                    r.status_code,
                    wait,
                    _safe_error_snippet(r.status_code, r.text, production),
                )
                import time

                time.sleep(wait)
                continue
            logger.error(
                "DeepSeek sync HTTP error: %s",
                _safe_error_snippet(r.status_code, r.text, production),
            )
            return r
        except (httpx.TimeoutException, httpx.ConnectError, httpx.NetworkError) as e:
            last_exc = e
            if attempt < 2:
                import time

                time.sleep((2**attempt) + random.uniform(0, 0.5))
                continue
            raise
    if last_exc:
        raise last_exc
    raise RuntimeError("DeepSeek sync request failed")


async def call_llm_async(prompt: str) -> str:
    api_key = get_deepseek_api_key()
    if not api_key:
        logger.error("DEEPSEEK_API_KEY missing")
        return "❌ API key missing"

    headers = get_deepseek_headers(api_key)
    payload = build_chat_payload(messages=[{"role": "user", "content": prompt}])

    try:
        response = await _post_deepseek_async(payload, headers)
        if response.status_code != 200:
            return f"❌ API Error {response.status_code}"

        data = response.json()
        if "choices" in data and len(data["choices"]) > 0:
            return data["choices"][0]["message"]["content"]
        logger.error("DeepSeek unexpected JSON shape (keys=%s)", list(data.keys())[:12])
        return "❌ Format de réponse invalide"
    except Exception as e:
        logger.error("call_llm_async failed: %s", e)
        return "❌ Server error"


def call_llm(prompt: str) -> str:
    """Synchronous LLM call (orchestrator / legacy). Prefer call_llm_async in async code."""
    api_key = get_deepseek_api_key()
    if not api_key:
        logger.error("DEEPSEEK_API_KEY missing")
        return "❌ API key missing"

    headers = get_deepseek_headers(api_key)
    payload = build_chat_payload(messages=[{"role": "user", "content": prompt}])

    try:
        response = _post_deepseek_sync(payload, headers)
        if response.status_code != 200:
            return f"❌ API Error {response.status_code}"

        data = response.json()
        if "choices" in data and len(data["choices"]) > 0:
            return data["choices"][0]["message"]["content"]
        logger.error("DeepSeek unexpected JSON shape (sync)")
        return "❌ Format de réponse invalide"
    except Exception as e:
        logger.error("call_llm failed: %s", e)
        return "❌ Server error"


async def translate_to_english_async(text: str) -> str:
    if not text or len(text.strip()) < 3:
        return text

    prompt = f"""
Translate the following text to English.

Rules:
- Keep the exact meaning
- Do not add explanations
- Do not rephrase too much
- Output ONLY the translated text

Text:
{text}
"""

    result = await call_llm_async(prompt)
    if result.startswith("❌"):
        return text
    return result.strip()


def translate_to_english(text: str) -> str:
    """Synchronous translation (orchestrator); uses blocking httpx."""
    if not text or len(text.strip()) < 3:
        return text

    prompt = f"""
Translate the following text to English.

Rules:
- Keep the exact meaning
- Do not add explanations
- Do not rephrase too much
- Output ONLY the translated text

Text:
{text}
"""

    result = call_llm(prompt)
    if result.startswith("❌"):
        return text
    return result.strip()
