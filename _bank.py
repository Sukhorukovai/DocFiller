# -*- coding: utf-8 -*-
"""Банк, р/с, к/с, БИК, Л/с, ИМК, соглашение."""
import re

from ..core.text import norm_text, digits_only
from .patterns import (
    _RE_RS, _RE_KS, _RE_BIK, _RE_LS, _RE_IMK, _RE_SOGL,
    _BANK_STRONG, _BANK_NEGATIVE, _BANK_FIELD_PREFIX, _BANK_FIELD_TAIL,
)


def clean_bank(s: str) -> str:
    if not s:
        return s
    # [bank-v19b] Фиксируем факт ведущего «в» ДО того, как его
    # срежут промежуточные re.sub (строки ниже). Иначе блок
    # [bank-v19] в конце видит уже «Филиале…» без «в» и
    # не возвращает его.
    _had_leading_v = bool(re.match(r'^\s*[Вв]\s+', s))
    s = re.sub(r'^[\s|,;\.]+', '', s)
    # [bank-v18] Однозначные метки — двоеточие опционально.
    s = re.sub(
        r'^(?:Полное\s+наименование\s+банка|Наименование\s+банка|'
        r'Наименование\s+Банка|Банковские\s+реквизиты|'
        r'Реквизиты|Место\s+нахожден\w*\s+банка)\s*:?\s*',
        '', s, flags=re.I)
    # [bank-v18] «Банк» / «Банка» — метка ТОЛЬКО с двоеточием.
    # Без ':' это часть имени («Банк ВТБ (ПАО)», «Банк Точка»).
    s = re.sub(
        r'^(?:Банка|Банк)\s*:\s*',
        '', s, flags=re.I)
    s = re.sub(r'^[а-яё]{0,3}\s*:\s*', '', s, flags=re.I)
    s = re.sub(r'^[\s"\'«»""]+', '', s)
    s = re.sub(r'^\s*в\s*[,\s]\s*', '', s)
    s = re.sub(
        r'^(?:(?:закупки|участника|ан|номер|№|код)\s+)+',
        '', s, flags=re.I)
    s = re.sub(r'^в\s+', '', s, flags=re.I)
    s = re.sub(r'^[\s"\'«»""]+', '', s)
    s = re.sub(r'\s*-\s*', '-', s)

    # [bank-clean-v10] срезать «Р/счет в» в начале...
    s = re.sub(
        r'^(?:Р\s*/\s*[сcСC](?:ч[её]т|ч)?|'
        r'Расч[её]т\w*\s+сч[её]т)\s+в\s+',
        '', s, flags=re.I)
    # ...и «: <15+ цифр>» в конце.
    s = re.sub(r'\s*:\s*\d{15,}\s*$', '', s)

    m = _BANK_FIELD_TAIL.search(s)
    if m:
        s = s[:m.start()]

    s = re.sub(r'[\s\.,;:»"\'`´‚„\-]+$', '', s)
    s = re.sub(r'\s+[^\s\d]$', '', s)
    s = re.sub(r'^[^\wА-ЯЁа-яё]+', '', s)
    s = re.sub(r'\s+', ' ', s).strip()

    open_q = s.count('«') + s.count('\u201C')
    close_q = s.count('»') + s.count('\u201D')
    if open_q > close_q and s:
        s = s.rstrip(' .,;:-') + '»'
    # [bank-v19] «в» пишем ТОЛЬКО если он был в реквизитах.
    # Снимаем ВСЕ ведущие «в » (0, 1 или 2), запоминая факт.
    # Возвращаем одно «в », только если:
    #   (а) в исходной строке было хотя бы одно «в»
    #   (б) остаток начинается с Филиал/Отделение.
    # Иначе — без ведущего «в».
    while True:
        m_v = re.match(r'^\s*[Вв]\s+', s)
        if not m_v:
            break
        s = s[m_v.end():]
    if _had_leading_v and re.match(
            r'^(?:Филиал|ФИЛИАЛ|филиал|'
            r'Отделени|ОТДЕЛЕНИ|'
            r'отделени)', s):
        s = 'в ' + s
    return s


def parse_bank_block(text: str) -> dict:
    out = {"extra_bank": []}
    text_flat = norm_text(text)

    rs = ks = bik = bank = ls = None
    extra = []

    m = _RE_RS.search(text_flat)
    if m:
        rs = digits_only(m.group(1))

    # [rs-fallback-v10] «Р/счет в <банк>: NNN» — название банка
    # между меткой и номером. _RE_RS такое не ловит.
    if not rs:
        _m_rs2 = re.search(
            r'Р\s*/\s*[сcСC](?:ч[её]т|ч)?\s+в\s+'
            r'[^\n]{2,120}?\s*:?\s*'
            r'(\d[\d\s]{18,25})',
            text_flat, re.I)
        if _m_rs2:
            rs = digits_only(_m_rs2.group(1))

    m = _RE_KS.search(text_flat)
    if m:
        ks = digits_only(m.group(1))

    m = _RE_BIK.search(text_flat)
    if m:
        bik = m.group(1)

    m = _RE_LS.search(text_flat)
    if m:
        ls = digits_only(m.group(1))
        extra.append(("Л/с", ls))

    m = _RE_IMK.search(text_flat)
    if m:
        extra.append(("ИМК", m.group(1)))

    m = _RE_SOGL.search(text_flat)
    if m:
        extra.append(("Соглашение", norm_text(m.group(1))))

    # 0) [bank-v22b] Банк ПЕРЕД р/с: «в Филиал… : <rs-digits>».
    # Случай: 'Р/счет в Филиале «Приволжский» АО «Банк ИНТЕЗА»
    # в г.Нижнем Новгороде: 40702810900002272151'.
    if not bank and rs:
        m0 = re.search(
            r'((?:в\s+)?(?:филиал\w*|Филиал\w*|Отделени\w*|'
            r'Банк|БАНК|АКБ|КБ|ОАО|ЗАО|ПАО|ООО|АО)\s+'
            r'[^\s\d].{2,400}?)'
            r'\s*:\s*' + re.escape(rs),
            text_flat, re.I | re.DOTALL)
        if m0:
            cand0 = clean_bank(m0.group(1))
            if (cand0 and _BANK_STRONG.search(cand0)
                    and not _BANK_NEGATIVE.search(cand0)):
                bank = cand0

    # 1) Банк после р/с — до ближайшего маркера поля.
    if rs:
        idx_rs = text_flat.find(rs)
        if idx_rs >= 0:
            after = text_flat[idx_rs + len(rs):]
            bm = re.match(
                r'\s*(?:в\s+)?(.+?)'
                r'(?=\s+(?:БИК|К\s*/\s*[сcСC]|Кор(?:р)?\.?\s*сч|'
                r'Корреспондентск|Место\s+нахожд|'
                r'Л\s*/\s*[сcСC]|Лицев|ИМК|'
                r'ИНН|КПП|ОГРН|ОГРНИП|ОКПО|ОКВЭД|ОКТМО|'
                r'Соглашение|Телефон|Тел\b|Факс|E-mail|Эл\.|$))',
                after, re.I)
            if bm:
                cand = clean_bank(bm.group(1))
                if (cand and _BANK_STRONG.search(cand)
                        and not _BANK_NEGATIVE.search(cand)):
                    bank = cand

    # 2) Ищем «Банк … БИК xxxxx».
    if not bank and bik:
        bm = re.search(
            r'((?:в\s+)?(?:филиал\w*|Филиал\w*|Отделение\w*|Банк|БАНК|АКБ|КБ|'
            r'ОАО|ЗАО|ПАО|ООО|АО)\s+[А-ЯЁA-Z][^,;{}]{2,200}?)'
            r'\s+(?:БИК\s*)?' + re.escape(bik),
            text_flat, re.I)
        if bm:
            cand = clean_bank(bm.group(1))
            if (cand and _BANK_STRONG.search(cand)
                    and not _BANK_NEGATIVE.search(cand)):
                bank = cand

    # 3) «в БАНК ... БИК xxxxx».
    if not bank and bik:
        bm = re.search(
            r'\sв\s+([^,;{}]{3,200}?)\s+БИК\s*' + re.escape(bik),
            text_flat, re.I)
        if bm:
            cand = clean_bank(bm.group(1))
            if (cand and _BANK_STRONG.search(cand)
                    and not _BANK_NEGATIVE.search(cand)):
                bank = cand

    # 4) Строка-кандидат «Банк: …» — берём первую подходящую.
    if not bank:
        for line in text.split('\n'):
            line_norm = norm_text(line)
            if not line_norm:
                continue
            if _BANK_FIELD_PREFIX.match(line_norm):
                continue
            if _BANK_NEGATIVE.search(line_norm):
                continue
            if _BANK_STRONG.search(line_norm):
                bank = clean_bank(line_norm)
                break

    out["rs"] = rs or ""
    out["ks"] = ks or ""
    out["bik"] = bik or ""
    out["bank"] = bank or ""
    out["extra_bank"] = extra
    return out
