#!/bin/sh
set -e

wait_for_service() {
    host="$1"
    port="$2"
    name="$3"
    echo "Waiting for $name ($host:$port)..."
    while ! python3 -c "import socket; s = socket.socket(); s.settimeout(2); s.connect(('$host', int('$port'))); s.close()" 2>/dev/null; do
        sleep 1
    done
    echo "$name is ready!"
}

# If running web service
if [ "$1" = "web" ]; then
    if [ -n "$DB_HOST" ] && [ -n "$DB_PORT" ]; then
        wait_for_service "$DB_HOST" "$DB_PORT" "PostgreSQL"
    fi

    echo "Running database migrations..."
    python manage.py migrate --noinput

    echo "Collecting static files..."
    python manage.py collectstatic --noinput

    echo "Starting Gunicorn server..."
    exec gunicorn config.wsgi:application \
        --bind 0.0.0.0:8000 \
        --workers 3 \
        --threads 2 \
        --timeout 60 \
        --access-logfile - \
        --error-logfile -
fi

# If running worker service
if [ "$1" = "worker" ]; then
    if [ -n "$DB_HOST" ] && [ -n "$DB_PORT" ]; then
        wait_for_service "$DB_HOST" "$DB_PORT" "PostgreSQL"
    fi
    if [ -n "$REDIS_HOST" ] && [ -n "$REDIS_PORT" ]; then
        wait_for_service "$REDIS_HOST" "$REDIS_PORT" "Redis"
    fi
    if [ -n "$QDRANT_HOST" ] && [ -n "$QDRANT_PORT" ]; then
        wait_for_service "$QDRANT_HOST" "$QDRANT_PORT" "Qdrant"
    fi

    echo "Starting Celery worker..."
    exec celery -A config worker --loglevel=info --concurrency=2
fi

exec "$@"
