"""
Настройки Django проекта PlanMeet — веб-сервис для согласования времени мероприятий.

Все секреты и параметры окружения читаются из переменных окружения.
Локально их можно задать в файле .env (см. .env.example).
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# Опциональная загрузка переменных из .env (если установлен python-dotenv).
# Не является обязательной зависимостью — при отсутствии просто пропускается.
try:
    from dotenv import load_dotenv
    load_dotenv(BASE_DIR / '.env')
except ImportError:
    pass

# --- Безопасность -----------------------------------------------------------
# В продакшене SECRET_KEY ОБЯЗАТЕЛЬНО задаётся через переменную окружения.
# Значение по умолчанию помечено как insecure и годится только для локальной разработки.
SECRET_KEY = os.environ.get(
    'DJANGO_SECRET_KEY',
    'django-insecure-dev-only-key-replace-in-production'
)

DEBUG = os.environ.get('DJANGO_DEBUG', 'False') == 'True'

_raw_hosts = os.environ.get('DJANGO_ALLOWED_HOSTS', '')
ALLOWED_HOSTS = [h.strip() for h in _raw_hosts.split(',') if h.strip()] or ['*']

# --- Приложения -------------------------------------------------------------
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'core',
    'users',
    'events',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    # WhiteNoise отдаёт статику в контейнере/проде без отдельного nginx.
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'doodle_project.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'doodle_project.wsgi.application'

# --- База данных ------------------------------------------------------------
# По умолчанию используется SQLite — так проект запускается «из коробки»
# без дополнительной настройки. Для продакшена задайте DJANGO_DB_ENGINE=mysql
# и остальные переменные окружения (см. .env.example).
if os.environ.get('DJANGO_DB_ENGINE', 'sqlite') == 'mysql':
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.mysql',
            'NAME': os.environ.get('DJANGO_DB_NAME', ''),
            'USER': os.environ.get('DJANGO_DB_USER', ''),
            'PASSWORD': os.environ.get('DJANGO_DB_PASSWORD', ''),
            'HOST': os.environ.get('DJANGO_DB_HOST', 'localhost'),
            'PORT': os.environ.get('DJANGO_DB_PORT', '3306'),
            'OPTIONS': {
                'charset': 'utf8mb4',
                'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
            },
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
     'OPTIONS': {'min_length': 4}},
]

# --- Локализация ------------------------------------------------------------
LANGUAGE_CODE = 'ru-ru'
TIME_ZONE = 'Europe/Moscow'
USE_I18N = True
USE_TZ = True

# --- Статика ----------------------------------------------------------------
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

# WhiteNoise ищет файлы и в STATICFILES_DIRS, поэтому стили отдаются сразу
# после клонирования — даже при DEBUG=False и без collectstatic.
# В продакшене всё равно рекомендуется выполнять collectstatic (так делает Dockerfile).
WHITENOISE_USE_FINDERS = True

# WhiteNoise: сжатие статики при сборке (без манифеста — безопасно для проекта).
STORAGES = {
    'default': {
        'BACKEND': 'django.core.files.storage.FileSystemStorage',
    },
    'staticfiles': {
        'BACKEND': 'whitenoise.storage.CompressedStaticFilesStorage',
    },
}

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# --- Авторизация ------------------------------------------------------------
LOGIN_URL = '/users/login/'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/'

SITE_URL = os.environ.get('DJANGO_SITE_URL', 'http://127.0.0.1:8000')

# --- Почта ------------------------------------------------------------------
# По умолчанию письма выводятся в консоль — удобно для локальной разработки.
# Для реальной отправки задайте DJANGO_EMAIL_BACKEND и SMTP-параметры в окружении.
EMAIL_BACKEND = os.environ.get(
    'DJANGO_EMAIL_BACKEND',
    'django.core.mail.backends.console.EmailBackend'
)
EMAIL_HOST = os.environ.get('DJANGO_EMAIL_HOST', '')
EMAIL_PORT = int(os.environ.get('DJANGO_EMAIL_PORT', '465'))
EMAIL_USE_SSL = os.environ.get('DJANGO_EMAIL_USE_SSL', 'True') == 'True'
EMAIL_USE_TLS = False
EMAIL_HOST_USER = os.environ.get('DJANGO_EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.environ.get('DJANGO_EMAIL_HOST_PASSWORD', '')
DEFAULT_FROM_EMAIL = os.environ.get('DJANGO_DEFAULT_FROM_EMAIL', 'PlanMeet <noreply@example.com>')
