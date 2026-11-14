#!/usr/bin/env bash
# ==============================================================================
# FurniCore ERP — Database Backup Script (PostgreSQL 16)
# ==============================================================================
# Usage:
#   ./scripts/backup_db.sh [custom_backup_dir]
#
# Creates a compressed PostgreSQL custom-format dump (.dump) suitable for
# pg_restore. Reads database credentials from environment variables or .env.
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Load .env if present
if [ -f "${BASE_DIR}/.env" ]; then
    # Export variables from .env without overriding already set env vars
    set -a
    # shellcheck disable=SC1091
    source <(grep -v '^#' "${BASE_DIR}/.env" | sed -e 's/\r$//' | grep -v '^$')
    set +a
fi

DB_HOST="${DB_HOST:-127.0.0.1}"
DB_PORT="${DB_PORT:-5435}"
DB_NAME="${DB_NAME:-furnicore_db}"
DB_USER="${DB_USER:-furnicore_user}"
DB_PASSWORD="${DB_PASSWORD:-}"
BACKUP_DIR="${1:-${BASE_DIR}/backups}"

mkdir -p "${BACKUP_DIR}"

TIMESTAMP="$(date +"%Y%m%d_%H%M%S")"
BACKUP_FILE="${BACKUP_DIR}/${DB_NAME}_backup_${TIMESTAMP}.dump"

echo "=========================================================="
echo "FurniCore ERP — Starting PostgreSQL Backup"
echo "=========================================================="
echo "Host:     ${DB_HOST}:${DB_PORT}"
echo "Database: ${DB_NAME}"
echo "User:     ${DB_USER}"
echo "Target:   ${BACKUP_FILE}"
echo "Date:     $(date -Iseconds)"
echo "----------------------------------------------------------"

if ! command -v pg_dump >/dev/null 2>&1; then
    echo "ERROR: pg_dump utility not found in PATH." >&2
    exit 1
fi

export PGPASSWORD="${DB_PASSWORD}"

# Run pg_dump in custom format (-Fc): compressed, flexible, supports parallel restore
pg_dump \
    -h "${DB_HOST}" \
    -p "${DB_PORT}" \
    -U "${DB_USER}" \
    -Fc \
    --blobs \
    --verbose \
    "${DB_NAME}" > "${BACKUP_FILE}" 2>/tmp/furnicore_pg_dump.log

DUMP_EXIT=$?

if [ ${DUMP_EXIT} -ne 0 ]; then
    echo "ERROR: pg_dump failed with exit code ${DUMP_EXIT}." >&2
    cat /tmp/furnicore_pg_dump.log >&2
    rm -f "${BACKUP_FILE}"
    exit ${DUMP_EXIT}
fi

BACKUP_SIZE="$(du -h "${BACKUP_FILE}" | cut -f1)"
CHECKSUM="$(md5sum "${BACKUP_FILE}" | cut -d' ' -f1)"

echo "----------------------------------------------------------"
echo "Backup successfully completed!"
echo "File:     ${BACKUP_FILE}"
echo "Size:     ${BACKUP_SIZE}"
echo "MD5:      ${CHECKSUM}"
echo "=========================================================="

# Retain backups for 14 days (optional cleanup of older files)
find "${BACKUP_DIR}" -name "${DB_NAME}_backup_*.dump" -type f -mtime +14 -delete 2>/dev/null || true

exit 0
