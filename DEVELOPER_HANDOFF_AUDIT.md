# Audit Technique et Handoff Developpeur
# Projet: `khalid-chatbot`

Version: 1.1  
Date: 2026-05-12  
Auteur: Audit technique interne

---

## 1. Objectif du document

Ce document a pour but de donner au developpeur une vision claire et exploitable de l'etat actuel de `khalid-chatbot`, de ses points forts, de ses fragilites, et des actions recommandees pour en faire un service plus propre, plus leger, et plus fiable en production.

Le but n'est pas de critiquer gratuitement le projet. Le projet est fonctionnel et a une base utile. En revanche, il y a un decalage important entre:

- la taille et la simplicite du code applicatif,
- et le poids / la complexite des dependances et du runtime.

---

## 1.1 Verifications realisees

Dans le cadre de cette revue, plusieurs verifications techniques ont ete realisees directement sur l'espace de travail et via terminal:

- compilation Python globale du projet,
- revue des imports et des dependances,
- revue du flux de demarrage de l'application,
- revue du pipeline CI/CD et de la strategie de deploiement,
- mesure de la taille reelle du code par rapport au poids des dependances,
- analyse du chemin d'execution du RAG, du fallback, et de l'admin,
- revue du comportement observe lors du deploiement Docker.

Les verifications de structure et de compilation ne remontent pas d'erreur de syntaxe bloquante. En revanche, les verifications de runtime et de deploiement montrent plusieurs points a corriger ou a clarifier, en particulier autour des dependances, du RAG et du demarrage du conteneur.

---

## 2. Resume executif

### Etat global

Le projet est **fonctionnel**, mais **pas encore proprement production-ready** au sens standard d'un service web robuste.

### Probleme principal

Le principal probleme n'est pas la logique metier.  
Le principal probleme est le **rapport disproportionne entre le poids des dependances et la taille reelle du projet**.

### Diagnostic simple

- Le coeur du projet est petit.
- Le chatbot utilise une architecture mixte:
  - chunks manuels en base,
  - fallback recherche simple,
  - couche RAG semantique locale plus lourde.
- La partie la plus lourde du projet vient surtout de:
  - `sentence-transformers`
  - `torch`
  - `numpy`
  - `scikit-learn`
  - `nltk`
- La partie la plus robuste aujourd'hui n'est probablement pas le RAG semantique, mais plutot:
  - le chunking manuel,
  - la base SQLite,
  - la recherche simple par contenu / tags.

### Orientation generale proposee

Si l'objectif est un chatbot **leger, simple, stable et deployable proprement**, la meilleure direction est:

1. garder la base FastAPI + admin + chunks manuels,
2. simplifier ou retirer le RAG embeddings local,
3. alleger les requirements,
4. garder un deploiement Docker,
5. corriger les incoherences de dependances.

---

## 3. Taille reelle du projet vs poids des dependances

Mesure rapide effectuee sur le repo:

- fichiers du projet hors `.git`, cache Python et DB: environ **0.15 MB**
- code Python seul: environ **61.5 KB**
- nombre de fichiers Python: **14**

Conclusion:

- le code est **petit**
- les dependances sont **enormes par rapport au code**

En pratique, aujourd'hui, les requirements sont bien plus gros que le projet lui-meme.

---

## 4. Architecture actuelle du chatbot

## 4.1 Composants principaux

- `main.py`  
  Application FastAPI, routes principales, CORS, auth, admin, rate limiting.

- `chatbot.py`  
  Pipeline principal des reponses utilisateur.

- `llm_client.py`  
  Appels LLM directs vers DeepSeek.

- `backend_client.py`  
  Recuperation de donnees live depuis le backend Hostay.

- `database.py`  
  Stockage SQLite local des sessions, messages, prompts, chunks RAG.

- `admin_routes.py`  
  Interface admin pour prompts, chunks, cache, upload de docs.

- `rag_engine_v2.py`  
  RAG semantique local avec embeddings.

- `data.py`  
  Recherche simple / fallback basee sur chunks DB + base de connaissance hardcodee.

---

## 5. Flux reel du chatbot aujourd'hui

### 5.1 Pipeline principal

Le flux actuel est globalement:

1. le message utilisateur arrive
2. detection langue / tension
3. tentative de recuperation d'un contexte RAG via `rag_engine.get_context(...)`
4. si echec, fallback vers `retrieve_context(...)`
5. recuperation optionnelle des donnees live backend
6. construction du prompt final
7. appel DeepSeek
8. sauvegarde session / messages / cache

### 5.2 Important

Le projet utilise donc un **mode hybride**:

- **RAG semantique en premier**
- **fallback recherche simple ensuite**

Mais dans les faits, la partie la plus robuste est souvent la recherche simple, pour les raisons expliquees plus bas.

---

## 6. Analyse honnete du RAG

## 6.1 Oui, le RAG semantique est bien appele

Le moteur `rag_engine_v2.py` est bien dans le chemin principal de resolution.

Il charge un modele `SentenceTransformer`, calcule des embeddings et fait une recherche par similarite cosinus.

## 6.2 Mais il n'est pas idealement integre

Probleme important:

- les chunks ajoutes depuis l'admin sont ecrits en DB
- mais le moteur semantique charge les chunks en memoire au demarrage
- il n'y a pas de mecanisme clair et automatique de rechargement des embeddings apres modification admin

Consequence:

- la DB peut etre a jour
- la recherche simple peut voir les nouveaux chunks
- le RAG semantique peut rester sur un etat ancien jusqu'au redemarrage

## 6.3 Ce qui est vraiment largement exploite aujourd'hui

La vraie base du systeme est:

- le **manual chunking**
- le **stockage DB**
- la **recherche fallback simple**

Le RAG lourd existe, mais il ressemble plus a une surcouche encore imparfaitement finalisee qu'a un coeur totalement fiable du systeme.

### Conclusion RAG

Le projet n'est pas dans un etat ou on peut dire:

> "Le RAG semantique est la partie la mieux exploitee et la plus fiable."

La phrase la plus juste serait:

> "Le projet repose surtout sur les chunks manuels et la DB, avec un RAG semantique local ajoute par-dessus."

---

## 7. Pourquoi le projet est lourd

Le poids vient surtout de la stack RAG locale.

### Dependances les plus lourdes ou structurantes

- `sentence-transformers`
- `torch` (dependance transitive)
- `numpy`
- `scikit-learn`
- `nltk`

### Effets de ces choix

- image Docker plus lourde
- build plus lent
- cold start plus lent
- plus de RAM
- plus de fragilite sur certains environnements
- complexite inutile si le besoin produit reste simple

---

## 8. Problemes de dependances et incoherences actuelles

Le `requirements.txt` actuel:

```txt
nltk
fastapi
uvicorn
pydantic
PyJWT
python-dotenv
requests
jinja2
python-multipart
sentence-transformers
numpy
scikit-learn
PyPDF2>=3.0.0
python-docx>=0.8.11
slowapi
redis
```

### Incoherences detectees apres revue du code et verification terminal

1. `httpx` est utilise dans le code mais n'apparait pas explicitement dans `requirements.txt`.
2. `python-jose` est utilise pour le JWT, mais n'apparait pas explicitement dans `requirements.txt`.
3. `PyJWT` apparait dans `requirements.txt`, alors que la logique JWT visible du projet repose surtout sur `python-jose`.
4. `numpy` est declare en direct dans les requirements, mais n'est pas utilise directement dans le code applicatif. Il peut rester installe de maniere transitive si la pile RAG lourde est conservee, mais sa declaration directe merite d'etre reevalee.
5. Il existe deux clients HTTP dans le projet:
   - `requests`
   - `httpx`

### Lecture technique du probleme

Cela cree une situation ou:

- le build peut se passer correctement,
- la compilation Python peut se passer correctement,
- mais le runtime peut rester fragile si certaines dependances ne sont pas explicites.

Autrement dit, une partie des verifications terminales peut passer alors qu'un crash apparait plus tard au demarrage du service ou du conteneur.

### Pistes de correction possibles

Sans imposer de choix unique, les options suivantes semblent saines:

- declarer explicitement `httpx`,
- declarer explicitement `python-jose[cryptography]`,
- reevaluer la presence de `PyJWT`,
- reevaluer la declaration directe de `numpy`,
- harmoniser les appels HTTP autour d'un seul client si cela reste pertinent.

---

## 8.1 Point runtime observe lors du deploiement Docker

Lors des verifications de deploiement, le conteneur a ete observe dans un etat de redemarrage boucle.

### Ce que cela signifie

Quand un conteneur construit correctement mais redemarre immediatement apres lancement, cela oriente generalement vers:

- une dependance manquante au runtime,
- une erreur d'import au demarrage,
- une variable d'environnement manquante,
- une initialisation applicative qui echoue trop tot.

### Lecture la plus probable a ce stade

Au vu de la revue du code, les causes les plus credibles a verifier en priorite sont:

- `httpx` utilise mais non declare explicitement,
- `python-jose` utilise mais non declare explicitement,
- une incoherence de runtime autour du chargement des modules d'authentification ou des appels backend/LLM.

### Pistes de correction possibles

- corriger d'abord la liste des dependances explicites,
- reconstruire l'image Docker sur cette base nettoyee,
- verifier ensuite les logs de demarrage du conteneur pour distinguer:
  - dependance manquante,
  - erreur de configuration,
  - erreur de demarrage applicatif.

Cette approche permet de corriger les causes structurelles avant de conclure trop vite a un probleme purement Docker.

---

## 9. Evaluation production-readiness

## 9.1 Points positifs

- API FastAPI claire
- architecture separant plusieurs concerns
- panneau admin utile
- rate limiting en place
- cache Redis prevu
- deploiement Docker maintenant en place
- DeepSeek direct deja branche

## 9.2 Points faibles

- SQLite comme stockage principal
- pas de vraie base de donnees plus robuste
- RAG lourd pour un usage qui pourrait etre bien plus simple
- downloads NLTK au runtime dans certains modules
- dependances incoherentes
- pas de rechargement propre du RAG apres changement de chunks
- peu de garanties de tests / healthchecks / observabilite

## 9.3 Verdict

Le projet peut tourner en production **petite echelle** si on accepte un niveau de risque.  
Mais pour une production plus propre, il faut le rationaliser.

---

## 10. Recommandation de direction technique

Deux chemins sont possibles.

## Option A - Mode lean (recommande)

Objectif:

- chatbot plus leger
- plus simple a maintenir
- moins cher a build / deploy
- moins fragile

### Idee

Supprimer le RAG semantique local lourd, et s'appuyer sur:

- les chunks manuels
- la DB
- une recherche simple par mots / tags / score
- DeepSeek pour la formulation finale

### Benefices

- plus besoin de `sentence-transformers`
- plus besoin de `torch`
- plus besoin de `numpy`
- plus besoin de `scikit-learn`
- `nltk` peut aussi etre reduit ou supprime plus tard

### Cas d'usage cible

Si le chatbot repond principalement a:

- FAQ,
- contenus injectes par admin,
- questions support Hostay,
- informations guidees,

alors cette option est largement suffisante.

## Option B - Garder le RAG semantique local

Objectif:

- conserver les embeddings locaux
- conserver la recherche semantique locale

### Conditions minimales

Si cette voie est conservee, il faut au moins:

1. corriger la liste des dependances
2. gerer proprement le rechargement des chunks / embeddings apres changement admin
3. maitriser le poids CPU/GPU
4. precharger ce qui doit l'etre dans l'image
5. verifier que le gain produit justifie le poids

### Mon avis

Pour ce projet, sauf besoin fort de semantic search locale, cette option semble disproportionnee.

---

## 11. Pistes de travail pour le developpeur

## 11.1 Court terme - stabilisation minimale

1. **Corriger les requirements**
   - ajouter explicitement `httpx`
   - ajouter explicitement `python-jose[cryptography]`
   - reevaluer `PyJWT`
   - reevaluer la declaration directe de `numpy`
   - decider si on garde `requests` ou `httpx`, idealement un seul

2. **Supprimer les downloads runtime inutiles**
   - deplacer les ressources NLTK dans le build Docker si elles restent necessaires

3. **Verifier le cycle de vie des chunks**
   - aujourd'hui la DB change mais pas forcement le moteur semantique en memoire
   - il faut soit recharger, soit simplifier l'architecture

4. **Ajouter un endpoint health**
   - ex. `/health`
   - verifier:
     - app OK
     - DB OK
     - Redis optionnel

5. **Verifier le demarrage Docker de bout en bout**
   - distinguer ce qui passe en compilation de ce qui echoue au runtime,
   - verifier que l'image contient toutes les dependances effectivement importees,
   - verifier les logs de conteneur avant de conclure a un probleme de code plus profond.

## 11.2 Piste de simplification - chantier lean

1. retirer `sentence-transformers`
2. retirer `numpy`
3. retirer `scikit-learn`
4. retirer `nltk` si remplacable
5. garder:
   - chunks DB
   - recherche simple
   - DeepSeek

### Resultat attendu si cette option est retenue

- image plus legere
- deploiement plus rapide
- moins de RAM
- moins de risque
- moins de complexite pour un resultat metier probablement similaire

---

## 12. Proposition de requirements allege

Si on passe en mode lean, une base plus propre pourrait etre:

```txt
fastapi
uvicorn[standard]
pydantic
python-dotenv
httpx
python-jose[cryptography]
jinja2
python-multipart
slowapi
redis
PyPDF2>=3.0.0
python-docx>=1.0.0
```

Ensuite:

- `requests` peut etre retire si tout passe en `httpx`
- `PyJWT` peut etre retire si `python-jose` reste l'unique lib JWT
- `numpy` peut etre retire des requirements directs si le RAG lourd n'est plus conserve

### Variante minimale sans decision architecturale forte

Si l'objectif immediat est simplement de stabiliser le projet sans encore trancher entre RAG lean et RAG lourd, une autre approche possible serait:

```txt
nltk
fastapi
uvicorn[standard]
pydantic
python-dotenv
httpx
python-jose[cryptography]
requests
jinja2
python-multipart
sentence-transformers
scikit-learn
PyPDF2>=3.0.0
python-docx>=1.0.0
slowapi
redis
```

Dans cette variante:

- `httpx` et `python-jose` deviennent explicites,
- `PyJWT` peut etre retire,
- `numpy` n'est plus declare directement si elle reste deja fournie via la pile ML,
- `requests` peut etre conserve temporairement tant que la migration vers `httpx` n'est pas decidee.

---

## 13. Si on garde l'upload admin

L'upload admin reste une vraie fonctionnalite utile.

Il utilise:

- PDF
- DOCX
- decoupage en morceaux
- traduction vers anglais pour uniformiser le contenu

Donc si cette fonction reste:

- `PyPDF2` est justifie
- `python-docx` est justifie

En revanche, il n'est pas obligatoire de garder une stack RAG lourde juste pour avoir un upload admin.

---

## 14. Deploiement et infra

### Etat actuel

Le projet a ete oriente vers un deploiement **Docker sur VPS**, ce qui est une meilleure direction que l'installation directe des dependances Python dans un `.venv` sur le serveur.

### Ce qu'il faut garder

- build Docker dans CI/CD
- conteneur unique pour le chatbot
- volume persistant pour la DB SQLite si SQLite reste en place

### Ce qu'il faut encore envisager

- si la prod monte en charge:
  - migrer SQLite vers une vraie DB
  - mieux gerer la persistence et le multi-instance

---

## 15. Priorites recommandees

### Priorite 1

- nettoyer les requirements
- corriger les dependances explicites manquantes
- stabiliser le runtime
- confirmer la cause exacte du restart Docker apres correction des dependances

### Priorite 2

- choisir officiellement entre:
  - RAG lean
  - RAG semantique local

### Priorite 3

- si RAG lean:
  - retirer la stack ML lourde
- si RAG lourd:
  - rechargement embeddings
  - gestion lifecycle propre

### Priorite 4

- remplacer SQLite si la production devient serieuse

---

## 16. Synthese a partager au developpeur

### Message court

Les tests et verifications techniques realises sur l'espace de travail montrent que le projet est globalement fonctionnel, que la compilation Python passe, et que le socle applicatif est exploitable. En revanche, plusieurs points doivent etre clarifies ou corriges pour fiabiliser le runtime et le deploiement.

Les sujets principaux identifies sont:

- poids tres important de la stack RAG locale par rapport a la taille du projet,
- dependances explicites incomplètes ou incoherentes,
- ecart entre le chunking manuel / recherche simple et la couche RAG semantique,
- comportement de redemarrage du conteneur Docker indiquant probablement un probleme de runtime a fiabiliser.

### Lecture proposee

Le projet peut continuer dans deux directions raisonnables:

1. conserver le RAG lourd, mais en le stabilisant proprement,
2. simplifier l'architecture autour des chunks manuels, de la DB et d'une recherche plus legere.

Le document present suggere des pistes, mais ne tranche pas a la place du developpeur. L'objectif est d'expliquer les problemes observes, les zones fragiles, et les corrections possibles pour permettre une decision technique eclairee.

---

## 17. Checklist actionnable

### A faire maintenant

- [ ] Corriger `requirements.txt`
- [ ] Ajouter `httpx`
- [ ] Ajouter `python-jose[cryptography]`
- [ ] Verifier si `PyJWT` est encore necessaire
- [ ] Choisir `requests` ou `httpx`
- [ ] Ajouter `/health`
- [ ] Retirer downloads runtime si possible
- [ ] Documenter le choix RAG lean vs RAG lourd

### A faire si choix lean

- [ ] Retirer `sentence-transformers`
- [ ] Retirer `numpy`
- [ ] Retirer `scikit-learn`
- [ ] Retirer `nltk` si remplacable
- [ ] Conserver chunks admin + recherche simple

### A faire si choix RAG lourd

- [ ] Recharger embeddings apres modification admin
- [ ] Verifier la charge RAM/CPU
- [ ] Standardiser le build Docker ML
- [ ] Verifier pertinence produit de ce surcout

---

## 18. Conclusion

`khalid-chatbot` a une base exploitable et utile.  
Mais en l'etat, le projet est **plus lourd qu'il ne devrait l'etre**, et la partie la plus fiable n'est pas le semantic RAG lourd, mais plutot le **manual chunking + DB + fallback simple**.

Le meilleur prochain pas est de **rationaliser** le chatbot avant d'ajouter de la complexite.

Si on simplifie bien:

- on gagne en stabilite
- on gagne en vitesse de deploiement
- on gagne en cout infra
- on perd tres probablement peu, voire rien, sur la valeur produit reelle

