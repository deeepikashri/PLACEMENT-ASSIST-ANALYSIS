"""
Resume PDF processing pipeline (spec section 6).

Pipeline:
    PDF -> is text extractable?
        YES -> extract with PyMuPDF
        NO (scanned/image-based) -> OCR fallback with Tesseract
    -> clean text

IMPORTANT: This module does NOT train any OCR model. Tesseract is used
purely as an off-the-shelf fallback OCR engine for scanned resumes.
"""

import io
import re
from typing import Tuple

try:
    import pymupdf as fitz  # PyMuPDF (modern import name)
except ImportError:
    import fitz  # PyMuPDF (legacy import name)

try:
    import pytesseract
    from PIL import Image
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False


class ResumeParsingError(Exception):
    """Raised when a resume PDF cannot be read or processed."""


MIN_CHARS_FOR_TEXT_PDF = 40  # below this we treat the page as "scanned"


def extract_text_from_pdf(file_bytes: bytes) -> str:
    """
    Extract raw text directly from a PDF using PyMuPDF.
    Returns an empty string if no extractable text layer exists.
    """
    try:
        doc = fitz.open(stream=file_bytes, filetype="pdf")
    except Exception as exc:
        raise ResumeParsingError(f"Could not open the PDF file: {exc}") from exc

    if doc.page_count == 0:
        raise ResumeParsingError("The uploaded PDF has no pages.")

    text_chunks = []
    for page in doc:
        text_chunks.append(page.get_text("text"))
    doc.close()
    return "\n".join(text_chunks)


def is_scanned_pdf(file_bytes: bytes) -> bool:
    """
    Heuristic: if PyMuPDF extracts very little text, the PDF is likely
    a scanned/image-based document rather than a real text layer.
    """
    try:
        text = extract_text_from_pdf(file_bytes)
    except ResumeParsingError:
        return True
    return len(text.strip()) < MIN_CHARS_FOR_TEXT_PDF


def extract_text_with_ocr(file_bytes: bytes, dpi: int = 300) -> str:
    """
    OCR fallback for scanned PDFs using Tesseract via pytesseract.
    Renders each PDF page to an image with PyMuPDF, then runs OCR.
    """
    if not OCR_AVAILABLE:
        raise ResumeParsingError(
            "OCR fallback is unavailable because 'pytesseract'/'Pillow' "
            "or the Tesseract binary is not installed on this machine. "
            "Please upload a resume with a selectable text layer instead."
        )

    try:
        doc = fitz.open(stream=file_bytes, filetype="pdf")
    except Exception as exc:
        raise ResumeParsingError(f"Could not open the PDF file for OCR: {exc}") from exc

    zoom = dpi / 72
    matrix = fitz.Matrix(zoom, zoom)
    ocr_text_chunks = []

    try:
        for page in doc:
            pix = page.get_pixmap(matrix=matrix)
            image = Image.open(io.BytesIO(pix.tobytes("png")))
            page_text = pytesseract.image_to_string(image)
            ocr_text_chunks.append(page_text)
    except Exception as exc:
        raise ResumeParsingError(f"OCR processing failed: {exc}") from exc
    finally:
        doc.close()

    return "\n".join(ocr_text_chunks)


def clean_resume_text(raw_text: str) -> str:
    """
    Normalize whitespace, remove control characters, and collapse
    repeated blank lines so downstream skill extraction sees consistent
    text.
    """
    if not raw_text:
        return ""

    text = raw_text.replace("\r", "\n")
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", " ", text)  # strip control chars
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def process_resume(file_bytes: bytes) -> Tuple[str, bool]:
    """
    Full pipeline entry point used by the Streamlit app.

    Returns:
        (cleaned_text, used_ocr)

    Raises:
        ResumeParsingError on any unrecoverable failure (invalid,
        empty, or corrupted PDF; OCR failure with no usable fallback).
    """
    if not file_bytes:
        raise ResumeParsingError("The uploaded file is empty.")

    used_ocr = False
    if is_scanned_pdf(file_bytes):
        raw_text = extract_text_with_ocr(file_bytes)
        used_ocr = True
    else:
        raw_text = extract_text_from_pdf(file_bytes)

    cleaned = clean_resume_text(raw_text)

    if not cleaned:
        raise ResumeParsingError(
            "No readable text could be extracted from this resume, even "
            "after OCR. Please try a clearer PDF or a resume with "
            "selectable text."
        )

    return cleaned, used_ocr
