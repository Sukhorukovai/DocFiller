# -*- coding: utf-8 -*-
"""
Чтение .pdf в текст.

Приоритет:
  1. pdfplumber.extract_text()  (для PDF с текстовым слоем).
  2. fitz.get_text()            (иногда читает то, что pdfplumber не может).
  3. OCR (fitz.get_pixmap или pdfplumber.to_image) — для сканов.
"""
import re
from pathlib import Path

from ..logging_setup import log
from . import ocr as _ocr

try:
    import pymupdf as fitz
except ImportError:
    try:
        import fitz  # noqa: F811
    except ImportError:
        fitz = None

try:
    import pdfplumber
except ImportError:
    pdfplumber = None

try:
    import cv2
    import numpy as np
except ImportError:
    cv2 = None


# =====================================================================
# Проверка качества текстового слоя
# =====================================================================

def pdf_text_looks_ok(text: str) -> bool:
    """Эвристика: похоже ли, что извлечённый текст — осмысленный русский."""
    if not text:
        return False
    sample = text[:800]
    total = len(sample)
    if total < 80:
        return False
    cyr = len(re.findall(r'[А-ЯЁа-яё]', sample))
    if cyr / total < 0.40:
        return False
    if len(re.findall(r';\s*\n\s*;', sample)) >= 2:
        return False
    low = sample.lower()
    markers = ['инн', 'кпп', 'огрн', 'бик', 'директор', 'адрес', 'банк']
    if sum(1 for m in markers if m in low) < 2:
        return False
    return True


# =====================================================================
# Извлечение текстового слоя
# =====================================================================

def text_via_plumber(path: Path) -> str:
    if not pdfplumber:
        return ""
    try:
        with pdfplumber.open(path) as pdf:
            return "\n".join(
                (page.extract_text() or "") + "\n" for page in pdf.pages)
    except Exception as e:
        log.info("pdfplumber упал на %s: %s", path.name, e)
        return ""


def text_via_fitz(path: Path) -> str:
    if fitz is None:
        return ""
    try:
        doc = fitz.open(path)
        chunks = [page.get_text() + "\n" for page in doc]
        doc.close()
        return "\n".join(chunks)
    except Exception as e:
        log.info("fitz.get_text упал на %s: %s", path.name, e)
        return ""


# =====================================================================
# Рендер страницы в BGR (для OCR)
# =====================================================================

def page_to_bgr_fitz(page, dpi: int = 300):
    if fitz is None or cv2 is None:
        return None
    try:
        pix = page.get_pixmap(dpi=dpi)
        arr = np.frombuffer(pix.tobytes("png"), np.uint8)
        return cv2.imdecode(arr, cv2.IMREAD_COLOR)
    except Exception:
        return None


def page_to_bgr_plumber(page, resolution: int = 220):
    if pdfplumber is None or cv2 is None or np is None:
        return None
    try:
        im = page.to_image(resolution=resolution, antialias=True)
        pil = im.original.convert("RGB")
        arr = np.array(pil)
        return cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
    except Exception as e:
        log.info("pdfplumber.to_image упал: %s", e)
        return None


# =====================================================================
# OCR
# =====================================================================

def pdf_ocr(path: Path) -> str:
    """OCR страниц PDF. Порядок: pdfplumber.to_image → fitz.get_pixmap."""
    chunks = []
    if pdfplumber is not None and _ocr.pytesseract is not None:
        try:
            with pdfplumber.open(path) as pdf:
                for page in pdf.pages:
                    img = page_to_bgr_plumber(page)
                    if img is not None:
                        chunks.append(_ocr.ocr_image(img))
        except Exception as e:
            log.info("pdfplumber OCR упал на %s: %s", path.name, e)
    if not chunks and fitz is not None and _ocr.pytesseract is not None:
        try:
            doc = fitz.open(path)
            for page in doc:
                img = page_to_bgr_fitz(page, dpi=300)
                if img is not None:
                    chunks.append(_ocr.ocr_image(img))
            doc.close()
        except Exception as e:
            log.info("fitz OCR упал на %s: %s", path.name, e)
    return "\n".join(chunks)


# =====================================================================
# Главная функция
# =====================================================================

def from_pdf(path: Path) -> str:
    text_plumber = text_via_plumber(path)
    text_fitz = text_via_fitz(path)
    text = text_plumber if len(text_plumber) >= len(text_fitz) else text_fitz
    log.info("from_pdf(%s): plumber=%d fitz=%d",
             path.name, len(text_plumber), len(text_fitz))

    if pdf_text_looks_ok(text):
        from .docx_reader import normalize_table_lines
        return normalize_table_lines(text)

    ok, _ = _ocr.ocr_available()
    if not ok:
        from .docx_reader import normalize_table_lines
        return normalize_table_lines(text)

    ocr_text = pdf_ocr(path)
    log.info("from_pdf(%s): OCR=%d", path.name, len(ocr_text or ""))

    from .docx_reader import normalize_table_lines
    if len(ocr_text.strip()) > len(text.strip()):
        return normalize_table_lines(ocr_text)
    return normalize_table_lines(text)