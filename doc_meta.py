# -*- coding: utf-8 -*-
"""
Определение типа документа и метаданных договора.

Используется в GUI, чтобы автоматически понимать:
  • что за файл лежит в строке «Реквизиты» (договор / акт / карточка);
  • если это договор — номер, дату и сумму договора.

Метаданные акта тянутся из договора (если акт делается из договора).
"""
import re


# ---------------------------------------------------------------------
# Тип документа
# ---------------------------------------------------------------------

def detect_doc_type(text: str) -> str:
    """
    'contract' | 'act' | 'card'

    Логика по первой значащей строке:
      • начинается с «Акт ...»  → 'act'
      • начинается с «Договор ...» → 'contract'
      • иначе → 'card'
    """
    if not text:
        return 'card'
    lines = [l.strip() for l in (text or '').split('\n') if l.strip()]
    if not lines:
        return 'card'
    # первые 3 непустые строки
    for line in lines[:3]:
        low = line.lower()
        if low.startswith('акт ') or low.startswith('акт\n'):
            return 'act'
        if low.startswith('договор ') or low.startswith('договор\n'):
            return 'contract'
    return 'card'


# ---------------------------------------------------------------------
# Номер договора
# ---------------------------------------------------------------------

# «Договор на выполнение работ № 9»
# «Договор № 10»
_RE_NO_1 = re.compile(
    r'Договор\b[^\n]{0,60}?№\s*([\d/А-Яа-яЁё\-]+)', re.IGNORECASE)
# «№ 9 от ...» в первых 400 символах
_RE_NO_2 = re.compile(r'№\s*([\d/]+)\s+от', re.IGNORECASE)


def extract_contract_no(text: str):
    if not text:
        return None
    head = text[:600]
    m = _RE_NO_1.search(head)
    if m:
        return m.group(1).strip()
    m = _RE_NO_2.search(head)
    if m:
        return m.group(1).strip()
    return None


# ---------------------------------------------------------------------
# Дата договора
# ---------------------------------------------------------------------

# ««04» октября 2026г.»
_RE_DATE = re.compile(
    r'«\s*\d{1,2}\s*»\s*[а-яё]+\s*\d{4}\s*г?\.?',
    re.IGNORECASE)


def extract_contract_date(text: str):
    if not text:
        return None
    m = _RE_DATE.search(text[:800])
    if m:
        return m.group(0).strip()
    return None


# ---------------------------------------------------------------------
# Сумма договора
# ---------------------------------------------------------------------

_RE_SUM_1 = re.compile(
    r'составляет\s+([\d\s]+)(?:[.,]\d+)?\s*(?:руб|₽)',
    re.IGNORECASE)
_RE_SUM_2 = re.compile(
    r'(\d[\d\s]{2,})\s*(?:руб|₽)', re.IGNORECASE)


def extract_contract_sum(text: str):
    if not text:
        return None
    m = _RE_SUM_1.search(text)
    if m:
        digits = re.sub(r'\D', '', m.group(1))
        if digits:
            return float(digits)
    m = _RE_SUM_2.search(text)
    if m:
        digits = re.sub(r'\D', '', m.group(1))
        if digits:
            return float(digits)
    return None
