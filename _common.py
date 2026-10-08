# -*- coding: utf-8 -*-
"""
Простые поля: ИНН, КПП, ОГРН, ОГРНИП, телефон, email, свид., ЕГРИП.

Фикс: если после «ОГРН» стоит 15 цифр — это ОГРНИП (у ИП).
Раньше _RE_OGRN_LOOSE обрезал такое до 13 цифр.
"""
import re

from ..core.text import norm_text, digits_only
from .patterns import (
    _RE_INN_KPP, _RE_INN, _RE_KPP,
    _RE_OGRNIP, _RE_OGRN, _RE_OGRN_LOOSE, _RE_OGRIP,
)


# ОГРН + 15 цифр — это ОГРНИП, даже если явный ОГРНИП в тексте не написан.
_RE_OGRN15 = re.compile(r'\bОГРН\w*\s*:?\s*(\d{15})', re.I)


def parse_common_fields(text: str) -> dict:
    out = {}

    m = _RE_INN_KPP.search(text)
    if m:
        out["inn"] = m.group(1)
        out["kpp"] = m.group(2)
    else:
        m = _RE_INN.search(text)
        if m:
            out["inn"] = m.group(1)
        m = _RE_KPP.search(text)
        if m:
            out["kpp"] = m.group(1)

    # Fallback: 10-значный ИНН + где-то 9 цифр рядом — считаем КПП.
    if not out.get("kpp") and out.get("inn") and len(out["inn"]) == 10:
        bik_val = None
        m_bik = re.search(r'\bБИК\b\s*:?\s*(\d{9})', text, re.I)
        if m_bik:
            bik_val = m_bik.group(1)
        for mm in re.finditer(r'(?<!\d)\d{9}(?!\d)', text):
            cand = mm.group(0)
            if cand != out["inn"] and cand != bik_val:
                out["kpp"] = cand
                break

    # Порядок: сначала самое специфичное.
    m = _RE_OGRNIP.search(text)
    if m:
        out["ogrn"] = m.group(1)
        out["ogrn_kind"] = "ОГРНИП"
    else:
        # «ОГРН» + 15 цифр → ОГРНИП (у ИП).
        m = _RE_OGRN15.search(text)
        if m:
            out["ogrn"] = m.group(1)
            out["ogrn_kind"] = "ОГРНИП"
        else:
            m = _RE_OGRIP.search(text)
            if m:
                out["ogrn"] = digits_only(m.group(1))
                out["ogrn_kind"] = "ОГРНИП"
            else:
                m = _RE_OGRN.search(text)
                if m:
                    out["ogrn"] = m.group(1)
                    out["ogrn_kind"] = "ОГРН"
                else:
                    m = _RE_OGRN_LOOSE.search(text)
                    if m:
                        out["ogrn"] = m.group(1)
                        out["ogrn_kind"] = "ОГРН"

    m = re.search(r'(?:Тел(?:ефон)?|т/ф|тел\.|факс)\s*[:.]?\s*'
                  r'(\+?[\d\s\-\(\)]{8,25})', text, re.I)
    if m:
        out["phone"] = norm_text(m.group(1))

    m = re.search(
        r'[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}', text)
    if m:
        out["email"] = m.group(0)

    m = re.search(r'Свидетельство\s*№?\s*:?\s*([^\n]+)', text, re.I)
    if m:
        out["witness"] = norm_text(m.group(1)).lstrip(': ').strip()

    m = re.search(r'ЕГРИП\s*:?\s*(\d[\d\s]{14,20})', text, re.I)
    if m:
        out["egrip"] = digits_only(m.group(1))

    return out
