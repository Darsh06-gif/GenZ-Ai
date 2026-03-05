from __future__ import annotations

from dataclasses import dataclass

from .text_clean import clean_ocr_text


@dataclass(frozen=True)
class Chunk:
    page_number: int
    chunk_index: int
    text: str
    char_start: int
    char_end: int


def chunk_page_text(
    *,
    page_number: int,
    text: str,
    target_chars: int = 900,
    overlap_chars: int = 150,
) -> list[Chunk]:

    # 🔹 CLEAN OCR TEXT FIRST
    text = clean_ocr_text(text)

    t = text.strip()
    if not t:
        return []

    # Prefer paragraph boundaries
    paras = [p.strip() for p in t.split("\n\n") if p.strip() and len(p.strip()) > 25]

    chunks: list[Chunk] = []
    buf = ""
    buf_start = 0
    pos = 0
    idx = 0

    def flush(end_pos: int) -> None:
        nonlocal buf, buf_start, idx

        if not buf.strip():
            buf = ""
            return

        s = buf.strip()

        # remove noisy chunks
        if len(s) < 40:
            buf = ""
            return

        start = buf_start
        end = end_pos

        chunks.append(
            Chunk(
                page_number=page_number,
                chunk_index=idx,
                text=s,
                char_start=start,
                char_end=end,
            )
        )

        idx += 1

        if overlap_chars > 0 and len(s) > overlap_chars:
            tail = s[-overlap_chars:]
            buf = tail
            buf_start = max(0, end - overlap_chars)
        else:
            buf = ""

    for para in paras:

        found_at = t.find(para, pos)
        if found_at >= 0:
            pos = found_at

        para_start = pos
        para_end = pos + len(para)

        if not buf:
            buf_start = para_start
            buf = para

        elif len(buf) + 2 + len(para) <= target_chars:
            buf = f"{buf}\n\n{para}"

        else:
            flush(end_pos=para_start)

            if not buf:
                buf_start = para_start
                buf = para

            else:
                if len(buf) + 2 + len(para) <= target_chars:
                    buf = f"{buf}\n\n{para}"
                else:
                    flush(end_pos=para_start)
                    buf_start = para_start
                    buf = para

        pos = para_end

    flush(end_pos=len(t))

    # fallback sliding window
    if len(chunks) == 1 and len(chunks[0].text) > target_chars * 2:

        chunks = []
        s = t
        start = 0
        idx = 0
        step = max(1, target_chars - overlap_chars)

        while start < len(s):

            end = min(len(s), start + target_chars)
            chunk_text = s[start:end].strip()

            if len(chunk_text) > 40:
                chunks.append(
                    Chunk(
                        page_number=page_number,
                        chunk_index=idx,
                        text=chunk_text,
                        char_start=start,
                        char_end=end,
                    )
                )

                idx += 1

            if end >= len(s):
                break

            start += step

    return chunks