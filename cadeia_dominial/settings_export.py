"""
Temporary settings for exporting data from PostgreSQL Docker container
"""
from .settings import *

# Override database configuration for PostgreSQL export
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'cadeia_dominial_dev',
        'USER': 'cadeia_user',
        'PASSWORD': 'dev_password',
        'HOST': 'localhost',
        'PORT': '5433',  # docker-compose.dev.yml maps to 5433
    }
}

DEBUG = True
