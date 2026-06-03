#!/bin/bash
set -euo pipefail

cd "$(dirname "$0")"

echo "================================================================"
echo "  emotionGame Startup Script"
echo "================================================================"
echo ""

# ------------------------------------------------------------------
# 1. Parse .env for secrets
# ------------------------------------------------------------------
echo "[1/2] Reading .env ..."

if [ ! -f ".env" ]; then
    echo "  ERROR: .env file not found in $(pwd)"
    exit 1
fi

# Parse .env safely — handles spaces and special chars in values
while IFS='=' read -r key value; do
    # Skip blank lines and comments
    [[ -z "$key" || "$key" =~ ^[[:space:]]*# ]] && continue
    # Strip trailing carriage return (Windows line endings)
    value="${value%$'\r'}"
    export "$key"="$value"
done < .env

DB_USER="${DB_USER:-root}"
DB_NAME="${DB_NAME:-camodb}"
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-3306}"
DB_SSL_CA="${DB_SSL_CA:-isrg-root-x1.pem}"

# Map .env variable names to what the rest of the script uses
DB_PASS="${DB_PASSWORD:-}"

# --- debug mode: skip remote DB, use local ---
if [ -n "${DEBUG_SHORT_RESPONSES:-}" ]; then
    echo ""
    echo "  *** DEBUG MODE: overriding DB to localhost ***"
    echo "  DEBUG_SHORT_RESPONSES = ${DEBUG_SHORT_RESPONSES}"
    DB_HOST="localhost"
    DB_PORT="3306"
    DB_USER="root"
    DB_PASS="${DB_DEBUG_PASSWORD:-}"
    DB_SSL_CA=""
fi

echo "  DB: ${DB_USER}@${DB_HOST}:${DB_PORT}/${DB_NAME}"
if [ -n "${DB_SSL_CA:-}" ]; then
    if [ -f "${DB_SSL_CA}" ]; then
        echo "  SSL CA: ${DB_SSL_CA}"
    else
        echo "  WARNING: SSL CA file not found: ${DB_SSL_CA} - proceeding without SSL"
        DB_SSL_CA=""
    fi
fi

# ------------------------------------------------------------------
# 2. Reset database to initial state
# ------------------------------------------------------------------
echo ""
echo "[2/2] Resetting camodb to initial state ..."

SQL_FILE="database/camodb_phase1.sql"
if [ ! -f "${SQL_FILE}" ]; then
    echo "  ERROR: Schema file not found: ${SQL_FILE}"
    exit 1
fi

# Check that mysql is on PATH
if ! command -v mysql &> /dev/null; then
    echo "  ERROR: 'mysql' command not found on PATH"
    echo "  Install MySQL client and ensure it's on your PATH."
    exit 1
fi

# Build SSL args for mysql CLI
MYSQL_SSL_ARGS=()
if [ -n "${DB_SSL_CA:-}" ] && [ -f "${DB_SSL_CA}" ]; then
    MYSQL_SSL_ARGS=(--ssl-ca="${DB_SSL_CA}" --ssl-mode=VERIFY_IDENTITY)
fi

# Run import — capture stderr in case of failure
echo "  Importing ${SQL_FILE} ..."
MYSQL_ERR=$(mktemp)
if ! mysql -u "${DB_USER}" -p"${DB_PASS}" \
     -h "${DB_HOST}" -P "${DB_PORT}" \
     "${MYSQL_SSL_ARGS[@]}" \
     --default-character-set=utf8mb4 < "${SQL_FILE}" 2>"${MYSQL_ERR}"; then
    echo "  ERROR: mysql import failed. Error output:"
    cat "${MYSQL_ERR}" 2>/dev/null || true
    rm -f "${MYSQL_ERR}"
    echo ""
    echo "  Retry manually:"
    echo "    mysql -u ${DB_USER} -p -h ${DB_HOST} -P ${DB_PORT} ${MYSQL_SSL_ARGS[*]} < ${SQL_FILE}"
    exit 1
fi
rm -f "${MYSQL_ERR}"
echo "  Database reset complete."

# ------------------------------------------------------------------
# 3. Prompt for player name (Enter = default "gabriel")
# ------------------------------------------------------------------
echo ""
echo "================================================================="
echo "  Player name (press Enter for default 'gabriel'):"
echo "================================================================="
read -p "  > " PLAYER_NAME_INPUT
if [ -z "${PLAYER_NAME_INPUT}" ]; then
    PLAYER_NAME="gabriel"
else
    PLAYER_NAME="${PLAYER_NAME_INPUT}"
fi
export PLAYER_NAME
echo "  Player: ${PLAYER_NAME}"

# ------------------------------------------------------------------
# 4. Start camo_server.py using the venv Python directly
# ------------------------------------------------------------------
echo ""
echo "================================================================"
echo "  Starting camo_server.py on http://0.0.0.0:5001 (Player: ${PLAYER_NAME})"
echo "================================================================"
echo ""

VENV_PYTHON="venv/bin/python"
if [ ! -f "${VENV_PYTHON}" ]; then
    echo "  ERROR: venv Python not found at ${VENV_PYTHON}"
    exit 1
fi

exec "${VENV_PYTHON}" camo_server.py
