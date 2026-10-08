# -*- coding: utf-8 -*-
"""
Проверка извлечения Заказчика. Запуск:  python _check_filled.py
"""
import sys
from pathlib import Path

for _name in ("stdout", "stderr"):
    _s = getattr(sys, _name, None)
    if _s is not None and hasattr(_s, "reconfigure"):
        try:
            _s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

from contract_filler.io_layer.extract import extract_text
from contract_filler.parsing.from_filled import (
    looks_like_filled_contract, parse_filled_contract,
    _extract_head_before_marker, _extract_customer_block,
)


EXPECTED = {
    "Образец1.doc": ("ООО «Трубный завод»",           "5018177696"),
    "Образец2.doc": ("АНО «АЦГ»",                     "5260482115"),
    "Образец3.doc": ("ИП Блинов Олег Анатольевич",    "526209167760"),
    "Образец4.doc": ("ИП Планкова Оксана Леонидовна", "550408473626"),
}

SAMPLES = Path(__file__).parent / "Образцы"


def main():
    print("=" * 78)
    print("ПРОВЕРКА parse_filled_contract")
    print("=" * 78)
    ok_count = 0
    fail_count = 0

    for name, (exp_name, exp_inn) in EXPECTED.items():
        path = SAMPLES / name
        print(f"\n--- {name} ---")
        if not path.exists():
            print(f"  [!] файл не найден")
            fail_count += 1
            continue

        text = extract_text(path)
        if not looks_like_filled_contract(text):
            print(f"  [!] не похож на готовый договор")
            fail_count += 1
            continue

        head = _extract_head_before_marker(text)
        block = _extract_customer_block(text)
        print(f"  HEAD (len={len(head)}): {head[:200]!r}")
        if block:
            print(f"  BLOCK (len={len(block)}): {block[:200]!r}")
        else:
            print(f"  BLOCK: None")

        d = parse_filled_contract(text)
        if d is None:
            print(f"  [FAIL] parse_filled_contract вернул None")
            fail_count += 1
            continue

        got_name = d.get("name") or ""
        got_inn = d.get("inn") or ""
        got_rs = d.get("rs") or ""
        got_bik = d.get("bik") or ""
        print(f"  ПОЛУЧЕНО:  name = {got_name!r}")
        print(f"             inn  = {got_inn!r}  rs = {got_rs!r}")
        print(f"             bik  = {got_bik!r}")

        if got_name == exp_name and (not exp_inn or got_inn == exp_inn):
            print(f"  [OK]")
            ok_count += 1
        else:
            print(f"  [!] НЕ СОВПАЛО (ожидалось name={exp_name!r}, inn={exp_inn!r})")
            fail_count += 1

    print()
    print("=" * 78)
    print(f"ИТОГ: OK = {ok_count}, FAIL = {fail_count}")
    print("=" * 78)
    return 0 if fail_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
