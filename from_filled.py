# -*- coding: utf-8 -*-
"""
Обратный парсер: извлекает реквизиты Заказчика из ГОТОВОГО договора.

Стратегия:
  1) HEAD — фрагмент шапки непосредственно перед «именуемое в дальнейшем
     «Заказчик»», начиная с последнего «с одной стороны».
  2) Из HEAD извлекаем: name, position (в им. падеже), fio_full,
     fio_short, basis, signer.
  3) BLOCK — фрагмент после последнего «Заказчик:» в конце документа.
  4) Для ИП реквизиты берём ТОЛЬКО из BLOCK.
  5) Для юрлиц — BLOCK + последние 55% текста.
  6) ИНН может быть записан с пробелами.
"""
import re

from ..core.text import norm_text, digits_only
from ..core.morphology import (
    normalize_fio_case, clean_fio_words, to_short, to_nominative_fio,
)
from .patterns import (
    _RE_ORG_NAME_SHORT, _RE_ORG_NAME_FULL, _ORG_PREFIX,
    _RE_IP_FULL, _RE_IP_SHORT, _RE_IP_SHORT_ABBR,
)
from ._names import (
    _normalize_prefix, _name_looks_valid, _looks_like_fio,
)
from ._addresses import parse_addresses
from ._bank import parse_bank_block
from ._common import parse_common_fields


_RE_LOOKS_LIKE_FILLED = re.compile(
    r'именуем\w+\s+в\s+дальнейшем\s*[«"\u201C\u201E]?\s*Заказчик',
    re.I)

# ---------------------------------------------------------------------
# Регекспы для шапки
# ---------------------------------------------------------------------

# Должность в родительном падеже после «в лице».
_LEAD_POS_PAT = (
    r'(?:'
    r'генеральн\w+\s+директор\w*|'
    r'директор\w*|'
    r'ГИП\w*|'
    r'управляющ\w+|'
    r'руководител\w+|'
    r'председател\w+(?:\s+правлени\w+)?|'
    r'владел\w+\s+компани\w+'
    r')'
)

_RE_POSITION = re.compile(
    r'в\s+лице\s+(?P<pos>' + _LEAD_POS_PAT + r')',
    re.UNICODE | re.IGNORECASE,
)

# Короткое ФИО: «Романенко В.В.» / «Романенко В. В.»
_SHORT_FIO_PAT = r'[А-ЯЁ][а-яё\-]+(?:\s+[А-ЯЁ]\.\s*[А-ЯЁ]?\.?)'
# Полное ФИО: «Коник Сергей Иванович»
_FULL_FIO_PAT = r'[А-ЯЁ][а-яё\-]+(?:\s+[А-ЯЁ][а-яё\-]+){1,2}'

_RE_FIO_AFTER_POS = re.compile(
    r'в\s+лице\s+' + _LEAD_POS_PAT + r'\s+'
    r'(?P<fio>'
    r'(?:' + _SHORT_FIO_PAT + r')'   # короткое — первым
    r'|'
    r'(?:' + _FULL_FIO_PAT + r')'    # полное
    r')',
    re.UNICODE | re.IGNORECASE,
)

# Фоллбэк: короткое ФИО в любом месте HEAD (для случаев, где «в лице»
# отсутствует, но «...Романенко В.В....»)
_RE_SHORT_FIO_ANYWHERE = re.compile(
    r'(?<![А-ЯЁа-яё])'
    r'[А-ЯЁ][а-яё\-]{1,}\s+[А-ЯЁ]\.\s*[А-ЯЁ]\.',
    re.UNICODE,
)


def _norm_position(pos_gen: str) -> str:
    p = (pos_gen or '').lower()
    if 'генеральн' in p and 'директор' in p:
        return 'Генеральный директор'
    if 'председател' in p and 'правлени' in p:
        return 'Председатель правления'
    if 'председател' in p:
        return 'Председатель'
    if 'директор' in p:
        return 'Директор'
    if 'гип' in p:
        return 'ГИП'
    if 'управляющ' in p:
        return 'Управляющий'
    if 'руководител' in p:
        return 'Руководитель'
    if 'владел' in p and 'компани' in p:
        return 'Владелец компании'
    return (pos_gen or '').capitalize()


def looks_like_filled_contract(text: str) -> bool:
    return bool(_RE_LOOKS_LIKE_FILLED.search(text or ''))


# ---------------------------------------------------------------------
# HEAD
# ---------------------------------------------------------------------

_SIDE_PAT = re.compile(r'с\s+одной\s+стороны', re.I)


def _extract_head_before_marker(text: str, window: int = 4000) -> str:
    m = _RE_LOOKS_LIKE_FILLED.search(text or '')
    if not m:
        return ''
    marker_pos = m.start()
    start = max(0, marker_pos - window)
    head = text[start:marker_pos]

    last_end = None
    for mm in _SIDE_PAT.finditer(head):
        last_end = mm.end()
    if last_end is not None:
        after = head[last_end:]
        after = re.sub(r'^\s*[,;]?\s*и\s+', '', after)
        head = after
    return head


def _parse_customer_preamble(head: str) -> dict:
    out = {}
    if not head:
        return out

    # --- ИП ---
    m_ip = _RE_IP_FULL.search(head) or _RE_IP_SHORT.search(head)
    if m_ip:
        fio = normalize_fio_case(
            clean_fio_words(norm_text(m_ip.group(1))))
        if _looks_like_fio(fio):
            fio_fixed = to_nominative_fio(fio)
            out['is_ip'] = True
            out['fio_full'] = fio_fixed
            out['fio_short'] = to_short(fio_fixed)
            out['name'] = f"ИП {fio_fixed}"
            out['signer'] = out['fio_short']
            return out

    # --- Должность ---
    m_pos = _RE_POSITION.search(head)
    if m_pos:
        pos_gen = norm_text(m_pos.group('pos')).lower()
        pos_gen = re.sub(r'\s+', ' ', pos_gen).strip()
        out['position'] = pos_gen
        out['position_nom'] = _norm_position(pos_gen)

    # --- ФИО ---
    m_fio = _RE_FIO_AFTER_POS.search(head)
    if m_fio:
        fio_raw = norm_text(m_fio.group('fio'))
        _fill_fio(out, fio_raw)
    else:
        # Фоллбэк: короткое ФИО в любом месте HEAD.
        m_short = _RE_SHORT_FIO_ANYWHERE.search(head)
        if m_short:
            _fill_fio(out, norm_text(m_short.group(0)))

    # --- basis ---
    m_basis = re.search(
        r'на\s+основании\s+([^\n,;.)]+)', head, re.IGNORECASE)
    if m_basis:
        basis = norm_text(m_basis.group(1)).strip(' .,;:')
        if basis:
            out['basis'] = basis

    return out


def _fill_fio(out: dict, fio_raw: str):
    """Определяет — короткое или полное ФИО, нормализует, пишет в out."""
    if not fio_raw:
        return
    # Короткое ФИО содержит инициалы с точками.
    is_short = bool(re.search(r'[А-ЯЁ]\.\s*[А-ЯЁ]?\.?', fio_raw))
    if is_short:
        out['fio_full'] = fio_raw
        out['fio_short'] = fio_raw
        out['signer'] = fio_raw
    else:
        fio_nom = to_nominative_fio(fio_raw)
        if _looks_like_fio(fio_nom):
            out['fio_full'] = fio_nom
            out['fio_short'] = to_short(fio_nom)
            out['signer'] = out['fio_short']
        elif _looks_like_fio(fio_raw):
            out['fio_full'] = fio_raw
            out['fio_short'] = to_short(fio_raw)
            out['signer'] = out['fio_short']


# ---------------------------------------------------------------------
# BLOCK «Заказчик:»
# ---------------------------------------------------------------------

_RE_LABEL_ONLY = re.compile(
    r'^\s*[|\s]*Заказчик\s*:?\s*[|\s]*$', re.I)
_RE_SUPPLIER_LABEL = re.compile(
    r'^\s*[|\s]*Подрядчик\s*:?\s*[|\s]*$', re.I)
_RE_OBJ_LABEL = re.compile(
    r'^\s*[|\s]*Исполнитель\s*:?\s*[|\s]*$', re.I)


def _extract_customer_block(text: str) -> str | None:
    lines = (text or '').split('\n')
    label_idx = None
    for i, line in enumerate(lines):
        if _RE_LABEL_ONLY.match(line):
            label_idx = i
    if label_idx is None:
        return None
    start = label_idx + 1
    out = []
    for line in lines[start:]:
        if (_RE_SUPPLIER_LABEL.match(line)
                or _RE_OBJ_LABEL.match(line)):
            break
        out.append(line)
    block = '\n'.join(out).strip()
    return block or None


_RE_NOISE_START = re.compile(
    r'^(?:ИНН|КПП|ОГРН|ОГРНИП|ГРН|БИК|'
    r'Р\s*/\s*[сcСC]|Р\s*/\s*С|Р\s*/\s*сч|Расч[её]тн|'
    r'К\s*/\s*[сcСC]|К\s*/\s*С|Корр|Кор\.|Кор\b|'
    r'Л\s*/\s*[cсСC]|Лицев|'
    r'Телефон|Тел|Факс|E-mail|Электронная|'
    r'Банк|В\s+Отделении|В\s+филиал|филиал|'
    r'Директор|Генеральный|ОГРНИП|ИМК|Соглашение)\b',
    re.I)


def _find_name_in_block(block: str) -> str:
    last_name = ''
    for m in _RE_ORG_NAME_SHORT.finditer(block):
        prefix = _normalize_prefix(m.group(1))
        body = norm_text(m.group(2))
        if _name_looks_valid(body):
            last_name = f"{prefix} «{body}»"
    return last_name


def _find_addr_without_label(block: str, name: str) -> list:
    if not block:
        return []
    lines = block.split('\n')
    start = 0
    if name:
        core = name.split('«')[-1].strip('»')[:15].lower()
        for i, line in enumerate(lines):
            if core and core in line.lower():
                start = i + 1
                break
    # [addr-multi-cols-v9] Собираем ВСЕХ адресных кандидатов, не
    # прерываясь на первом. Возвращаем последнего с индексом —
    # в таблицах Заказчик идёт правой колонкой (последним).
    candidates = []
    buffer = []
    _RE_CONT_START = re.compile(
        r'^(?:\d{6}\b|г\.|город|ул\.|улица|пр-кт|проспект|'
        r'пер\.|переулок|шоссе|ш\.|наб\.|набережная|'
        r'бул\.|бульвар|б-р|пл\.|площадь|мкр|микрорайон)',
        re.I)
    for line in lines[start:]:
        s = norm_text(line.strip('| '))
        if not s:
            if buffer:
                candidates.append(' '.join(buffer))
                buffer = []
            continue
        if _RE_NOISE_START.match(s):
            if buffer:
                candidates.append(' '.join(buffer))
                buffer = []
            break
        if _RE_CONT_START.match(s):
            if buffer:
                candidates.append(' '.join(buffer))
            buffer = [s]
        elif buffer:
            buffer.append(s)
    if buffer:
        candidates.append(' '.join(buffer))

    idx_cands = [c for c in candidates
                 if re.match(r'^\d{6}\b', c)]
    if idx_cands:
        return [('Юридический адрес', idx_cands[-1])]
    if candidates:
        return [('Юридический адрес', candidates[0])]
    return []


# ---------------------------------------------------------------------
# ИНН с пробелами
# ---------------------------------------------------------------------

_RE_INN_SPACED = re.compile(r'\bИНН\b[\s:]*([\d][\d\s]{8,22}\d)', re.I)


def _extra_inn_search(text: str) -> str:
    if not text:
        return ''
    m = _RE_INN_SPACED.search(text)
    if not m:
        return ''
    digits = re.sub(r'\D', '', m.group(1))
    if 10 <= len(digits) <= 12:
        return digits
    return ''


# ---------------------------------------------------------------------
# Главная функция
# ---------------------------------------------------------------------

def parse_filled_contract(text: str) -> dict | None:
    if not looks_like_filled_contract(text):
        return None

    head = _extract_head_before_marker(text)
    pre = _parse_customer_preamble(head)
    block = _extract_customer_block(text)

    out = {
        "name": "", "full_name": "", "is_ip": False,
        "fio_full": "", "fio_short": "",
        "position": "", "position_nom": "", "basis": "",
        "gender": None, "addresses": [],
        "inn": "", "kpp": "",
        "ogrn": "", "ogrn_kind": "",
        "rs": "", "ks": "", "bank": "", "bik": "",
        "extra_bank": [], "witness": "", "egrip": "",
        "phone": "", "email": "", "signer": "",
    }

    out.update(pre)

    # Имя: сначала из шапки.
    if not out.get('name') and head:
        last_m = None
        for mm in _RE_ORG_NAME_SHORT.finditer(head):
            last_m = mm
        if last_m:
            prefix = _normalize_prefix(last_m.group(1))
            body = norm_text(last_m.group(2))
            if _name_looks_valid(body):
                out['name'] = f"{prefix} «{body}»"
                out['full_name'] = out['name']

    # Если не нашли в шапке — ищем в блоке.
    if not out.get('name') and block:
        block_name = _find_name_in_block(block)
        if block_name:
            out['name'] = block_name
            if not out.get('full_name'):
                out['full_name'] = block_name

    # ИНН с пробелами приоритетно из BLOCK (для ИП).
    if not out.get('inn') and block:
        v = _extra_inn_search(block)
        if v:
            out['inn'] = v

    # Основной поиск реквизитов.
    n = len(text)
    tail = text[max(0, int(n * 0.55)):]

    # Если есть блок «Заказчик:» — ищем ТОЛЬКО в нём.
    # Tail может содержать блок «Подрядчик:» — там ЧУЖИЕ реквизиты.
    if block:
        sources = (block,)
    elif tail:
        sources = (tail,)
    else:
        sources = ()

    for src in sources:
        if not src:
            continue
        bb = parse_bank_block(src)
        for k, v in bb.items():
            if v and not out.get(k):
                out[k] = v
        cc = parse_common_fields(src)
        for k, v in cc.items():
            if v and not out.get(k):
                out[k] = v
        if (out.get('inn') and out.get('rs') and out.get('bik')):
            break

    # Повторный ИНН с пробелами.
    if not out.get('inn'):
        for src in (block, tail):
            v = _extra_inn_search(src)
            if v:
                out['inn'] = v
                break

    # Адреса.
    addresses = parse_addresses(block or '')
    if not addresses:
        addresses = parse_addresses(tail)
    if not addresses:
        addresses = _find_addr_without_label(
            block or tail, out.get('name', ''))
    out['addresses'] = addresses

    # signer fallback.
    if not out.get('signer'):
        if out.get('fio_short'):
            out['signer'] = out['fio_short']
        elif out.get('fio_full'):
            out['signer'] = to_short(out['fio_full'])

    filled = sum(1 for f in ('name', 'inn', 'rs', 'bik')
                 if out.get(f))
    if filled < 2:
        return None

    return out
