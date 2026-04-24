# chatbot.py - Hostay Chatbot avec RAG + Tension + OpenRouter API + Multilangue (FIXED)
import re
import os
import requests
from data import retrieve_context
from tension import classify_tension
from dotenv import load_dotenv
import database
from database import get_prompt  # ← Import dynamique prompt

load_dotenv()

ANTHROPIC_API_URL = "https://openrouter.ai/api/v1/chat/completions"
ANTHROPIC_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
CLAUDE_MODEL = "deepseek/deepseek-chat"


def is_dangerous(text: str) -> bool:
    blacklist = ["rm -rf", "drop database", "shutdown", "format c:"]
    return any(bad in text.lower() for bad in blacklist)


def detect_language(text: str) -> str:
    text_lower = text.lower()

    darija_words = [
        "wash", "kifash", "fin", "mnin", "chno", "3ndek", "bghit", "wach", 
        "nta", "ana", "dyal", "bach", "ndir", "khasni", "3endi", "3endek", 
        "bghiti", "wnti", "nti", "nta", "kifach", "chhal", "ch7al", "bch7al", 
        "wakha", "safi", "3ziz", "3zizi", "chokran", "afak", "3afak", "min", 
        "fik", "ghadi", "daba", "dakchi", "walo", "mzyan", "mezyan", "wach",
        "bghit", "bghiti", "3nd", "3ndi", "3ndk", "3ndek", "3ndna", "3ndhom"
    ]
    
    french_words = ["bonjour", "comment", "quoi", "merci", "pourquoi", "est-ce", "je", "vous", "pas", "une"]
    english_words = ["hello", "what", "how", "why", "who", "where", "when", "please", "can you", "i need"]
    arabic_words = ["كيف", "يمكنني", "أريد", "حجز", "هل", "ما", "من", "أين", "متى", "كيفية"]
    
    if any(word in text_lower for word in darija_words):
        return "Moroccan Darija"
    if any(word in text for word in arabic_words):
        return "Arabic"
    
    fr_score = sum(1 for w in french_words if w in text_lower)
    en_score = sum(1 for w in english_words if w in text_lower)
    
    if fr_score > 0 and fr_score >= en_score:
        return "French"
    if en_score > 0:
        return "English"
    
    return "French"


def clean_output(text: str) -> str:
    text = text.strip()
    text = re.sub(r" thinking.*?/thinking>", "", text, flags=re.DOTALL)
    return text.strip()


def _get_lang_rule(lang: str) -> str:
    """Helper: Retourne la règle de langue pour le prompt"""
    if lang == "Moroccan Darija":
        return '''RÈGLE STRICTE: Tu dois ABSOLUMENT répondre en Darija (langue marocaine).
EXEMPLE: "Bache dir réservation, kteb email dyalek w dates li bghiti."
EXEMPLE: "Wash khassek chi mochkil? Nta 3endek chi so2al?"'''
    
    elif lang == "Arabic":
        return "يجب أن ترد باللغة العربية الفصحى فقط."
    
    elif lang == "French":
        return "Tu dois répondre UNIQUEMENT en Français."
    
    elif lang == "English":
        return "You must respond ONLY in English."
    
    else:
        return "Tu dois répondre UNIQUEMENT en Français."

def build_system_prompt(lang: str, role: str, tension_instruction: str, rag_context: str) -> str:
    """
    Construit le prompt système DYNAMIQUE:
    - Prompt de base depuis la DB (par rôle)
    - Règle de langue
    - Contexte RAG + Instructions urgence
    """
    
    # 1️⃣ Charger prompt dynamique depuis la DB (par rôle)
    db_prompt = get_prompt(role) or "Tu es l'assistant IA officiel de Hostay."
    
    # 2️⃣ Règle de langue (extraite en helper)
    lang_rule = _get_lang_rule(lang)
    
    # 3️⃣ Sections optionnelles
    tension_section = f"\n\nINSTRUCTION URGENCE: {tension_instruction}" if tension_instruction else ""
    rag_section = f"\n\nINFORMATIONS HOSTAY:\n{rag_context}" if rag_context else ""
    
    # 4️⃣ Assemblage final
    return f"""{db_prompt}

RÈGLES ABSOLUES:
- {lang_rule}
- Réponds UNIQUEMENT à la question posée.
- Sois concis.
- Si tu ne sais pas, dis-le clairement.
- Ne génère pas de code.
- Reste dans le contexte Hostay.{rag_section}{tension_section}"""


def get_answer(message: str, role: str) -> dict:
    if is_dangerous(message):
        return {"reply": "⛔ Commande non autorisée.", "saved": False}

    lang = detect_language(message)
    tension = classify_tension(message)
    rag_context = retrieve_context(message)

    if not ANTHROPIC_API_KEY:
        return {"reply": "⚠️ API key manquante.", "saved": False}

    system_prompt = build_system_prompt(
        lang=lang,
        role=role,
        tension_instruction=tension["instruction"],
        rag_context=rag_context
    )

    headers = {
        "Authorization": f"Bearer {ANTHROPIC_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": CLAUDE_MODEL,
        "max_tokens": 1024,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": message}
        ]
    }

    try:
        response = requests.post(ANTHROPIC_API_URL, json=payload, headers=headers, timeout=30)

        if response.status_code != 200:
            return {"reply": f"❌ API error {response.status_code}", "saved": False}

        data = response.json()
        answer = data["choices"][0]["message"]["content"]
        final = tension["response_prefix"] + clean_output(answer)
        
        # Sauvegarde
        conv_id = database.save_conversation(
            user_role=role,
            message=message,
            reply=final,
            language=lang,
            urgency=tension
        )
        
        return {"reply": final, "saved": True, "conversation_id": conv_id, "language": lang}

    except Exception as e:
        return {"reply": f"❌ Server error: {str(e)}", "saved": False}