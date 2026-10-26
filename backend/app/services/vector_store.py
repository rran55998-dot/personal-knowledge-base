from __future__ import annotations

import json
import pickle
import re
from pathlib import Path
from typing import Optional

import jieba
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from app.config import VECTOR_DIR, get_settings


def _split_tokens(text: str) -> list[str]:
    return text.split()


class VectorStore:
    """本地 TF-IDF 向量库，无需 Docker / 外部向量服务。"""

    def __init__(self) -> None:
        get_settings()
        self.index_path = VECTOR_DIR / "tfidf_index.pkl"
        self.meta_path = VECTOR_DIR / "tfidf_meta.json"
        self.vectorizer: Optional[TfidfVectorizer] = None
        self.matrix = None
        self.chunk_ids: list[int] = []
        self.document_ids: list[int] = []
        self.chunk_indices: list[int] = []
        self.contents: list[str] = []
        self._load()

    def _tokenize(self, text: str) -> str:
        text = re.sub(r"\s+", " ", text or "").strip()
        if not text:
            return ""
        return " ".join(jieba.cut_for_search(text))

    def _load(self) -> None:
        if not self.index_path.exists() or not self.meta_path.exists():
            self.vectorizer = TfidfVectorizer(analyzer=_split_tokens)
            self.matrix = None
            self.chunk_ids = []
            self.document_ids = []
            self.chunk_indices = []
            self.contents = []
            return

        with self.index_path.open("rb") as f:
            payload = pickle.load(f)
        self.vectorizer = payload["vectorizer"]
        self.matrix = payload["matrix"]

        meta = json.loads(self.meta_path.read_text(encoding="utf-8"))
        self.chunk_ids = meta.get("chunk_ids", [])
        self.document_ids = meta.get("document_ids", [])
        self.chunk_indices = meta.get("chunk_indices", [])
        self.contents = meta.get("contents", [])

    def _save(self) -> None:
        VECTOR_DIR.mkdir(parents=True, exist_ok=True)
        with self.index_path.open("wb") as f:
            pickle.dump({"vectorizer": self.vectorizer, "matrix": self.matrix}, f)
        self.meta_path.write_text(
            json.dumps(
                {
                    "chunk_ids": self.chunk_ids,
                    "document_ids": self.document_ids,
                    "chunk_indices": self.chunk_indices,
                    "contents": self.contents,
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

    def rebuild(self, rows: list[dict]) -> None:
        self.chunk_ids = [int(r["id"]) for r in rows]
        self.document_ids = [int(r["document_id"]) for r in rows]
        self.chunk_indices = [int(r["chunk_index"]) for r in rows]
        self.contents = [str(r["content"]) for r in rows]

        if not rows:
            self.vectorizer = TfidfVectorizer(analyzer=_split_tokens)
            self.matrix = None
            self._save()
            return

        corpus = [self._tokenize(c) for c in self.contents]
        self.vectorizer = TfidfVectorizer(analyzer=_split_tokens)
        self.matrix = self.vectorizer.fit_transform(corpus)
        self._save()

    def search(
        self,
        query: str,
        top_k: int = 5,
        category_document_ids: Optional[set[int]] = None,
    ) -> list[dict]:
        if self.matrix is None or not self.contents or self.vectorizer is None:
            return []

        query_vec = self.vectorizer.transform([self._tokenize(query)])
        scores = cosine_similarity(query_vec, self.matrix).flatten()
        order = np.argsort(scores)[::-1]

        results: list[dict] = []
        for idx in order:
            score = float(scores[idx])
            if score <= 0:
                continue
            document_id = self.document_ids[idx]
            if category_document_ids is not None and document_id not in category_document_ids:
                continue
            results.append(
                {
                    "chunk_id": self.chunk_ids[idx],
                    "document_id": document_id,
                    "chunk_index": self.chunk_indices[idx],
                    "content": self.contents[idx],
                    "score": score,
                }
            )
            if len(results) >= top_k:
                break
        return results


_vector_store: Optional[VectorStore] = None


def get_vector_store() -> VectorStore:
    global _vector_store
    if _vector_store is None:
        _vector_store = VectorStore()
    return _vector_store


def reset_vector_store() -> None:
    global _vector_store
    _vector_store = None
