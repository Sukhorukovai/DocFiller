# -*- coding: utf-8 -*-
"""
Имена: организации, ИП, ФИО.

Патч S: если в тексте есть явная строка
  «Сокращённое наименование: <X>» / «Сокращённо: <X>»
и <X> содержит кавычки, то name = <X> без автогенерации из полного.
"""
import re

from ..core.text import norm_text
from ..core.morphology import (
    normalize_fio_case, clean_fio_words, to_short, to_nominative_fio,
)
from .patterns import (
    _ORG_PREFIX, _NAME_STOPWORDS,
    _RE_IP_FULL, _RE_IP_SHORT, _RE_IP_SHORT_ABBR,
    _RE_ORG_NAME_SHORT, _RE_ORG_NAME_FULL,
)


def _normalize_prefix(p: str) -> str:
    """ООО/ОАО/... с OCR-ошибками -> каноническое написание."""
    up = re.sub(r'\s+', '', p.upper())
    pairs = [
        (r'[ОO0]{3}', 'ООО'), (r'[ТT][СC][НH]', 'ТСН'),
        (r'[ТT][СC][ЖJ]', 'ТСЖ'), (r'[ДD][УY][КK]', 'ДУК'),
        (r'[ЖJ][СC][КK]', 'ЖСК'), (r'[ЖJ][КK]', 'ЖК'),
        (r'[СC][НH][ТT]', 'СНТ'), (r'[ОO][НH][ТT]', 'ОНТ'),
        (r'[НH][КK][ОO]', 'НКО'), (r'[ДD][НH][ПП]', 'ДНП'),
        (r'[ДD][НH][ТT]', 'ДНТ'), (r'[АA][ОO]', 'АО'),
        (r'[АA][НH][ОO]', 'АНО'), (r'[З3][АA][ОO]', 'ЗАО'),
        (r'[ПП][АA][ОO]', 'ПАО'), (r'[ИИ][ПП]', 'ИП'),
        (r'[ТT][ПП][ПП]', 'ТПП'),
    ]
    for rx, canon in pairs:
        if re.fullmatch(rx, up):
            return canon
    return p


def _name_looks_valid(name: str) -> bool:
    """
    Отбрасываем имена, у которых ПЕРВОЕ слово — служебное
    («БАНК», «ГОРОД», «ФИЛИАЛ», «ОБЛАСТЬ», ...). Остальные слова
    могут быть любыми: «АНАЛИТИЧЕСКИЙ ЦЕНТР ГОРОДА НИЖНЕГО
    НОВГОРОДА» — валидное имя, потому что первое слово неслужебное.
    """
    if not name:
        return False
    words = re.findall(r'[А-ЯЁA-Z]+', name.upper())
    if not words:
        return False
    if words[0] in _NAME_STOPWORDS:
        return False
    return True


_RE_INITIALS = re.compile(r'^[А-ЯЁ]\.\s*[А-ЯЁ]?\.?$')


def _looks_like_fio(s: str) -> bool:
    """
    True для:
      • «Коник Сергей Иванович»
      • «Романенко В.В.»
      • «Романенко В. В.»
    False если есть стоп-слова или хотя бы одно слово не похоже
    на имя/фамилию/инициалы.
    """
    if not s:
        return False
    parts = s.split()
    if not 2 <= len(parts) <= 3:
        return False
    for p in parts:
        if _RE_INITIALS.match(p):
            continue
        if not re.fullmatch(r'[А-ЯЁ][А-ЯЁа-яё\-]+', p):
            return False
        if p.upper() in _NAME_STOPWORDS:
            return False
    return True


def _is_person_short(s: str) -> bool:
    return bool(re.fullmatch(
        r'[А-ЯЁ][а-яё\-]+\s+[А-ЯЁ]\.\s*[А-ЯЁ]?\.?', s or ''))


# ---------------------------------------------------------------------
# Патч S: явные сокращённые/полные наименования
# ---------------------------------------------------------------------

_RE_SHORT_LABEL = re.compile(
    r'(?im)^\s*(?:Сокращ[её]нное\s+наименование|Сокращ[её]нно)\s*:\s*'
    r'([^\n]+)')

_RE_FULL_LABEL = re.compile(
    r'(?im)^\s*(?:Полное\s+наименование|'
    r'Полное\s+и\s+сокращ[её]нное\s+наименование)\s*:\s*'
    r'([^\n]+)')


def _has_quoted_body(s: str) -> bool:
    """Есть ли в строке фрагмент «...» или "..." с непустым телом."""
    return bool(re.search(r'[«"\u201C\u201E][^»"\u201D\u201F\n\r]{1,200}'
                          r'[»"\u201D\u201F]', s))


def _extract_explicit_short(text: str):
    """Возвращает name из «Сокращённое наименование: X» или None."""
    m = _RE_SHORT_LABEL.search(text)
    if not m:
        return None
    raw = norm_text(m.group(1)).strip(' ,;')
    if not raw or not _has_quoted_body(raw):
        return None
    # Отсечём вторичные ярлыки, если строка затянула соседние поля.
    raw = re.split(
        r'\s+(?:Полное|Сокращ[её]нн\w*|Адрес|ИНН|КПП|ОГРН|'
        r'Телефон|E-mail|Банк)\b',
        raw, maxsplit=1)[0].strip(' ,;')
    if not raw or not _has_quoted_body(raw):
        return None
    return raw


def _extract_explicit_full(text: str):
    """Возвращает full_name из «Полное наименование: X» или None.

    Требует, чтобы X начиналось с явного ОПФ — иначе не подставляем.
    """
    m = _RE_FULL_LABEL.search(text)
    if not m:
        return None
    raw = norm_text(m.group(1)).strip(' ,;')
    if not raw:
        return None
    # Убираем мусор между «наименование» и «:» — если он проскочил.
    raw = re.split(
        r'\s+(?:Сокращ[её]нн\w*|Адрес|ИНН|КПП|ОГРН|Телефон|E-mail|Банк)\b',
        raw, maxsplit=1)[0].strip(' ,;')
    if not re.match(
            r'(?i)Общество\s+с\s+ограниченной|'
            r'Автономная\s+некоммерческая|'
            r'Акционерное\s+общество|'
            r'Публичное\s+акционерное|'
            r'Товарищество\s+собственников',
            raw):
        return None
    return raw


# ---------------------------------------------------------------------
# Основной разбор
# ---------------------------------------------------------------------

def parse_names(text: str) -> dict:
    out = {"is_ip": False}

    # Патч S: сначала явные ярлыки — они важнее автогенерации.
    explicit_short = _extract_explicit_short(text)
    if explicit_short:
        out["name"] = explicit_short

    explicit_full = _extract_explicit_full(text)
    if explicit_full:
        out["full_name"] = explicit_full

    # 1) «Индивидуальный предприниматель ФИО»
    m_ip_full = _RE_IP_FULL.search(text)
    if m_ip_full:
        fio = normalize_fio_case(
            clean_fio_words(norm_text(m_ip_full.group(1))))
        if _looks_like_fio(fio):
            out["fio_full"] = fio
            if "name" not in out:
                out["name"] = f"ИП {fio}"
            out["is_ip"] = True

    # 2) «ИП ФИО»
    if not out["is_ip"]:
        m_ip = _RE_IP_SHORT.search(text)
        if m_ip:
            fio = normalize_fio_case(
                clean_fio_words(norm_text(m_ip.group(1))))
            if _looks_like_fio(fio):
                out["fio_full"] = fio
                if "name" not in out:
                    out["name"] = f"ИП {fio}"
                out["is_ip"] = True

    # 3) «ИП Иванов И. И.»
    if not out["is_ip"]:
        m_ip_sh = _RE_IP_SHORT_ABBR.search(text)
        if m_ip_sh:
            fio = normalize_fio_case(norm_text(m_ip_sh.group(1)))
            out["fio_full"] = fio
            out["fio_short"] = fio
            if "name" not in out:
                out["name"] = f"ИП {fio}"
            out["is_ip"] = True

    # Приведение родительного падежа ФИО к именительному.
    if out.get("is_ip") and out.get("fio_full"):
        fio_fixed = to_nominative_fio(out["fio_full"])
        if fio_fixed != out["fio_full"]:
            out["fio_full"] = fio_fixed
        if "name" not in out or out["name"].startswith("ИП "):
            out["name"] = f"ИП {out['fio_full']}"
        parts = out["fio_full"].split()
        if len(parts) >= 2:
            out["fio_short"] = to_short(out["fio_full"])

    # 4a) Каз[её]нное предприятие … «…» — прицельный регексп.
    _RE_KP_FULL = re.compile(
        r'(?i)(Каз[её]нное\s+предприятие[^«"\n\r\u201C\u201E]{0,80}'
        r'[«"\u201C\u201E]\s*'
        r'([^»"\u201D\u201F\n\r]{2,150}?)'
        r'\s*[»"\u201D\u201F])')
    if "full_name" not in out:
        m_kp = _RE_KP_FULL.search(text)
        if m_kp:
            out["full_name"] = norm_text(m_kp.group(1))
            if "name" not in out:
                out["name"] = out["full_name"]

    # 4) Полное наименование организации через общий регэксп.
    if "full_name" not in out:
        m_full = _RE_ORG_NAME_FULL.search(text)
        if m_full:
            prefix_raw = m_full.group(1)
            mid = norm_text(m_full.group(2)) if m_full.group(2) else ""
            body = norm_text(m_full.group(3))
            out["full_name"] = (
                f"{prefix_raw}{(' ' + mid) if mid else ''} «{body}»"
            )
            short_prefix = {
                "общество с ограниченной ответственностью": "ООО",
                "автономная некоммерческая организация": "АНО",
                "акционерное общество": "АО",
                "публичное акционерное общество": "ПАО",
                "товарищество собственников недвижимости": "ТСН",
                "товарищество собственников жилья": "ТСЖ",
            }.get(prefix_raw.lower())
            if short_prefix and "name" not in out:
                mid_short = mid
                if re.fullmatch(r'(?i:ГРУППА\s+КОМПАНИЙ)', mid_short):
                    mid_short = "ГК"
                if mid_short:
                    out["name"] = f"{short_prefix} {mid_short} «{body}»"
                else:
                    out["name"] = f"{short_prefix} «{body}»"
            if "name" not in out and re.match(
                    r'(?i)Каз[её]нное\s+предприятие', prefix_raw):
                out["name"] = out["full_name"]

    # 5) Сокращённое «ООО «Ника»» через общий регэксп.
    if "name" not in out:
        m_sh = _RE_ORG_NAME_SHORT.search(text)
        if m_sh:
            body = norm_text(m_sh.group(2))
            prefix = _normalize_prefix(m_sh.group(1))
            if _name_looks_valid(body):
                out["name"] = f"{prefix} «{body}»"
                if "full_name" not in out:
                    out["full_name"] = out["name"]

    # [kp-niriz-v7] прицельно: «Каз[её]нное предприятие …»
    if out.get("full_name", "").strip() in ("", "КП «НИРИЗ»"):
        _m_kp = re.search(
            r'(?i)(Каз[её]нное\s+предприятие[^\n\r]{5,200})',
            text)
        if _m_kp:
            _v_kp = re.split(
                r'\s*(?:\(|ИНН|ОГРН|КПП|Юр\.|Юридический|'
                r'Почтовый|Банк|Р/с|К/с|Телефон|Тел|Адрес|'
                r'e-mail|E-mail)',
                _m_kp.group(1), maxsplit=1)[0]
            _v_kp = norm_text(_v_kp).strip(' ,;:')
            if _v_kp:
                out["full_name"] = _v_kp
                out["name"] = _v_kp

    # [kp-niriz-v8] финальный проход: markdown → пробел, нормализация пробелов,
    # затем берём фрагмент "Каз[её]нное предприятие ... »" (первая закрывающая кавычка).
    if re.search(r'(?i)Каз[её]нное\s+предприятие', text):
        _text_kp8 = re.sub(r'[\*\|>]+', ' ', text)
        _text_kp8 = norm_text(_text_kp8)
        _m_kp8 = re.search(
            r'(?i)(Каз[её]нное\s+предприятие.{5,200}?)»',
            _text_kp8)
        if _m_kp8:
            _v_kp8 = (_m_kp8.group(1) + '»').strip(' ,;:')
            if len(_v_kp8) > len(out.get("full_name", "")):
                out["full_name"] = _v_kp8
                out["name"] = _v_kp8

    return out
