# -*- coding: utf-8 -*-
"""
Послідовна версія: пошук шаблонів у тексті алгоритмом Рабіна-Карпа.

Запуск:  python solution/rk_sequential.py ВХІДНИЙ_ФАЙЛ ВИХІДНИЙ_ФАЙЛ
Приклад: python solution/rk_sequential.py input/text_small.txt output.txt

Код сумісний із Python 2.7 і Python 3.
"""
from __future__ import print_function, division

import io
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rabin_karp import read_input, search  # noqa: E402


def main():
    if len(sys.argv) != 3:
        print("Usage: python rk_sequential.py INPUT_FILE OUTPUT_FILE")
        sys.exit(1)
    input_file, output_file = sys.argv[1], sys.argv[2]

    t_start = time.time()
    patterns, text = read_input(input_file)
    data = bytearray(text.encode('ascii'))
    pattern_bytes = [bytearray(p.encode('ascii')) for p in patterns]
    t_read = time.time() - t_start

    found, windows, collisions = search(data, pattern_bytes, 0)
    elapsed = time.time() - t_start

    with io.open(output_file, 'w', encoding='ascii', newline='\n') as f:
        f.write(u"Version: sequential\n")
        f.write(u"Text length: %d\n" % len(text))
        f.write(u"Pattern length: %d\n" % len(patterns[0]))
        f.write(u"Patterns: %d\n" % len(patterns))
        f.write(u"Windows checked: %d\n" % windows)
        f.write(u"Hash collisions: %d\n" % collisions)
        f.write(u"Occurrences: %d\n" % sum(len(v) for v in found.values()))
        f.write(u"Read time: %.3f s\n" % t_read)
        f.write(u"Total time: %.3f s\n" % elapsed)
        f.write(u"Results:\n")
        for i, p in enumerate(patterns):
            positions = found[i]
            f.write(u"%s: %d: %s\n" % (p, len(positions), u" ".join(str(x) for x in positions)))

    print("Text length: %d, patterns: %d" % (len(text), len(patterns)))
    for i, p in enumerate(patterns):
        print("  %s: %d occurrences" % (p, len(found[i])))
    print("Hash collisions: %d" % collisions)
    print("Total time: %.3f s (reading %.3f s)" % (elapsed, t_read))


if __name__ == '__main__':
    main()
