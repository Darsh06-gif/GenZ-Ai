from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from sklearn.feature_extraction.text import HashingVectorizer
from sklearn.preprocessing import normalize


@dataclass(frozen=True)
class Embedder:
    dim: int = 1024

    def __post_init__(self) -> None:
        # HashingVectorizer's n_features must be 2**k
        if self.dim & (self.dim - 1) != 0:
            raise ValueError("dim must be a power of two for HashingVectorizer.")

    def _vectorizer(self) -> HashingVectorizer:
        return HashingVectorizer(
            n_features=self.dim,
            alternate_sign=False,
            norm=None,
            lowercase=True,
            stop_words="english",
            ngram_range=(1, 2),
        )

    def embed_texts(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, self.dim), dtype=np.float32)
        X = self._vectorizer().transform(texts)
        X = X.astype(np.float32)
        X = normalize(X, norm="l2", axis=1, copy=False)
        return X.toarray().astype(np.float32, copy=False)

    def embed_query(self, text: str) -> np.ndarray:
        v = self.embed_texts([text])
        return v[0] if len(v) else np.zeros((self.dim,), dtype=np.float32)


def vector_to_bytes(v: np.ndarray) -> bytes:
    v = np.asarray(v, dtype=np.float32)
    return v.tobytes(order="C")


def bytes_to_vector(b: bytes, dim: int) -> np.ndarray:
    v = np.frombuffer(b, dtype=np.float32)
    if v.size != dim:
        raise ValueError(f"Vector dim mismatch: expected {dim}, got {v.size}")
    return v

