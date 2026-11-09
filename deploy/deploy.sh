#!/usr/bin/env bash
set -euo pipefail
cd /opt/transaction-pipeline
exec 9>/opt/transaction-pipeline/pipeline.lock
flock -w 300 9
[ -f .env ] || { echo 'Créer /opt/transaction-pipeline/.env avant le déploiement.' >&2; exit 1; }
docker compose config --quiet
docker compose build --pull pipeline
docker compose up -d --wait postgres s3
# Initialise le schéma et vérifie la connexion à la base.
docker compose run --rm -T pipeline init --source s3
docker compose run --rm -T pipeline report
# systemd lance la lecture des nouveaux objets toutes les minutes.
sudo install -m 644 deploy/transaction-pipeline.service /etc/systemd/system/
sudo install -m 644 deploy/transaction-pipeline.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now transaction-pipeline.timer
