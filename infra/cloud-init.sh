#!/usr/bin/env bash
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y docker.io docker-compose-v2 openssl
systemctl enable --now docker
usermod -aG docker ubuntu
install -d -o ubuntu -g ubuntu -m 750 /opt/transaction-pipeline
umask 077
# Les secrets sont créés sur la VM, pas dans le state Terraform ou les logs CI.
if [ ! -e /opt/transaction-pipeline/.env ]; then
  {
    printf 'POSTGRES_PASSWORD=%s\n' "$(openssl rand -hex 24)"
    printf 'S3_ACCESS_KEY=%s\n' "$(openssl rand -hex 12)"
    printf 'S3_SECRET_KEY=%s\n' "$(openssl rand -hex 24)"
    printf 'S3_BUCKET=transactions\nPOSTGRES_PORT=5433\nS3_PORT=8333\n'
  } > /opt/transaction-pipeline/.env
  chown ubuntu:ubuntu /opt/transaction-pipeline/.env
fi
