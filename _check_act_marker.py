# -*- coding: utf-8 -*-
"""
Проверка: находит ли XML-обход абзац с CONTRACT.
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

from docx import Document
from docx.oxml.ns import qn
from contract_filler.io_layer.word_bridge import ensure_docx_cached


def main():
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("Акт.doc")
    if not path.exists():
        print(f"Нет файла: {path}")
        return 1
    docx_path = ensure_docx_cached(path)
    doc = Document(str(docx_path))
    body = doc.element.body
    found = False
    for p_el in body.iter(qn('w:p')):
        texts = [t.text for t in p_el.iter(qn('w:t')) if t.text]
        full = ''.join(texts)
        if 'CONTRACT' in full.upper():
            print(f"✅ Найден абзац с CONTRACT: {full!r}")
            found = True
    if not found:
        print("❌ CONTRACT не найден через XML-обход.")
        print("Проверьте, что в шаблоне есть абзац с текстом CONTRACT")
        print("(латиница, капсом, без русских букв).")
    return 0 if found else 1


if __name__ == "__main__":
    sys.exit(main())
