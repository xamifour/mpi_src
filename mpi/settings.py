"""
Django settings for mpi project.

For more information on this file, see
https://docs.djangoproject.com/en/5.0/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/5.0/ref/settings/
"""

import os
from pathlib import Path

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve(strict=True).parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv('SECRET_KEY', 'django-insecure-^rtb8vn##v7c-c0n9p(&((=dv)i$v0ygqj&jaj7z$ehzhf*q=&')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.getenv('DEBUG', 'True') == 'True'
ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', 'localhost,127.0.0.1,192.168.88.230').split(',')


# Application definition
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "usermanager",
    'django_celery_beat',
    'widget_tweaks',
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

AUTH_USER_MODEL = 'usermanager.User'

# LOGOUT_REDIRECT_URL = '/
LOGIN_URL = 'sign_in'
LOGIN_REDIRECT_URL = 'user_detail'  # Redirect to user detail after successful login

ROOT_URLCONF = "mpi.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        'DIRS': [os.path.join(os.path.dirname(BASE_DIR), 'templates'),],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
            'libraries':{
                'sidebar_links': 'templatetags.sidebar_links',
            }
        },
    },
]

WSGI_APPLICATION = "mpi.wsgi.application"

# Database configuration
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# Internationalization
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')
MEDIA_URL = '/media/'

STATIC_URL = '/static/'
STATICFILES_DIRS = [os.path.join(os.path.dirname(BASE_DIR), "static"),]
STATIC_ROOT = os.path.join(os.path.dirname(os.path.dirname((BASE_DIR))), 'staticfiles')

# Default primary key field type
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ other settings

# Logging configuration
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'file': {
            'level': 'ERROR',
            'class': 'logging.FileHandler',
            'filename': BASE_DIR / 'django_errors.log',
        },
        'console': {
            'level': 'ERROR',
            'class': 'logging.StreamHandler',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['file', 'console'],
            'level': 'ERROR',
            'propagate': False,
        },
        'usermanager': {
            'handlers': ['file'],
            'level': 'ERROR',
            'propagate': False,
        },
    },
}

# Environment variables
ROUTER_IP = os.getenv('ROUTER_IP')
ROUTER_USERNAME = os.getenv('ROUTER_USERNAME')
ROUTER_PASSWORD = os.getenv('ROUTER_PASSWORD')
# 
PAYSTACK_SECRET_KEY = os.getenv('PAYSTACK_SECRET_KEY')
PAYSTACK_PUBLIC_KEY = os.getenv('PAYSTACK_PUBLIC_KEY')
# PAYSTACK_CALLBACK_URL = 'https://yourdomain.com/payment/verify/'
PAYSTACK_CALLBACK_URL = 'http://127.0.0.1/payment/verify/'


from celery.schedules import crontab
# Celery settings
CELERY_BROKER_URL = 'redis://localhost:6379'
CELERY_RESULT_BACKEND = 'redis://localhost:6379'
CELERY_ACCEPT_CONTENT = ['application/json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'Africa/Accra'

from datetime import timedelta

CELERY_BEAT_SCHEDULE = {
    'sync_mikrotik_data_every_30_seconds': {
        'task': 'usermanager.tasks.sync_mikrotik_data',
        'schedule': timedelta(seconds=30),  # Run every 30 seconds
    },
}

# running tasks in celery at the same time
# CELERY_BEAT_SCHEDULE = {
#     'sync_mikrotik_data_every_5_minutes': {
#         'task': 'usermanager.tasks.sync_mikrotik_data',
#         'schedule': 300.0,  # 300 seconds = 5 minutes
#     },
# }

# # running tasks in celery at individual time intervals
# CELERY_BEAT_SCHEDULE = {
#     'sync_users_every_hour': {
#         'task': 'usermanager.tasks.sync_users',
#         'schedule': crontab(minute=0, hour='*/1'),  # every hour
#     },
#     'sync_profiles_every_hour': {
#         'task': 'usermanager.tasks.sync_profiles',
#         'schedule': crontab(minute=0, hour='*/1'),  # every hour
#     },
#     'sync_user_profiles_every_hour': {
#         'task': 'usermanager.tasks.sync_user_profiles',
#         'schedule': crontab(minute=0, hour='*/1'),  # every hour
#     },
#     'sync_sessions_every_minute': {
#         'task': 'usermanager.tasks.sync_sessions',
#         'schedule': crontab(minute='*/1'),  # every minute
#     },
# }

# # run celery server
# redis-server 

# Start the Celery worker:
# celery -A your_project worker --loglevel=info
# celery -A mpi worker --loglevel=info

# Start the Celery Beat scheduler:
# celery -A your_project beat --loglevel=info


# Add Channels support
ASGI_APPLICATION = "mpi.asgi.application"

CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            "hosts": [('127.0.0.1', 6379)],  # Adjust host and port as needed
        },
    },
}

# For Celery:
CELERY_BROKER_URL = 'redis://localhost:6379/0'
CELERY_RESULT_BACKEND = 'redis://localhost:6379/0'
