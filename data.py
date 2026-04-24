# data.py - RAG amélioré pour Hostay (FIXED - reads from DB)
import re
import database

KNOWLEDGE_BASE = [
    {
        "id": "checkin",
        "tags": ["checkin", "arrivée", "entrée", "accès", "clé", "code", "porte"],
        "content": "Le check-in digital Hostay se fait via l'app ou par code SMS. Le code d'accès est envoyé 2h avant l'arrivée. En cas de problème, contactez le concierge."
    },
    {
        "id": "iot",
        "tags": ["iot", "tuya", "lumière", "climatisation", "wifi", "internet", "télévision", "tv"],
        "content": "Hostay utilise l'API Tuya pour tous les appareils connectés : lumières, climatiseur, TV. Si un appareil ne répond pas, redémarrez l'app Hostay ou contactez le support."
    },
    {
        "id": "reservation",
        "tags": ["réservation", "booking", "annulation", "remboursement", "dates", "disponibilité"],
        "content": "Les réservations sont gérées en temps réel via le dashboard Hostay. L'annulation est gratuite jusqu'à 48h avant l'arrivée. Après, des frais de 50% s'appliquent."
    },
    {
        "id": "roles",
        "tags": ["rôle", "guest", "owner", "concierge", "accès", "permissions"],
        "content": "3 rôles existent : Guest (accès logement), Owner (gestion complète), Concierge (assistance 24/7)."
    },
    {
        "id": "urgence_serrure",
        "tags": ["serrure", "bloqué", "coincé", "rentrer", "dehors", "enfermé"],
        "content": "En cas de problème avec la serrure : 1) Redémarrez l'app. 2) Essayez le code manuel sur la porte. 3) Appelez le concierge."
    },
    {
        "id": "urgence_eau",
        "tags": ["eau", "fuite", "inondation", "robinet", "chauffe-eau", "plomberie"],
        "content": "En cas de fuite d'eau : Fermez le robinet principal. Contactez le concierge immédiatement. Évitez les appareils électriques."
    },
    {
        "id": "paiement",
        "tags": ["paiement", "facture", "prix", "tarif", "caution", "dépôt"],
        "content": "Le paiement se fait en ligne à la réservation. Une caution de 500 MAD est prélevée et remboursée sous 48h après départ."
    },
    {
        "id": "wifi",
        "tags": ["wifi", "internet", "connexion"],
        "content": "Le WiFi est fourni gratuitement dans tous les logements Hostay."
    },
    {
        "id": "parking",
        "tags": ["parking", "voiture", "garage"],
        "content": "Certains logements disposent d'un parking privé."
    },
    {
        "id": "cleaning",
        "tags": ["ménage", "nettoyage"],
        "content": "Le ménage est effectué après chaque départ."
    }
]


def retrieve_context(query: str, max_results: int = 3) -> str:
    """
    RAG: Combine hardcoded knowledge + DB chunks uploadés par admin
    """
    query_lower = query.lower()
    query_words = set(re.findall(r'\w+', query_lower))

    scored_entries = []

    # ===== 1. Hardcoded knowledge base =====
    for entry in KNOWLEDGE_BASE:
        entry_tags = set(tag.lower() for tag in entry["tags"])
        matching_words = query_words.intersection(entry_tags)
        score = len(matching_words)
        if any(word in entry["content"].lower() for word in query_words):
            score += 0.5
        if score > 0:
            scored_entries.append((score, entry["content"]))

    # ===== 2. DB chunks (uploaded by admin) =====
    try:
        db_chunks = database.get_all_chunks()
        for chunk in db_chunks:
            content = chunk.get("content", "")
            title = chunk.get("title", "")
            tags_raw = chunk.get("tags", "")

            # Parse tags
            chunk_tags = set()
            if tags_raw:
                chunk_tags = set(t.strip().lower() for t in tags_raw.split(","))

            # Score: tags match + content match
            score = len(query_words.intersection(chunk_tags))
            if any(word in content.lower() for word in query_words):
                score += 1.0
            if any(word in title.lower() for word in query_words):
                score += 0.5

            if score > 0:
                scored_entries.append((score, f"[{title}] {content}"))

    except Exception as e:
        print(f"⚠️ DB chunks error: {e}")

    # ===== 3. Sort + return top results =====
    scored_entries.sort(key=lambda x: x[0], reverse=True)
    top = scored_entries[:max_results]

    if not top:
        return ""

    return "\n\n".join(content for _, content in top)