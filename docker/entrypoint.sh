#!/bin/sh
set -eu

case "${1:-web}" in
  web)
    if [ ! -f app/translations/ka/LC_MESSAGES/messages.mo ]; then
      echo "[entrypoint] compiling translation catalogues"
      pybabel compile -d app/translations -f --statistics
    fi
    if [ -d /srv/static ]; then
      if [ -w /srv/static ]; then
        echo "[entrypoint] publishing static assets for nginx"
        rm -rf /srv/static/* && cp -R /app/app/static/. /srv/static/
      else
        echo "[entrypoint] WARNING: /srv/static is not writable; nginx may serve stale assets" >&2
      fi
    fi
    if [ "${APP_ENV:-production}" = "production" ]; then
      echo "[entrypoint] checking production configuration"
      flask --app wsgi:app check-production
    else
      echo "[entrypoint] APP_ENV=${APP_ENV}: skipping the production configuration check"
    fi
    echo "[entrypoint] applying database migrations"
    flask --app wsgi:app db upgrade
    echo "[entrypoint] seeding roles/permissions/settings (idempotent)"
    flask --app wsgi:app seed-roles
    echo "[entrypoint] seeding CyberHero content on first start (kept as-is afterwards)"
    flask --app wsgi:app seed-cyberhero --if-empty
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
