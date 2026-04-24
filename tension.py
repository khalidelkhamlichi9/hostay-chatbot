# tension.py - Détection de tension/urgence
import re

URGENCY_PATTERNSS = {
    "urgence_serrure": ["serrure", "bloqué", "coincé", "rentrer", "dehors", "enfermé", "clé"],
    "urgence_eau": ["fuite", "inondation", "eau", "dégât", "dégats des eaux", "robinet"],
    "urgence_electricité": ["coupure", "électricité", "courant", "disjoncteur", "fuse"],
    "urgence_internet": ["wifi", "internet", "connexion", "déconnecté", "réseau"],
    "urgence_bruit": ["bruit", "tapage", "voisins", "insomnie", "calme"],
    "urgence_chaleur": ["chauffage", "clim", "froid", "chaud", "température"],
    "urgence_proprete": ["sale", "propre", "désinfecter", "hygiène", "nettoyage"]
}

def classify_tension(message: str) -> dict:
    """
    Classifie le message selon le niveau de tension/urgence
    """
    message_lower = message.lower()
    
    detected = {
        "level": "normal",
        "type": None,
        "instruction": None,
        "response_prefix": ""
    }
    
    for urgency_type, keywords in URGENCY_PATTERNSS.items():
        if any(keyword in message_lower for keyword in keywords):
            detected["level"] = "Urgence"
            detected["type"] = urgency_type.replace("urgence_", "")
            
            if urgency_type == "urgence_serrure":
                detected["instruction"] = "Contactez immédiatement le concierge au numéro d'urgence. Essayez le code de secours si visible."
                detected["response_prefix"] = "🚨 URGENCE SERRURE: "
            elif urgency_type == "urgence_eau":
                detected["instruction"] = "Fermez le robinet principal immédiatement. Contactez le concierge en urgence."
                detected["response_prefix"] = "🚨 URGENCE FUITE D'EAU: "
            elif urgency_type == "urgence_electricité":
                detected["instruction"] = "Ne touchez à aucun appareil électrique. Contactez le concierge."
                detected["response_prefix"] = "🚨 URGENCE ÉLECTRICITÉ: "
            else:
                detected["instruction"] = "Contactez le concierge pour assistance."
                detected["response_prefix"] = "🚨 URGENCE: "
            
            break
    
    return detected