# -*- coding: utf-8 -*-
"""
Морфология ФИО: склонение, сокращение, определение рода,
очистка от служебных ярлыков.

pymorphy3 — опциональная зависимость. Если её нет, склонение не
производится, но остальной функционал работает.
"""
import re

try:
    import pymorphy3
    _morph = pymorphy3.MorphAnalyzer()
except ImportError:
    _morph = None


# Слова, которые НЕ могут быть частью ФИО (ярлыки полей).
_FIO_LABEL_LOWER = frozenset((
    'полное', 'наименование', 'сокращенное', 'сокращённое',
    'адрес', 'телефон', 'факс', 'почта', 'e-mail', 'email',
    'юридический', 'почтовый', 'фактический',
    'ф.и.о.', 'фио',
))

# Расширенный стоп-лист для ФИО (иногда OCR затягивает служебные слова).
_FIO_EXTRA_STOP = frozenset((
    'наименование', 'полное', 'сокращённое', 'сокращенное',
    'компании', 'организации', 'предприниматель',
    'фирменное', 'сведения',
))


def detect_gender(parts) -> str | None:
    """'masc' / 'femn' / None — по отчеству, затем имени, затем фамилии."""
    if not _morph:
        return None
    for i in (2, 1, 0):
        if i >= len(parts):
            continue
        for pr in _morph.parse(parts[i]):
            tag = pr.tag
            if 'femn' in tag and 'masc' not in tag:
                return 'femn'
            if 'masc' in tag and 'femn' not in tag:
                return 'masc'
    return None


def _surname_genitive(word: str, gender: str | None = None) -> str:
    if not word:
        return word
    low = word.lower()
    if gender == 'femn':
        if low.endswith(('ова', 'ева', 'ёва', 'ина', 'ына')):
            return word[:-1] + 'ой'
        if low.endswith(('ская', 'цкая', 'ая')):
            return word[:-2] + 'ой'
        if low.endswith(('ко', 'енко', 'их', 'ых', 'аго', 'яго',
                         'ово', 'ево')):
            return word
        return word
    if low.endswith(('ов', 'ев', 'ёв', 'ин', 'ын')):
        return word + 'а'
    if low.endswith('ий'):
        return word[:-2] + 'его'
    if low.endswith('ый'):
        return word[:-2] + 'ого'
    if low.endswith('ой'):
        return word[:-2] + 'ого'
    return word


def to_genitive(fio: str) -> str:
    """ФИО в родительный падеж: «Иванов Иван Иванович» → «Иванова Ивана Ивановича»."""
    if not fio:
        return fio
    parts = fio.split()
    if not parts:
        return fio
    gender = detect_gender(parts)
    out = []
    for i, p in enumerate(parts):
        if i == 0:
            out.append(_surname_genitive(p, gender).capitalize())
            continue
        chosen = None
        if _morph:
            for tag in ('Name', 'Patr'):
                candidates = [pr for pr in _morph.parse(p) if tag in pr.tag]
                if not candidates:
                    continue
                if gender:
                    for pr in candidates:
                        if gender in pr.tag:
                            chosen = pr
                            break
                if chosen is None:
                    chosen = candidates[0]
                break
            if chosen is None:
                for pr in _morph.parse(p):
                    chosen = pr
                    break
        if chosen is None:
            out.append(p.capitalize())
            continue
        try:
            g = chosen.inflect({"gent"})
            out.append((g.word if g else p).capitalize())
        except Exception:
            out.append(p.capitalize())
    return " ".join(out)


def to_nominative_fio(fio: str) -> str:
    """
    Обратное к to_genitive: «Иванова Ивана Ивановича» → «Иванов Иван Иванович».
    Работает только если окончания явно указывают на косвенный падеж.
    Сокращения («Иванов И. И.») не трогает.
    """
    if not fio or not _morph:
        return fio
    parts = fio.split()
    if len(parts) < 2:
        return fio
    tail = parts[-1].lower()
    need_fix = (
        tail.endswith(('овича', 'евича', 'ича', 'ыча',
                       'овны', 'евны', 'ичны', 'иничны'))
        or (len(parts) >= 2
            and parts[1].lower().endswith(('ии', 'ьи')))
    )
    if not need_fix:
        return fio
    out = []
    for i, p in enumerate(parts):
        chosen = None
        for pr in _morph.parse(p):
            tags = pr.tag
            if i == 0:
                if not any(t in tags for t in ('Surn', 'Name', 'Patr')):
                    continue
            else:
                if not any(t in tags for t in ('Name', 'Patr')):
                    continue
            g = pr.inflect({'nomn'})
            if g:
                chosen = g.word
                break
        out.append((chosen or p).capitalize())
    return ' '.join(out)


def to_short(fio: str) -> str:
    """«Иванов Иван Иванович» → «Иванов И. И.»."""
    if not fio:
        return fio
    parts = fio.split()
    if len(parts) < 2:
        return fio
    return parts[0] + " " + " ".join(f"{p[0]}." for p in parts[1:])


def normalize_fio_case(s: str) -> str:
    """Всё капсом или всё строчными — привести к «Заглавная+строчные»."""
    if not s:
        return s
    out = []
    for w in s.split():
        if not w:
            continue
        if w.isupper() or w.islower():
            out.append(w.capitalize())
        else:
            out.append(w)
    return ' '.join(out)


def clean_fio_words(fio: str) -> str:
    """Убирает служебные ярлыки («наименование», «полное», «фио»...)."""
    if not fio:
        return fio
    out = []
    for p in fio.split():
        token = p.lower().strip('.,;:«»"\'()')
        if token in _FIO_LABEL_LOWER:
            continue
        if token in _FIO_EXTRA_STOP:
            continue
        out.append(p)
    return ' '.join(out)