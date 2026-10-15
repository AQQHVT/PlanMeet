# Образ приложения PlanMeet
FROM python:3.11-slim

# Не писать .pyc, не буферизовать stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Зависимости — отдельным слоем, чтобы кешировались при неизменном requirements.txt
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Код приложения
COPY . .

# Сборка статики (SECRET_KEY берётся из dev-дефолта, БД при этом не требуется)
RUN python manage.py collectstatic --noinput

EXPOSE 8000

# entrypoint применит миграции и запустит gunicorn
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]
