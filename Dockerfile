# Dockerfile para Cadeia Dominial Django App
FROM python:3.11-slim

# Definir variáveis de ambiente
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DJANGO_SETTINGS_MODULE=cadeia_dominial.settings_prod

# Definir diretório de trabalho
WORKDIR /app

# Instalar dependências do sistema
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        postgresql-client \
        build-essential \
        libpq-dev \
        curl \
        # Dependências para weasyprint
        libpango-1.0-0 \
        libharfbuzz0b \
        libpangoft2-1.0-0 \
        libffi-dev \
        libjpeg-dev \
        libopenjp2-7-dev \
        libcairo2 \
        libpango1.0-dev \
        libgdk-pixbuf2.0-dev \
        libffi-dev \
        shared-mime-info \
    && rm -rf /var/lib/apt/lists/*

# Copiar requirements e instalar dependências Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código da aplicação
COPY . .

# Criar usuário não-root para segurança
RUN adduser --disabled-password --gecos '' appuser

# Criar diretório de logs
RUN mkdir -p /var/log/cadeia_dominial \
    && chown -R appuser:appuser /var/log/cadeia_dominial

# Copiar scripts de inicialização e dar permissão (como root)
COPY scripts/init.sh /app/init.sh
COPY scripts/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/init.sh /app/entrypoint.sh

# Criar diretório staticfiles e media (perms garantidas no entrypoint root)
RUN mkdir -p /app/staticfiles /app/media \
    && chown -R appuser:appuser /app/staticfiles /app/media

# Coletar arquivos estáticos como ROOT (entrypoint dropa privilegios depois)
RUN python manage.py collectstatic --noinput

# Expor porta
EXPOSE 8000

# Comando de inicialização: entrypoint como ROOT garante perms do bind mount,
# entao dropa privilegios para appuser via su
ENTRYPOINT ["/app/entrypoint.sh"]