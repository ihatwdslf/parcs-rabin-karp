#!/usr/bin/env bash
# Видаляє кластер PARCS (усі VM з міткою lab=parcs разом із дисками) і правило firewall.
# Запуск: bash tools/gcp_down.sh
set -uo pipefail

ZONE=${ZONE:-europe-central2-a}
PROJECT=$(gcloud config get-value project 2>/dev/null)

VMS=$(gcloud compute instances list --project "$PROJECT" --filter=labels.lab=parcs --format='value(name)')
if [ -n "$VMS" ]; then
    echo "Видаляю VM: $(echo $VMS)"
    # shellcheck disable=SC2086
    gcloud compute instances delete $VMS --project "$PROJECT" --zone "$ZONE" --delete-disks=all --quiet
fi

if [ -n "$(gcloud compute firewall-rules list --project "$PROJECT" --filter=name=parcs-web --format='value(name)')" ]; then
    gcloud compute firewall-rules delete parcs-web --project "$PROJECT" --quiet
fi
rm -f .master_url

# перевіряємо, що нічого платного не лишилося
LEFT_VMS=$(gcloud compute instances list --project "$PROJECT" --format='value(name)')
LEFT_DISKS=$(gcloud compute disks list --project "$PROJECT" --format='value(name)')
if [ -z "$LEFT_VMS" ] && [ -z "$LEFT_DISKS" ]; then
    echo "Готово: у проєкті не залишилося жодної VM і жодного диска."
else
    echo "УВАГА: у проєкті ще є ресурси. VM: ${LEFT_VMS:-немає}; диски: ${LEFT_DISKS:-немає}"
    exit 1
fi
