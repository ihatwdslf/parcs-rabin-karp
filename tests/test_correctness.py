# -*- coding: utf-8 -*-
"""
Перевірка правильності: обидві версії порівнюються з незалежним пошуком (str.find).

Запуск: python tests/test_correctness.py
Перевіряється:
  - випадкові тексти з малим алфавітом (багато входжень, у тому числі тих, що перекриваються);
  - різна кількість воркерів, зокрема більше воркерів, ніж позицій у тексті;
  - входження на межах фрагментів воркерів;
  - діапазони воркерів покривають усі позиції рівно один раз;
  - хибні збіги хешу (колізії) не потрапляють у результат (перевірка з малим модулем);
  - некоректні вхідні файли відхиляються.
"""
from __future__ import print_function, division

import io
import os
import random
import sys
import tempfile

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
sys.path.insert(0, os.path.join(ROOT, 'solution'))

import rabin_karp  # noqa: E402
import rk_parallel  # noqa: E402
from rk_parallel import Solver  # noqa: E402


class Future(object):
    def __init__(self, value):
        self.value = value


class SyncWorker(object):
    """Воркер, що виконує mymap одразу (для тестів паралельність не потрібна)."""
    calls = []

    def mymap(self, chunk, patterns, offset):
        SyncWorker.calls.append((offset, len(chunk)))
        return Future(Solver.mymap(chunk, patterns, offset))


def find_all(text, pattern):
    result = []
    i = text.find(pattern)
    while i != -1:
        result.append(i)
        i = text.find(pattern, i + 1)
    return result


def write_input(path, patterns, text):
    with io.open(path, 'w', encoding='ascii', newline='\n') as f:
        f.write(u"%d\n" % len(patterns))
        for p in patterns:
            f.write(p + u"\n")
        f.write(text + u"\n")


def parse_results(path):
    results = {}
    with io.open(path, 'r', encoding='ascii') as f:
        lines = f.read().split(u"\n")
    start = lines.index(u"Results:") + 1
    for line in lines[start:]:
        if not line:
            continue
        p, count, positions = line.split(u": ", 2)
        results[p] = [int(x) for x in positions.split()] if positions.strip() else []
        assert len(results[p]) == int(count)
    return results


def run_parallel(path_in, path_out, n_workers):
    SyncWorker.calls = []
    stdout, sys.stdout = sys.stdout, open(os.devnull, 'w')  # повідомлення Solver тут не потрібні
    try:
        Solver([SyncWorker() for _ in range(n_workers)], path_in, path_out).solve()
    finally:
        sys.stdout.close()
        sys.stdout = stdout
    return parse_results(path_out)


def check_case(tmp, patterns, text, worker_counts):
    path_in = os.path.join(tmp, 'in.txt')
    path_out = os.path.join(tmp, 'out.txt')
    write_input(path_in, patterns, text)
    expected = dict((p, find_all(text, p)) for p in patterns)

    # послідовна версія
    ps, t = rabin_karp.read_input(path_in)
    found, windows, _ = rabin_karp.search(bytearray(t.encode('ascii')),
                                          [bytearray(p.encode('ascii')) for p in ps], 0)
    for i, p in enumerate(ps):
        assert found[i] == expected[p], ("sequential", p, found[i], expected[p])
    assert windows == max(len(text) - len(patterns[0]) + 1, 0)

    # паралельна версія
    m = len(patterns[0])
    for k in worker_counts:
        got = run_parallel(path_in, path_out, k)
        for p in patterns:
            assert got[p] == expected[p], ("parallel", k, p, got[p], expected[p])
        # кожна позиція перевіряється рівно одним воркером
        covered = []
        for offset, chunk_len in SyncWorker.calls:
            covered.extend(range(offset, offset + max(chunk_len - m + 1, 0)))
        assert covered == list(range(max(len(text) - m + 1, 0))), ("coverage", k)


def test_random(tmp):
    rng = random.Random(1)
    cases = 0
    for _ in range(300):
        alphabet = rng.choice([u"ab", u"abc", u"abcdefghij"])
        m = rng.randint(1, 6)
        n = rng.randint(0, 200)
        text = u"".join(rng.choice(alphabet) for _ in range(n))
        patterns = set()
        while len(patterns) < rng.randint(1, 4):
            if text and rng.random() < 0.7 and n >= m:
                s = rng.randint(0, n - m)
                patterns.add(text[s:s + m])        # шаблон, який точно є в тексті
            else:
                patterns.add(u"".join(rng.choice(alphabet + u"z") for _ in range(m)))
        check_case(tmp, sorted(patterns), text, [1, 2, 3, 4, 7, 16])
        cases += 1
    print("random cases: %d OK" % cases)


def test_boundaries(tmp):
    # шаблон рівно на межі фрагментів 2 і 4 воркерів
    text = u"a" * 47 + u"needle" + u"b" * 47 + u"needle" + u"c" * 44
    check_case(tmp, [u"needle", u"absent"], text, [1, 2, 3, 4, 5, 8])
    # текст коротший за шаблон і текст рівно довжини шаблону
    check_case(tmp, [u"abcd"], u"abc", [1, 4])
    check_case(tmp, [u"abcd"], u"abcd", [1, 4])
    # шаблони, що перекриваються самі з собою
    check_case(tmp, [u"aaa", u"aab"], u"aaaaaab" * 10, [1, 2, 4, 7])
    print("boundary cases: OK")


def test_collisions(tmp):
    """З малим модулем хеші часто збігаються - результат має лишитися правильним."""
    old = (rabin_karp.MOD, rk_parallel.MOD)
    rabin_karp.MOD = rk_parallel.MOD = 7
    try:
        rng = random.Random(2)
        text = u"".join(rng.choice(u"abcd") for _ in range(500))
        patterns = [text[10:15], text[300:305], u"zzzzz"]
        check_case(tmp, patterns, text, [1, 3, 4])
        _, _, collisions = rabin_karp.search(bytearray(text.encode('ascii')),
                                             [bytearray(p.encode('ascii')) for p in patterns], 0)
        assert collisions > 0
    finally:
        rabin_karp.MOD, rk_parallel.MOD = old
    print("hash collisions handled: OK (%d false hash matches rejected)" % collisions)


def test_bad_input(tmp):
    path = os.path.join(tmp, 'bad.txt')
    bad_files = [
        u"2\nabc\nabcd\ntext\n",       # різна довжина шаблонів
        u"2\nabc\nabc\ntext\n",        # повтор шаблону
        u"1\n\ntext\n",                # порожній шаблон
        u"0\ntext\n",                  # немає шаблонів
        u"1\nabc\ntext\nmore text\n",  # текст у кількох рядках
    ]
    for content in bad_files:
        with io.open(path, 'w', encoding='ascii', newline='\n') as f:
            f.write(content)
        for reader in (lambda: rabin_karp.read_input(path),
                       lambda: Solver([], path, None).read_input()):
            try:
                reader()
            except ValueError:
                pass
            else:
                raise AssertionError("accepted bad input: %r" % content)
    print("bad input rejected: OK")


def main():
    tmp = tempfile.mkdtemp()
    test_random(tmp)
    test_boundaries(tmp)
    test_collisions(tmp)
    test_bad_input(tmp)
    print("ALL TESTS PASSED (Python %d.%d)" % sys.version_info[:2])


if __name__ == '__main__':
    main()
