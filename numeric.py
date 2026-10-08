# -*- coding: utf-8 -*-
"""
Число прописью на русском: 16000.0 → «Шестнадцать тысяч рублей 00 копеек».

Поддерживает целые до 999_999_999_999.
"""
from decimal import Decimal, ROUND_HALF_UP


_ONES_M = ['', 'один', 'два', 'три', 'четыре', 'пять', 'шесть',
           'семь', 'восемь', 'девять']
_ONES_F = ['', 'одна', 'две', 'три', 'четыре', 'пять', 'шесть',
           'семь', 'восемь', 'девять']
_TEENS = ['десять', 'одиннадцать', 'двенадцать', 'тринадцать',
          'четырнадцать', 'пятнадцать', 'шестнадцать',
          'семнадцать', 'восемнадцать', 'девятнадцать']
_TENS = ['', '', 'двадцать', 'тридцать', 'сорок', 'пятьдесят',
         'шестьдесят', 'семьдесят', 'восемьдесят', 'девяносто']
_HUNDREDS = ['', 'сто', 'двести', 'триста', 'четыреста',
             'пятьсот', 'шестьсот', 'семьсот', 'восемьсот',
             'девятьсот']


def _chunk_2_words(n: int, female: bool = False) -> list:
    """Число 0..999 → список слов."""
    words = []
    if n >= 100:
        words.append(_HUNDREDS[n // 100])
        n %= 100
    if 10 <= n < 20:
        words.append(_TEENS[n - 10])
        n = 0
    elif n >= 20:
        words.append(_TENS[n // 10])
        n %= 10
    if n > 0:
        arr = _ONES_F if female else _ONES_M
        words.append(arr[n])
    return words


def _plural_form(n: int, one: str, few: str, many: str) -> str:
    n = abs(n) % 100
    if 11 <= n <= 14:
        return many
    n %= 10
    if n == 1:
        return one
    if 2 <= n <= 4:
        return few
    return many


def _int_to_words(n: int) -> str:
    if n == 0:
        return 'ноль'
    parts = []
    # миллиарды
    if n >= 1_000_000_000:
        b = n // 1_000_000_000
        parts.append(' '.join(_chunk_2_words(b, female=False)))
        parts.append(_plural_form(b, 'миллиард', 'миллиарда', 'миллиардов'))
        n %= 1_000_000_000
    if n >= 1_000_000:
        m = n // 1_000_000
        parts.append(' '.join(_chunk_2_words(m, female=False)))
        parts.append(_plural_form(m, 'миллион', 'миллиона', 'миллионов'))
        n %= 1_000_000
    if n >= 1000:
        t = n // 1000
        parts.append(' '.join(_chunk_2_words(t, female=True)))
        parts.append(_plural_form(t, 'тысяча', 'тысячи', 'тысяч'))
        n %= 1000
    if n > 0:
        parts.append(' '.join(_chunk_2_words(n, female=False)))
    return ' '.join(p for p in parts if p)


def num_to_words(amount, currency='руб', kop='коп') -> str:
    """
    Возвращает строку «Шестнадцать тысяч рублей 00 копеек».

    amount: float/str/Decimal.
    currency: 'руб' или 'руб.'.
    kop:      'коп' или 'коп.'.
    """
    d = Decimal(str(amount)).quantize(Decimal('0.01'),
                                      rounding=ROUND_HALF_UP)
    int_part = int(d)
    frac = int((d - int_part) * 100)

    int_words = _int_to_words(int_part)
    cur_word = _plural_form(int_part, currency, currency, currency)
    kop_word = _plural_form(frac,
                            'копейка', 'копейки', 'копеек')
    return (f"{int_words.capitalize()} {cur_word} "
            f"{frac:02d} {kop_word}")
