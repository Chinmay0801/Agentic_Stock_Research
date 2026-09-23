"""
Development-specific settings.
"""
import os

from .base import BASE_DIR  # noqa: F401

DEBUG = True

ALLOWED_HOSTS = ['*']

# SQLite keeps local setup to one command — no PostgreSQL install required.
# docker-compose sets USE_SQLITE=0 so containers use the real Postgres service.
USE_SQLITE = os.environ.get('USE_SQLITE', '1').lower() in ('1', 'true', 'yes')

if USE_SQLITE:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

CORS_ALLOW_ALL_ORIGINS = True
