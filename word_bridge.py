# -*- coding: utf-8 -*-
"""
Мост к Microsoft Word через win32com.

Используется для:
  • doc → docx  (иначе python-docx не откроет),
  • docx → pdf  (для OCR-фолбэка),
  • docx → docx (resave, когда strict OOXML не читается python-docx).

Если pywin32 не установлен — все функции бросают RuntimeError,
вызывающий код это ловит и работает без Word.
"""
import atexit
import re
import shutil
import tempfile
import uuid
import zipfile
from pathlib import Path

from ..logging_setup import log

try:
    import win32com.client
except ImportError:
    win32com = None


_TMP_DIR: Path | None = None
_CONVERTED_CACHE: dict[str, Path] = {}


def _get_tmp_dir() -> Path:
    global _TMP_DIR
    if _TMP_DIR is None or not _TMP_DIR.exists():
        _TMP_DIR = Path(tempfile.mkdtemp(prefix="contract_filler_"))
        atexit.register(_cleanup_tmp)
    return _TMP_DIR


def _cleanup_tmp() -> None:
    global _TMP_DIR
    if _TMP_DIR and _TMP_DIR.exists():
        shutil.rmtree(_TMP_DIR, ignore_errors=True)
    _TMP_DIR = None


_SMARTTAG_OPEN_RE = re.compile(
    r'<w:smartTag\b[^>]*>', re.IGNORECASE
)
_SMARTTAG_CLOSE_RE = re.compile(
    r'</w:smartTag\s*>', re.IGNORECASE
)
# [smarttags-v13d] Word 2010 при сохранении в strict OOXML
# срезает <w:smartTag>, но оставляет orphan <w:smartTagPr>,
# внутри которого w:val содержит метаданные смарт-тега
# (например '603043, г'). Текст в <w:t> не трогаем — эти
# метаданные к отображению не относятся.
_SMARTTAGPR_RE = re.compile(
    r'<w:smartTagPr\b[^>]*/>'
    r'|'
    r'<w:smartTagPr\b[^>]*>.*?</w:smartTagPr\s*>',
    re.DOTALL | re.IGNORECASE,
)


def _strip_smart_tags(docx_path: Path) -> bool:
    """
    Удаляет теги <w:smartTag> / </w:smartTag> из word/document.xml.
    Текст внутри смарт-тега сохраняется — удаляется только обёртка.
    Возвращает True, если файл был изменён.
    """
    if not docx_path.exists() or docx_path.suffix.lower() != '.docx':
        return False
    try:
        with zipfile.ZipFile(docx_path, 'r') as zin:
            names = zin.namelist()
            if 'word/document.xml' not in names:
                return False
            items = {n: zin.read(n) for n in names}
    except Exception:
        log.exception('_strip_smart_tags: чтение %s упало',
                      docx_path.name)
        return False

    xml_bytes = items['word/document.xml']
    xml = xml_bytes.decode('utf-8', errors='replace')
    if 'smartTag' not in xml:
        return False

    before = xml
    xml = _SMARTTAG_OPEN_RE.sub('', xml)
    xml = _SMARTTAG_CLOSE_RE.sub('', xml)
    xml = _SMARTTAGPR_RE.sub('', xml)
    if xml == before:
        return False

    items['word/document.xml'] = xml.encode('utf-8')
    tmp = docx_path.with_suffix('.docx.tmp')
    try:
        with zipfile.ZipFile(tmp, 'w', zipfile.ZIP_DEFLATED) as zout:
            for name, data in items.items():
                zout.writestr(name, data)
        tmp.replace(docx_path)
    except Exception:
        log.exception('_strip_smart_tags: запись %s упала',
                      docx_path.name)
        if tmp.exists():
            tmp.unlink(missing_ok=True)
        return False
    log.info('_strip_smart_tags: очищен %s', docx_path.name)
    return True


def word_convert(src: Path, out_suffix: str, file_format: int = None) -> Path:
    """
    Открывает src в Word и сохраняет в новый файл с указанным форматом.

    file_format: 16 = docx, 17 = pdf (см. WdSaveFormat / WdExportFormat).
    """
    if win32com is None:
        raise RuntimeError("pywin32 не установлен")
    tmp = _get_tmp_dir()
    out = tmp / f"{src.stem}_{uuid.uuid4().hex[:6]}{out_suffix}"
    word = win32com.client.Dispatch("Word.Application")
    word.Visible = False
    word.DisplayAlerts = 0
    # [smarttags-v13b] В Word 2010 (14.0) COM-свойства
    # SmartTagRecognizers больше нет — Microsoft удалила
    # поддержку смарт-тегов в Office 2010. Чистим XML после
    # конвертации (см. _strip_smart_tags ниже).
    try:
        d = word.Documents.Open(str(src.resolve()), ReadOnly=True)
        # [fields-update-v11] ОТКЛЮЧЕНО v15 — проверяем, не оно ли
        # ломает таблицу акта. Вернуть: убрать 'if False:' ниже.
        if False:  # v15-disable-v11
            try:
                d.Fields.Update()
            except Exception:
                log.exception('Fields.Update упал')
            try:
                d.Repaginate()
            except Exception:
                log.exception('Repaginate упал')
        if file_format == 17:
            d.ExportAsFixedFormat(str(out.resolve()), 17)
        else:
            d.SaveAs2(str(out.resolve()), FileFormat=file_format or 16)
        d.Close(False)
    finally:
        word.Quit()
    # [smarttags-v13c] Чистим смарт-теги ПОСЛЕ word.Quit(),
    # иначе Word ещё держит файл и os.replace падает с
    # PermissionError [WinError 5]. Только для .docx.
    if file_format != 17:
        _strip_smart_tags(out)
    return out


def doc_to_docx_via_word(doc_path: Path) -> Path:
    """Конвертирует .doc в .docx. Результат — во временной папке."""
    return word_convert(doc_path, ".docx", 16)


def docx_resave_via_word(docx_path: Path) -> Path:
    """Пересохраняет .docx. Помогает на strict OOXML и текстовых полях."""
    return word_convert(docx_path, ".docx", 16)


def docx_to_pdf_via_word(docx_path: Path) -> Path:
    """Конвертирует .docx в .pdf для OCR-фолбэка."""
    return word_convert(docx_path, ".pdf", 17)


def ensure_docx_cached(path: Path) -> Path:
    """
    Кэширует doc → docx конвертацию на время работы приложения
    (шаблон может конвертироваться несколько раз).
    """
    suffix = path.suffix.lower()
    if suffix == ".docx":
        return path
    if suffix != ".doc":
        raise ValueError(
            f"Ожидался .doc или .docx, получено: {path.suffix}"
        )
    key = str(path.resolve())
    cached = _CONVERTED_CACHE.get(key)
    if cached is not None and cached.exists():
        return cached
    out = doc_to_docx_via_word(path)
    _CONVERTED_CACHE[key] = out
    return out