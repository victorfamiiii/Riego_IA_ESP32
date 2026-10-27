#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="${PROJECT_DIR:-$(cd "$SCRIPT_DIR/.." && pwd)}"
BACKUP_DIR="${BACKUP_DIR:-$PROJECT_DIR/backups}"
DB_CONTAINER="${DB_CONTAINER:-esp32-db}"
DB_USER="${DB_USER:-victor}"
DB_NAME="${DB_NAME:-esp32db}"
DB_EXTRA_NAME="${DB_EXTRA_NAME:-victor}"
KEEP_LAST="${KEEP_LAST:-7}"
ENCRYPT_SCRIPT="${ENCRYPT_SCRIPT:-$SCRIPT_DIR/encrypt_backup.py}"

: "${BACKUP_ENCRYPTION_KEY:?ERROR: define BACKUP_ENCRYPTION_KEY en el entorno}"

TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP_NAME="esp32-backup-${TIMESTAMP}"

mkdir -p "$BACKUP_DIR"

echo "[backup] Exportando bases de datos..."
docker exec "$DB_CONTAINER" pg_dump -U "$DB_USER" "$DB_NAME" | gzip > "$BACKUP_DIR/${BACKUP_NAME}-db.sql.gz"

INCLUDE_EXTRA_DB=false
if docker exec "$DB_CONTAINER" psql -U "$DB_USER" -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='${DB_EXTRA_NAME}'" | grep -q 1; then
  docker exec "$DB_CONTAINER" pg_dump -U "$DB_USER" "$DB_EXTRA_NAME" | gzip > "$BACKUP_DIR/${BACKUP_NAME}-victor.sql.gz"
  INCLUDE_EXTRA_DB=true
else
  echo "[backup] Aviso: la base '${DB_EXTRA_NAME}' no existe; se omite su dump"
fi

cd "$BACKUP_DIR"

if command -v zip >/dev/null 2>&1; then
  zip -q "${BACKUP_NAME}-COMPLETO.zip" "${BACKUP_NAME}-db.sql.gz"
  if [ "$INCLUDE_EXTRA_DB" = true ]; then
    zip -q "${BACKUP_NAME}-COMPLETO.zip" "${BACKUP_NAME}-victor.sql.gz"
  fi
  PACKAGE_PATH="$BACKUP_DIR/${BACKUP_NAME}-COMPLETO.zip"
else
  tar czf "${BACKUP_NAME}-COMPLETO.tar.gz" \
    "${BACKUP_NAME}-db.sql.gz" \
    $( [ "$INCLUDE_EXTRA_DB" = true ] && echo "${BACKUP_NAME}-victor.sql.gz" )
  PACKAGE_PATH="$BACKUP_DIR/${BACKUP_NAME}-COMPLETO.tar.gz"
fi

rm -f "${BACKUP_NAME}-db.sql.gz"
if [ "$INCLUDE_EXTRA_DB" = true ]; then
  rm -f "${BACKUP_NAME}-victor.sql.gz"
fi

python3 "$ENCRYPT_SCRIPT" "$PACKAGE_PATH"
rm -f "$PACKAGE_PATH"

ENCRYPTED_PATH="${PACKAGE_PATH}.enc"
echo "[backup] OK: $ENCRYPTED_PATH"
ls -lh "$ENCRYPTED_PATH"

echo "[backup] Limpiando históricos (mantener: $KEEP_LAST)..."
ls -t esp32-backup-*-COMPLETO.zip.enc esp32-backup-*-COMPLETO.tar.gz.enc 2>/dev/null \
  | tail -n +$((KEEP_LAST + 1)) \
  | xargs -r rm -f

echo "[backup] Proceso completado"