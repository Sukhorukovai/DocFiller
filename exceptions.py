# -*- coding: utf-8 -*-
"""Исключения пакета. Пока используются мало, но задают иерархию."""


class ContractFillerError(Exception):
    """Базовое исключение."""


class RequisitesParseError(ContractFillerError):
    """Не удалось разобрать реквизиты."""


class TemplateProcessingError(ContractFillerError):
    """Ошибка обработки шаблона (не найден блок, неверный формат и т.п.)."""


class OcrUnavailableError(ContractFillerError):
    """OCR недоступен (нет tesseract / pytesseract)."""