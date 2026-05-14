# Audit technique - Securite, Performance et Industrialisation (Hostay Chatbot)

## Domaines analyses

- securite
- performance
- fiabilite
- scalabilite
- maintenabilite
- exploitation production (ops)

---

## Synthese executive

L'implementation actuelle correspond a un **niveau MVP**. Elle est exploitable pour des tests et demonstrations, mais **pas encore conforme aux exigences d'un environnement production**.

Risques majeurs identifies:

1. surface d'administration insuffisamment protegee
2. incoherences dans la chaine d'authentification
3. architecture data/recherche limitee pour la charge
4. manque d'observabilite et de controle de defaillance

---

## Evaluation securite

## Risques eleves

- Presence de credentials/secret hardcodes ou valeurs par defaut faibles.
- Protection insuffisante de certaines routes admin (authentification/autorisation).
- Incoherence de gestion des secrets JWT selon les modules.
- Absence de politique RBAC explicite et centralisee pour les operations sensibles.

## Risques moyens

- Limitation de debit (rate limiting) non systematique.
- Validation/sanitization d'entrees a renforcer.
- Gestion des secrets a industrialiser (rotation, obligations d'env, audit).

## Actions securite prioritaires

1. Supprimer tous les secrets et identifiants en dur.
2. Uniformiser JWT: une librairie, une source de secret, controle strict au demarrage.
3. Proteger toutes les routes admin via middleware auth + RBAC.
4. Ajouter des controles anti-abus (rate limiting, quotas, blocage comportemental).
5. Journaliser les actions admin et appels d'outils avec trace d'audit.

---

## Evaluation performance

## Goulots d'etranglement actuels

- Appels externes synchrones dans le chemin critique de reponse.
- Recalculs repetes (DB + RAG) a chaque requete.
- SQLite limite la concurrence en charge.
- Absence de strategie de cache partage.

## Recommandations performance

1. Introduire Redis pour les caches RAG/prompt/reponse generic.
2. Passer d'une logique majoritairement lexicale a une retrieval indexee (vectorielle + fallback).
3. Standardiser timeout/retry/backoff/circuit breaker sur appels externes.
4. Migrer vers une base production (Postgres) avec pooling de connexions.

---

## Fiabilite et resilience

## Constats

- Chemins de degradation partielle insuffisants.
- Politique de timeout/coupure inegale selon les etapes.
- Certaines operations de setup au demarrage augmentent la fragilite runtime.

## Recommandations

1. Definir des fallbacks explicites pour chaque etape critique:
   - echec retrieval
   - timeout LLM
   - echec de persistance
2. Mettre en place un circuit breaker pour dependances externes.
3. Deplacer les taches lourdes de preparation hors du chemin de demarrage.

---

## Scalabilite

## Etat actuel

- Correct pour faible trafic.
- Non adapte a une mise a l'echelle horizontale en l'etat.

## Recommandations

- Externaliser l'etat applicatif:
  - Postgres pour conversations/configurations
  - Redis pour cache et metadonnees de session
  - stockage objet pour fichiers/chunks volumineux
- Ajouter des workers pour ingestion/chunking asynchrones.

---

## Observabilite et operations

## Manques identifies

- Pas de standard de logs structures uniforme.
- Pas de tableau de bord latence/erreurs.
- Correlation de traces insuffisante entre composants.

## Minimum requis

1. Logs JSON structures avec `request_id`.
2. Metriques de pilotage:
   - latence API p50/p95
   - latence et taux d'erreur LLM
   - taux de hit cache
   - latence/erreurs base de donnees
3. Endpoints de sante (`health`/`readiness`) avec verification des dependances.

---

## Preparation aux APIs dynamiques

L'existant contient des bases, mais pas encore une couche outil industrialisee.

Pour activer les APIs dynamiques en securite:

1. Construire une abstraction d'outil (`nom`, schema d'entree, regles auth, timeout).
2. Ajouter un routeur deterministe `API`/`RAG`/`BOTH`.
3. Valider strictement les entrees/outils.
4. Ajouter retry/backoff/fallback par outil.
5. Journaliser chaque appel outil (audit et supervision).

---

## Preparation au cache

Plan de cache recommande a court terme:

- **Redis**
  - `rag:query:{hash}` (TTL 10 min)
  - `prompt:role:{role}` (TTL 5 min, invalidation sur mise a jour)
  - `llm:generic:{hash}` (TTL 3 min, reserve aux cas non sensibles)

Regles de securite cache:

- ne jamais mutualiser globalement des sorties sensibles utilisateur
- inclure role/locale/version contexte dans la cle
- invalider le cache apres mise a jour des connaissances/prompts

---

## Score de maturite production (etat actuel)

- Securite: **3/10**
- Performance: **4/10**
- Fiabilite: **4/10**
- Scalabilite: **3/10**
- Observabilite: **2/10**
- Global: **3.5/10**

---

## Plan de livraison recommande

## Phase 1 (urgent - 2 a 4 jours)

- durcissement securite (auth, RBAC, secrets)
- rate limiting des endpoints
- unification JWT
- logs structures de base

## Phase 2 (1 semaine)

- integration couche Redis
- couche outils pour APIs dynamiques (disponibilite, reservation, logement)
- politique standard timeout/retry/circuit breaker

## Phase 3 (1 a 2 semaines)

- migration Postgres
- retrieval avancee (vector index + reranker)
- dashboard metriques et alerting

