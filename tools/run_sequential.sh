#!/usr/bin/env bash
# Заміри послідовної версії на VM майстра - на такій самій машині, у тому самому
# контейнері і на тому самому Python 2.7, що й воркери PARCS. Тоді порівняння чесне.
#
# Запуск:  bash tools/run_sequential.sh ВХІДНИЙ_ФАЙЛ ПАПКА_РЕЗУЛЬТАТІВ [ПРОГОНІВ]
# Приклад: bash tools/run_sequential.sh input/text_100m.txt results/run1 3
#
# Запускати, коли на кластері не виконується жодна задача.
set -euo pipefail

INPUT=$1
OUT=$2
RUNS=${3:-3}
ZONE=${ZONE:-europe-central2-a}
PROJECT=$(gcloud config get-value project 2>/dev/null)

CSV="$OUT/sequential.csv"
if [ -e "$CSV" ]; then
    echo "$CSV вже існує. Вкажи нову папку результатів."
    exit 1
fi
mkdir -p "$OUT"

ssh_master() { gcloud compute ssh master --project "$PROJECT" --zone "$ZONE" --quiet --command "$1"; }

echo "Копіюю програму і вхідні дані на майстра (перший раз gcloud створить SSH-ключ - просто натискай Enter)..."
gcloud compute scp solution/rk_sequential.py solution/rabin_karp.py "$INPUT" master:~ \
    --project "$PROJECT" --zone "$ZONE" --quiet
NAME=$(basename "$INPUT")
ssh_master "sudo docker exec parcs mkdir -p /tmp/seq && \
    sudo docker cp ~/rk_sequential.py parcs:/tmp/seq/ && \
    sudo docker cp ~/rabin_karp.py parcs:/tmp/seq/ && \
    sudo docker cp ~/$NAME parcs:/tmp/seq/input.txt && \
    sudo docker exec parcs python2.7 --version"

echo "run,text_length,occurrences,read_time_s,total_time_s" > "$CSV"
for run in $(seq 1 "$RUNS"); do
    echo -n "sequential run=$run: "
    file="$OUT/output_sequential_r${run}.txt"
    ssh_master "sudo docker exec parcs python2.7 /tmp/seq/rk_sequential.py /tmp/seq/input.txt /tmp/seq/output.txt >/dev/null && \
        sudo docker exec parcs cat /tmp/seq/output.txt" > "$file"
    field() { sed -n "s/^$1: *//p" "$file" | head -1 | sed 's/ s$//'; }
    echo "$run,$(field 'Text length'),$(field Occurrences),$(field 'Read time'),$(field 'Total time')" >> "$CSV"
    echo "час $(field 'Total time') с, знайдено $(field Occurrences)"
done

ssh_master "sudo docker exec parcs rm -rf /tmp/seq; rm -f ~/rk_sequential.py ~/rabin_karp.py ~/$NAME"
echo "ГОТОВО. Результати: $CSV"
