import asyncio
import os
import re
from typing import List, Dict
import logging

from sklearn.metrics.pairwise import cosine_similarity
import nltk
from nltk.tokenize import sent_tokenize

from llm_client import call_llm_async
from database import get_all_chunks
from cache import cache

logger = logging.getLogger(__name__)

nltk.download('punkt', quiet=True)
nltk.download('punkt_tab', quiet=True)


class AdvancedRAGEngineV2:

    def __init__(self):
        self.chunks = []
        self.embeddings = []
        self.cache = {}
        self._model = None

    @property
    def model(self):
        if self._model is None:
            logger.info("Loading embedding model (fastembed)...")
            from fastembed import TextEmbedding
            self._model = TextEmbedding(
                model_name='sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2',
                cache_dir=os.getenv('FASTEMBED_CACHE_PATH', '/app/.cache/fastembed'),
            )
            logger.info("Embedding model ready.")
        return self._model

    def clean_text(self, text: str) -> str:
        text = text.lower()
        text = re.sub(r'http\S+|www\S+', '', text)
        text = re.sub(r'\S+@\S+', '', text)
        text = re.sub(r'[^\w\s\.\!\?\,\;\:\-]', '', text)
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    def add_document(self, doc_id: str, title: str, content: str, tags=None):
        if tags is None:
            tags = []
        elif isinstance(tags, str):
            tags = [t.strip() for t in tags.split(",") if t.strip()]

        sentences = sent_tokenize(content)
        count = 0
        for i, sent in enumerate(sentences):
            text = sent.strip()
            if len(text) < 5:
                continue
            self.chunks.append({
                "id": f"{doc_id}_{i}",
                "title": title,
                "content": text,
                "tags": tags,
            })
            # fastembed.embed() returns a generator — pull the single vector out
            self.embeddings.append(next(self.model.embed([text])))
            count += 1

        logger.info("Added '%s' (%d chunks)", title, count)

    def search(self, query: str, top_k: int = 3) -> List[Dict]:
        if not self.embeddings:
            return []

        query_emb = next(self.model.embed([self.clean_text(query)]))
        scores = cosine_similarity([query_emb], self.embeddings)[0]

        return [
            {"chunk": self.chunks[idx], "score": float(score)}
            for idx, score in sorted(enumerate(scores), key=lambda x: x[1], reverse=True)[:top_k]
            if score > 0.2
        ]

    async def get_context(self, query: str, top_k: int = 3) -> str:
        cache_key = f"rag_context_{query}"
        cached = await cache.get(cache_key)
        if cached:
            return cached

        # model.embed() runs ONNX inference — keep off the event loop
        results = await asyncio.to_thread(self.search, query, top_k)
        if not results:
            return ""

        context = "\n\n".join(
            f"[{r['chunk']['title']}] {r['chunk']['content']}"
            for r in results
        )
        await cache.set(cache_key, context, expire=3600)
        return context

    async def query(self, question: str) -> str:
        """Standalone RAG query (not used by main chat flow)."""
        cache_key = f"rag_query_{question}"
        cached = await cache.get(cache_key)
        if cached:
            return cached

        context = await self.get_context(question)
        if context:
            prompt = f"""You are a precise assistant. Use ONLY the context below.

{context}

Question: {question}

Rules:
- Answer only from the context
- If missing, say "I don't know"
- Be concise"""
        else:
            prompt = f"You are a helpful assistant. Answer concisely.\n\nQuestion: {question}"

        response = await call_llm_async(prompt)
        await cache.set(cache_key, response, expire=3600)
        return response

    def load_from_database(self):
        chunks = get_all_chunks()
        for chunk in chunks:
            self.add_document(
                doc_id=chunk["doc_id"],
                title=chunk["title"] or "",
                content=chunk["content"],
                tags=chunk.get("tags", ""),
            )
        logger.info("Loaded %d chunks from database", len(chunks))


rag_engine = AdvancedRAGEngineV2()


def init_kb():
    rag_engine.add_document("checkin", "Check-in Digital",
        "Le check-in se fait via code SMS envoyé avant arrivée.")
    rag_engine.add_document("reservation", "Réservation",
        "Les réservations sont faites en ligne avec paiement sécurisé.")
    rag_engine.add_document("urgence", "Urgence",
        "Contactez le concierge en cas de problème urgent.")
    rag_engine.load_from_database()


def init_rag_kb() -> None:
    """Load hardcoded KB + SQLite chunks (called once from app lifespan)."""
    init_kb()


def reload_rag_kb() -> None:
    """Clear in-memory state and reload from scratch (called after admin KB mutations)."""
    rag_engine.chunks.clear()
    rag_engine.embeddings.clear()
    rag_engine.cache.clear()
    init_kb()
    logger.info("RAG engine reloaded from DB")
