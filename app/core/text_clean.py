import re


def normalize_query(text: str) -> str:
    """Normalize user query for retrieval."""
    text = text.lower()
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def clean_ocr_text(text: str) -> str:
    """Clean OCR output to remove noise from handwritten scans."""

    # remove OCR garbage symbols
    text = re.sub(r"[|_~`^]+", " ", text)

    # remove repeated punctuation
    text = re.sub(r"[!]{2,}", "!", text)

    # remove broken characters
    text = re.sub(r"\s+[^\w\s]{1,2}\s+", " ", text)

    # remove repeated single characters like | | |
    text = re.sub(r"(?:\b\w\b\s*){3,}", " ", text)

    # normalize spacing
    text = re.sub(r"\s+", " ", text)

    return text.strip()