"""
JARVIS v4 - Vector Store for Semantic Memory Retrieval (RAG)
"""

import os
import pickle
import numpy as np
from typing import List, Dict, Any, Optional, Callable
from config.settings import settings
from utils.logger import logger

class VectorStore:
    def __init__(self, index_name: str = "jarvis_memory"):
        self.index_name = index_name
        self.save_dir = settings.VECTOR_DB_DIR
        self.index_path = self.save_dir / f"{index_name}.faiss"
        self.meta_path = self.save_dir / f"{index_name}.pkl"
        
        self.documents: List[Dict[str, Any]] = []
        self.embeddings: List[np.ndarray] = []
        
        self._model = None
        self._faiss = None
        self._init_encoder()
        self._init_faiss()

    def _init_encoder(self):
        try:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
            logger.info("SentenceTransformer encoder loaded successfully.")
        except Exception as e:
            logger.warning(f"SentenceTransformer unavailable ({e}). Using lightweight dummy vector encoder.")

    def _init_faiss(self):
        try:
            import faiss
            self._faiss = faiss
            logger.info("FAISS initialized successfully.")
        except Exception as e:
            logger.warning(f"FAISS unavailable ({e}). Using numpy fallback for vector search.")
            
        self.load()

    def _encode(self, text: str) -> np.ndarray:
        if self._model:
            emb = self._model.encode([text])[0]
            return np.array(emb, dtype=np.float32)
        # Fallback hash-based embedding for fallback environments
        vec = np.zeros(384, dtype=np.float32)
        for i, char in enumerate(text):
            vec[i % 384] += ord(char)
        norm = np.linalg.norm(vec)
        return vec / (norm if norm > 0 else 1.0)

    def add_text(self, text: str, metadata: Optional[Dict[str, Any]] = None):
        """Encodes and indexes a text document into vector store."""
        emb = self._encode(text)
        self.embeddings.append(emb)
        self.documents.append({"text": text, "metadata": metadata or {}})
        self.save()

    def count(self) -> int:
        """Number of indexed documents."""
        return len(self.documents)

    def delete_where(self, predicate: Callable[[Dict[str, Any]], bool]) -> List[Dict[str, Any]]:
        """
        Removes every document for which `predicate(document)` is True.

        Deletion has to exist for "forget this" to be honest: without it the
        SQLite row would go while the embedding stayed searchable, so JARVIS
        would still recall something it said it had forgotten. It is a plain list
        plus a pickle here -- the FAISS index is rebuilt on each search -- so
        removal is filtering followed by a save, with the embeddings kept in
        lockstep with the documents.
        """
        if not self.documents:
            return []

        keep_docs: List[Dict[str, Any]] = []
        keep_embs: List[np.ndarray] = []
        removed: List[Dict[str, Any]] = []

        for index, document in enumerate(self.documents):
            try:
                doomed = bool(predicate(document))
            except Exception as e:
                logger.warning(f"Vector store delete predicate failed on item {index}: {e}")
                doomed = False

            if doomed:
                removed.append(document)
            else:
                keep_docs.append(document)
                if index < len(self.embeddings):
                    keep_embs.append(self.embeddings[index])

        if removed:
            self.documents = keep_docs
            self.embeddings = keep_embs
            self.save()
            logger.info(f"Removed {len(removed)} item(s) from vector memory.")
        return removed

    def delete_by_metadata(self, **filters: Any) -> List[Dict[str, Any]]:
        """Removes documents whose metadata matches every given key/value."""
        if not filters:
            return []

        def matches(document: Dict[str, Any]) -> bool:
            metadata = document.get("metadata") or {}
            return all(metadata.get(key) == value for key, value in filters.items())

        return self.delete_where(matches)

    def delete_matching_text(self, query: str, case_sensitive: bool = False) -> List[Dict[str, Any]]:
        """Removes documents whose text mentions `query` (for 'forget about X')."""
        needle = (query or "").strip()
        if not needle:
            return []
        if not case_sensitive:
            needle = needle.lower()

        def matches(document: Dict[str, Any]) -> bool:
            text = str(document.get("text", ""))
            return needle in (text if case_sensitive else text.lower())

        return self.delete_where(matches)

    def clear(self) -> int:
        """Empties the whole store. Returns how many items were dropped."""
        removed = len(self.documents)
        self.documents = []
        self.embeddings = []
        self.save()
        logger.info(f"Vector memory cleared ({removed} item(s)).")
        return removed

    def search(self, query: str, top_k: int = 3) -> List[Dict[str, Any]]:
        """Searches vector index for semantic similarity matching query."""
        if not self.embeddings:
            return []

        query_emb = self._encode(query)
        matrix = np.array(self.embeddings, dtype=np.float32)

        if self._faiss:
            dim = matrix.shape[1]
            index = self._faiss.IndexFlatIP(dim)
            # Normalize vectors for Cosine Similarity via Inner Product
            faiss_matrix = matrix / np.linalg.norm(matrix, axis=1, keepdims=True)
            faiss_query = query_emb / (np.linalg.norm(query_emb) or 1.0)
            index.add(faiss_matrix)
            scores, indices = index.search(np.array([faiss_query], dtype=np.float32), min(top_k, len(self.documents)))
            results = []
            for score, idx in zip(scores[0], indices[0]):
                if idx < len(self.documents) and idx >= 0:
                    results.append({
                        "score": float(score),
                        "text": self.documents[idx]["text"],
                        "metadata": self.documents[idx]["metadata"]
                    })
            return results

        # Numpy Fallback Cosine Similarity
        norms = np.linalg.norm(matrix, axis=1) * (np.linalg.norm(query_emb) or 1.0)
        sims = np.dot(matrix, query_emb) / np.maximum(norms, 1e-8)
        top_indices = np.argsort(sims)[::-1][:top_k]
        
        return [
            {
                "score": float(sims[i]),
                "text": self.documents[i]["text"],
                "metadata": self.documents[i]["metadata"]
            }
            for i in top_indices if i < len(self.documents)
        ]

    def save(self):
        """Persists vector embeddings and metadata to disk."""
        try:
            with open(self.meta_path, 'wb') as f:
                pickle.dump({"documents": self.documents, "embeddings": self.embeddings}, f)
        except Exception as e:
            logger.error(f"Failed to save vector store: {e}")

    def load(self):
        """Loads vector embeddings and metadata from disk."""
        if self.meta_path.exists():
            try:
                with open(self.meta_path, 'rb') as f:
                    data = pickle.load(f)
                    self.documents = data.get("documents", [])
                    self.embeddings = data.get("embeddings", [])
                logger.info(f"Loaded {len(self.documents)} items into vector store.")
            except Exception as e:
                logger.error(f"Failed to load vector store: {e}")
