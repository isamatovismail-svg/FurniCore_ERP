#!/usr/bin/env bash
# Exit immediately if a command exits with a non-zero status
set -o errexit

echo "==> Upgrading pip and installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

echo "==> Collecting static files..."
python manage.py collectstatic --no-input

echo "==> Applying database migrations..."
python manage.py migrate

# Create/update the presentation administrator only when its secret is configured.
python manage.py ensure_presentation_admin

# Optional: seed demo data if explicitly requested in environment
if [ "${SEED_DEMO:-false}" = "true" ] || [ "${SEED_DEMO:-false}" = "1" ]; then
    echo "==> Seeding demo data (SEED_DEMO=true)..."
    python manage.py seed_demo
fi

echo "==> Build process completed successfully!"
