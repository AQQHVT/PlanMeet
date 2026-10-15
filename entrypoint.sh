#!/bin/sh
set -e

echo "==> Применяю миграции базы данных"
python manage.py migrate --noinput

echo "==> Запускаю gunicorn на 0.0.0.0:8000"
exec gunicorn doodle_project.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers 3
