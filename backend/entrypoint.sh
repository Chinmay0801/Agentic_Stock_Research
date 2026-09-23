#!/bin/sh
# Container entrypoint: wait for the database, apply migrations, then hand off
# to the command from docker-compose. Keeps `docker compose up` a one-liner.
set -e

if [ "${USE_SQLITE:-1}" = "0" ]; then
  echo "Waiting for PostgreSQL at ${POSTGRES_HOST:-db}:${POSTGRES_PORT:-5432}…"
  until python -c "
import os, socket, sys
host = os.environ.get('POSTGRES_HOST', 'db')
port = int(os.environ.get('POSTGRES_PORT', '5432'))
sock = socket.socket()
sock.settimeout(2)
try:
    sock.connect((host, port))
except OSError:
    sys.exit(1)
finally:
    sock.close()
"; do
    sleep 1
  done
  echo "PostgreSQL is up."
fi

echo "Applying migrations…"
python manage.py migrate --noinput

# SEED_DEMO_DATA=1 populates tickers, live snapshots and sample reports.
if [ "${SEED_DEMO_DATA:-0}" = "1" ]; then
  echo "Seeding demo data…"
  python manage.py shell -c "
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(is_superuser=True).exists():
    User.objects.create_superuser('admin', 'admin@example.com', 'admin123')
    print('Created superuser admin / admin123')
"
  python seed_demo_data.py || echo "Seeding skipped (Yahoo Finance unreachable)."
fi

exec "$@"
