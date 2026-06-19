"""Простое векторное хранилище на numpy.

Для базы знаний фонда (тысячи чанков) полноценная векторная БД не нужна —
косинусный поиск перебором в numpy работает мгновенно и без лишних зависимостей.

Индекс хранится в двух файлах:
  data/index/vectors.npy      — матрица нормированных векторов (N, D)
  data/index/metadata.jsonl   — метаданные чанков (text, source, title, lang)
"""
import json

import numpy as np

from src.config import INDEX_DIR

VECTORS_PATH = INDEX_DIR / "vectors.npy"
METADATA_PATH = INDEX_DIR / "metadata.jsonl"


def _normalize(matrix: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    return matrix / (norms + 1e-8)


class VectorStore:
    def __init__(self) -> None:
        self.vectors: np.ndarray | None = None  # (N, D), нормированы
        self.metadata: list[dict] = []

    def add(self, vectors: list[list[float]], metadatas: list[dict]) -> None:
        arr = _normalize(np.asarray(vectors, dtype=np.float32))
        self.vectors = arr if self.vectors is None else np.vstack([self.vectors, arr])
        self.metadata.extend(metadatas)

    def search(self, query_vector: list[float], top_k: int = 5) -> list[tuple[dict, float]]:
        """Возвращает [(метаданные, score), ...] по убыванию косинусной близости."""
        if self.vectors is None or not self.metadata:
            return []
        query = np.asarray(query_vector, dtype=np.float32)
        query = query / (np.linalg.norm(query) + 1e-8)
        scores = self.vectors @ query
        top_idx = np.argsort(-scores)[:top_k]
        return [(self.metadata[i], float(scores[i])) for i in top_idx]

    def save(self) -> None:
        if self.vectors is not None:
            np.save(VECTORS_PATH, self.vectors)
        with open(METADATA_PATH, "w", encoding="utf-8") as f:
            for meta in self.metadata:
                f.write(json.dumps(meta, ensure_ascii=False) + "\n")

    @classmethod
    def load(cls) -> "VectorStore":
        store = cls()
        if VECTORS_PATH.exists() and METADATA_PATH.exists():
            store.vectors = np.load(VECTORS_PATH)
            with open(METADATA_PATH, encoding="utf-8") as f:
                store.metadata = [json.loads(line) for line in f if line.strip()]
        return store

    def __len__(self) -> int:
        return len(self.metadata)
