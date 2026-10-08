# -*- coding: utf-8 -*-
"""
Проверка полноты выгрузки данных из договоров.

Запуск:  python _check_contracts.py

Для каждого .doc/.docx в папке Образцы/, чьё имя начинается с
«Образец», вызываем parse_filled_contract + doc_meta и печатаем
таблицу заполненности полей.
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
)
from contract_filler.parsing.doc_meta import (
    extract_contract_no, extract_contract_date, extract_contract_sum,
)


SAMPLES = Path(__file__).parent / "Образцы"

# Ключевые поля, которые нужны для акта.
CRITICAL = [
    'name', 'fio_full', 'fio_short',
    'position', 'position_nom', 'basis',
    'inn', 'kpp', 'ogrn', 'ogrn_kind',
    'rs', 'ks', 'bank', 'bik',
    'signer',
]

# Поля, не критичные для ИП.
IP_EXEMPT = {'position', 'position_nom', 'basis', 'kpp',
             'full_name'}
OPTIONAL = ['phone', 'email', 'witness', 'egrip']


def _v(val):
    if val is None or val == '':
        return '—'
    if isinstance(val, list):
        return f'({len(val)} шт.)'
    s = str(val)
    if len(s) > 60:
        s = s[:57] + '...'
    return s


def _is_filled(v):
    if v is None or v == '':
        return False
    if isinstance(v, (list, dict)):
        return bool(v)
    return True


def main():
    if not SAMPLES.exists():
        print(f"Нет папки {SAMPLES}")
        return 1

    files = sorted(
        p for p in SAMPLES.rglob("*")
        if p.is_file()
        and p.suffix.lower() in ('.doc', '.docx')
        and p.name.lower().startswith('образец')
        and not p.name.startswith('~$')
        and not p.name.endswith('.ocr.txt')
    )

    if not files:
        print("Не нашёл договоров, начинающихся с «Образец».")
        return 1

    print(f"Найдено договоров: {len(files)}")
    print("=" * 78)

    global_missing = {}  # field -> список файлов, где пусто

    for path in files:
        print(f"\n### {path.name}")
        text = extract_text(path)

        if not looks_like_filled_contract(text):
            print("  [!] не похож на готовый договор — пропуск")
            continue

        d = parse_filled_contract(text)
        if d is None:
            print("  [!] parse_filled_contract вернул None")
            continue

        # --- Реквизиты Заказчика ---
        print("  --- Реквизиты Заказчика ---")
        is_ip = bool(d.get('is_ip'))
        for f in CRITICAL:
            v = d.get(f)
            filled = _is_filled(v)
            mark = 'OK ' if filled else '  !'
            print(f"    {mark} {f:14s} = {_v(v)}")
            if not filled:
                # Для ИП position/basis/kpp/full_name не критичны.
                if is_ip and f in IP_EXEMPT:
                    continue
                global_missing.setdefault(f, []).append(path.name)

        for f in OPTIONAL:
            v = d.get(f)
            if _is_filled(v):
                print(f"     · {f:14s} = {_v(v)}")

        addresses = d.get('addresses') or []
        if addresses:
            print(f"     · addresses     = ({len(addresses)} шт.)")
            for label, val in addresses:
                print(f"         [{label}] {_v(val)}")
        else:
            global_missing.setdefault('addresses', []).append(path.name)
            print(f"       ! addresses     = пусто")

        # --- Метаданные договора ---
        print("  --- Метаданные договора ---")
        no = extract_contract_no(text)
        dt = extract_contract_date(text)
        sm = extract_contract_sum(text)
        print(f"     № договора = {_v(no)}")
        print(f"     дата       = {_v(dt)}")
        print(f"     сумма      = {_v(sm)}")
        if not no:
            global_missing.setdefault('contract_no', []).append(path.name)
        if not dt:
            global_missing.setdefault('contract_date', []).append(path.name)
        if not sm:
            global_missing.setdefault('contract_sum', []).append(path.name)

    # ===============================================================
    # СВОДКА
    # ===============================================================
    print("\n" + "=" * 78)
    print("СВОДКА: поля, которые встречаются пустыми")
    print("=" * 78)

    if not global_missing:
        print("  Всё заполнено. Проблем нет.")
        return 0

    for f, fl in sorted(global_missing.items()):
        print(f"  {f:14s}  пропущено в {len(fl)} файл(ах): "
              f"{', '.join(fl)}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
