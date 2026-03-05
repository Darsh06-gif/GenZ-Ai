from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

import fitz  # PyMuPDF
import pytesseract
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
from PIL import Image, ImageEnhance, ImageOps

from .text_clean import clean_ocr_text


# -----------------------------
# OCR SETTINGS
# -----------------------------

@dataclass(frozen=True)
class OcrSettings:
    dpi: int = 400
    lang: str = "eng"
    psm: int = 3
    oem: int = 1
    # Optional explicit path to tesseract.exe; if None, PATH is used.
    tesseract_cmd: str | None = None


@dataclass(frozen=True)
class OcrPage:
    page_number: int
    text: str


# -----------------------------
# UTILITIES
# -----------------------------

def file_sha256(path: Path) -> str:
    """Generate SHA256 hash for a file."""
    h = hashlib.sha256()

    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)

    return h.hexdigest()


def _validate_tesseract(settings: OcrSettings):
    """Ensure Tesseract executable exists and is usable."""

    # Default Windows installation path
    default_path = Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe")

    # Use provided path if available
    if settings.tesseract_cmd:
        exe = Path(settings.tesseract_cmd)
    else:
        exe = default_path

    if not exe.exists():
        raise RuntimeError(
            f"Tesseract executable not found at:\n{exe}\n\n"
            "Install it from:\n"
            "https://github.com/UB-Mannheim/tesseract/wiki"
        )

    # Configure pytesseract
    pytesseract.pytesseract.tesseract_cmd = str(exe)

    try:
        pytesseract.get_tesseract_version()
    except Exception as e:
        raise RuntimeError(
            "Tesseract OCR is installed but cannot run.\n"
            f"Executable path: {exe}\n"
            f"Error: {e}"
        )


# -----------------------------
# IMAGE RENDERING
# -----------------------------

def _render_page_to_pil(page: fitz.Page, *, dpi: int) -> Image.Image:
    """Render PDF page to PIL image."""
    zoom = dpi / 72
    mat = fitz.Matrix(zoom, zoom)

    pix = page.get_pixmap(matrix=mat, alpha=False)

    img = Image.frombytes(
        "RGB",
        (pix.width, pix.height),
        pix.samples
    )

    return img


# -----------------------------
# IMAGE PREPROCESSING
# -----------------------------

def _preprocess_for_ocr(img: Image.Image) -> Image.Image:
    """Improve image quality for OCR."""

    img = img.convert("RGB")

    img = ImageOps.grayscale(img)

    img = ImageEnhance.Contrast(img).enhance(2.0)

    img = ImageEnhance.Sharpness(img).enhance(1.5)

    img = ImageOps.autocontrast(img)

    # Binarization
    img = img.point(lambda p: 255 if p > 180 else 0)

    return img


# -----------------------------
# OCR PIPELINE
# -----------------------------

def ocr_pdf(
    pdf_path: Path,
    *,
    settings: OcrSettings,
    cache_dir: Path | None = None,
) -> Iterator[OcrPage]:

    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    _validate_tesseract(settings)

    cache_dir_path = None

    if cache_dir:
        cache_dir_path = Path(cache_dir)
        cache_dir_path.mkdir(parents=True, exist_ok=True)

    try:
        with fitz.open(str(pdf_path)) as doc:

            for i in range(doc.page_count):

                page = doc.load_page(i)

                img: Image.Image

                # -----------------------------
                # CACHE IMAGE
                # -----------------------------

                if cache_dir_path:

                    img_path = cache_dir_path / f"page_{i+1:04d}.png"

                    if img_path.exists():
                        with Image.open(img_path) as cached:
                            img = cached.copy()
                    else:
                        img = _render_page_to_pil(page, dpi=settings.dpi)
                        img.save(img_path)

                else:
                    img = _render_page_to_pil(page, dpi=settings.dpi)

                # -----------------------------
                # PREPROCESS
                # -----------------------------

                img = _preprocess_for_ocr(img)

                # -----------------------------
                # OCR
                # -----------------------------

                config = f"--oem {settings.oem} --psm {settings.psm}"

                try:
                    raw_text = pytesseract.image_to_string(
                        img,
                        lang=settings.lang,
                        config=config,
                    )

                except PermissionError as e:
                    raise RuntimeError(
                        "Windows blocked execution of Tesseract.\n"
                        "Try:\n"
                        "1. Running terminal as Administrator\n"
                        "2. Reinstalling Tesseract\n"
                        "3. Checking antivirus"
                    ) from e

                cleaned = clean_ocr_text(raw_text)

                yield OcrPage(
                    page_number=i + 1,
                    text=cleaned,
                )

    except Exception as e:
        raise RuntimeError(f"OCR failed for {pdf_path}\nError: {e}")