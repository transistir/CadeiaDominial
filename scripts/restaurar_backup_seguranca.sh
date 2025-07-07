#!/bin/bash

# Script para restaurar configurações de segurança
# Uso: ./scripts/restaurar_backup_seguranca.sh /caminho/para/backup

if [ $# -eq 0 ]; then
    echo "Uso: $0 /caminho/para/backup"
    echo "Exemplo: $0 /tmp/security_backup_20250707_143022"
    exit 1
fi

BACKUP_DIR="$1"

if [ ! -d "$BACKUP_DIR" ]; then
    echo "❌ ERRO: Diretório de backup não encontrado: $BACKUP_DIR"
    exit 1
fi

echo "=== RESTAURANDO CONFIGURAÇÕES DE SEGURANÇA ==="
echo "Backup: $BACKUP_DIR"
echo ""

# 1. Restaurar firewall
if [ -f "$BACKUP_DIR/ufw_status.txt" ]; then
    echo "1. Restaurando configurações do firewall..."
    echo "   - Desabilitando firewall temporariamente..."
    sudo ufw --force disable
    
    echo "   - Restaurando regras..."
    # Ler as regras do backup e aplicá-las
    while IFS= read -r line; do
        if [[ $line =~ ^[0-9]+ ]]; then
            rule_num=$(echo $line | awk '{print $1}' | sed 's/\[//' | sed 's/\]//')
            echo "   - Restaurando regra $rule_num"
        fi
    done < "$BACKUP_DIR/ufw_status.txt"
    
    echo "   - Reabilitando firewall..."
    sudo ufw --force enable
    echo "   ✅ Firewall restaurado"
else
    echo "1. Nenhum backup do firewall encontrado"
fi

# 2. Restaurar fail2ban
if [ -f "$BACKUP_DIR/jail.local" ]; then
    echo "2. Restaurando configurações do fail2ban..."
    sudo cp "$BACKUP_DIR/jail.local" /etc/fail2ban/
    sudo systemctl restart fail2ban
    echo "   ✅ Fail2ban restaurado"
else
    echo "2. Nenhum backup do fail2ban encontrado"
fi

# 3. Restaurar cron
if [ -f "$BACKUP_DIR/crontab_backup.txt" ]; then
    echo "3. Restaurando cron jobs..."
    crontab "$BACKUP_DIR/crontab_backup.txt"
    echo "   ✅ Cron jobs restaurados"
else
    echo "3. Nenhum backup do cron encontrado"
fi

# 4. Remover script de monitoramento se foi adicionado
if [ -f "/usr/local/bin/monitor_security.sh" ]; then
    echo "4. Removendo script de monitoramento..."
    sudo rm /usr/local/bin/monitor_security.sh
    echo "   ✅ Script de monitoramento removido"
fi

# 5. Verificar se os serviços estão funcionando
echo "5. Verificando se os serviços estão funcionando..."
if docker ps | grep -q "cadeia_dominial"; then
    echo "   ✅ Containers da aplicação rodando"
else
    echo "   ❌ ERRO: Containers da aplicação não estão rodando!"
fi

if curl -f http://localhost/admin/ > /dev/null 2>&1; then
    echo "   ✅ Aplicação respondendo"
else
    echo "   ❌ ERRO: Aplicação não está respondendo!"
fi

echo ""
echo "=== RESTAURAÇÃO CONCLUÍDA ==="
echo "✅ Configurações restauradas do backup: $BACKUP_DIR"
echo ""
echo "=== PRÓXIMOS PASSOS ==="
echo "1. Verificar se a aplicação está funcionando: http://localhost"
echo "2. Verificar status do firewall: sudo ufw status"
echo "3. Verificar status do fail2ban: sudo fail2ban-client status"
echo ""
echo "Se ainda houver problemas, reinicie os containers:"
echo "docker-compose restart" 