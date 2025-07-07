#!/bin/bash

echo "=== Investigando tentativas de conexão suspeitas no servidor de produção ==="

# Verificar logs do PostgreSQL para identificar padrões
echo "1. Analisando logs do PostgreSQL para tentativas de conexão:"
echo "   - Últimas 20 tentativas de conexão com usuário 'postgres':"
docker logs cadeia_dominial_db 2>&1 | grep "postgres" | tail -20

echo -e "\n2. Verificando padrões de IP que estão tentando conectar:"
echo "   - IPs que tentaram conexão com usuário 'postgres':"
docker logs cadeia_dominial_db 2>&1 | grep "postgres" | grep -oE "from [0-9]+\.[0-9]+\.[0-9]+\.[0-9]+" | sort | uniq -c

echo -e "\n3. Verificando frequência das tentativas:"
echo "   - Tentativas por hora:"
docker logs cadeia_dominial_db 2>&1 | grep "postgres" | awk '{print $1, $2}' | cut -d' ' -f1-2 | sort | uniq -c | tail -10

echo -e "\n4. Verificando se há processos suspeitos rodando:"
echo "   - Processos que podem estar tentando conexão:"
docker exec cadeia_dominial_db ps aux | grep -E "(psql|pg_dump|pg_restore|postgres)" || echo "Nenhum processo suspeito encontrado"

echo -e "\n5. Verificando conexões ativas no banco:"
echo "   - Conexões ativas:"
docker exec cadeia_dominial_db psql -U cadeia_user -d cadeia_dominial -c "SELECT client_addr, usename, application_name, state FROM pg_stat_activity WHERE client_addr IS NOT NULL;" 2>/dev/null || echo "Erro ao verificar conexões"

echo -e "\n6. Verificando se há cron jobs ou scripts agendados:"
echo "   - Cron jobs no servidor:"
docker exec cadeia_dominial_web crontab -l 2>/dev/null || echo "Nenhum cron job encontrado"

echo -e "\n7. Verificando logs do nginx para tentativas de acesso:"
echo "   - Últimas tentativas de acesso HTTP:"
docker logs cadeia_dominial_nginx 2>&1 | grep -E "(error|warning)" | tail -10

echo -e "\n=== Análise de Segurança ==="
echo "Se você identificar:"
echo "1. Muitas tentativas do mesmo IP → Possível ataque"
echo "2. Tentativas de IPs diferentes → Scanning automatizado"
echo "3. Tentativas regulares → Script de monitoramento"
echo "4. Tentativas esporádicas → Ferramentas de administração"

echo -e "\n=== Recomendações de Segurança ==="
echo "1. Configurar firewall para limitar acesso à porta 5432"
echo "2. Usar apenas conexões locais para o banco (127.0.0.1)"
echo "3. Configurar fail2ban para bloquear IPs suspeitos"
echo "4. Monitorar logs regularmente"
echo "5. Usar VPN para acesso administrativo"

echo -e "\n=== Para bloquear IPs suspeitos (exemplo):"
echo "sudo ufw deny from IP_SUSPEITO"
echo "sudo iptables -A INPUT -s IP_SUSPEITO -j DROP"

echo -e "\n=== Para configurar acesso apenas local ao PostgreSQL:"
echo "Editar pg_hba.conf para permitir apenas conexões locais" 