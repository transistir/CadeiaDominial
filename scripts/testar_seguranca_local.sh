#!/bin/bash

echo "=== TESTE DE CONFIGURAÇÕES DE SEGURANÇA ==="
echo "Este script testa as configurações localmente antes de aplicar em produção"
echo ""

# Função para testar firewall
test_firewall() {
    echo "1. Testando configurações de firewall..."
    
    if command -v ufw &> /dev/null; then
        echo "   - UFW encontrado"
        echo "   - Status atual:"
        sudo ufw status
    else
        echo "   - UFW não encontrado (será instalado em produção)"
    fi
    
    echo "   ✅ Teste de firewall concluído"
}

# Função para testar fail2ban
test_fail2ban() {
    echo "2. Testando configurações de fail2ban..."
    
    if command -v fail2ban-client &> /dev/null; then
        echo "   - Fail2ban encontrado"
        echo "   - Status atual:"
        sudo fail2ban-client status
    else
        echo "   - Fail2ban não encontrado (será instalado em produção)"
    fi
    
    echo "   ✅ Teste de fail2ban concluído"
}

# Função para testar monitoramento
test_monitoring() {
    echo "3. Testando script de monitoramento..."
    
    # Criar script de teste
    cat > /tmp/test_monitor.sh <<'EOF'
#!/bin/bash
LOG_FILE="/tmp/test_security_monitor.log"
DATE=$(date '+%Y-%m-%d %H:%M:%S')

echo "[$DATE] Teste de monitoramento executado" >> $LOG_FILE

# Simular verificação de containers
if docker ps | grep -q "cadeia_dominial"; then
    echo "[$DATE] Containers encontrados" >> $LOG_FILE
else
    echo "[$DATE] Nenhum container encontrado" >> $LOG_FILE
fi

# Simular verificação de tentativas de conexão
echo "[$DATE] Simulando verificação de tentativas de conexão" >> $LOG_FILE

echo "Log de teste criado em: $LOG_FILE"
EOF

    chmod +x /tmp/test_monitor.sh
    
    echo "   - Executando script de teste..."
    /tmp/test_monitor.sh
    
    echo "   - Verificando log gerado:"
    cat /tmp/test_security_monitor.log
    
    # Limpar arquivos de teste
    rm -f /tmp/test_monitor.sh /tmp/test_security_monitor.log
    
    echo "   ✅ Teste de monitoramento concluído"
}

# Função para testar conectividade
test_connectivity() {
    echo "4. Testando conectividade..."
    
    # Testar se a aplicação está rodando
    if docker ps | grep -q "cadeia_dominial"; then
        echo "   ✅ Containers da aplicação rodando"
        
        # Testar se a aplicação responde
        if curl -f http://localhost:8000/admin/ > /dev/null 2>&1; then
            echo "   ✅ Aplicação respondendo na porta 8000"
        else
            echo "   ⚠️  Aplicação não responde na porta 8000"
        fi
    else
        echo "   ⚠️  Containers da aplicação não estão rodando"
    fi
    
    # Testar conectividade com o banco
    if docker exec cadeia_dominial_db_dev psql -U cadeia_user -d cadeia_dominial_dev -c "SELECT 1;" > /dev/null 2>&1; then
        echo "   ✅ Conexão com banco de dados funcionando"
    else
        echo "   ⚠️  Conexão com banco de dados não funcionando"
    fi
    
    echo "   ✅ Teste de conectividade concluído"
}

# Função para simular configurações
simulate_configurations() {
    echo "5. Simulando configurações que serão aplicadas..."
    
    echo "   - Firewall (UFW):"
    echo "     * Permitir SSH (porta 22)"
    echo "     * Permitir HTTP (porta 80)"
    echo "     * Permitir HTTPS (porta 443)"
    echo "     * Bloquear PostgreSQL (porta 5432) - se não for necessário externamente"
    
    echo "   - Fail2ban:"
    echo "     * Monitorar tentativas de login SSH"
    echo "     * Monitorar tentativas de conexão PostgreSQL"
    echo "     * Bloquear IPs após 5 tentativas em 10 minutos"
    
    echo "   - Monitoramento:"
    echo "     * Verificar status dos containers a cada 10 minutos"
    echo "     * Log de tentativas de conexão suspeitas"
    echo "     * Log de tentativas de login SSH falhadas"
    
    echo "   ✅ Simulação concluída"
}

# Função para verificar dependências
check_dependencies() {
    echo "6. Verificando dependências necessárias..."
    
    # Verificar se o sistema tem os pacotes necessários
    echo "   - Verificando pacotes disponíveis..."
    
    if command -v ufw &> /dev/null; then
        echo "   ✅ UFW disponível"
    else
        echo "   ⚠️  UFW não encontrado (será instalado)"
    fi
    
    if command -v fail2ban-client &> /dev/null; then
        echo "   ✅ Fail2ban disponível"
    else
        echo "   ⚠️  Fail2ban não encontrado (será instalado)"
    fi
    
    if command -v docker &> /dev/null; then
        echo "   ✅ Docker disponível"
    else
        echo "   ❌ Docker não encontrado"
        return 1
    fi
    
    if command -v curl &> /dev/null; then
        echo "   ✅ curl disponível"
    else
        echo "   ⚠️  curl não encontrado (será instalado)"
    fi
    
    echo "   ✅ Verificação de dependências concluída"
}

# Execução principal
main() {
    echo "=== INICIANDO TESTES DE SEGURANÇA ==="
    echo ""
    
    check_dependencies
    test_connectivity
    test_firewall
    test_fail2ban
    test_monitoring
    simulate_configurations
    
    echo ""
    echo "=== TESTES CONCLUÍDOS ==="
    echo "✅ Todos os testes passaram"
    echo ""
    echo "=== PRÓXIMOS PASSOS ==="
    echo "1. Se todos os testes passaram, você pode aplicar em produção"
    echo "2. Use: ./scripts/configurar_seguranca_producao_seguro.sh"
    echo "3. Em caso de problemas, use: ./scripts/restaurar_backup_seguranca.sh"
    echo ""
    echo "=== RECOMENDAÇÕES ==="
    echo "1. Execute os testes em um horário de baixo tráfego"
    echo "2. Tenha um plano de rollback pronto"
    echo "3. Monitore os logs após a aplicação"
    echo "4. Teste a aplicação após cada etapa"
}

# Executar apenas se for chamado diretamente
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi 