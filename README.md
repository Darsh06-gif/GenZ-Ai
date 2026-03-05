# Handwritten PDF Notes Understanding System (Offline)

Local study assistant that **OCRs handwritten PDFs**, stores them in a **local SQLite database**, and answers questions using **only your notes** with **page-cited sources**.

## What this does

- **OCR handwritten PDFs** page-by-page (offline)
- **Chunk + index** extracted text for fast search (SQLite FTS5)
- **Embeds chunks** into numeric vectors (offline hashing embeddings) for semantic-ish retrieval
- **Answers questions** with **citations** (page number + excerpt)
- Returns **"I don't have enough information"** when the notes don’t support an answer

## Requirements

- **Python 3.10+**
- **Tesseract OCR** installed locally (used by `pytesseract`)
  - Windows: install “Tesseract OCR” and ensure `tesseract.exe` is on PATH (or configure path in the app)

## Setup

Create a venv and install dependencies:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## Install Tesseract (Windows)

- Install “Tesseract OCR” (UB Mannheim build is common on Windows).
- Ensure `tesseract.exe` is on PATH, or copy its full path into the app’s **Settings → Tesseract path**.
- Verify:

```bash
tesseract --version
```

## Run the app (UI)

```bash
python -m streamlit run app\main.py
```

## Smoke test (no PDF required)

This just creates/migrates the local DB:

```bash
python -m scripts.smoke
```

## Data & offline notes

- Everything is stored locally in `data\` (database + cached page images).
- No network calls are required after install.

## Troubleshooting

- If OCR fails, verify Tesseract works:
  - `tesseract --version`
- If the app can’t find Tesseract, set the path in the UI (Settings).

