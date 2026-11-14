#!/usr/bin/env bash
# run_e2e.sh — Start Django server, run E2E tests, then stop server
set -e

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
PYTHON="$PROJECT_DIR/.venv/bin/python"
PYTEST="$PROJECT_DIR/.venv/bin/pytest"
PORT=8099
LOG="/tmp/fc_e2e_server.log"

echo "==> Starting Django dev server on port $PORT..."
"$PYTHON" manage.py runserver "$PORT" --noreload > "$LOG" 2>&1 &
SERVER_PID=$!
echo "    Server PID=$SERVER_PID"

# Wait up to 20s for server
for i in $(seq 1 20); do
    if curl -s -o /dev/null -w "%{http_code}" "http://localhost:$PORT/accounts/login/" 2>/dev/null | grep -q "200"; then
        echo "    Server ready after ${i}s"
        break
    fi
    sleep 1
done

# Verify
STATUS=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:$PORT/accounts/login/" 2>/dev/null)
if [ "$STATUS" != "200" ]; then
    echo "ERROR: Server not responding (HTTP $STATUS)"
    cat "$LOG"
    kill $SERVER_PID 2>/dev/null
    exit 1
fi

echo "==> Running E2E tests..."
set +e
"$PYTEST" tests/test_phase6_e2e.py -v --no-header -c pytest_e2e.ini "$@"
EXIT_CODE=$?
set -e

echo "==> Stopping server (PID=$SERVER_PID)..."
kill $SERVER_PID 2>/dev/null
wait $SERVER_PID 2>/dev/null || true

echo "==> Done. Exit code: $EXIT_CODE"
exit $EXIT_CODE
