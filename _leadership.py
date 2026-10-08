# -*- coding: utf-8 -*-
"""Должности и ФИО руководителей + «на основании Устава»."""
import re

from ..core.text import norm_text
from ..core.morphology import (
    normalize_fio_case, clean_fio_words, to_short,
    to_nominative_fio,
)
from .patterns import (
    _FIO_PATTERN, _LEAD_TAIL,
    _RE_BASIS_INLINE, _BASIS_STOP,
)
from ._names import _looks_like_fio, _is_person_short


# Приоритетный порядок должностей (чем выше — тем важнее).
_POS_ORDER = [
    (r'Генеральн\w+\s+директор\w*', 'генерального директора'),
    (r'Исполнительн\w+\s+директор\w*', 'исполнительного директора'),
    (r'(?<!Генерального\s)(?<!Исполнительного\s)(?<!вице-)(?<!Вице-)'
     r'\bДиректор\w*', 'директора'),
    (r'Председател\w+(?:\s+правлени\w+)?', None),
    (r'\bГИП\b', 'ГИП'),
    (r'Управляющ\w+', 'управляющего'),
    (r'Руководител\w+', 'руководителя'),
    (r'Владелец\s+компании', 'генерального директора'),
]


def _lead_regex(pos_pat: str, short: bool = False) -> re.Pattern:
    if short:
        fio = r'([А-ЯЁ][А-ЯЁа-яё\-]+\s+[А-ЯЁ]\.\s*[А-ЯЁ]?\.?)'
    else:
        fio = r'(' + _FIO_PATTERN + r')'
    return re.compile(
        r'(?<![А-ЯЁа-яё\(])' + pos_pat + _LEAD_TAIL + fio,
        re.UNICODE | re.IGNORECASE)


def _is_preceded_by_ip(text: str, start: int) -> bool:
    """Перед должностью стоит «ИП» / «Индивидуальный предприниматель»?"""
    pre = text[max(0, start - 60):start]
    return bool(re.search(
        r'(?:ИП|Индивидуальн\w+\s+предпринимател\w+)\s*$',
        pre, re.I))


def _pos_to_nom_gen(raw_nom: str):
    """Из «Генеральный директор» → nom + gen."""
    key = raw_nom.strip().lower()
    table = {
        'генеральный директор': 'генерального директора',
        'исполнительный директор': 'исполнительного директора',
        'директор': 'директора',
        'председатель правления': 'Председателя правления',
        'председатель': 'Председателя',
        'гип': 'ГИП',
        'управляющий': 'управляющего',
        'руководитель': 'руководителя',
        'владелец компании': 'генерального директора',
    }
    return table.get(key, raw_nom)


_POS_NOM_TABLE = {
    'генерального директора': 'Генеральный директор',
    'генеральный директор': 'Генеральный директор',
    'исполнительного директора': 'Исполнительный директор',
    'исполнительный директор': 'Исполнительный директор',
    'директора': 'Директор',
    'директор': 'Директор',
    'председателя правления': 'Председатель правления',
    'председатель правления': 'Председатель правления',
    'председателя': 'Председатель',
    'председатель': 'Председатель',
    'гип': 'ГИП',
    'управляющего': 'Управляющий',
    'управляющий': 'Управляющий',
    'руководителя': 'Руководитель',
    'руководитель': 'Руководитель',
    'владельца компании': 'Владелец компании',
    'владелец компании': 'Владелец компании',
}


def _to_nominative_position(pos_raw: str) -> str:
    return _POS_NOM_TABLE.get(
        (pos_raw or '').strip().lower(), pos_raw)


def find_position(text: str):
    """Оставлено для совместимости с внешним кодом."""
    for pos_pat, _ in _POS_ORDER:
        m = re.search(pos_pat, text, re.I)
        if m:
            raw = norm_text(m.group(0))
            return raw, _pos_to_nom_gen(raw)
    return None, None


def parse_leadership(text: str) -> dict:
    out = {}

    # 1) По приоритету должностей ищем руководителя.
    for pos_pat, _gen in _POS_ORDER:
        found = None
        for short in (False, True):
            rx = _lead_regex(pos_pat, short=short)
            for m in rx.finditer(text):
                fio = normalize_fio_case(
                    clean_fio_words(norm_text(m.group(1))))
                if short:
                    if not _is_person_short(fio):
                        continue
                else:
                    if not _looks_like_fio(fio):
                        continue
                if _is_preceded_by_ip(text, m.start()):
                    continue
                found = (fio, short)
                break
            if found:
                break
        if not found:
            continue

        fio, short = found
        if not short:
            fio = to_nominative_fio(fio)
        out["fio_full"] = fio
        out["fio_short"] = fio if short else to_short(fio)

        # Должность — берём в её исходном написании.
        m_pos = re.search(pos_pat, text, re.I)
        pos_matched = norm_text(m_pos.group(0)) if m_pos else pos_pat
        pos_nom = _to_nominative_position(pos_matched)
        out["position_nom"] = pos_nom
        out["position"] = _pos_to_nom_gen(pos_nom)
        break

    # 2) Основание.
    m_b = _RE_BASIS_INLINE.search(text)
    if m_b:
        basis = norm_text(m_b.group(1))
        basis = _BASIS_STOP.split(basis)[0]
        basis = basis.strip(' .,;:')
        if basis:
            out["basis"] = basis

    return out
