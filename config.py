# -*- coding: utf-8 -*-
"""
Общие константы.

Вынесено из старого main.py, чтобы не тащить зависимости при импорте
в модули, которым нужны только эти числа/строки.
"""
import os

# Путь к tesseract.exe на Windows. Если файла нет — pytesseract ищет в PATH.
TESSERACT_EXE = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

# Цвет, которым подсвечиваются заменённые фрагменты в Word.
RED_HEX = "FF0000"

# Длина итоговой подписи «____________ / ФИО /».
SIGNATURE_TOTAL_LEN = 38

# Порог и потолок угла выравнивания при OCR.
DESKEW_MIN_ANGLE = 0.3
DESKEW_MAX_ANGLE = 20.0

# Поддерживаемые расширения файлов реквизитов.
SUPPORTED_REQ_SUFFIXES = (
    ".doc", ".docx", ".pdf",
    ".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp",
)

# Поддерживаемые расширения шаблонов документов.
SUPPORTED_TPL_SUFFIXES = (".doc", ".docx")


def tesseract_is_configured() -> bool:
    """True, если нашли tesseract.exe по известному пути."""
    return os.path.isfile(TESSERACT_EXE)