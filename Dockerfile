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

# Criar diretório de logs
RUN mkdir -p /var/log/cadeia_dominial \
    && chown -R appuser:appuser /var/log/cadeia_dominial

# Coletar arquivos estáticos como root primeiro
RUN python manage.py collectstatic --noinput

# Mudar permissões dos arquivos estáticos
RUN chown -R appuser:appuser /app/staticfiles

USER appuser

# Expor porta
EXPOSE 8000

# Copiar script de inicialização
COPY scripts/init.sh /app/init.sh
RUN chmod +x /app/init.sh

# Comando de inicialização
CMD ["/app/init.sh"] 