# -*- coding: utf-8 -*-
"""
Совместимая обёртка: читает реквизиты из файла и передаёт их в
ContractProcessor. Оставлена, чтобы GUI и старые импорты продолжали
работать без изменений.
"""
from pathlib import Path

from .io_layer.extract import extract_text
from .parsing.requisites import parse_requisites
from .documents.base import Requisites
from .documents.contract.processor import ContractProcessor
from .logging_setup import log


def process(template_path, requisites_path) -> Path:
    template_path = Path(template_path)
    requisites_path = Path(requisites_path)

    req_text = extract_text(requisites_path)
    log.info("Реквизиты: %r", req_text[:500])

    if len((req_text or '').strip()) < 20:
        raise RuntimeError(
            "Файл реквизитов не распознан — из него не извлечено "
            "ни одной строки текста.\n\n"
            "Возможные причины:\n"
            "  • плохое качество скана / размытое изображение;\n"
            "  • не установлен Tesseract-OCR;\n"
            "  • не установлен Microsoft Word;\n"
            "  • не установлен pdfplumber или pymupdf;\n"
            "  • файл повреждён."
        )

    req_dict = parse_requisites(req_text)
    log.info("Разобрано: name=%r is_ip=%r inn=%r kpp=%r ogrn=%r(%s) "
             "rs=%r ks=%r bank=%r bik=%r addresses=%r "
             "fio_full=%r position=%r basis=%r",
             req_dict.get('name'), req_dict.get('is_ip'),
             req_dict.get('inn'), req_dict.get('kpp'),
             req_dict.get('ogrn'), req_dict.get('ogrn_kind'),
             req_dict.get('rs'), req_dict.get('ks'),
             req_dict.get('bank'), req_dict.get('bik'),
             req_dict.get('addresses'), req_dict.get('fio_full'),
             req_dict.get('position'), req_dict.get('basis'))

    if not req_dict.get("name"):
        import re
        preview = re.sub(r'\s+', ' ', (req_text or '')[:200]).strip()
        raise RuntimeError(
            "В файле реквизитов не удалось найти наименование "
            "организации (ООО / АО / ИП).\n\n"
            f"Распознанный текст (первые 200 символов):\n"
            f"«{preview}»"
        )

    req = Requisites.from_dict(req_dict)

    processor = ContractProcessor()
    output_path = (template_path.parent
                   / f"Новый_Договор_{template_path.stem}.docx")
    return processor.process(template_path, req, output_path)
