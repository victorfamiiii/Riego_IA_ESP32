#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="${PROJECT_DIR:-$(cd "$SCRIPT_DIR/.." && pwd)}"
BACKUP_DIR="${BACKUP_DIR:-$PROJECT_DIR/backups}"
REMOTE="${REMOTE:-onedrive:esp32-backups/postgres}"

if ! command -v rclone >/dev/null 2>&1; then
  echo "ERROR: rclone no está instalado"
  exit 1
fi

if ! rclone listremotes | grep -qx 'onedrive:'; then
  echo "ERROR: el remoto 'onedrive:' no está configurado en rclone"
  exit 1
fi

if [[ ! -d "$BACKUP_DIR" ]]; then
  echo "ERROR: no existe BACKUP_DIR=$BACKUP_DIR"
  exit 1
fi

rclone copy "$BACKUP_DIR" "$REMOTE" \
  --include "esp32-backup-*-COMPLETO.zip.enc" \
  --include "esp32-backup-*-COMPLETO.tar.gz.enc" \
  --transfers 2 --checkers 4 --fast-list

rclone delete "$REMOTE" \
  --min-age 30d \
  --include "esp32-backup-*-COMPLETO.zip.enc" \
  --include "esp32-backup-*-COMPLETO.tar.gz.enc"

echo "OK upload onedrive"