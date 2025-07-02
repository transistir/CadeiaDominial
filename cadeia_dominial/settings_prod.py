"""
Configurações para ambiente de produção
"""
import os
from .settings import *

# Configurações de Segurança
DEBUG = False
SECRET_KEY = os.environ.get('SECRET_KEY', 'sua-chave-secreta-de-producao-muito-segura')

# Configurações de Hosts Permitidos
ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', '46.62.152.252,localhost,127.0.0.1').split(',')

# Configurações de CSRF
CSRF_TRUSTED_ORIGINS = [
    'http://46.62.152.252',
    'https://46.62.152.252',
]

# Configurações do Banco de Dados PostgreSQL
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ.get('DB_NAME', 'cadeia_dominial'),
        'USER': os.environ.get('DB_USER', 'cadeia_user'),
        'PASSWORD': os.environ.get('DB_PASSWORD', 'sua_senha_segura_aqui'),
        'HOST': os.environ.get('DB_HOST', 'localhost'),
        'PORT': os.environ.get('DB_PORT', '5432'),
    }
}

# Configurações de Arquivos Estáticos
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
STATICFILES_STORAGE = 'django.contrib.staticfiles.storage.StaticFilesStorage'
# Remover STATICFILES_DIRS para evitar conflitos em produção
STATICFILES_DIRS = []

# Configurações de Logging
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}

# Configurações de Email (opcional)
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = os.environ.get('EMAIL_HOST', 'smtp.gmail.com')
EMAIL_PORT = int(os.environ.get('EMAIL_PORT', 587))
EMAIL_USE_TLS = os.environ.get('EMAIL_USE_TLS', 'True').lower() == 'true'
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD')

# Configurações de Cache
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'unique-snowflake',
    }
}

# Configurações de Sessão
SESSION_COOKIE_SECURE = False  # Mudar para True se usar HTTPS
CSRF_COOKIE_SECURE = False     # Mudar para True se usar HTTPS
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True

# Configurações de Segurança Adicionais
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True 