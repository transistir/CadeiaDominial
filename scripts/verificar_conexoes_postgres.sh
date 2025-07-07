#!/bin/bash

echo "=== Investigando tentativas de conexão com usuário 'postgres' ==="

# Verificar se o usuário postgres existe
echo "1. Verificando se o usuário 'postgres' existe no banco:"
docker exec cadeia_dominial_db psql -U cadeia_user -d cadeia_dominial -c "\du" 2>/dev/null || echo "Erro ao conectar com o banco"

# Verificar logs do PostgreSQL para identificar origem das conexões
echo -e "\n2. Últimas tentativas de conexão com usuário 'postgres':"
docker logs cadeia_dominial_db 2>&1 | grep "postgres" | tail -10

# Verificar processos que podem estar tentando se conectar
echo -e "\n3. Verificando processos que podem estar tentando conexão:"
docker exec cadeia_dominial_db ps aux | grep -E "(psql|pg_dump|pg_restore)" || echo "Nenhum processo de backup encontrado"

# Verificar se há algum script ou cron job tentando conexão
echo -e "\n4. Verificando cron jobs no host:"
docker exec cadeia_dominial_web crontab -l 2>/dev/null || echo "Nenhum cron job encontrado"

# Verificar variáveis de ambiente que podem estar causando o problema
echo -e "\n5. Verificando variáveis de ambiente do container web:"
docker exec cadeia_dominial_web env | grep -E "(DB_|POSTGRES_)" || echo "Nenhuma variável de banco encontrada"

# Verificar se há algum health check ou monitoramento configurado
echo -e "\n6. Verificando configurações de health check:"
docker inspect cadeia_dominial_db | grep -A 10 -B 5 "healthcheck" || echo "Nenhum health check configurado"

echo -e "\n=== Soluções possíveis ==="
echo "1. Se houver ferramentas externas tentando conectar, configure-as para usar 'cadeia_user'"
echo "2. Se houver scripts de backup, atualize-os para usar o usuário correto"
echo "3. Se houver monitoramento, configure-o para usar as credenciais corretas"
echo "4. Verifique se há algum cliente PostgreSQL configurado incorretamente"

echo -e "\n=== Para criar o usuário postgres (se necessário):"
echo "docker exec -it cadeia_dominial_db psql -U cadeia_user -d cadeia_dominial -c \"CREATE USER postgres WITH PASSWORD 'senha_temporaria';\""
echo "docker exec -it cadeia_dominial_db psql -U cadeia_user -d cadeia_dominial -c \"GRANT ALL PRIVILEGES ON DATABASE cadeia_dominial TO postgres;\"" 