# test_rag.py
from rag_engine_v2 import rag_engine

questions = [
    "Quels sont les services proposés ?",
    "Comment fonctionne le check-in ?",
    "Je veux savoir wifi et réservation",
    "Est-ce que vous avez piscine ?",
    "kifach ndir checkin ?"
]

for q in questions:
    print("\n" + "="*60)
    print("❓ Question:", q)
    print("="*60)

    response = rag_engine.query(q, debug=False)

    print("💬 Réponse:")
    print(response)