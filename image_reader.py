# -*- coding: utf-8 -*-
"""Чтение изображения (.jpg/.png/.tif/...) через OCR."""
from pathlib import Path

from . import ocr as _ocr

try:
    import cv2
    import numpy as np
    from PIL import Image
except ImportError:
    cv2 = None


def from_image(path: Path) -> str:
    ok, msg = _ocr.ocr_available()
    if not ok:
        raise RuntimeError(msg)
    img = None
    try:
        pil = Image.open(str(path)).convert("RGB")
        img = cv2.cvtColor(np.array(pil), cv2.COLOR_RGB2BGR)
    except Exception:
        try:
            data = np.fromfile(str(path), dtype=np.uint8)
            img = cv2.imdecode(data, cv2.IMREAD_COLOR)
        except Exception:
            pass
    if img is None:
        raise ValueError(f"Не читается: {path}")

    from .docx_reader import normalize_table_lines
    return normalize_table_lines(_ocr.ocr_image(img))