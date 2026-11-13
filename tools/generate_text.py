# -*- coding: utf-8 -*-
"""
Генерує вхідний файл: випадковий текст з літер a-z і вставлені в нього шаблони.

Запуск (Python 3):
    python tools/generate_text.py ДОВЖИНА_ТЕКСТУ ВИХІДНИЙ_ФАЙЛ [--seed N]
Приклад:
    python tools/generate_text.py 20000000 input/text_20m.txt --seed 42

Шаблони і кількість їх вставок задано в PLANTED нижче. Шаблон "notfound"
не вставляється і вилучається з тексту, якщо випадково трапився:
він контрольний, програма НЕ повинна його знайти.
Одне й те саме зерно (--seed) завжди дає той самий файл.
"""
import argparse
import random
import string

# шаблон -> скільки разів вставити (усі шаблони мають однакову довжину 8)
PLANTED = [
    ("parallel", 100),
    ("computer", 50),
    ("hashcode", 25),
    ("notfound", 0),   # контрольний шаблон
]


def find_all(text, pattern):
    """Усі позиції входжень (у тому числі тих, що перекриваються) - незалежна перевірка."""
    result = []
    i = text.find(pattern)
    while i != -1:
        result.append(i)
        i = text.find(pattern, i + 1)
    return result


def main():
    parser = argparse.ArgumentParser(description="Generate input for the Rabin-Karp lab")
    parser.add_argument("length", type=int, help="text length in characters")
    parser.add_argument("output", help="output file")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    m = len(PLANTED[0][0])
    assert all(len(p) == m for p, _ in PLANTED), "all patterns must have the same length"
    total_planted = sum(c for _, c in PLANTED)
    if args.length < 2 * m * (total_planted + 1):
        parser.error("text is too short for so many patterns")

    rng = random.Random(args.seed)
    # текст будуємо блоками байтів: так 100 млн символів займають ~100 МБ пам'яті
    letters = list(string.ascii_lowercase.encode("ascii"))
    text = bytearray()
    block = 1000000
    while len(text) < args.length:
        text += bytes(rng.choices(letters, k=min(block, args.length - len(text))))

    # вставляємо шаблони у випадкові місця так, щоб вставки не перекривалися
    used = set()
    for pattern, count in PLANTED:
        placed = 0
        while placed < count:
            pos = rng.randrange(0, args.length - m + 1)
            if any(c in used for c in range(pos - m + 1, pos + m)):
                continue
            used.add(pos)
            text[pos:pos + m] = pattern.encode("ascii")
            placed += 1

    # контрольний шаблон не повинен зустрічатися в тексті
    for pattern, count in PLANTED:
        if count == 0:
            for pos in find_all(text, pattern.encode("ascii")):
                text[pos] = ord("x")

    with open(args.output, "wb") as f:
        f.write(b"%d\n" % len(PLANTED))
        for pattern, _ in PLANTED:
            f.write(pattern.encode("ascii") + b"\n")
        f.write(text)
        f.write(b"\n")

    print("Written %s: %d characters, seed %d" % (args.output, len(text), args.seed))
    for pattern, count in PLANTED:
        print("  %s: inserted %d, actually in text %d" % (pattern, count, len(find_all(text, pattern.encode("ascii")))))


if __name__ == "__main__":
    main()
