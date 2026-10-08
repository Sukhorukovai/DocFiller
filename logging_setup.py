# -*- coding: utf-8 -*-
"""
Единая точка настройки логгера.

Лог пишется в <папка шаблона>/_service/app.log. Так же дублируется в stderr.
Раньше эти функции жили в main.py; теперь импортируются всеми модулями.
"""
import logging
import sys
from pathlib import Path


log = logging.getLogger("contract_filler")


# Принудительный UTF-8 для stdout/stderr, чтобы не падать на cp1251.
for _stream_name in ("stdout", "stderr"):
    _s = getattr(sys, _stream_name, None)
    if _s is not None and hasattr(_s, "reconfigure"):
        try:
            _s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def setup_logger_for_template(template_path: Path) -> None:
    """Настраивает логгер так, чтобы app.log лежал рядом с шаблоном."""
    service_dir = Path(template_path).parent / "_service"
    service_dir.mkdir(exist_ok=True)
    log_path = service_dir / "app.log"

    for h in list(log.handlers):
        log.removeHandler(h)
    log.setLevel(logging.DEBUG)

    fh = logging.FileHandler(log_path, encoding="utf-8")
    fh.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s"))
    log.addHandler(fh)

    sh = logging.StreamHandler()
    sh.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
    log.addHandler(sh)


def setup_logger_console_only() -> None:
    """Только stderr — для CLI-утилит и диагностики."""
    for h in list(log.handlers):
        log.removeHandler(h)
    log.setLevel(logging.DEBUG)
    sh = logging.StreamHandler()
    sh.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
    log.addHandler(sh)