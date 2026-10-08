# -*- coding: utf-8 -*-
"""
OCR и препроцессинг изображений.

Порядок:
  1. Автоориентация через tesseract OSD.
  2. Антиперекос через Hough-линии (детект медианного угла).
  3. Несколько бинаризаций (Otsu / adaptive) → несколько psm → берём
     результат с максимальным «ocr_score».
"""
import os
import re

from ..config import (
    TESSERACT_EXE, DESKEW_MIN_ANGLE, DESKEW_MAX_ANGLE,
)
from ..logging_setup import log

try:
    import pytesseract
    import cv2
    import numpy as np
    from PIL import Image
except ImportError:
    pytesseract = None


if pytesseract and os.path.isfile(TESSERACT_EXE):
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_EXE


# =====================================================================
# Доступность
# =====================================================================

def ocr_available() -> tuple[bool, str]:
    """(True, 'ok') или (False, причина)."""
    if pytesseract is None:
        return False, "pytesseract не установлен"
    if not os.path.isfile(TESSERACT_EXE):
        try:
            pytesseract.get_tesseract_version()
            return True, "ok"
        except Exception as e:
            return False, f"Tesseract не найден: {e}"
    return True, "ok"


# =====================================================================
# Препроцессинг
# =====================================================================

def to_gray(img):
    if img is None:
        return None
    if img.ndim == 3:
        return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return img


def auto_orient(img_bgr):
    """Поворачивает по OSD tesseract. Возвращает (img, angle_deg)."""
    if pytesseract is None or img_bgr is None:
        return img_bgr, 0
    try:
        osd = pytesseract.image_to_osd(
            img_bgr, config='--psm 0 -c min_characters_to_try=5')
        m = re.search(r'Rotate:\s*(\d+)', osd)
        if not m:
            return img_bgr, 0
        rot = int(m.group(1)) % 360
        if rot == 0:
            return img_bgr, 0
        if rot == 90:
            fixed = cv2.rotate(img_bgr, cv2.ROTATE_90_COUNTERCLOCKWISE)
        elif rot == 180:
            fixed = cv2.rotate(img_bgr, cv2.ROTATE_180)
        elif rot == 270:
            fixed = cv2.rotate(img_bgr, cv2.ROTATE_90_CLOCKWISE)
        else:
            return img_bgr, 0
        return fixed, rot
    except Exception:
        return img_bgr, 0


def detect_skew_angle(img_bgr) -> float:
    """Медианный угол наклона строк по Hough. 0.0 при неудаче."""
    if cv2 is None:
        return 0.0
    gray = to_gray(img_bgr)
    if gray is None or gray.size == 0:
        return 0.0

    h, w = gray.shape[:2]
    max_side = max(h, w)
    if max_side > 3000:
        scale = 3000.0 / max_side
        gray = cv2.resize(gray, (int(w * scale), int(h * scale)),
                          interpolation=cv2.INTER_AREA)

    try:
        blur = cv2.GaussianBlur(gray, (3, 3), 0)
        binary = cv2.adaptiveThreshold(
            blur, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY_INV, 31, 15)
    except Exception:
        return 0.0

    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (40, 2))
    try:
        dilated = cv2.dilate(binary, kernel, iterations=1)
    except Exception:
        return 0.0

    try:
        lines = cv2.HoughLinesP(
            dilated, 1, np.pi / 720.0, threshold=200,
            minLineLength=max(100, int(min(h, w) * 0.4)),
            maxLineGap=20)
    except Exception:
        lines = None

    if lines is None or len(lines) == 0:
        return 0.0

    angles = []
    for ln in lines:
        try:
            coords = np.asarray(ln, dtype=np.float64).ravel()
        except Exception:
            continue
        if coords.size < 4:
            continue
        x1, y1, x2, y2 = coords[0], coords[1], coords[2], coords[3]
        dx = x2 - x1
        dy = y2 - y1
        if dx == 0:
            continue
        ang = float(np.degrees(np.arctan2(dy, dx)))
        if abs(ang) > 45:
            continue
        angles.append(ang)

    if not angles:
        return 0.0

    median = float(np.median(angles))
    if abs(median) > DESKEW_MAX_ANGLE:
        return 0.0
    return median


def deskew_image(img_bgr, force: bool = False):
    """Выравнивает наклон. Возвращает (img, angle_deg)."""
    if cv2 is None or img_bgr is None:
        return img_bgr, 0.0
    angle = detect_skew_angle(img_bgr)
    if not force and abs(angle) < DESKEW_MIN_ANGLE:
        return img_bgr, 0.0

    (h, w) = img_bgr.shape[:2]
    center = (w // 2, h // 2)
    M = cv2.getRotationMatrix2D(center, angle, 1.0)
    border_val = (255, 255, 255) if img_bgr.ndim == 3 else 255
    rotated = cv2.warpAffine(
        img_bgr, M, (w, h),
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=border_val)
    return rotated, angle


def preprocess_for_ocr(img_bgr) -> list:
    """Набор вариантов изображения для OCR: original / oriented / deskewed."""
    if cv2 is None or img_bgr is None:
        return []
    variants = []
    seen_sizes = set()

    def _add(img):
        if img is None:
            return
        key = (img.shape[0] // 8, img.shape[1] // 8)
        if key in seen_sizes:
            return
        seen_sizes.add(key)
        variants.append(img)

    _add(img_bgr.copy())
    oriented, _ = auto_orient(img_bgr)
    _add(oriented)
    deskewed, _ = deskew_image(oriented)
    _add(deskewed)
    return variants


# =====================================================================
# Распознавание
# =====================================================================

def ocr_score(text: str) -> int:
    """Чем больше — тем «текстовее». Домены/маркеры дают бонус."""
    if not text:
        return 0
    sample = text[:2000]
    cyr = len(re.findall(r'[А-ЯЁа-яё]', sample))
    digits = len(re.findall(r'\d', sample))
    low = sample.lower()
    markers = ['инн', 'кпп', 'огрн', 'бик', 'директор', 'адрес',
               'банк', 'счет', 'счёт', 'р/с', 'к/с']
    marker_bonus = sum(200 for m in markers if m in low)
    return cyr * 2 + digits + marker_bonus + len(sample) // 4


def ocr_single(img_bgr, lang: str = "rus") -> str:
    """Один прогон: 3 варианта бинаризации × 3 psm → лучший по ocr_score."""
    if pytesseract is None or img_bgr is None:
        return ""
    gray = to_gray(img_bgr)
    if gray is None or gray.size == 0:
        return ""

    try:
        gray = cv2.normalize(gray, None, 0, 255, cv2.NORM_MINMAX)
    except Exception:
        pass

    variants = []
    try:
        _, otsu = cv2.threshold(
            gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        variants.append(otsu)
    except Exception:
        pass
    try:
        thr = cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY, 31, 15)
        variants.append(thr)
    except Exception:
        pass
    variants.append(gray)

    results = []
    for v in variants:
        for psm in ('6', '4', '3'):
            try:
                t = pytesseract.image_to_string(
                    v, lang=lang, config=f'--psm {psm}')
                if t and len(t.strip()) > 15:
                    results.append(t)
            except Exception:
                pass
    if not results:
        return ""
    return max(results, key=ocr_score)


def ocr_variants(img_bgr, lang: str = "rus") -> str:
    """Прогон по preprocess_for_ocr: лучший по ocr_score результат."""
    if pytesseract is None:
        return ""
    candidates = []
    for img in preprocess_for_ocr(img_bgr):
        h, w = img.shape[:2]
        if max(h, w) < 1800:
            img = cv2.resize(img, (w * 2, h * 2),
                             interpolation=cv2.INTER_CUBIC)
        text = ocr_single(img, lang=lang)
        if text and len(text.strip()) > 15:
            candidates.append(text)
    if not candidates:
        return ""
    return max(candidates, key=ocr_score)


def ocr_image(img_bgr) -> str:
    """Сначала русский, при неудаче — английский."""
    if pytesseract is None or img_bgr is None:
        return ""
    text = ocr_variants(img_bgr, lang="rus")
    if text and len(text.strip()) > 20:
        return text
    text_en = ocr_variants(img_bgr, lang="eng")
    if text_en and len(text_en.strip()) > len((text or '').strip()):
        return text_en
    return text or ""