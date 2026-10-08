# -*- coding: utf-8 -*-
"""Адреса: метки, склейки, мусор."""
import re

from ..core.text import norm_text
from .patterns import (
    _ADDR_LABELS,
    _RE_ADDR_LINE, _RE_ADDR_LINE_NO_COLON, _RE_ADDR_LINE_GLUED,
    _RE_ADDR_LINE_EMPTY,
    _ADDR_STOP,
)


_ADDR_LABEL_CANON = [
    (re.compile(r'Юр\.?\s*адрес|Юридический\s+адрес', re.I),
     'Юридический адрес'),
    (re.compile(rf'Место[\s\'’`´\-]*нахождения|Местонахождение', re.I),
     'Юридический адрес'),
    (re.compile(rf'Фактическое\s+место[\s\'’`´\-]*нахождения', re.I),
     'Фактический адрес'),
    (re.compile(r'Почтовый\s+адрес', re.I), 'Почтовый адрес'),
    (re.compile(r'Фактический\s+адрес|Фактич\.?\s*адрес', re.I),
     'Фактический адрес'),
    (re.compile(r'^Адрес$', re.I), 'Юридический адрес'),
]

_NON_ADDR_LABELS = ('электронной почты', 'e-mail', 'email', 'эл.',
                    'адрес сайта')


def canon_addr_label(raw: str) -> str:
    for rx, canon in _ADDR_LABEL_CANON:
        if rx.search(raw):
            return canon
    return raw


_ADDR_VALUE_NOISE = re.compile(
    r'(электронной\s+почты|учредител|сведения|'
    r'фирменное\s+наименование|организационно-правовая|'
    r'банковские\s+реквизиты|наименование\s+банка|'
    r'платежные\s+реквизиты|место\s+жительства\s*\(для|'
    r'код\s+подразделения|паспорт\s+\d|выдан\s+УВД|'
    r'виды\s+экономической\s+деятельности)',
    re.I)


def addr_value_is_noise(value: str) -> bool:
    if not value:
        return True
    return bool(_ADDR_VALUE_NOISE.search(value))


_CONTINUATION_START_RE = re.compile(
    r'^(?:г\.|город|ул\.|улица|пр-кт|проспект|пр\.|переулок|'
    r'пер\.|шоссе|ш\.|наб\.|набережная|бул\.|бульвар|б-р|'
    r'пл\.|площадь|мкр|микрорайон|д\.|дом|корп|корпус|'
    r'пом\.|помещение|кв\.|квартира|оф\.|офис|стр\.|строение|'
    r'лит\.|литера|[А-ЯЁ][а-яё]+,)',
    re.I)


def _looks_like_addr_continuation(value: str) -> bool:
    if not value:
        return False
    return bool(_CONTINUATION_START_RE.match(value))


def _clean_addr_value(v: str) -> str:                                # [addr-clean-v2]
    if not v:
        return v
    # Убрать только предлоги/союзы, НЕ трогая «г.», «д.», «ул.», «кв.» и т.п.
    v = re.sub(r'\s+(?:в|на|и|с|по|из|от|до|для|к)\s+(?=[А-ЯЁ])',
               ' ', v)
    # «дом№ 10В-21» → «дом № 10В-21»
    v = re.sub(r'\bдом\s*№\s*', 'дом № ', v)
    # «г.Н.Новгород» → «г. Н. Новгород»
    v = re.sub(r'\bг\.\s*([А-ЯЁ])', r'г. \1', v)
    v = re.sub(r'\bН\.\s*Новгород\b', 'Н. Новгород', v)
    # «пом: 2» → «пом. 2», «кв : 5» → «кв. 5», «оф:» → «оф.»
    v = re.sub(r'\b(пом|кв|оф|корп|стр|лит|д|г|ул|пер|пр-кт)\s*:\s*',
               r'\1. ', v)
    # «пом. 2.» → «пом. 2» (лишняя точка перед закрывающей или в конце)
    v = re.sub(r'(\b(?:пом|кв|оф|корп|стр|лит)\.)\s*(\d+)\.',
               r'\1 \2', v)
    # сохранить индекс в начале адреса, если он не разбит
    m = re.match(r'^(\d{6})\s*[, ]?\s*(.*)$', v)
    if m:
        v = m.group(1) + ', ' + m.group(2).lstrip(' ,')
    v = re.sub(r'\s+', ' ', v).strip(' .,;:')
    # вернём точку после «пом», если есть число
    v = re.sub(r'\bпом\s+(\d+)', r'пом. \1', v)
    v = re.sub(r'\bпом\.\s*(\d+)', r'пом. \1', v)
    return v


def _merge_addr_fragments(items):
    result = []
    for label, val in items:
        val = _clean_addr_value(val)
        if addr_value_is_noise(val):
            continue
        if result:
            prev_label, prev_val = result[-1]
            if (prev_label == label
                    and _looks_like_addr_continuation(val)
                    and not _looks_like_addr_continuation(prev_val)):
                merged = prev_val.rstrip(' ,') + ' ' + val.lstrip(' ,')
                result[-1] = (prev_label, merged)
                continue
        result.append((label, val))
    return result


_OTHER_ADDR_LABEL_RE = re.compile(
    r'^\s*(?:' + _ADDR_LABELS + r')\s*:', re.I)


def _merge_addr_labels_with_value(text: str) -> str:
    """Патч Q: «Юридический адрес:» + значение ниже → одна строка."""
    if not text:
        return text
    lines = text.split('\n')
    out = []
    i = 0
    while i < len(lines):
        cur = lines[i]
        m = _RE_ADDR_LINE_EMPTY.match(cur)
        if m:
            j = i + 1
            while j < len(lines) and not lines[j].strip():
                j += 1
            if j < len(lines):
                nxt = lines[j].strip()
                if nxt and not _OTHER_ADDR_LABEL_RE.match(nxt):
                    out.append(cur.rstrip() + ' ' + nxt)
                    i = j + 1
                    continue
        out.append(cur)
        i += 1
    return '\n'.join(out)


# --- PDF-таблицы (форма-анкета): слипшиеся поля -----------------------
_PDF_TABLE_FIELDS = re.compile(                                       # [addr-pdf-patch]
    r'(\d{1,2})\s+(?=(?:'
    r'Полное\s+и\s+сокращ[её]нное|'
    r'Организационно-правовая|'
    r'Место\s+нахождения|'
    r'Фактическое\s+место|'
    r'Почтовый\s+адрес|'
    r'Место\s+жительства|'
    r'Телефон|Факс|'
    r'Учредители|'
    r'Виды\s+экономической|'
    r'Банковские\s+реквизиты'
    r'))',
    re.IGNORECASE)


def _preprocess_pdf_table(text: str) -> str:                          # [addr-pdf-patch]
    """Расставляет переводы строк перед «N Поле» в PDF-анкетах."""
    if not text:
        return text
    return _PDF_TABLE_FIELDS.sub(r'\n\1 ', text)


# --- Адрес без метки: «603159, Нижний Новгород г, Волжская наб, дом№ 10В-21» ---
_RE_BARE_ADDRESS = re.compile(                                        # [addr-bare-v4]
    r'^\s*(\d{6})\s*[,.]?\s*'
    r'([А-ЯЁ][А-ЯЁа-яё\-\s]{2,60}?'
    r'(?:\s+г\.?|\s+город)?\s*,.*)$',
    re.UNICODE)


def _extract_bare_addresses(text: str) -> list:                       # [addr-bare-v4]
    """Ищет строки, начинающиеся с индекса + город/область без метки."""
    found = []
    for raw in (text or '').split('\n'):
        line = raw.strip()
        if not line:
            continue
        m = _RE_BARE_ADDRESS.match(line)
        if not m:
            continue
        idx = m.group(1)
        rest = m.group(2).strip()
        # Отсечём варианты, где после индекса идёт ФИО/наименование.
        if re.match(r'^[А-ЯЁ][а-яё]+\s+[А-ЯЁ]\.', rest):
            continue
        found.append(('Юридический адрес', idx + ', ' + rest))
    return found


def parse_addresses(text: str) -> list:
    text = _preprocess_pdf_table(text)                                # [addr-pdf-patch]
    text = _merge_addr_labels_with_value(text)
    addresses = []
    lines = [norm_text(l) for l in text.split('\n')]
    i = 0
    while i < len(lines):
        m = _RE_ADDR_LINE.match(lines[i])
        if m:
            label_raw = (m.group(1) + ' ' + m.group(2)).strip()
            rest = norm_text(m.group(3))
        else:
            m2 = _RE_ADDR_LINE_NO_COLON.match(lines[i])
            if m2:
                label_raw = norm_text(m2.group(1))
                rest = norm_text(m2.group(2))
            else:
                m3 = _RE_ADDR_LINE_GLUED.match(lines[i])
                if not m3:
                    i += 1
                    continue
                label_raw = norm_text(m3.group(1))
                rest = norm_text(m3.group(2))
        if any(k in label_raw.lower() for k in _NON_ADDR_LABELS):
            i += 1
            continue
        # [addr-blank-line-v9] разрешаем РОВНО одну пустую строку
        # внутри адреса, если следующая строка — продолжение
        # (г., ул., кв., д., пом. и т. п.).
        j = i + 1
        blank_seen = False
        while j < len(lines):
            nxt = lines[j]
            if not nxt:
                if blank_seen:
                    j += 1
                    break
                blank_seen = True
                j += 1
                continue
            if _ADDR_STOP.match(nxt):
                break
            if (_RE_ADDR_LINE.match(nxt)
                    or _RE_ADDR_LINE_NO_COLON.match(nxt)
                    or _RE_ADDR_LINE_GLUED.match(nxt)):
                break
            if blank_seen and not _looks_like_addr_continuation(nxt):
                break
            blank_seen = False
            rest += ' ' + nxt
            j += 1
            if len(rest) > 400:
                break
        rest = re.sub(r'\s+', ' ', rest).strip(' ,')
        rest = re.split(
            r'\s+(?:ГРН|ИНН|КПП|ОГРН|ОГРНИП|БИК|Л/с|Л/С|'
            r'Р/с|Р/С|Р/сч[её]т|Расч[её]т\w*|К/с|К/С|К/сч|Корр|Кор\.|'
            r'Телефон|Тел|Факс|E-mail|Эл\.|Директор|Генеральный|ГИП|'
            r'Председатель|Банка?|Наименование\s+банка|'
            r'Почтовый|Юридический|Юр\.|Фактический|Фактич\.|Адрес'
            r')\b\s*:?',
            rest, maxsplit=1)[0].strip(' ,')
        parts = re.split(
            r'\s+(Почтовый\s+адрес|Юридический\s+адрес|'
            r'Юр(?:ид)?\.?\s*адрес|'
            r'Фактический\s+адрес|Фактич\.?\s*адрес|'
            r'Адрес)\b\s*:?\s*',
            rest)
        if len(parts) >= 3:
            head = parts[0].strip(' ,')
            if head:
                addresses.append((canon_addr_label(label_raw), head))
            for k in range(1, len(parts) - 1, 2):
                sub_label = canon_addr_label(parts[k])
                sub_val = parts[k + 1].strip(' ,')
                if sub_val:
                    addresses.append((sub_label, sub_val))
        else:
            if rest:
                addresses.append((canon_addr_label(label_raw), rest))
        i = j

    addresses = _merge_addr_fragments(addresses)

    # [addr-dedup-patch] умная дедупликация: если две записи с одинаковым
    # label и одна является префиксом другой (по нормализованной форме),
    # оставляем более длинную.
    def _norm(s):
        return re.sub(r'[\s.,;:]+', '', s.lower())

    unique = []
    for label, val in addresses:
        key = _norm(val)
        if not key:
            continue
        replaced = False
        for i, (ulab, uval) in enumerate(unique):
            if ulab != label:
                continue
            ukey = _norm(uval)
            if key == ukey:
                replaced = True
                break
            if key.startswith(ukey) and len(key) > len(ukey):
                # новая запись — длиннее, заменяем
                unique[i] = (ulab, val)
                replaced = True
                break
            if ukey.startswith(key) and len(ukey) > len(key):
                # уже есть более длинная — эта короче, игнорируем
                replaced = True
                break
        if not replaced:
            unique.append((label, val))
    addresses = unique
    order = {'Юридический адрес': 0, 'Почтовый адрес': 1,
             'Фактический адрес': 2}
    unique.sort(key=lambda x: order.get(x[0], 9))

    # Дополняем адресами без метки (индекс + город).
    known = {re.sub(r'\s+', '', v.lower()) for _, v in unique}
    for lab, val in _extract_bare_addresses(text):
        key = re.sub(r'\s+', '', val.lower())
        if key not in known:
            unique.append((lab, val))
            known.add(key)

    return unique
