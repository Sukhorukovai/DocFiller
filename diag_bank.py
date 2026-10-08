# -*- coding: utf-8 -*-
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, ".")

from pathlib import Path
from contract_filler.io_layer.extract import extract_text
from contract_filler.parsing._bank import parse_bank_block

src = Path(r"D:\Install\Work\ИИ\Заполнение Договора и Акта\Образцы\Реквизиты\Реквизиты Комплексстрой.doc")
text = extract_text(src)

print("=== Строки с банком / р/с ===")
for line in text.split("\n"):
    if any(w in line for w in ("илиал", "Отделен", "счет", "БИК", "ИНТЕЗА", "Банк")):
        print(f"  {line!r}")

print()
r = parse_bank_block(text)
print("bank:", repr(r["bank"]))
print("rs:  ", repr(r["rs"]))
print("bik: ", repr(r["bik"]))