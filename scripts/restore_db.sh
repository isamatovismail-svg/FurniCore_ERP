#!/usr/bin/env bash
# ==============================================================================
# FurniCore ERP — Database Restore Script (PostgreSQL 16)
# ==============================================================================
# Usage:
#   ./scripts/restore_db.sh <backup_file.dump> <target_database_name> [--force-production]
#
# Examples:
#   # Safe test restore onto an isolated verification database:
#   ./scripts/restore_db.sh backups/furnicore_db_backup_20261114_180000.dump furnicore_restore_test
#
#   # Production disaster recovery (requires explicit confirmation flag):
#   ./scripts/restore_db.sh backups/furnicore_db_backup_20261114_180000.dump furnicore_db --force-production
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Load .env if present
if [ -f "${BASE_DIR}/.env" ]; then
    set -a
    # shellcheck disable=SC1091
    source <(grep -v '^#' "${BASE_DIR}/.env" | sed -e 's/\r$//' | grep -v '^$')
    set +a
fi

DB_HOST="${DB_HOST:-127.0.0.1}"
DB_PORT="${DB_PORT:-5435}"
PROD_DB_NAME="${DB_NAME:-furnicore_db}"
DB_USER="${DB_USER:-furnicore_user}"
DB_PASSWORD="${DB_PASSWORD:-}"

if [ $# -lt 2 ]; then
    echo "Usage: $0 <backup_file.dump> <target_database_name> [--force-production]"
    echo ""
    echo "Examples:"
    echo "  $0 backups/furnicore_db_backup_20261114_120000.dump furnicore_restore_test"
    echo "  $0 backups/furnicore_db_backup_20261114_120000.dump ${PROD_DB_NAME} --force-production"
    exit 1
fi

BACKUP_FILE="$1"
TARGET_DB="$2"
FORCE_PROD="${3:-}"

if [ ! -f "${BACKUP_FILE}" ]; then
    echo "ERROR: Backup file not found: ${BACKUP_FILE}" >&2
    exit 1
fi

if ! command -v pg_restore >/dev/null 2>&1; then
    echo "ERROR: pg_restore utility not found in PATH." >&2
    exit 1
fi

# CRITICAL SAFETY GUARD: Prevent accidental restore over production
if [ "${TARGET_DB}" = "${PROD_DB_NAME}" ]; then
    if [ "${FORCE_PROD}" != "--force-production" ]; then
        echo "==========================================================" >&2
        echo "CRITICAL SAFETY GUARD REJECTION" >&2
        echo "==========================================================" >&2
        echo "Target database '${TARGET_DB}' is the primary production database." >&2
        echo "Restoring over production will overwrite active data!" >&2
        echo "If you really intend to perform disaster recovery on production," >&2
        echo "you must pass --force-production as the third argument:" >&2
        echo "  $0 ${BACKUP_FILE} ${TARGET_DB} --force-production" >&2
        echo "==========================================================" >&2
        exit 2
    fi
    echo "WARNING: Proceeding with RESTORE OVER PRODUCTION database '${TARGET_DB}'."
fi

export PGPASSWORD="${DB_PASSWORD}"

echo "=========================================================="
echo "FurniCore ERP — Starting Database Restore"
echo "=========================================================="
echo "Backup file: ${BACKUP_FILE}"
echo "Target DB:   ${TARGET_DB}"
echo "Host:        ${DB_HOST}:${DB_PORT}"
echo "User:        ${DB_USER}"
echo "Date:        $(date -Iseconds)"
echo "----------------------------------------------------------"

# Check if target database exists; if not, create it
DB_EXISTS=$(psql -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" -d postgres -tAc \
    "SELECT 1 FROM pg_database WHERE datname='${TARGET_DB}';" 2>/dev/null || \
    psql -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" -d "${PROD_DB_NAME}" -tAc \
    "SELECT 1 FROM pg_database WHERE datname='${TARGET_DB}';" 2>/dev/null || echo "0")

if [ "${DB_EXISTS}" != "1" ]; then
    echo "Target database '${TARGET_DB}' does not exist. Creating it..."
    createdb -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" "${TARGET_DB}"
    echo "Created database '${TARGET_DB}'."
else
    echo "Target database '${TARGET_DB}' exists."
fi

echo "Restoring schema and data with pg_restore..."

# Run pg_restore:
# -d: target database
# --no-owner: don't attempt to set ownership of restored objects
# --no-privileges: don't attempt to set permissions (avoids permission errors across environments)
# --clean --if-exists: cleanly drop existing tables/constraints before recreating if restoring into existing db
pg_restore \
    -h "${DB_HOST}" \
    -p "${DB_PORT}" \
    -U "${DB_USER}" \
    -d "${TARGET_DB}" \
    --no-owner \
    --no-privileges \
    --clean \
    --if-exists \
    --verbose \
    "${BACKUP_FILE}" >/dev/null 2>/tmp/furnicore_pg_restore.log || true

# Check restore verification
VERIFY_COUNT=$(psql -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" -d "${TARGET_DB}" -tAc \
    "SELECT count(*) FROM django_migrations;" 2>/dev/null || echo "0")

TABLE_COUNT=$(psql -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" -d "${TARGET_DB}" -tAc \
    "SELECT count(*) FROM information_schema.tables WHERE table_schema='public';" 2>/dev/null || echo "0")

if [ "${VERIFY_COUNT}" -gt 0 ]; then
    echo "----------------------------------------------------------"
    echo "Restore successfully verified!"
    echo "Target DB:     ${TARGET_DB}"
    echo "Total tables:  ${TABLE_COUNT}"
    echo "Migrations:    ${VERIFY_COUNT}"
    echo "=========================================================="
    exit 0
else
    echo "ERROR: Restore verification failed. No migrations found in '${TARGET_DB}'." >&2
    cat /tmp/furnicore_pg_restore.log >&2
    exit 1
fi
