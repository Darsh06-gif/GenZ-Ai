from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .chunking import chunk_page_text
from .db import Db, db_conn, insert_chunk, insert_page, upsert_document, upsert_embedding
from .embeddings import Embedder, vector_to_bytes
from .ocr import OcrSettings, file_sha256, ocr_pdf


@dataclass(frozen=True)
class IngestResult:
    document_id: str
    pages: int
    chunks: int


def ingest_pdf(
    *,
    db: Db,
    pdf_path: Path,
    display_name: str | None,
    ocr_settings: OcrSettings,
    embedder: Embedder,
    cache_images_dir: Path | None = None,
) -> IngestResult:
    db.migrate()
    doc_id = file_sha256(pdf_path)
    created_at = datetime.now(timezone.utc).isoformat()

    name = display_name.strip() if display_name and display_name.strip() else pdf_path.name

    total_pages = 0
    total_chunks = 0

    with db_conn(db) as conn:
        upsert_document(
            conn,
            document_id=doc_id,
            filename=pdf_path.name,
            display_name=name,
            created_at=created_at,
        )

        # OCR all pages first; then embed chunks in a batch.
        chunk_texts: list[str] = []
        chunk_meta: list[tuple[int, int, int, int, int]] = []
        # (page_number, chunk_index, char_start, char_end, placeholder_chunk_id)

        for page in ocr_pdf(pdf_path, settings=ocr_settings, cache_dir=cache_images_dir):
            total_pages += 1
            insert_page(conn, document_id=doc_id, page_number=page.page_number, text=page.text)

            chunks = chunk_page_text(page_number=page.page_number, text=page.text)
            for ch in chunks:
                chunk_id = insert_chunk(
                    conn,
                    document_id=doc_id,
                    page_number=ch.page_number,
                    chunk_index=ch.chunk_index,
                    text=ch.text,
                    char_start=ch.char_start,
                    char_end=ch.char_end,
                    created_at=created_at,
                )
                total_chunks += 1
                chunk_texts.append(ch.text)
                chunk_meta.append((ch.page_number, ch.chunk_index, ch.char_start, ch.char_end, chunk_id))

        # Embeddings
        if chunk_texts:
            vectors = embedder.embed_texts(chunk_texts)
            for (_, _, _, _, chunk_id), v in zip(chunk_meta, vectors, strict=True):
                upsert_embedding(
                    conn,
                    chunk_id=chunk_id,
                    dim=embedder.dim,
                    vector_bytes=vector_to_bytes(v),
                )

    return IngestResult(document_id=doc_id, pages=total_pages, chunks=total_chunks)

