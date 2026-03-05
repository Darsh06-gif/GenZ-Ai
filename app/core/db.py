from __future__ import annotations

import contextlib
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator


SCHEMA_SQL = """
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS documents (
  id TEXT PRIMARY KEY,
  filename TEXT NOT NULL,
  display_name TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS pages (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
  page_number INTEGER NOT NULL,
  text TEXT NOT NULL,
  UNIQUE(document_id, page_number)
);

CREATE TABLE IF NOT EXISTS chunks (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
  page_number INTEGER NOT NULL,
  chunk_index INTEGER NOT NULL,
  text TEXT NOT NULL,
  char_start INTEGER NOT NULL,
  char_end INTEGER NOT NULL,
  created_at TEXT NOT NULL,
  UNIQUE(document_id, page_number, chunk_index)
);

-- Keyword index (BM25) for fast lexical search
CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
  text,
  document_id UNINDEXED,
  page_number UNINDEXED,
  chunk_id UNINDEXED,
  tokenize = "unicode61"
);

-- Embeddings stored as float32 bytes
CREATE TABLE IF NOT EXISTS embeddings (
  chunk_id INTEGER PRIMARY KEY REFERENCES chunks(id) ON DELETE CASCADE,
  dim INTEGER NOT NULL,
  vector BLOB NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_chunks_doc ON chunks(document_id);
CREATE INDEX IF NOT EXISTS idx_pages_doc ON pages(document_id);
"""


@dataclass(frozen=True)
class Db:
    path: Path

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON;")
        return conn

    def migrate(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as conn:
            conn.executescript(SCHEMA_SQL)


@contextlib.contextmanager
def db_conn(db: Db) -> Iterator[sqlite3.Connection]:
    conn = db.connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def upsert_document(
    conn: sqlite3.Connection,
    *,
    document_id: str,
    filename: str,
    display_name: str,
    created_at: str,
) -> None:
    conn.execute(
        """
        INSERT INTO documents (id, filename, display_name, created_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
          filename=excluded.filename,
          display_name=excluded.display_name
        """,
        (document_id, filename, display_name, created_at),
    )


def get_document(conn: sqlite3.Connection, document_id: str) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT id, display_name, filename, created_at FROM documents WHERE id=?",
        (document_id,),
    ).fetchone()


def list_documents(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return list(
        conn.execute(
            "SELECT id, display_name, filename, created_at FROM documents ORDER BY created_at DESC"
        ).fetchall()
    )


def insert_page(
    conn: sqlite3.Connection,
    *,
    document_id: str,
    page_number: int,
    text: str,
) -> None:
    conn.execute(
        """
        INSERT INTO pages (document_id, page_number, text)
        VALUES (?, ?, ?)
        ON CONFLICT(document_id, page_number) DO UPDATE SET text=excluded.text
        """,
        (document_id, page_number, text),
    )


def insert_chunk(
    conn: sqlite3.Connection,
    *,
    document_id: str,
    page_number: int,
    chunk_index: int,
    text: str,
    char_start: int,
    char_end: int,
    created_at: str,
) -> int:
    cur = conn.execute(
        """
        INSERT INTO chunks (document_id, page_number, chunk_index, text, char_start, char_end, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(document_id, page_number, chunk_index) DO UPDATE SET
          text=excluded.text,
          char_start=excluded.char_start,
          char_end=excluded.char_end
        """,
        (document_id, page_number, chunk_index, text, char_start, char_end, created_at),
    )
    if cur.lastrowid:
        chunk_id = int(cur.lastrowid)
    else:
        row = conn.execute(
            """
            SELECT id FROM chunks
            WHERE document_id=? AND page_number=? AND chunk_index=?
            """,
            (document_id, page_number, chunk_index),
        ).fetchone()
        if row is None:
            raise RuntimeError("Failed to resolve chunk id after upsert.")
        chunk_id = int(row["id"])

    # FTS5 virtual tables don't reliably support standard UPSERT; do explicit replace.
    conn.execute("DELETE FROM chunks_fts WHERE rowid=?", (chunk_id,))
    conn.execute(
        """
        INSERT INTO chunks_fts (rowid, text, document_id, page_number, chunk_id)
        VALUES (?, ?, ?, ?, ?)
        """,
        (chunk_id, text, document_id, page_number, chunk_id),
    )
    return chunk_id


def upsert_embedding(
    conn: sqlite3.Connection,
    *,
    chunk_id: int,
    dim: int,
    vector_bytes: bytes,
) -> None:
    conn.execute(
        """
        INSERT INTO embeddings (chunk_id, dim, vector)
        VALUES (?, ?, ?)
        ON CONFLICT(chunk_id) DO UPDATE SET
          dim=excluded.dim,
          vector=excluded.vector
        """,
        (chunk_id, dim, sqlite3.Binary(vector_bytes)),
    )


def fts_search(
    conn: sqlite3.Connection,
    *,
    document_id: str,
    query: str,
    limit: int,
) -> list[sqlite3.Row]:
    # bm25() returns lower-is-better.
    return list(
        conn.execute(
            """
            SELECT chunk_id, page_number, text, bm25(chunks_fts) AS bm25_score
            FROM chunks_fts
            WHERE chunks_fts MATCH ? AND document_id=?
            ORDER BY bm25_score ASC
            LIMIT ?
            """,
            (query, document_id, limit),
        ).fetchall()
    )


def get_chunks_for_document(conn: sqlite3.Connection, document_id: str) -> list[sqlite3.Row]:
    return list(
        conn.execute(
            """
            SELECT c.id, c.page_number, c.chunk_index, c.text, c.char_start, c.char_end, e.dim, e.vector
            FROM chunks c
            LEFT JOIN embeddings e ON e.chunk_id = c.id
            WHERE c.document_id=?
            ORDER BY c.page_number ASC, c.chunk_index ASC
            """,
            (document_id,),
        ).fetchall()
    )

