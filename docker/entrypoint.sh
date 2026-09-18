#!/bin/sh
set -eu

case "${1:-web}" in
  web)
    if [ -d /srv/static ] && [ -w /srv/static ]; then
      echo "[entrypoint] publishing static assets for nginx"
      rm -rf /srv/static/* && cp -R /app/app/static/. /srv/static/
    fi
    echo "[entrypoint] checking production configuration"
    flask --app wsgi:app check-production
    echo "[entrypoint] applying database migrations"
    flask --app wsgi:app db upgrade
    echo "[entrypoint] seeding roles/permissions/settings (idempotent)"
    flask --app wsgi:app seed-roles
    exec gunicorn --config gunicorn.conf.py wsgi:app
    ;;
  worker)
    exec celery -A app.celery_worker:celery worker --loglevel="${LOG_LEVEL:-INFO}" --concurrency="${WORKER_COUNT:-2}"
    ;;
  beat)
    exec celery -A app.celery_worker:celery beat --loglevel="${LOG_LEVEL:-INFO}"
    ;;
  *)
    exec "$@"
    ;;
esac
