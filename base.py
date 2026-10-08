# -*- coding: utf-8 -*-
"""
Базовые абстракции для всех обработчиков документов.

  Requisites       — единая структура реквизитов (dataclass).
  DocumentProcessor — интерфейс. Наследники реализуют matches()
                      и process().
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class Requisites:
    """Структура реквизитов одного контрагента."""

    name: str = ""
    full_name: str = ""
    is_ip: bool = False
    fio_full: str = ""
    fio_short: str = ""
    position: str = ""
    position_nom: str = ""
    basis: str = ""
    gender: Optional[str] = None
    addresses: list = field(default_factory=list)
    inn: str = ""
    kpp: str = ""
    ogrn: str = ""
    ogrn_kind: str = ""
    rs: str = ""
    ks: str = ""
    bank: str = ""
    bik: str = ""
    extra_bank: list = field(default_factory=list)
    phone: str = ""
    email: str = ""
    signer: str = ""
    witness: str = ""
    egrip: str = ""

    @classmethod
    def from_dict(cls, d: dict) -> "Requisites":
        """Строит объект из dict, игнорируя лишние ключи."""
        known = {f.name for f in cls.__dataclass_fields__.values()}
        return cls(**{k: v for k, v in (d or {}).items() if k in known})


class DocumentProcessor(ABC):
    """Обработчик одного типа шаблона (договор, акт, счёт, ...)."""

    kind: str = ""
    title: str = ""

    @classmethod
    @abstractmethod
    def matches(cls, template_path: Path) -> bool:
        """Подходит ли этот обработчик для файла-шаблона."""

    @abstractmethod
    def process(self, template_path: Path, req: Requisites,
                output_path: Path) -> Path:
        """Заполнить шаблон req-данными и сохранить в output_path."""
