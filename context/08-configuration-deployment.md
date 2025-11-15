# Configuration and Deployment

## Environment Configuration

### Environment Variables

The system uses `python-decouple` for environment-based configuration.

**File:** `.env` (create from `env.example`)

```bash
# Django Settings
DEBUG=False
SECRET_KEY=your_very_secure_secret_key_here
ALLOWED_HOSTS=localhost,127.0.0.1,your-domain.com

# Database (PostgreSQL in production)
DB_NAME=cadeia_dominial
DB_USER=cadeia_user
DB_PASSWORD=your_secure_password
DB_HOST=db  # or localhost
DB_PORT=5432

# SSL/Let's Encrypt (production only)
DOMAIN_NAME=your-domain.com
CERTBOT_EMAIL=your-email@example.com

# Email Configuration (optional)
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your_app_password

# Timezone
TIME_ZONE=America/Sao_Paulo

# Logging
LOG_LEVEL=INFO

# Admin User (required for first setup)
ADMIN_USERNAME=admin
ADMIN_EMAIL=admin@cadeiadominial.com.br
ADMIN_PASSWORD=your_very_secure_admin_password
```

### Settings Files

**Structure:**
```
cadeia_dominial/
├── settings.py         # Base settings (development defaults)
├── settings_dev.py     # Development-specific overrides
└── settings_prod.py    # Production-specific settings
```

#### Base Settings (`settings.py`)

**Key Configurations:**

```python
# Debug mode
DEBUG = True  # Override in production

# Secret key
SECRET_KEY = 'django-insecure-...'  # Override in production

# Allowed hosts
ALLOWED_HOSTS = ['localhost', '127.0.0.1', '0.0.0.0', 'testserver']

# Authentication
LOGIN_URL = '/accounts/login/'
LOGIN_REDIRECT_URL = '/'

# Installed apps
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'cadeia_dominial',
    'django_extensions',
    'dominial',
    'dal',  # Django Autocomplete Light
    'dal_select2',
]

# Middleware
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',  # Static files
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

# Database (SQLite for development)
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# Static files
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Static files storage (WhiteNoise)
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# Templates
TEMPLATES = [{
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
}]

# Internationalization
LANGUAGE_CODE = 'pt-br'
TIME_ZONE = 'America/Sao_Paulo'
USE_I18N = True
USE_TZ = True

# Default auto field
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
```

#### Production Settings (`settings_prod.py`)

```python
from .settings import *
from decouple import config

# Security
DEBUG = config('DEBUG', default=False, cast=bool)
SECRET_KEY = config('SECRET_KEY')
ALLOWED_HOSTS = config('ALLOWED_HOSTS').split(',')

# Database (PostgreSQL)
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': config('DB_NAME'),
        'USER': config('DB_USER'),
        'PASSWORD': config('DB_PASSWORD'),
        'HOST': config('DB_HOST'),
        'PORT': config('DB_PORT', default='5432'),
    }
}

# Security settings
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'

# HSTS (HTTP Strict Transport Security)
SECURE_HSTS_SECONDS = 31536000  # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# Logging
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'file': {
            'level': config('LOG_LEVEL', default='INFO'),
            'class': 'logging.FileHandler',
            'filename': BASE_DIR / 'logs' / 'django.log',
            'formatter': 'verbose',
        },
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['file', 'console'],
            'level': config('LOG_LEVEL', default='INFO'),
            'propagate': True,
        },
        'dominial': {
            'handlers': ['file', 'console'],
            'level': 'DEBUG',
            'propagate': False,
        },
    },
}
```

---

## Dependencies

### Python Requirements

**File:** `requirements.txt`

```
asgiref==3.8.1                    # ASGI interface
Django==5.2.3                     # Web framework
django-autocomplete-light==3.12.1 # Autocomplete widgets
django-extensions==4.1            # Admin extensions
requests==2.31.0                  # HTTP library
sqlparse==0.5.3                   # SQL parsing
psycopg2-binary==2.9.9            # PostgreSQL driver
gunicorn==21.2.0                  # WSGI server
python-decouple==3.8              # Configuration management
whitenoise==6.6.0                 # Static file serving
weasyprint==62.2                  # PDF generation
openpyxl==3.1.5                   # Excel generation
```

### System Dependencies

**For PDF Generation (WeasyPrint):**

**Ubuntu/Debian:**
```bash
sudo apt-get install -y \
    python3-dev \
    python3-pip \
    python3-setuptools \
    python3-wheel \
    python3-cffi \
    libcairo2 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf2.0-0 \
    libffi-dev \
    shared-mime-info
```

**macOS:**
```bash
brew install cairo pango gdk-pixbuf libffi
```

**For PostgreSQL:**
```bash
sudo apt-get install -y postgresql postgresql-contrib libpq-dev
```

---

## Development Setup

### Local Development

**1. Clone Repository:**
```bash
git clone <repository_url>
cd CadeiaDominial
```

**2. Create Virtual Environment:**
```bash
python3 -m venv venv
source venv/bin/activate  # Linux/macOS
# or
venv\Scripts\activate  # Windows
```

**3. Install Dependencies:**
```bash
pip install -r requirements.txt
```

**4. Create Environment File:**
```bash
cp env.example .env
# Edit .env with your settings
```

**5. Run Migrations:**
```bash
python manage.py migrate
```

**6. Create Superuser:**
```bash
python manage.py createsuperuser
```

**7. Initialize Reference Data:**
```bash
# Create document types
python manage.py criar_tipos_documento

# Create transaction types
python manage.py criar_tipos_lancamento

# Import indigenous lands (optional)
python manage.py importar_terras_indigenas

# Import cartórios for specific state (optional)
python manage.py importar_cartorios_estado --estado BA
```

**8. Collect Static Files:**
```bash
python manage.py collectstatic --no-input
```

**9. Run Development Server:**
```bash
python manage.py runserver
```

**10. Access Application:**
```
http://localhost:8000/
```

---

## Production Deployment

### Option 1: Docker Deployment

**Files:**
- `Dockerfile` - Container image definition
- `docker-compose.yml` - Production orchestration
- `docker-compose.dev.yml` - Development orchestration

#### Dockerfile

```dockerfile
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    postgresql-client \
    libpq-dev \
    gcc \
    python3-dev \
    libcairo2 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf2.0-0 \
    libffi-dev \
    shared-mime-info \
    && rm -rf /var/lib/apt/lists/*

# Set work directory
WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project
COPY . .

# Collect static files
RUN python manage.py collectstatic --no-input

# Create logs directory
RUN mkdir -p logs

# Expose port
EXPOSE 8000

# Run gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "3", "cadeia_dominial.wsgi:application"]
```

#### docker-compose.yml (Production)

```yaml
version: '3.8'

services:
  db:
    image: postgres:15
    environment:
      POSTGRES_DB: ${DB_NAME}
      POSTGRES_USER: ${DB_USER}
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${DB_USER} -d ${DB_NAME}"]
      interval: 5s
      timeout: 5s
      retries: 5
    restart: unless-stopped

  web:
    build: .
    command: gunicorn cadeia_dominial.wsgi:application --bind 0.0.0.0:8000
    volumes:
      - static_volume:/app/staticfiles
      - media_volume:/app/media
    env_file:
      - .env
    depends_on:
      db:
        condition: service_healthy
    restart: unless-stopped

  nginx:
    image: nginx:alpine
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
      - static_volume:/app/staticfiles
      - media_volume:/app/media
    ports:
      - "80:80"
      - "443:443"
    depends_on:
      - web
    restart: unless-stopped

volumes:
  postgres_data:
  static_volume:
  media_volume:
```

#### Deployment Steps

**1. Prepare Server:**
```bash
# Install Docker and Docker Compose
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh

# Install Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose
```

**2. Clone Repository:**
```bash
git clone <repository_url>
cd CadeiaDominial
```

**3. Configure Environment:**
```bash
cp env.example .env
nano .env  # Edit with production values
```

**4. Build and Start:**
```bash
docker-compose up -d --build
```

**5. Run Migrations:**
```bash
docker-compose exec web python manage.py migrate
```

**6. Create Superuser:**
```bash
docker-compose exec web python manage.py createsuperuser
```

**7. Initialize Data:**
```bash
docker-compose exec web python manage.py criar_tipos_documento
docker-compose exec web python manage.py criar_tipos_lancamento
```

**8. Access Application:**
```
http://your-server-ip/
```

---

### Option 2: Traditional VPS Deployment

**Requirements:**
- Ubuntu 20.04 or 22.04
- Python 3.8+
- PostgreSQL 12+
- Nginx
- Supervisor (process manager)

#### Setup Steps

**1. Install System Packages:**
```bash
sudo apt update
sudo apt install -y \
    python3 \
    python3-pip \
    python3-venv \
    postgresql \
    postgresql-contrib \
    nginx \
    supervisor \
    libpq-dev \
    libcairo2 \
    libpango-1.0-0 \
    git
```

**2. Create PostgreSQL Database:**
```bash
sudo -u postgres psql
CREATE DATABASE cadeia_dominial;
CREATE USER cadeia_user WITH PASSWORD 'secure_password';
ALTER ROLE cadeia_user SET client_encoding TO 'utf8';
ALTER ROLE cadeia_user SET default_transaction_isolation TO 'read committed';
ALTER ROLE cadeia_user SET timezone TO 'UTC';
GRANT ALL PRIVILEGES ON DATABASE cadeia_dominial TO cadeia_user;
\q
```

**3. Setup Application:**
```bash
# Create app directory
sudo mkdir -p /opt/cadeia_dominial
sudo chown $USER:$USER /opt/cadeia_dominial

# Clone repository
cd /opt/cadeia_dominial
git clone <repository_url> .

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp env.example .env
nano .env  # Edit with production values

# Run migrations
python manage.py migrate

# Collect static files
python manage.py collectstatic --no-input

# Create superuser
python manage.py createsuperuser

# Initialize data
python manage.py criar_tipos_documento
python manage.py criar_tipos_lancamento
```

**4. Configure Gunicorn:**

**File:** `/opt/cadeia_dominial/gunicorn.conf.py`
```python
bind = "127.0.0.1:8000"
workers = 3
worker_class = "sync"
worker_connections = 1000
timeout = 30
keepalive = 2
errorlog = "/opt/cadeia_dominial/logs/gunicorn_error.log"
accesslog = "/opt/cadeia_dominial/logs/gunicorn_access.log"
loglevel = "info"
```

**5. Configure Supervisor:**

**File:** `/etc/supervisor/conf.d/cadeia_dominial.conf`
```ini
[program:cadeia_dominial]
command=/opt/cadeia_dominial/venv/bin/gunicorn cadeia_dominial.wsgi:application -c /opt/cadeia_dominial/gunicorn.conf.py
directory=/opt/cadeia_dominial
user=www-data
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/opt/cadeia_dominial/logs/supervisor.log
```

```bash
sudo supervisorctl reread
sudo supervisorctl update
sudo supervisorctl start cadeia_dominial
```

**6. Configure Nginx:**

**File:** `/etc/nginx/sites-available/cadeia_dominial`
```nginx
server {
    listen 80;
    server_name your-domain.com;

    client_max_body_size 10M;

    location /static/ {
        alias /opt/cadeia_dominial/staticfiles/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    location /media/ {
        alias /opt/cadeia_dominial/media/;
    }

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/cadeia_dominial /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

**7. Setup SSL (Let's Encrypt):**
```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
```

---

## Database Management

### Backup

**PostgreSQL Backup:**
```bash
# Create backup
pg_dump -U cadeia_user -h localhost cadeia_dominial > backup_$(date +%Y%m%d).sql

# Restore backup
psql -U cadeia_user -h localhost cadeia_dominial < backup_20240101.sql
```

**Docker Backup:**
```bash
# Backup
docker-compose exec -T db pg_dump -U cadeia_user cadeia_dominial > backup.sql

# Restore
cat backup.sql | docker-compose exec -T db psql -U cadeia_user cadeia_dominial
```

### Migrations

**Create Migration:**
```bash
python manage.py makemigrations
```

**Apply Migrations:**
```bash
python manage.py migrate
```

**Show Migrations:**
```bash
python manage.py showmigrations
```

**Rollback Migration:**
```bash
python manage.py migrate dominial 0042  # Rollback to migration 0042
```

---

## Monitoring and Maintenance

### Log Files

**Django Logs:**
- Location: `/opt/cadeia_dominial/logs/django.log`
- Level: INFO (configurable via LOG_LEVEL)

**Gunicorn Logs:**
- Access: `/opt/cadeia_dominial/logs/gunicorn_access.log`
- Error: `/opt/cadeia_dominial/logs/gunicorn_error.log`

**Nginx Logs:**
- Access: `/var/log/nginx/access.log`
- Error: `/var/log/nginx/error.log`

**PostgreSQL Logs:**
- Location: `/var/log/postgresql/postgresql-15-main.log`

### Health Checks

**Database Connection:**
```bash
python manage.py dbshell
\conninfo
\q
```

**Check Migrations:**
```bash
python manage.py showmigrations --plan
```

**Test Email:**
```bash
python manage.py shell
from django.core.mail import send_mail
send_mail('Test', 'Test message', 'from@example.com', ['to@example.com'])
```

### Performance Monitoring

**Database Query Analysis:**
```bash
python manage.py shell
from django.db import connection
from django.db import reset_queries
reset_queries()
# Run some queries
print(len(connection.queries))  # Number of queries
```

**Check Static Files:**
```bash
python manage.py collectstatic --dry-run
```

---

## Troubleshooting

### Common Issues

**1. Database Connection Error:**
```
Solution:
- Check PostgreSQL is running: sudo systemctl status postgresql
- Verify .env DATABASE_* settings
- Check pg_hba.conf for connection permissions
```

**2. Static Files Not Loading:**
```
Solution:
- Run: python manage.py collectstatic
- Check STATIC_ROOT permissions
- Verify Nginx static location configuration
```

**3. WeasyPrint PDF Error:**
```
Solution:
- Install system dependencies (see System Dependencies section)
- Check cairo/pango libraries: ldconfig -p | grep cairo
```

**4. Import Errors:**
```
Solution:
- Verify all requirements installed: pip list
- Check Python version: python --version (must be 3.8+)
- Reinstall dependencies: pip install -r requirements.txt --force-reinstall
```

**5. Permission Denied:**
```
Solution:
- Check file permissions: ls -la
- Set correct owner: sudo chown -R www-data:www-data /opt/cadeia_dominial
```

---

## Security Checklist

**Production Deployment:**

- [ ] Set `DEBUG=False`
- [ ] Generate unique `SECRET_KEY`
- [ ] Configure `ALLOWED_HOSTS`
- [ ] Enable HTTPS (SSL/TLS)
- [ ] Set secure cookie flags
- [ ] Configure CSRF protection
- [ ] Enable HSTS
- [ ] Set up firewall (UFW)
- [ ] Use strong database password
- [ ] Restrict database access
- [ ] Regular backups configured
- [ ] Log rotation enabled
- [ ] Disable unnecessary services
- [ ] Keep dependencies updated
- [ ] Monitor security advisories

---

## Updating

### Application Updates

```bash
# Pull latest code
cd /opt/cadeia_dominial
git pull origin main

# Activate virtual environment
source venv/bin/activate

# Install new dependencies
pip install -r requirements.txt

# Run migrations
python manage.py migrate

# Collect static files
python manage.py collectstatic --no-input

# Restart application
sudo supervisorctl restart cadeia_dominial
# or with Docker:
docker-compose restart web
```

### Dependency Updates

```bash
# Check outdated packages
pip list --outdated

# Update specific package
pip install --upgrade django

# Update all packages (carefully!)
pip install --upgrade -r requirements.txt

# Test thoroughly before deploying
python manage.py test
```

---

## Scaling Considerations

### Horizontal Scaling

**Load Balancer Configuration:**
- Multiple Gunicorn instances
- Nginx load balancing
- Session storage in database or Redis

**Database Optimization:**
- Connection pooling
- Read replicas for reporting
- Query optimization
- Indexing strategy

### Caching

**Redis Integration (Future):**
```python
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': 'redis://127.0.0.1:6379/1',
    }
}
```

### CDN for Static Files

**AWS S3 / CloudFront:**
```python
# settings_prod.py
DEFAULT_FILE_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'
STATICFILES_STORAGE = 'storages.backends.s3boto3.S3StaticStorage'
AWS_STORAGE_BUCKET_NAME = 'your-bucket'
```

---

## Summary

The application supports multiple deployment options:
- **Development:** SQLite + Django dev server
- **Docker:** Containerized with PostgreSQL
- **VPS:** Traditional deployment with Nginx + Gunicorn
- **Scaling:** Ready for horizontal scaling with load balancers

Follow best practices for:
- Security configuration
- Regular backups
- Monitoring and logging
- Performance optimization
- Dependency management
