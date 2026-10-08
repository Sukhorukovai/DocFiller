# -*- coding: utf-8 -*-
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from pathlib import Path
import re
import zipfile

from contract_filler.io_layer.word_bridge import (
    doc_to_docx_via_word, _strip_smart_tags,
)

src = Path(r"D:\Install\Work\ИИ\Заполнение Договора и Акта\Образцы\Реквизиты\Реквизиты Комплексстрой.doc")
print("1) Конвертируем...")
p = doc_to_docx_via_word(src)
print("   path =", p)
print("   exists =", p.exists())
print("   size =", p.stat().st_size)

print("\n2) Читаем word/document.xml...")
with zipfile.ZipFile(p) as z:
    names = z.namelist()
    print("   частей в архиве:", len(names))
    print("   'word/document.xml' in names:", 'word/document.xml' in names)
    x = z.read('word/document.xml').decode('utf-8')

print("\n3) Что видим в xml:")
print("   'smartTag' в x (подстрока):", 'smartTag' in x)
print("   'w:smartTag' в x (подстрока):", 'w:smartTag' in x)
idx = x.find('smartTag')
if idx != -1:
    print("   фрагмент вокруг:", repr(x[max(0, idx-80):idx+200]))

print("\n4) Проверяем сами регулярки:")
RE_OPEN = re.compile(r'<w:smartTag\b[^>]*>', re.IGNORECASE)
RE_CLOSE = re.compile(r'</w:smartTag\s*>', re.IGNORECASE)
opens = RE_OPEN.findall(x)
closes = RE_CLOSE.findall(x)
print("   открывающих по регулярке:", len(opens))
print("   закрывающих по регулярке:", len(closes))
if opens:
    print("   пример открывающего:", repr(opens[0]))
if closes:
    print("   пример закрывающего:", repr(closes[0]))

print("\n5) Зовём _strip_smart_tags(p) руками...")
res = _strip_smart_tags(p)
print("   результат:", res)

with zipfile.ZipFile(p) as z:
    x2 = z.read('word/document.xml').decode('utf-8')
print("   после вызова: 'w:smartTag' в x2:", 'w:smartTag' in x2)
print("   после вызова: '603043'  в x2:", '603043' in x2)

print("\n6) Файл изменился?")
print("   исходный x == x2:", x == x2)