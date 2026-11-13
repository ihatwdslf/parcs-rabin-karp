#!/usr/bin/env bash
# Створює кластер PARCS у Google Cloud: майстер і N воркерів.
# Запускати в Google Cloud Shell (там уже є gcloud і вибраний проєкт).
#
# Запуск:  bash tools/gcp_up.sh [КІЛЬКІСТЬ_ВОРКЕРІВ] [ТВОЯ_IP_АДРЕСА]
# Приклад: bash tools/gcp_up.sh 4 93.170.12.34
#
# ТВОЯ_IP_АДРЕСА - адреса твого домашнього інтернету (дізнатися: https://checkip.amazonaws.com).
# Вона потрібна, щоб відкрити вебсторінку PARCS у браузері. Без неї сторінка буде
# доступна лише з Cloud Shell.
#
# УВАГА: віртуальні машини коштують грошей, поки існують.
# Після роботи обов'язково запусти: bash tools/gcp_down.sh
set -Eeuo pipefail  # -E: пастка ERR спрацьовує і всередині функцій

WORKERS=${1:-4}
MY_IP=${2:-}
ZONE=${ZONE:-europe-central2-a}          # Варшава - найближчий до Києва регіон
MACHINE=${MACHINE:-n1-standard-1}        # 1 vCPU, 3,75 ГБ пам'яті
IMAGE=registry.hub.docker.com/hummer12007/parcs-node

PROJECT=$(gcloud config get-value project 2>/dev/null)
if [ -z "$PROJECT" ]; then
    echo "Проєкт не вибрано. Виконай: gcloud config set project ID_ПРОЄКТУ"
    exit 1
fi
echo "Проєкт: $PROJECT, зона: $ZONE, воркерів: $WORKERS"

echo "Вмикаю Compute Engine API (перший раз може тривати 1-2 хвилини)..."
gcloud services enable compute.googleapis.com --project "$PROJECT"

if [ -n "$(gcloud compute instances list --project "$PROJECT" --filter=labels.lab=parcs --format='value(name)')" ]; then
    echo "Кластер уже існує. Спочатку видали його: bash tools/gcp_down.sh"
    exit 1
fi

# PARCS виконує будь-який надісланий код без пароля, тому порт 8080
# відкриваємо лише для Cloud Shell і твоєї домашньої адреси.
SHELL_IP=$(curl -fsS --max-time 15 https://checkip.amazonaws.com | tr -d '[:space:]')
SOURCES="$SHELL_IP/32"
[ -n "$MY_IP" ] && SOURCES="$SOURCES,$MY_IP/32"
echo "Доступ до порту 8080 дозволено з: $SOURCES"

# мережа default і правило для обміну між VM зазвичай створюються з проєктом;
# якщо їх немає - створюємо
if ! gcloud compute networks describe default --project "$PROJECT" >/dev/null 2>&1; then
    gcloud compute networks create default --project "$PROJECT" --subnet-mode=auto
fi
if [ -z "$(gcloud compute firewall-rules list --project "$PROJECT" --filter=name=default-allow-internal --format='value(name)')" ]; then
    gcloud compute firewall-rules create default-allow-internal --project "$PROJECT" --network=default \
        --direction=INGRESS --action=ALLOW --rules=tcp,udp,icmp --source-ranges=10.128.0.0/9
fi
if [ -z "$(gcloud compute firewall-rules list --project "$PROJECT" --filter=name=default-allow-ssh --format='value(name)')" ]; then
    gcloud compute firewall-rules create default-allow-ssh --project "$PROJECT" --network=default \
        --direction=INGRESS --action=ALLOW --rules=tcp:22 --source-ranges=0.0.0.0/0
fi
if [ -n "$(gcloud compute firewall-rules list --project "$PROJECT" --filter=name=parcs-web --format='value(name)')" ]; then
    gcloud compute firewall-rules update parcs-web --project "$PROJECT" --source-ranges="$SOURCES"
else
    gcloud compute firewall-rules create parcs-web --project "$PROJECT" --network=default \
        --direction=INGRESS --action=ALLOW --rules=tcp:8080 --source-ranges="$SOURCES" --target-tags=parcs-master
fi

# стартовий скрипт VM: запускає контейнер PARCS із потрібною роллю
startup_script() {
    cat <<EOF
#!/bin/bash
# Container-Optimized OS блокує вхідні з'єднання; ззовні доступ і далі обмежує firewall Google Cloud
iptables -w -A INPUT -p tcp -j ACCEPT
docker rm -f parcs 2>/dev/null
docker run -d --name parcs --restart=always --network host -e PARCS_ARGS="$1" $IMAGE
EOF
}

create_vm() {  # ім'я, роль PARCS, мережевий тег, розмір диска
    local file
    file=$(mktemp)
    startup_script "$2" > "$file"
    # --no-service-account: образ PARCS сторонній, тож VM не отримує доступу до API проєкту
    # --labels=lab=parcs: за цією міткою gcp_down.sh знаходить машини
    gcloud compute instances create "$1" --project "$PROJECT" --zone "$ZONE" \
        --machine-type "$MACHINE" --image-family=cos-stable --image-project=cos-cloud \
        --boot-disk-size="$4GB" --no-service-account --no-scopes \
        --tags="$3" --labels=lab=parcs --metadata-from-file=startup-script="$file"
    rm -f "$file"
}

cleanup_on_error() {
    echo
    echo "ПОМИЛКА під час створення кластера. Видаляю вже створені VM, щоб вони не коштували грошей..."
    bash "$(dirname "$0")/gcp_down.sh" || echo "Не вдалося видалити VM! Запусти вручну: bash tools/gcp_down.sh"
}
trap cleanup_on_error ERR

create_vm master master parcs-master 20
INTERNAL=$(gcloud compute instances describe master --project "$PROJECT" --zone "$ZONE" --format='get(networkInterfaces[0].networkIP)')
EXTERNAL=$(gcloud compute instances describe master --project "$PROJECT" --zone "$ZONE" --format='get(networkInterfaces[0].accessConfigs[0].natIP)')

for i in $(seq 1 "$WORKERS"); do
    create_vm "worker$i" "worker $INTERNAL" parcs-worker 10
done
trap - ERR

echo "http://$EXTERNAL:8080" > .master_url
echo
echo "VM створено. Чекаю, поки PARCS запуститься і воркери зареєструються (зазвичай 2-4 хвилини)..."
for _ in $(seq 1 60); do
    count=$(curl -fsS --max-time 5 "http://$EXTERNAL:8080/api/worker" 2>/dev/null \
        | python3 -c "import json,sys; print(len(json.load(sys.stdin)['workers']))" 2>/dev/null || echo 0)
    echo "  зареєстровано воркерів: $count з $WORKERS"
    [ "$count" -ge "$WORKERS" ] && break
    sleep 10
done

echo
echo "Готово. Адреса майстра PARCS: http://$EXTERNAL:8080 (збережено у файлі .master_url)"
[ -n "$MY_IP" ] && echo "Її можна відкрити у браузері на твоєму комп'ютері."
echo "НЕ ЗАБУДЬ після роботи видалити кластер: bash tools/gcp_down.sh"
