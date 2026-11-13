# -*- coding: utf-8 -*-
"""
PARCS: паралельний пошук шаблонів у тексті алгоритмом Рабіна-Карпа.

Текст має N символів, шаблони - m символів, отже вікон (можливих позицій
входження) P = N - m + 1. Майстер ділить позиції на k рівних діапазонів
[start, end) за кількістю воркерів і надсилає кожному воркеру фрагмент
text[start : end + m - 1]. Фрагменти сусідніх воркерів перекриваються на
m - 1 символів, тому входження на межі фрагментів не губляться.
Воркери шукають шаблони у своїх фрагментах, майстер об'єднує позиції.

Вхідний файл: кількість шаблонів K, K шаблонів однакової довжини, текст одним рядком.
Код сумісний із Python 2.7 (вузли PARCS) і Python 3.
"""
from __future__ import print_function, division

import io
import time

try:
    from Pyro4 import expose
except ImportError:  # для локального запуску без PARCS декоратор не потрібен
    def expose(f):
        return f

try:
    range = xrange  # у Python 2 range створив би величезний список
except NameError:
    pass

BASE = 256              # основа: кожен байт рядка - "цифра" від 0 до 255
MOD = 1000000007        # просте число; BASE * MOD < 2^63, тому обчислення не виходять за 64 біти


class Solver:

    def __init__(self, workers=None, input_file_name=None, output_file_name=None):
        self.input_file_name = input_file_name
        self.output_file_name = output_file_name
        self.workers = workers
        print("Inited")

    def solve(self):
        print("Job Started")
        n_workers = len(self.workers)
        print("Workers %d" % n_workers)
        t_start = time.time()

        patterns, text = self.read_input()
        t_read = time.time() - t_start
        m = len(patterns[0])
        positions = max(len(text) - m + 1, 0)  # кількість вікон

        # map: виклики асинхронні, тому всі воркери рахують одночасно
        ranges = []
        mapped = []
        for i in range(n_workers):
            start = positions * i // n_workers
            end = positions * (i + 1) // n_workers
            ranges.append((start, end))
            chunk = text[start:end + m - 1] if end > start else u""
            mapped.append(self.workers[i].mymap(chunk, patterns, start))

        # reduce: чекаємо всіх воркерів і об'єднуємо знайдені позиції
        found, worker_results = self.myreduce(mapped, len(patterns))

        elapsed = time.time() - t_start
        self.write_output(n_workers, patterns, len(text), found, elapsed, t_read, ranges, worker_results)
        print("Job Finished in %.3f s" % elapsed)

    @staticmethod
    @expose
    def mymap(chunk, patterns, offset):
        """Виконується на воркері; повертає (позиції, вікна, колізії, секунди)."""
        t0 = time.time()
        data = bytearray(chunk.encode('ascii'))
        pattern_bytes = [bytearray(p.encode('ascii')) for p in patterns]
        found, windows, collisions = Solver.search(data, pattern_bytes, offset)
        # список списків надійніше передається через Pyro4, ніж словник
        result = [found[i] for i in range(len(patterns))]
        return result, windows, collisions, time.time() - t0

    @staticmethod
    @expose
    def myreduce(mapped, n_patterns):
        found = [[] for _ in range(n_patterns)]
        worker_results = []
        for future in mapped:
            result, windows, collisions, seconds = future.value  # .value чекає завершення воркера
            for i in range(n_patterns):
                found[i].extend(result[i])   # воркери йдуть по порядку, тож позиції вже відсортовані
            worker_results.append((sum(len(r) for r in result), windows, collisions, seconds))
        return found, worker_results

    @staticmethod
    def search(data, patterns, offset):
        """
        Алгоритм Рабіна-Карпа для кількох шаблонів однакової довжини m.
        data - фрагмент тексту (bytearray), offset - його позиція у всьому тексті.
        Повертає ({номер шаблону: [позиції]}, кількість вікон, кількість хибних збігів хешу).
        """
        m = len(patterns[0])
        n = len(data)
        found = dict((i, []) for i in range(len(patterns)))
        if n < m:
            return found, 0, 0

        # хеші шаблонів: h -> список номерів шаблонів із таким хешем
        targets = {}
        for i, p in enumerate(patterns):
            targets.setdefault(Solver.poly_hash(p, m), []).append(i)

        high = pow(BASE, m - 1, MOD)       # BASE^(m-1): "вага" першого символу вікна
        h = Solver.poly_hash(data, m)      # хеш першого вікна
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

    @staticmethod
    def poly_hash(data, m):
        """Поліноміальний хеш перших m символів: (c0*B^(m-1) + ... + c(m-1)) mod MOD."""
        h = 0
        for j in range(m):
            h = (h * BASE + data[j]) % MOD
        return h

    def read_input(self):
        with io.open(self.input_file_name, 'r', encoding='ascii', newline='') as f:
            k = int(f.readline().strip())
            if k < 1:
                raise ValueError("There must be at least one pattern")
            patterns = [f.readline().rstrip(u'\r\n') for _ in range(k)]
            text = f.readline().rstrip(u'\r\n')
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

    def write_output(self, n_workers, patterns, text_length, found, elapsed, t_read, ranges, worker_results):
        m = len(patterns[0])
        with io.open(self.output_file_name, 'w', encoding='ascii', newline='\n') as f:
            f.write(u"Version: parallel\n")
            f.write(u"Workers: %d\n" % n_workers)
            f.write(u"Text length: %d\n" % text_length)
            f.write(u"Pattern length: %d\n" % m)
            f.write(u"Patterns: %d\n" % len(patterns))
            f.write(u"Windows checked: %d\n" % sum(r[1] for r in worker_results))
            f.write(u"Hash collisions: %d\n" % sum(r[2] for r in worker_results))
            f.write(u"Occurrences: %d\n" % sum(len(x) for x in found))
            f.write(u"Read time: %.3f s\n" % t_read)
            f.write(u"Total time: %.3f s\n" % elapsed)
            f.write(u"Worker compute times: %s\n" % u", ".join(u"%.3f" % r[3] for r in worker_results))
            # номер воркера: діапазон позицій [start, end), розмір фрагмента, знахідки, вікна, колізії, секунди
            for i in range(n_workers):
                start, end = ranges[i]
                chunk_len = (end - start + m - 1) if end > start else 0
                count, windows, collisions, seconds = worker_results[i]
                f.write(u"Worker %d: positions %d-%d, chunk %d chars, found %d, windows %d, collisions %d, %.3f s\n"
                        % (i + 1, start, end, chunk_len, count, windows, collisions, seconds))
            f.write(u"Results:\n")
            for i, p in enumerate(patterns):
                f.write(u"%s: %d: %s\n" % (p, len(found[i]), u" ".join(str(x) for x in found[i])))
        print("output done")
