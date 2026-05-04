# rag_engine_v2.py - Advanced RAG Engine V2 (FIXED + DB Sync + Full Preprocessing)

import numpy as np
import string
import re
from typing import List, Dict
import logging

logger = logging.getLogger(__name__)

from sklearn.metrics.pairwise import cosine_similarity

import nltk
from nltk.tokenize import sent_tokenize, word_tokenize
from nltk.corpus import stopwords
from nltk.stem import SnowballStemmer

from llm_client import call_llm
from database import get_all_chunks

# =========================
# NLTK SETUP (safe)
# =========================
nltk.download('punkt', quiet=True)
nltk.download('punkt_tab', quiet=True)
nltk.download('stopwords', quiet=True)
nltk.download('wordnet', quiet=True)

# =========================
# RAG ENGINE CLASS
# =========================
class AdvancedRAGEngineV2:

    def __init__(self):
        self.chunks = []
        self.embeddings = []
        self.cache = {}
        self._model = None

        # Stop words (FR + EN + punctuation)
        self.stop_words = set(stopwords.words("english"))
        self.stop_words.update(stopwords.words("french"))
        self.stop_words.update(string.punctuation)

        # Stemmers
        self.stemmer_fr = SnowballStemmer("french")
        self.stemmer_en = SnowballStemmer("english")

    @property
    def model(self):
        if self._model is None:
            logger.info("⏳ Lazy loading embedding model...")
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
            logger.info("✅ Model loaded!")
        return self._model

    # =========================
    # 1. TEXT CLEANING
    # =========================
    def clean_text(self, text: str) -> str:
        """Nettoyage du texte brut"""
        # Lowercase
        text = text.lower()
        # Supprime URLs
        text = re.sub(r'http\S+|www\S+', '', text)
        # Supprime emails
        text = re.sub(r'\S+@\S+', '', text)
        # Supprime chiffres isolés
        text = re.sub(r'\b\d+\b', '', text)
        # Supprime caractères spéciaux sauf ponctuation utile
        text = re.sub(r'[^\w\s\.\!\?\,\;\:\-]', '', text)
        # Supprime espaces multiples
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    # =========================
    # 2. TOKENIZATION
    # =========================
    def tokenize(self, text: str) -> List[str]:
        """Word tokenization"""
        return word_tokenize(text, language='french')

    # =========================
    # 3. STOP WORD REMOVAL
    # =========================
    def remove_stopwords(self, tokens: List[str]) -> List[str]:
        """Supprime les stop words"""
        return [t for t in tokens if t.lower() not in self.stop_words and len(t) > 1]

    # =========================
    # 4. STEMMING
    # =========================
    def stem(self, tokens: List[str], lang: str = "french") -> List[str]:
        """Stemming des tokens"""
        stemmer = self.stemmer_fr if lang == "french" else self.stemmer_en
        return [stemmer.stem(t) for t in tokens]

    # =========================
    # PIPELINE COMPLET PREPROCESSING
    # =========================
    def preprocess(self, text: str) -> str:
        """Pipeline: Clean → Tokenize → StopWords → Stem → rejoin"""
        cleaned    = self.clean_text(text)
        tokens     = self.tokenize(cleaned)
        tokens     = self.remove_stopwords(tokens)
        tokens     = self.stem(tokens)
        return " ".join(tokens)

    # =========================
    # ADD DOCUMENT
    # =========================
    def add_document(self, doc_id: str, title: str, content: str, tags=None):
        """Ajoute un document et génère ses embeddings"""
        if tags is None:
            tags = []
        elif isinstance(tags, str):
            tags = [t.strip() for t in tags.split(",") if t.strip()]

        # Sentence tokenization (sur texte original — pas preprocessé)
        sentences = sent_tokenize(content)

        for i, sent in enumerate(sentences):
            if len(sent.strip()) < 5:
                continue

            # Texte original pour affichage
            original = sent.strip()
            # Texte preprocessé pour embedding
            preprocessed = self.preprocess(original)

            chunk = {
                "id": f"{doc_id}_{i}",
                "title": title,
                "content": original,        # ← original pour LLM
                "preprocessed": preprocessed,  # ← preprocessé pour debug
                "tags": tags
            }

            self.chunks.append(chunk)
            # Embedding sur texte original (SentenceTransformer gère mieux l'original)
            self.embeddings.append(self.model.encode(original))

        logger.info(f"✅ Added: {title} ({len(sentences)} chunks)")

    # =========================
    # SEARCH
    # =========================
    def search(self, query: str, top_k: int = 3) -> List[Dict]:
        """Recherche vectorielle par similarité cosinus"""
        if len(self.embeddings) == 0:
            return []

        # Preprocessing sur la query aussi
        query_clean = self.clean_text(query)
        query_emb   = self.model.encode(query_clean)

        scores = cosine_similarity([query_emb], self.embeddings)[0]

        ranked = sorted(
            enumerate(scores),
            key=lambda x: x[1],
            reverse=True
        )

        results = []
        for idx, score in ranked[:top_k]:
            if score > 0.2:
                results.append({
                    "chunk": self.chunks[idx],
                    "score": float(score)
                })

        return results

    # =========================
    # GET CONTEXT
    # =========================
    def get_context(self, query: str, top_k: int = 3) -> str:
        """Retourne le contexte formaté pour le LLM"""
        results = self.search(query, top_k)

        if not results:
            return ""

        return "\n\n".join(
            f"[{r['chunk']['title']}] {r['chunk']['content']}"
            for r in results
        )

    # =========================
    # QUERY (Pipeline complet)
    # =========================
    def query(self, question: str, debug: bool = False) -> str:
        """Pipeline complet: Cache → RAG → LLM"""
        # 1. Cache
        if question in self.cache:
            if debug: logger.info("⚡ Cache hit")
            return self.cache[question]

        # 2. Preprocess query
        q = question.lower().strip()
        faq_signals = ["what is", "c'est quoi", "comment", "how", "prix", "chno"]
        is_faq = any(s in q for s in faq_signals)

        # 3. Routing
        use_rag = not ("bonjour" in q or len(q.split()) < 3)

        # 4. Context
        context = self.get_context(question) if use_rag else ""

        # 5. Prompt
        if use_rag and context:
            prompt = f"""You are a precise AI assistant. Use ONLY the context below:

{context}

Question: {question}

Rules:
- Answer only using context
- If missing, say "I don't know"
- Be concise"""
        else:
            prompt = f"You are a helpful assistant. Question: {question}\nAnswer concisely."

        # 6. LLM Call
        response = call_llm(prompt)

        # 7. Cache store
        self.cache[question] = response
        return response

    # =========================
    # LOAD FROM DB
    # =========================
    def load_from_database(self):
        """Charge tous les chunks depuis la DB SQLite"""
        chunks = get_all_chunks()
        for chunk in chunks:
            self.add_document(
                doc_id=chunk["doc_id"],
                title=chunk["title"],
                content=chunk["content"],
                tags=chunk.get("tags", "")
            )
        logger.info(f"✅ Loaded {len(chunks)} chunks from database")


# =========================
# INSTANCE GLOBALE
# =========================
rag_engine = AdvancedRAGEngineV2()


# =========================
# INITIALISATION
# =========================
def init_kb():
    """Initialise la KB avec docs hardcoded + DB"""

    # 1️⃣ Docs hardcoded (fallback si DB vide)
    rag_engine.add_document("checkin", "Check-in Digital",
        "Le check-in se fait via code SMS envoyé avant arrivée.")
    rag_engine.add_document("reservation", "Réservation",
        "Les réservations sont faites en ligne avec paiement sécurisé.")
    rag_engine.add_document("urgence", "Urgence",
        "Contactez le concierge en cas de problème urgent.")

    # 2️⃣ Charge les chunks depuis la DB (admin panel)
    rag_engine.load_from_database()


# 🔥 Appel d'initialisation
init_kb()