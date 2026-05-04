# llm_client.py - OpenRouter LLM Client (Fixed)
import os
import requests
from dotenv import load_dotenv
import logging

logger = logging.getLogger(__name__)

# 🔥 Charger les variables d'environnement (.env file)
load_dotenv()

def call_llm(prompt: str) -> str:
    """
    Appelle l'API OpenRouter avec le modèle DeepSeek
    Returns: réponse brute du LLM ou message d'erreur
    """
    
    # 🔐 Récupérer la clé API (dakh l'function = best practice)
    api_key = os.getenv("OPENROUTER_API_KEY")
    
    if not api_key:
        logger.error("❌ ERREUR: OPENROUTER_API_KEY non trouvée dans .env")
        return "❌ API key missing"

    # 🌐 Configuration de l'API OpenRouter
    url = "https://openrouter.ai/api/v1/chat/completions"
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost",  # Requis par OpenRouter
        "X-Title": "Hostay Chatbot"           # Requis par OpenRouter
    }

    # 📦 Payload de la requête
    payload = {
        "model": "deepseek/deepseek-chat",  # Modèle utilisé
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "max_tokens": 1024,
        "temperature": 0.7
    }

    try:
        # 🚀 Envoi de la requête POST
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        
        # ❌ Gestion des erreurs HTTP
        if response.status_code != 200:
            logger.error(f"❌ HTTP Error {response.status_code}: {response.text}")
            return f"❌ API Error {response.status_code}"
        
        # ✅ Parsing de la réponse JSON
        data = response.json()
        
        # Extraction sécurisée du contenu
        if "choices" in data and len(data["choices"]) > 0:
            return data["choices"][0]["message"]["content"]
        else:
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
    Traduction vers l'anglais via DeepSeek (OpenRouter)
    Optimisée pour RAG (courte, propre, sans bruit)
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

    # 🔒 Sécurité (si erreur API)
    if result.startswith("❌"):
        return text

    return result.strip()