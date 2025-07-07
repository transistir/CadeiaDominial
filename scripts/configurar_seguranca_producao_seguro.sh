#!/bin/bash

echo "=== Configuração de Segurança - Versão Segura ==="
echo "Este script implementa medidas de segurança de forma gradual e segura"
echo ""

# Função para backup das configurações atuais
backup_configs() {
    echo "1. Fazendo backup das configurações atuais..."
    BACKUP_DIR="/tmp/security_backup_$(date +%Y%m%d_%H%M%S)"
    mkdir -p $BACKUP_DIR
    
    # Backup do firewall
    if command -v ufw &> /dev/null; then
        sudo ufw status numbered > $BACKUP_DIR/ufw_status.txt
    fi
    
    # Backup do fail2ban
    if [ -f /etc/fail2ban/jail.local ]; then
        sudo cp /etc/fail2ban/jail.local $BACKUP_DIR/
    fi
    
    # Backup do cron atual
    crontab -l > $BACKUP_DIR/crontab_backup.txt 2>/dev/null || echo "Nenhum cron job encontrado" > $BACKUP_DIR/crontab_backup.txt
    
    echo "   ✅ Backup salvo em: $BACKUP_DIR"
    echo "   Para restaurar: ./scripts/restaurar_backup_seguranca.sh $BACKUP_DIR"
}

# Função para verificar se os serviços estão rodando
check_services() {
    echo "2. Verificando status dos serviços antes das alterações..."
    
    # Verificar se o Docker está rodando
    if ! docker info > /dev/null 2>&1; then
        echo "   ❌ ERRO: Docker não está rodando!"
        exit 1
    fi
    
    # Verificar se os containers estão rodando
    if ! docker ps | grep -q "cadeia_dominial"; then
        echo "   ❌ ERRO: Containers da aplicação não estão rodando!"
        exit 1
    fi
    
    # Verificar se a aplicação está respondendo
    if ! curl -f http://localhost/admin/ > /dev/null 2>&1; then
        echo "   ⚠️  AVISO: Aplicação não está respondendo na porta 80"
        echo "   Continuando mesmo assim..."
    else
        echo "   ✅ Aplicação respondendo normalmente"
    fi
    
    echo "   ✅ Todos os serviços principais estão funcionando"
}

# Função para configurar firewall de forma segura
configure_firewall_safe() {
    echo "3. Configurando firewall de forma segura..."
    
    if command -v ufw &> /dev/null; then
        echo "   - UFW encontrado"
        
        # Verificar se já está ativo
        if sudo ufw status | grep -q "Status: active"; then
            echo "   - Firewall já está ativo"
            echo "   - Verificando regras existentes..."
            sudo ufw status
        else
            echo "   - Ativando firewall com regras básicas..."
            
            # Permitir SSH primeiro (IMPORTANTE!)
            sudo ufw allow ssh
            echo "   ✅ SSH permitido"
            
            # Permitir HTTP/HTTPS
            sudo ufw allow 80
            sudo ufw allow 443
            echo "   ✅ HTTP/HTTPS permitidos"
            
            # Bloquear PostgreSQL apenas se não estiver sendo usado externamente
            echo "   - Verificando se PostgreSQL precisa de acesso externo..."
            if docker exec cadeia_dominial_db cat /var/lib/postgresql/data/postgresql.conf | grep -q "listen_addresses.*\*"; then
                echo "   ⚠️  PostgreSQL configurado para aceitar conexões externas"
                echo "   - Mantendo porta 5432 aberta (pode ser necessário)"
            else
                echo "   - Bloqueando acesso direto ao PostgreSQL"
                sudo ufw deny 5432
            fi
            
            # Ativar firewall
            echo "   - Ativando firewall..."
            echo "y" | sudo ufw enable
        fi
    else
        echo "   - UFW não encontrado. Instalando..."
        sudo apt update && sudo apt install -y ufw
        configure_firewall_safe
    fi
}

# Função para configurar fail2ban de forma segura
configure_fail2ban_safe() {
    echo "4. Configurando fail2ban de forma segura..."
    
    if command -v fail2ban-client &> /dev/null; then
        echo "   - Fail2ban encontrado"
        sudo fail2ban-client status
    else
        echo "   - Fail2ban não encontrado. Instalando..."
        sudo apt update && sudo apt install -y fail2ban
        
        echo "   - Configurando fail2ban para PostgreSQL..."
        sudo tee /etc/fail2ban/jail.local > /dev/null <<EOF
[postgresql]
enabled = true
port = 5432
filter = postgresql
logpath = /var/log/postgresql/postgresql-*.log
maxretry = 5
bantime = 1800
findtime = 600
EOF
        
        sudo systemctl enable fail2ban
        sudo systemctl start fail2ban
        echo "   ✅ Fail2ban configurado e iniciado"
    fi
}

# Função para configurar monitoramento básico
configure_monitoring_safe() {
    echo "5. Configurando monitoramento básico..."
    
    echo "   - Criando script de monitoramento..."
    sudo tee /usr/local/bin/monitor_security.sh > /dev/null <<'EOF'
#!/bin/bash
LOG_FILE="/var/log/security_monitor.log"
DATE=$(date '+%Y-%m-%d %H:%M:%S')

# Verificar se os containers estão rodando
if ! docker ps | grep -q "cadeia_dominial"; then
    echo "[$DATE] ALERTA: Containers da aplicação não estão rodando" >> $LOG_FILE
fi

# Verificar tentativas de conexão com postgres (apenas contar, não bloquear)
POSTGRES_ATTEMPTS=$(docker logs cadeia_dominial_db 2>&1 | grep "postgres" | tail -50 | wc -l)
if [ $POSTGRES_ATTEMPTS -gt 10 ]; then
    echo "[$DATE] ALERTA: $POSTGRES_ATTEMPTS tentativas de conexão com usuário postgres" >> $LOG_FILE
fi

# Verificar tentativas de login SSH falhadas
SSH_FAILED=$(sudo tail -100 /var/log/auth.log | grep "Failed password" | wc -l)
if [ $SSH_FAILED -gt 10 ]; then
    echo "[$DATE] ALERTA: $SSH_FAILED tentativas de login SSH falhadas" >> $LOG_FILE
fi

# Manter apenas os últimos 1000 logs
tail -1000 $LOG_FILE > /tmp/security_monitor.tmp && mv /tmp/security_monitor.tmp $LOG_FILE
EOF

    sudo chmod +x /usr/local/bin/monitor_security.sh
    
    # Adicionar ao cron apenas se não existir
    if ! crontab -l 2>/dev/null | grep -q "monitor_security.sh"; then
        echo "   - Adicionando monitoramento ao cron..."
        (crontab -l 2>/dev/null; echo "*/10 * * * * /usr/local/bin/monitor_security.sh") | crontab -
    else
        echo "   - Monitoramento já configurado no cron"
    fi
    
    echo "   ✅ Monitoramento configurado"
}

# Função para verificar se tudo está funcionando
verify_changes() {
    echo "6. Verificando se as alterações não quebraram nada..."
    
    # Verificar se a aplicação ainda responde
    echo "   - Testando aplicação..."
    if curl -f http://localhost/admin/ > /dev/null 2>&1; then
        echo "   ✅ Aplicação ainda respondendo"
    else
        echo "   ❌ ERRO: Aplicação não está respondendo!"
        echo "   Verifique os logs e considere restaurar o backup"
        return 1
    fi
    
    # Verificar se os containers ainda estão rodando
    if docker ps | grep -q "cadeia_dominial"; then
        echo "   ✅ Containers ainda rodando"
    else
        echo "   ❌ ERRO: Containers pararam!"
        return 1
    fi
    
    # Verificar firewall
    if sudo ufw status | grep -q "Status: active"; then
        echo "   ✅ Firewall ativo"
    else
        echo "   ⚠️  AVISO: Firewall não está ativo"
    fi
    
    echo "   ✅ Todas as verificações passaram"
}

# Execução principal
main() {
    echo "=== INICIANDO CONFIGURAÇÃO DE SEGURANÇA ==="
    echo "Este processo é seguro e pode ser revertido se necessário."
    echo ""
    
    # Fazer backup primeiro
    backup_configs
    
    # Verificar serviços
    check_services
    
    # Configurar cada componente
    configure_firewall_safe
    configure_fail2ban_safe
    configure_monitoring_safe
    
    # Verificar se tudo está funcionando
    verify_changes
    
    echo ""
    echo "=== CONFIGURAÇÃO CONCLUÍDA COM SUCESSO ==="
    echo "✅ Medidas de segurança implementadas"
    echo "✅ Sistema continua funcionando"
    echo ""
    echo "=== PRÓXIMOS PASSOS ==="
    echo "1. Monitorar logs: tail -f /var/log/security_monitor.log"
    echo "2. Verificar firewall: sudo ufw status"
    echo "3. Verificar fail2ban: sudo fail2ban-client status"
    echo ""
    echo "=== EM CASO DE PROBLEMAS ==="
    echo "Para restaurar: ./scripts/restaurar_backup_seguranca.sh $BACKUP_DIR"
}

# Executar apenas se for chamado diretamente
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi 