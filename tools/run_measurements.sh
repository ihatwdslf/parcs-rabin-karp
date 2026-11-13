#!/usr/bin/env bash
# Заміри паралельної версії на кластері PARCS для різної кількості воркерів.
# Задача надсилається через API майстра; зайві воркери на час прогону вимикаються,
# тому перестворювати кластер не потрібно.
#
# Запуск:  bash tools/run_measurements.sh ВХІДНИЙ_ФАЙЛ ПАПКА_РЕЗУЛЬТАТІВ [ПРОГОНІВ] [КІЛЬКОСТІ_ВОРКЕРІВ]
# Приклад: bash tools/run_measurements.sh input/text_100m.txt results/run1 3 "1 2 4"
#
# Адреса майстра береться з файлу .master_url (його створює gcp_up.sh)
# або зі змінної MASTER, наприклад: MASTER=http://1.2.3.4:8080 bash tools/run_measurements.sh ...
set -uo pipefail

INPUT=$1
OUT=$2
RUNS=${3:-3}
COUNTS=${4:-"1 2 4"}
SOLUTION=solution/rk_parallel.py
JOB_TIMEOUT=1800
MASTER=${MASTER:-$(cat .master_url 2>/dev/null)}

[ -n "$MASTER" ] || { echo "Невідома адреса майстра: запусти gcp_up.sh або задай MASTER=http://IP:8080"; exit 1; }
[ -f "$INPUT" ] || { echo "Немає файлу $INPUT"; exit 1; }

# не дописуємо до старих замірів, щоб не змішати середні значення
CSV="$OUT/parallel.csv"
if [ -e "$CSV" ]; then
    echo "$CSV вже існує. Вкажи нову папку результатів."
    exit 1
fi
mkdir -p "$OUT"
echo "workers,run,job_id,text_length,occurrences,read_time_s,total_time_s,worker_times_s" > "$CSV"

worker_ids() {
    curl -fsS --max-time 20 "$MASTER/api/worker" \
        | python3 -c "import json,sys; print(' '.join(str(w['id']) for w in sorted(json.load(sys.stdin)['workers'], key=lambda w: w['id'])))"
}

# вмикає перших N воркерів, решту вимикає
set_workers() {
    local want=$1 used=0 id state
    for id in $(worker_ids); do
        if [ "$used" -lt "$want" ]; then state=enable; used=$((used + 1)); else state=disable; fi
        curl -fsS --max-time 20 -o /dev/null -X POST "$MASTER/api/worker/$id/$state" || return 1
    done
    [ "$used" -eq "$want" ]
}

field() { sed -n "s/^$1: *//p" "$2" | head -1 | sed 's/ s$//'; }

# PARCS нумерує задачі по порядку: беремо номер останньої і додаємо 1
last_job() {
    curl -fsS --max-time 20 "$MASTER/jobs" | grep -o '/api/job/[0-9]*/' | grep -o '[0-9]*' | sort -n | tail -1
}

for workers in $COUNTS; do
    set_workers "$workers" || { echo "Не вдалося вибрати $workers воркерів (є: $(worker_ids))"; exit 1; }
    for run in $(seq 1 "$RUNS"); do
        prev=$(last_job)
        echo -n "workers=$workers run=$run: надсилаю задачу... "
        curl -fsS --max-time 600 -o /dev/null \
            -F "job_name=w${workers}_r${run}" -F "solution_file=@$SOLUTION" -F "input_file=@$INPUT" \
            "$MASTER/api/job" || { echo "не вдалося надіслати задачу"; exit 1; }
        job=$(last_job)
        if [ -z "$job" ] || [ "$job" = "$prev" ]; then echo "не знайдено номер нової задачі"; exit 1; fi

        file="$OUT/output_w${workers}_r${run}.txt"
        start=$SECONDS
        # код 200 - готово, 400 - ще виконується, інший - помилка
        while :; do
            code=$(curl -sS --max-time 60 -o "$file" -w '%{http_code}' "$MASTER/api/job/$job/output")
            [ "$code" = 200 ] && break
            if [ "$code" != 400 ]; then echo "задача $job завершилась помилкою (http $code). Подивись $MASTER/jobs"; exit 1; fi
            if [ $((SECONDS - start)) -gt "$JOB_TIMEOUT" ]; then echo "задача $job не завершилась за $JOB_TIMEOUT с"; exit 1; fi
            sleep 2
        done

        got=$(field Workers "$file")
        if [ "$got" != "$workers" ]; then echo "задача $job використала $got воркерів замість $workers"; exit 1; fi
        total=$(field 'Total time' "$file")
        echo "$workers,$run,$job,$(field 'Text length' "$file"),$(field Occurrences "$file"),$(field 'Read time' "$file"),$total,\"$(field 'Worker compute times' "$file")\"" >> "$CSV"
        echo "час ${total} с, знайдено $(field Occurrences "$file")"
    done
done

set_workers "$(worker_ids | wc -w)"
echo "ГОТОВО. Результати: $CSV"
