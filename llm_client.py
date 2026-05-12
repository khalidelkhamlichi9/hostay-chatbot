# llm_client.py - DeepSeek LLM Client
import os
import requests
from dotenv import load_dotenv
import logging

logger = logging.getLogger(__name__)

# Charger les variables d'environnement
load_dotenv()

DEEPSEEK_API_URL = os.getenv("DEEPSEEK_API_URL", "https://api.deepseek.com/chat/completions")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")


def get_deepseek_api_key() -> str:
    return os.getenv("DEEPSEEK_API_KEY", "")


def get_deepseek_headers(api_key: str | None = None) -> dict:
    resolved_api_key = api_key or get_deepseek_api_key()
    return {
        "Authorization": f"Bearer {resolved_api_key}",
        "Content-Type": "application/json",
    }


def build_chat_payload(messages: list[dict], max_tokens: int = 1024, temperature: float = 0.7) -> dict:
    return {
        "model": DEEPSEEK_MODEL,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }


def call_llm(prompt: str) -> str:
    """
    Appelle directement l'API DeepSeek.

    Returns: réponse brute du LLM ou message d'erreur.
    """

    api_key = get_deepseek_api_key()

    if not api_key:
        logger.error("❌ ERREUR: DEEPSEEK_API_KEY non trouvée dans .env")
        return "❌ API key missing"

    headers = get_deepseek_headers(api_key)
    payload = build_chat_payload(
        messages=[{"role": "user", "content": prompt}],
        max_tokens=1024,
        temperature=0.7,
    )

    try:
        response = requests.post(DEEPSEEK_API_URL, headers=headers, json=payload, timeout=30)

        if response.status_code != 200:
            logger.error(f"❌ HTTP Error {response.status_code}: {response.text}")
            return f"❌ API Error {response.status_code}"

        data = response.json()

        if "choices" in data and len(data["choices"]) > 0:
            return data["choices"][0]["message"]["content"]
        logger.error(f"❌ Réponse inattendue: {data}")
        return "❌ Format de réponse invalide"

    except requests.exceptions.Timeout:
        logger.error("❌ Timeout: La requête a pris trop de temps")
        return "❌ Timeout error"

    except requests.exceptions.ConnectionError:
        logger.error("❌ ConnectionError: Vérifiez votre connexion internet")
        return "❌ Connection error"

    except Exception as e:
        logger.error(f"❌ Exception inattendue: {str(e)}")
        return f"❌ Server error: {str(e)}"


def translate_to_english(text: str) -> str:
    """
    Traduction vers l'anglais via DeepSeek.

    Optimisée pour RAG (courte, propre, sans bruit).
    """

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