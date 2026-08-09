#!/bin/bash
# Entrypoint raiz: garante permissões em /app/media e /app/staticfiles antes de dropar privilegios
set -e

echo "🔐 [entrypoint] Garantindo ownership de /app/media e /app/staticfiles para appuser..."
mkdir -p /app/media
chown -R appuser:appuser /app/media
# staticfiles já existe no image, mas garante tbm
mkdir -p /app/staticfiles
chown -R appuser:appuser /app/staticfiles

echo "🔓 [entrypoint] Dropping privileges para appuser..."
# Usa su para rodar init.sh como appuser (nao root)
exec su -s /bin/bash appuser -c "/app/init.sh"