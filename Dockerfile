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
    && rm -rf /var/lib/apt/lists/*

# Copiar requirements e instalar dependências Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código da aplicação
COPY . .

# Criar usuário não-root para segurança
RUN adduser --disabled-password --gecos '' appuser \
    && chown -R appuser:appuser /app
USER appuser

# Coletar arquivos estáticos
RUN python manage.py collectstatic --noinput

# Expor porta
EXPOSE 8000

# Comando de inicialização
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "3", "cadeia_dominial.wsgi:application"] 