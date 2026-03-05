from __future__ import annotations

import re
from dataclasses import dataclass

from .retrieval import RetrievedChunk
from .text_clean import normalize_query, clean_ocr_text


@dataclass(frozen=True)
class Answer:
    text: str
    sources: list["Source"]
    confidence: float


@dataclass(frozen=True)
class Source:
    page_number: int
    excerpt: str
    score: float


_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+")


def _best_excerpt(chunk_text: str, query: str, *, max_chars: int = 600) -> str:
    # 🔹 CLEAN OCR TEXT FIRST
    chunk_text = clean_ocr_text(chunk_text)

    q = normalize_query(query.lower())
    terms = [t for t in re.split(r"\W+", q) if len(t) >= 3]

    sents = _SENT_SPLIT.split(chunk_text.strip())

    if not sents:
        return chunk_text[:max_chars]

    def score_sent(s: str) -> int:
        ls = s.lower()
        return sum(1 for t in terms if t in ls)

    # remove garbage sentences
    filtered = []
    for s in sents:
        s = s.strip()

        if len(s) < 20:
            continue

        # skip OCR junk patterns
        if re.search(r"[|_~`^]{2,}", s):
            continue

        filtered.append(s)

    if not filtered:
        return chunk_text[:max_chars]

    sents_scored = sorted(filtered, key=score_sent, reverse=True)

    best = sents_scored[0].strip()

    if len(best) <= max_chars:
        return best

    return best[: max_chars - 1].rstrip() + "…"


def build_answer(query: str, hits: list[RetrievedChunk], *, max_sources: int = 6) -> Answer:
    if not hits:
        return Answer(text="I don't have enough information.", sources=[], confidence=0.0)

    top = hits[:max_sources]

    excerpts = [_best_excerpt(h.text, query) for h in top]

    if all(len(e.strip()) < 25 for e in excerpts):
        return Answer(text="I don't have enough information.", sources=[], confidence=0.0)

    answer_text = "\n\n".join(excerpts)

    sources = [
        Source(
            page_number=h.page_number,
            excerpt=_best_excerpt(h.text, query),
            score=h.score,
        )
        for h in top
    ]

    confidence = float(top[0].score)

    return Answer(
        text=answer_text,
        sources=sources,
        confidence=confidence,
    )