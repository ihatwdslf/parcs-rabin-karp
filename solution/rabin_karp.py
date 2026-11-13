# -*- coding: utf-8 -*-
"""
Спільні функції алгоритму Рабіна-Карпа: читання вхідного файлу і пошук.

Цей файл використовує ПОСЛІДОВНА версія. Паралельна версія для PARCS
містить копію функції search, бо PARCS приймає рівно один файл з кодом.

Код сумісний із Python 2.7 (вузли PARCS) і Python 3.
"""
from __future__ import print_function, division

import io

try:
    range = xrange  # у Python 2 range створив би величезний список
except NameError:
    pass

BASE = 256              # основа: кожен байт рядка - "цифра" від 0 до 255
MOD = 1000000007        # просте число; BASE * MOD < 2^63, тому обчислення не виходять за 64 біти


def read_input(file_name):
    """
    Формат вхідного файлу:
        1-й рядок: кількість шаблонів K
        наступні K рядків: шаблони (усі однакової довжини m)
        останній рядок: текст, у якому шукаємо (один рядок, без переносів)
    Повертає (patterns, text): список шаблонів і текст (рядки ASCII).
    """
    with io.open(file_name, 'r', encoding='ascii', newline='') as f:
        k = int(f.readline().strip())
        if k < 1:
            raise ValueError("There must be at least one pattern")
        patterns = [f.readline().rstrip('\r\n') for _ in range(k)]
        text = f.readline().rstrip('\r\n')
        if f.read().strip():
            raise ValueError("The text must be on a single line")
    m = len(patterns[0])
    if m == 0:
        raise ValueError("Patterns must not be empty")
    for p in patterns:
        if len(p) != m:
            raise ValueError("All patterns must have the same length")
    if len(set(patterns)) != len(patterns):
        raise ValueError("Patterns are repeated")
    return patterns, text


def search(data, patterns, offset):
    """
    Алгоритм Рабіна-Карпа для кількох шаблонів однакової довжини m.

    data     - фрагмент тексту (bytearray), offset - його позиція у всьому тексті.
    patterns - список шаблонів (bytearray).
    Перевіряються всі вікна data[s:s+m], s = 0 .. len(data)-m.

    Повертає (found, windows, collisions):
        found      - словник {номер шаблону: [позиції у всьому тексті]}
        windows    - скільки вікон перевірено
        collisions - скільки разів хеш збігся, а рядок - ні (хибні збіги)
    """
    m = len(patterns[0])
    n = len(data)
    found = dict((i, []) for i in range(len(patterns)))
    if n < m:
        return found, 0, 0

    # хеші шаблонів: h -> список номерів шаблонів із таким хешем
    targets = {}
    for i, p in enumerate(patterns):
        targets.setdefault(poly_hash(p, m), []).append(i)

    high = pow(BASE, m - 1, MOD)  # BASE^(m-1): "вага" першого символу вікна
    h = poly_hash(data, m)        # хеш першого вікна
    collisions = 0
    # локальні змінні прискорюють цикл, який виконується мільйони разів
    base, mod, get = BASE, MOD, targets.get
    last = n - m
    s = 0
    while True:
        hit = get(h)
        if hit is not None:
            window = data[s:s + m]
            matched = False
            for i in hit:
                if window == patterns[i]:   # хеші можуть збігтися випадково - перевіряємо рядок
                    found[i].append(offset + s)
                    matched = True
            if not matched:
                collisions += 1
        if s == last:
            break
        # ковзний хеш: прибираємо перший символ вікна, додаємо наступний
        h = ((h - data[s] * high) * base + data[s + m]) % mod
        s += 1
    return found, last + 1, collisions


def poly_hash(data, m):
    """Поліноміальний хеш перших m символів: (c0*B^(m-1) + ... + c(m-1)) mod MOD."""
    h = 0
    for j in range(m):
        h = (h * BASE + data[j]) % MOD
    return h
