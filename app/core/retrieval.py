from __future__ import annotations

import math
import re
import sqlite3
from dataclasses import dataclass

import numpy as np

from .db import fts_search
from .embeddings import bytes_to_vector
from .text_clean import normalize_query


@dataclass(frozen=True)
class RetrievedChunk:
    chunk_id: int
    page_number: int
    text: str
    score: float
    score_lexical: float | None = None
    score_semantic: float | None = None


_FTS_SPECIAL = re.compile(r"""[^\w\s]""", re.UNICODE)


def _fts_query(user_query: str) -> str:
    """
    Build a conservative FTS5 query:
    - remove punctuation
    - split into words
    - AND them together with prefix matching
    """
    q = normalize_query(user_query.lower())
    q = _FTS_SPECIAL.sub(" ", q)
    terms = [t for t in q.split(" ") if t]
    if not terms:
        return ""
    # prefix-match each term: term*
    return " AND ".join(f'"{t}"*' for t in terms[:10])


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    denom = (np.linalg.norm(a) * np.linalg.norm(b))
    if denom == 0.0:
        return 0.0
    return float(np.dot(a, b) / denom)


def retrieve(
    conn: sqlite3.Connection,
    *,
    document_id: str,
    query: str,
    embedder_dim: int,
    query_vector: np.ndarray,
    limit: int = 8,
    lexical_pool: int = 80,
) -> list[RetrievedChunk]:
    fts_q = _fts_query(query)
    lexical_rows: list[sqlite3.Row] = []
    if fts_q:
        try:
            lexical_rows = fts_search(conn, document_id=document_id, query=fts_q, limit=lexical_pool)
        except sqlite3.OperationalError:
            # Malformed FTS query; treat as no lexical hits.
            lexical_rows = []

    # Convert bm25 (lower is better) into a bounded lexical score in (0,1].
    lexical_by_id: dict[int, tuple[int, str, float]] = {}
    for r in lexical_rows:
        chunk_id = int(r["chunk_id"])
        bm25 = float(r["bm25_score"])
        lexical_score = 1.0 / (1.0 + max(0.0, bm25))
        lexical_by_id[chunk_id] = (int(r["page_number"]), str(r["text"]), lexical_score)

    # Fetch embeddings for lexical pool; if none, we can't do semantic scoring.
    semantic_scores: dict[int, float] = {}
    if lexical_by_id:
        rows = conn.execute(
            """
            SELECT e.chunk_id, e.dim, e.vector
            FROM embeddings e
            WHERE e.chunk_id IN (%s)
            """
            % (",".join("?" for _ in lexical_by_id)),
            tuple(lexical_by_id.keys()),
        ).fetchall()
        for r in rows:
            cid = int(r["chunk_id"])
            dim = int(r["dim"])
            if dim != embedder_dim:
                continue
            v = bytes_to_vector(r["vector"], dim)
            semantic_scores[cid] = _cosine(query_vector, v)

    # Combine scores. If semantic is missing, use lexical only.
    results: list[RetrievedChunk] = []
    for cid, (page, text, lex) in lexical_by_id.items():
        sem = semantic_scores.get(cid)
        if sem is None:
            score = lex
        else:
            # Weighted blend; lexical tends to be more precise on handwritten OCR.
            score = 0.65 * lex + 0.35 * max(0.0, sem)
        results.append(
            RetrievedChunk(
                chunk_id=cid,
                page_number=page,
                text=text,
                score=float(score),
                score_lexical=float(lex),
                score_semantic=float(sem) if sem is not None else None,
            )
        )

    results.sort(key=lambda x: x.score, reverse=True)
    return results[:limit]


def should_answer(hits: list[RetrievedChunk], *, min_score: float = 0.12) -> bool:
    if not hits:
        return False
    best = hits[0].score
    if best < min_score:
        return False
    return True

