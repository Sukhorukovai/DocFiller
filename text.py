# -*- coding: utf-8 -*-
"""Утилиты нормализации текста. Без внешних зависимостей."""
import re


_INVISIBLE_RE = re.compile(r'[\u00AD\u200B\u200C\u200D\uFEFF]')
_SPACE_CHARS = ' \t\n\r\x0b\x0c\u00A0\u2009\u202F'


def clean_invisible(s: str) -> str:
    """Убирает невидимые символы (soft hyphen, ZWSP, BOM, ...)."""
    return _INVISIBLE_RE.sub('', s or '')


def norm_text(s: str) -> str:
    """Сжимает любые пробелы (в т.ч. NBSP) в один и обрезает края."""
    if not s:
        return s
    s = clean_invisible(s)
    s = re.sub(r'[' + re.escape(_SPACE_CHARS) + r']+', ' ', s)
    return s.strip()


def norm_cmp(s: str) -> str:
    """normalize + lowercase — для сравнений."""
    return norm_text(s or '').lower()


def digits_only(s: str) -> str:
    """Оставляет только цифры."""
    return re.sub(r'\D', '', s or '')


def is_zip(path) -> bool:
    """True, если файл — zip-контейнер (docx/xlsx/pptx)."""
    try:
        with open(path, 'rb') as f:
            return f.read(4) == b'PK\x03\x04'
    except Exception:
        return False


def normalize_newlines(s: str) -> str:
    """CRLF / CR → LF, плюс чистка невидимых символов."""
    if not s:
        return s
    s = clean_invisible(s)
    s = s.replace('\r\n', '\n').replace('\r', '\n')
    return s