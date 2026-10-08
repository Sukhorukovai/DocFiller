# -*- coding: utf-8 -*-
"""
Фасад: extract_text(любой_файл) → строка.

Определяет тип по расширению и вызывает нужный ридер.
"""
from pathlib import Path

from .docx_reader import from_docx
from .pdf_reader import from_pdf
from .image_reader import from_image
from .word_bridge import doc_to_docx_via_word


def extract_text(path: Path) -> str:
    suffix = Path(path).suffix.lower()
    if suffix == ".docx":
        return from_docx(Path(path))
    if suffix == ".doc":
        return from_docx(doc_to_docx_via_word(Path(path)))
    if suffix == ".pdf":
        return from_pdf(Path(path))
    if suffix in (".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp"):
        return from_image(Path(path))
    raise ValueError(f"Неподдерживаемый формат: {suffix}")