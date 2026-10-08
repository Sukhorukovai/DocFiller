# -*- coding: utf-8 -*-
"""
Единая точка входа: parse_requisites(текст) → dict.

Собирает данные из модулей _names / _leadership / _addresses / _bank /
_common. Никакого OCR и работы с docx здесь нет — только текст.
"""
from ..core.text import normalize_newlines
from ..core.morphology import detect_gender, to_short
from ._names import parse_names
from ._leadership import parse_leadership
from ._addresses import parse_addresses, addr_value_is_noise
from ._bank import parse_bank_block
from ._common import parse_common_fields


def parse_requisites(text: str) -> dict:
    text = normalize_newlines(text or "")

    result = {
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

    for k, v in parse_names(text).items():
        if v:
            result[k] = v

    lead = parse_leadership(text)
    for k, v in lead.items():
        if v and not result.get(k):
            result[k] = v

    if result["is_ip"] and result["fio_full"]:
        result["gender"] = detect_gender(result["fio_full"].split())
        result["signer"] = result.get("fio_short") or result["fio_full"]
    if not result["is_ip"] and result.get("fio_short"):
        result["signer"] = result["fio_short"]

    result["addresses"] = parse_addresses(text)

    bank_block = parse_bank_block(text)
    for k, v in bank_block.items():
        if v or k == "extra_bank":
            result[k] = v

    for k, v in parse_common_fields(text).items():
        if v and not result.get(k):
            result[k] = v

    if result["is_ip"] and not result["ogrn_kind"]:
        result["ogrn_kind"] = "ОГРНИП"
    if result["fio_full"] and not result["gender"]:
        result["gender"] = detect_gender(result["fio_full"].split())

    # --- Нормализация whitespace во всех строковых полях --------------
    # Появились многострочные значения из PDF/Word-таблиц. Схлопываем
    # переносы строк и кратные пробелы прямо здесь, до Requisites,
    # потому что у Requisites __slots__.
    import re as _re_ws
    def _collapse_ws(s):
        if not isinstance(s, str):
            return s
        s = s.replace('\r', ' ').replace('\n', ' ').replace('\t', ' ')
        return _re_ws.sub(r' {2,}', ' ', s).strip()

    for _k, _v in list(result.items()):
        if isinstance(_v, str):
            result[_k] = _collapse_ws(_v)
        elif isinstance(_v, list):
            # например addresses = [(label, value), ...]
            _new_list = []
            for _item in _v:
                if isinstance(_item, (list, tuple)) and len(_item) == 2:
                    _new_list.append((_collapse_ws(_item[0]),
                                      _collapse_ws(_item[1])))
                else:
                    _new_list.append(_item)
            result[_k] = _new_list
    # ------------------------------------------------------------------

    return result


# Экспорт полезного наружу — используется валидацией и диагностикой.
__all__ = ["parse_requisites", "addr_value_is_noise"]
