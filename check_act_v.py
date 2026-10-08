# -*- coding: utf-8 -*-
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, ".")

from contract_filler.documents.act.processor import _ensure_bank_leading_v as f

cases = [
    'в в Филиале «Приволжский» АО «Банк ИНТЕЗА» в г.Нижнем Новгороде',
    'в Филиале «Приволжский» АО «Банк ИНТЕЗА» в г.Нижнем Новгороде',
    'Филиале «Приволжский» АО «Банк ИНТЕЗА» в г.Нижнем Новгороде',
    'Отделение №5230 ПАО Сбербанк',
    'ФИЛИАЛ «ЦЕНТРАЛЬНЫЙ» БАНКА ВТБ (ПАО) в г. Москве',
    'Банк ВТБ (ПАО)',
    'ПАО Сбербанк',
]
for s in cases:
    print(f"IN : {s}")
    print(f"OUT: {f(s)}")
    print()