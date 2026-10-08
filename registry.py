# -*- coding: utf-8 -*-
"""
Реестр доступных обработчиков документов.

Порядок важен: более специфичные идут первыми.
"""
from pathlib import Path

from .base import DocumentProcessor
from .contract.processor import ContractProcessor
from .act.processor import ActProcessor


DOCUMENT_TYPES: list[type[DocumentProcessor]] = [
    ActProcessor,
    ContractProcessor,
]


def find_processor(template_path: Path) -> DocumentProcessor:
    for cls in DOCUMENT_TYPES:
        if cls.matches(Path(template_path)):
            return cls()
    raise LookupError(f"Нет обработчика для шаблона: {template_path}")


def list_processors() -> list[type[DocumentProcessor]]:
    return list(DOCUMENT_TYPES)
