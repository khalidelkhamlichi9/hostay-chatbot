# orchestrator.py
import json
from llm_client import call_llm, translate_to_english
import database
from auth import decode_jwt


# -----------------------------
# 🔎 Simple RAG search
# -----------------------------
def search_rag(query: str, top_k: int = 5) -> str:
    chunks = database.get_all_chunks()
    results = []

    q = query.lower()

    for ch in chunks:
        text = (ch.get("content") or "").lower()
        if any(token in text for token in q.split()):
            results.append(ch.get("content"))

    if not results:
        results = [ch.get("content") for ch in chunks[:top_k]]

    return "\n---\n".join(results[:top_k])


# -----------------------------
# 🧠 Router
# -----------------------------
def route_query(user_query: str) -> dict:
    prompt = f"""
You are an AI router.

Decide how to handle the query.

Actions:
- RAG
- API
- BOTH

Also detect language: fr, en, ar

Return ONLY JSON:
{{
  "action": "RAG" | "API" | "BOTH",
  "needs_translation": true | false,
  "language": "fr" | "en" | "ar"
}}

Query:
{user_query}
"""

    raw = call_llm(prompt)

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {
            "action": "RAG",
            "needs_translation": True,
            "language": "en"
        }


# -----------------------------
# 📚 RAG
# -----------------------------
def rag_answer(query_en: str, original_query: str) -> str:
    context = search_rag(query_en)

    prompt = f"""
You are a helpful assistant.

Use ONLY the context.

Context:
{context}

Question:
{original_query}

Answer clearly.
"""

    return call_llm(prompt)


# -----------------------------
# 🌐 API
# -----------------------------
def call_api(user_query: str) -> str:
    return "API result: availability is high, price is 120€/night."


# -----------------------------
# 🔗 FINAL FUSION
# -----------------------------
def final_answer(user_query: str, rag_result: str, api_result: str, context: dict) -> str:

    prompt = f"""
You are Hostay AI assistant.

USER CONTEXT:
- Role: {context.get("role")}
- Reservation ID: {context.get("reservation_hashId")}

RAG:
{rag_result}

API:
{api_result}

Question:
{user_query}

Rules:
- If reservation exists, mention it
- Adapt answer based on role
- Be precise and helpful

Final answer:
"""

    return call_llm(prompt)


# -----------------------------
# 🚀 MAIN PIPELINE (JWT ENABLED)
# -----------------------------
def process_query(user_query: str, token: str = None) -> dict:

    # =========================
    # 🔐 JWT CONTEXT
    # =========================
    context = {
        "user_hashId": None,
        "role": "guest",
        "reservation_hashId": None
    }

    if token:
        decoded = decode_jwt(token)
        if decoded:
            context.update(decoded)

    # =========================
    # 🧠 ROUTER
    # =========================
    decision = route_query(user_query)

    action = decision.get("action", "RAG")
    needs_translation = decision.get("needs_translation", True)

    # =========================
    # 🌍 TRANSLATION
    # =========================
    query_en = translate_to_english(user_query) if needs_translation else user_query

    rag_result = ""
    api_result = ""

    # =========================
    # ⚙️ EXECUTION
    # =========================
    if action == "RAG":
        rag_result = rag_answer(query_en, user_query)
        final = rag_result

    elif action == "API":
        api_result = call_api(user_query)
        final = api_result

    else:  # BOTH
        rag_result = rag_answer(query_en, user_query)
        api_result = call_api(user_query)
        final = final_answer(user_query, rag_result, api_result, context)

    # =========================
    # 📤 OUTPUT
    # =========================
    return {
        "decision": decision,
        "context": context,
        "rag": rag_result,
        "api": api_result,
        "answer": final
    }