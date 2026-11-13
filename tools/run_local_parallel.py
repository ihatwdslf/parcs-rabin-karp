# -*- coding: utf-8 -*-
"""
Локальний запуск паралельної версії БЕЗ PARCS - тільки для перевірки правильності.

Воркерів PARCS тут імітують окремі процеси (multiprocessing), а сам код
solution/rk_parallel.py не змінюється. Час цього запуску НЕ йде у звіт:
заміри для звіту робляться на кластері в хмарі.

Запуск:  python tools/run_local_parallel.py ВХІДНИЙ_ФАЙЛ ВИХІДНИЙ_ФАЙЛ [КІЛЬКІСТЬ_ВОРКЕРІВ]
Приклад: python tools/run_local_parallel.py input/text_small.txt output_parallel.txt 4
"""
from __future__ import print_function

import multiprocessing
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'solution'))
from rk_parallel import Solver  # noqa: E402


def call_mymap(args):
    return Solver.mymap(*args)


class Future(object):
    """Те саме, що повертає PARCS: результат доступний через .value."""

    def __init__(self, async_result):
        self._r = async_result

    @property
    def value(self):
        return self._r.get()


class LocalWorker(object):
    """Імітує воркер PARCS: mymap виконується в окремому процесі."""

    def __init__(self, pool):
        self.pool = pool

    def mymap(self, *args):
        return Future(self.pool.apply_async(call_mymap, (args,)))


def main():
    if len(sys.argv) not in (3, 4):
        print("Usage: python tools/run_local_parallel.py INPUT_FILE OUTPUT_FILE [WORKERS]")
        sys.exit(1)
    n_workers = int(sys.argv[3]) if len(sys.argv) == 4 else 4
    pool = multiprocessing.Pool(n_workers)
    try:
        workers = [LocalWorker(pool) for _ in range(n_workers)]
        Solver(workers, sys.argv[1], sys.argv[2]).solve()
    finally:
        pool.close()
        pool.join()
    print("Result written to %s" % sys.argv[2])


if __name__ == '__main__':
    main()
