# Rapport d'evaluation - Traitement des messages (Hostay Chatbot)

## Perimetre

Ce document evalue la chaine actuelle de traitement des messages:

- reception de la requete utilisateur
- detection du contexte (role, langue, urgence)
- recuperation de contexte (RAG)
- generation de reponse (LLM)
- composition de la sortie
- persistance des conversations

Il repond a trois questions cles:

1. Le processus est-il bon?
2. Le systeme est-il puissant?
3. Le niveau est-il compatible avec la production?

---

## Flux actuel observe

1. L'endpoint `POST /chat` recoit le message et le contexte JWT.
2. `chatbot.get_answer()` execute successivement:
   - verification de mots-cles de danger
   - detection de langue
   - classification de l'urgence/tension
   - recuperation RAG depuis une base de connaissance + chunks en base
   - construction dynamique du prompt systeme selon le role
   - appel LLM via OpenRouter/DeepSeek
   - sauvegarde de la conversation dans SQLite
3. L'API retourne la reponse et des metadonnees.

---

## Qualite du processus

**Evaluation: correcte pour un MVP, insuffisante pour un produit final.**

### Points forts

- Architecture lisible et relativement modulaire.
- Presence de briques utiles: multi-langue, priorisation, RAG, prompts par role, persistance.
- Administration fonctionnelle permettant des ajustements rapides.

### Limites

- Qualite de reponse encore dependante d'une recherche lexicale simple.
- Separation insuffisante entre entree utilisateur et controles d'administration/runtime.
- Absence d'un pipeline de validation et de garde-fous complet avant/apres appel LLM.

---

## Puissance fonctionnelle

**Evaluation: puissance moyenne (bonne en demo, limitee en exploitation reelle).**

### Capacites actuelles

- Gestion de base du multilingue.
- Enrichissement des reponses par contexte RAG.
- Adaptation du ton/contenu selon le role.

### Capacites manquantes

- Recherche semantique robuste (embeddings + reranking).
- Couche d'outils pour APIs dynamiques en temps reel.
- Strategie memoire multi-tour (court terme + long terme).
- Controle qualite des sorties (grounding, anti-hallucination, conformite).

---

## Niveau de preparation production

**Conclusion: non, pas a ce stade.**

Raisons principales:

- Niveau de securite insuffisant sur la surface admin et conversationnelle.
- Fiabilite, supervision et pilotage technique incomplets.
- Couche data/retrieval non dimensionnee pour la montee en charge.

---

## Evolutions indispensables avant mise en production

## 1) Durcir le pipeline de messages

- Definir des schemas stricts de requete/reponse a chaque etape.
- Centraliser la gestion d'exceptions avec contrats d'erreur stables.
- Appliquer des budgets de timeout par composant (RAG, LLM, persistence).
- Implementer des modes de secours (fallback) en cas d'echec partiel.

## 2) Moderniser la retrieval

- Conserver la recherche lexicale comme filet de securite.
- Ajouter une retrieval vectorielle (embeddings + index).
- Integrer un reranker pour la pertinence top-k.
- Ajouter l'attribution des sources dans les metadonnees de reponse.

## 3) Securiser la qualite des sorties

- Ajouter un post-traitement des reponses:
  - filtre de politique de contenu
  - verification de fuite de donnees sensibles (PII)
  - controle de longueur et de ton
- Introduire un score de confiance + templates de repli.

## 4) Renforcer l'observabilite

- Assigner un identifiant de trace par requete.
- Journaliser les durees de chaque etape en logs structures.
- Suivre des metriques cles: latence p50/p95, erreurs, tokens, taux de hit cache.

---

## Recommandations cache (priorite demandee)

Caches recommandes:

1. **Cache requetes RAG**  
   Cle: requete normalisee + role + locale + version KB  
   TTL: 5 a 15 minutes  
   Gain: reduction forte de latence sur questions repetitives

2. **Cache de prompts**  
   Cle: version du prompt de role  
   TTL: 1 a 5 minutes (ou invalidation immediate a la mise a jour)  
   Gain: reduction des lectures base repetitives

3. **Cache de reponse LLM (perimetre controle)**  
   Cle: question normalisee + hash du contexte + modele  
   TTL: court (2 a 10 minutes), jamais globaliser du contenu sensible  
   Gain: baisse des couts et du temps de reponse sur FAQs

Technologie cible: **Redis** en cache partage de production.

---

## Recommandations APIs dynamiques (priorite demandee)

Le code actuel contient des elements preparatoires, mais pas de couche outillee complete.

Plan recommande:

1. Definir un catalogue de capacites API:
   - disponibilite
   - details de reservation
   - informations logement
   - statut ticket support

2. Ajouter un registre d'outils:
   - schema d'entree
   - regles d'autorisation
   - timeout et retry policy

3. Ajouter une couche de decision:
   - classer chaque requete en `RAG`, `API` ou `BOTH`
   - appliquer les permissions selon le role

4. Mettre en place la fusion de reponse:
   - combiner donnees API + contexte RAG avec citation de sources

5. Proteger l'execution API:
   - circuit breaker
   - limitation de debit
   - journal d'audit par appel outil

---

## Verdict final (traitement des messages)

- **Processus "bon"?** Oui pour un prototype.
- **Processus "puissant"?** Niveau moyen, suffisant pour demo, limite en exploitation.
- **Pret production?** Non. Un chantier de durcissement est requis (securite, retrieval, observabilite, execution outillee).

