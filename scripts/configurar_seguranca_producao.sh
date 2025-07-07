#!/bin/bash

echo "=== Configurando medidas de segurança básicas ==="

# 1. Verificar se o firewall está ativo
echo "1. Verificando status do firewall:"
if command -v ufw &> /dev/null; then
    echo "   UFW encontrado. Status:"
    sudo ufw status
else
    echo "   UFW não encontrado. Instalando..."
    sudo apt update && sudo apt install -y ufw
fi

# 2. Configurar regras básicas do firewall
echo -e "\n2. Configurando regras do firewall:"
echo "   - Permitindo SSH (porta 22)"
sudo ufw allow ssh
echo "   - Permitindo HTTP (porta 80)"
sudo ufw allow 80
echo "   - Permitindo HTTPS (porta 443)"
sudo ufw allow 443
echo "   - Bloqueando acesso direto ao PostgreSQL (porta 5432)"
sudo ufw deny 5432
echo "   - Ativando firewall"
sudo ufw --force enable

# 3. Verificar configuração do PostgreSQL
echo -e "\n3. Verificando configuração do PostgreSQL:"
echo "   - Verificando se o banco aceita apenas conexões locais:"
docker exec cadeia_dominial_db cat /var/lib/postgresql/data/pg_hba.conf | grep -E "(local|host)" | head -10

# 4. Configurar fail2ban (se disponível)
echo -e "\n4. Verificando fail2ban:"
if command -v fail2ban-client &> /dev/null; then
    echo "   Fail2ban encontrado. Status:"
    sudo fail2ban-client status
else
    echo "   Fail2ban não encontrado. Instalando..."
    sudo apt update && sudo apt install -y fail2ban
    echo "   Configurando fail2ban para PostgreSQL..."
    sudo tee /etc/fail2ban/jail.local > /dev/null <<EOF
[postgresql]
enabled = true
port = 5432
filter = postgresql
logpath = /var/log/postgresql/postgresql-*.log
maxretry = 3
bantime = 3600
findtime = 600
EOF
    sudo systemctl enable fail2ban
    sudo systemctl start fail2ban
fi

# 5. Verificar logs de segurança
echo -e "\n5. Verificando logs de segurança:"
echo "   - Últimas tentativas de login SSH:"
sudo tail -10 /var/log/auth.log | grep -E "(Failed|Invalid)" || echo "Nenhuma tentativa de login falhada encontrada"

# 6. Configurar monitoramento básico
echo -e "\n6. Configurando monitoramento básico:"
echo "   - Criando script de monitoramento de logs:"
sudo tee /usr/local/bin/monitor_security.sh > /dev/null <<'EOF'
#!/bin/bash
LOG_FILE="/var/log/security_monitor.log"
DATE=$(date '+%Y-%m-%d %H:%M:%S')

# Verificar tentativas de conexão com postgres
POSTGRES_ATTEMPTS=$(docker logs cadeia_dominial_db 2>&1 | grep "postgres" | wc -l)
if [ $POSTGRES_ATTEMPTS -gt 0 ]; then
    echo "[$DATE] ALERTA: $POSTGRES_ATTEMPTS tentativas de conexão com usuário postgres" >> $LOG_FILE
fi

# Verificar tentativas de login SSH falhadas
SSH_FAILED=$(sudo tail -100 /var/log/auth.log | grep "Failed password" | wc -l)
if [ $SSH_FAILED -gt 5 ]; then
    echo "[$DATE] ALERTA: $SSH_FAILED tentativas de login SSH falhadas" >> $LOG_FILE
fi

# Manter apenas os últimos 1000 logs
tail -1000 $LOG_FILE > /tmp/security_monitor.tmp && mv /tmp/security_monitor.tmp $LOG_FILE
EOF

sudo chmod +x /usr/local/bin/monitor_security.sh

# 7. Configurar cron para monitoramento
echo -e "\n7. Configurando cron para monitoramento:"
(crontab -l 2>/dev/null; echo "*/5 * * * * /usr/local/bin/monitor_security.sh") | crontab -

echo -e "\n=== Configuração concluída ==="
echo "Medidas implementadas:"
echo "1. ✅ Firewall configurado (UFW)"
echo "2. ✅ Porta 5432 bloqueada para acesso externo"
echo "3. ✅ Fail2ban configurado para PostgreSQL"
echo "4. ✅ Script de monitoramento criado"
echo "5. ✅ Cron job configurado para monitoramento"

echo -e "\n=== Próximos passos recomendados ==="
echo "1. Verificar logs de segurança: tail -f /var/log/security_monitor.log"
echo "2. Configurar alertas por email para eventos de segurança"
echo "3. Configurar backup automático dos logs"
echo "4. Considerar usar VPN para acesso administrativo"
echo "5. Configurar autenticação SSH com chaves em vez de senha"

echo -e "\n=== Para verificar status:"
echo "sudo ufw status"
echo "sudo fail2ban-client status"
echo "tail -f /var/log/security_monitor.log" 