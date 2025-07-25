# Medidas de Segurança - Ataque PostgreSQL

## Data: 25/07/2025
## Problema Identificado: Ataque de Força Bruta

### Descrição do Ataque
- **IP Atacante**: 125.220.159.112
- **Tipo**: Tentativas repetidas de conexão com usuário "postgres"
- **Frequência**: A cada segundo
- **Método**: Ataque de força bruta no PostgreSQL

### Medidas Implementadas

#### 1. Bloqueio de IP Malicioso
```bash
# Bloquear IP atacante
iptables -A INPUT -s 125.220.159.112 -j DROP

# Salvar regras do iptables
mkdir -p /etc/iptables
iptables-save > /etc/iptables/rules.v4
```

#### 2. Bloqueio da Porta PostgreSQL
```bash
# Bloquear acesso externo à porta 5432
iptables -A INPUT -p tcp --dport 5432 -j DROP
```

#### 3. Remoção da Exposição da Porta no Docker
- **Arquivo**: `docker-compose.yml`
- **Alteração**: Comentada a linha `- "5432:5432"`
- **Motivo**: Impedir acesso externo ao banco de dados

### Configuração Atual de Segurança

#### Docker Compose (Seguro)
```yaml
db:
  image: postgres:15
  container_name: cadeia_dominial_db
  environment:
    POSTGRES_DB: ${DB_NAME:-cadeia_dominial}
    POSTGRES_USER: ${DB_USER:-cadeia_user}
    POSTGRES_PASSWORD: ${DB_PASSWORD:-sua_senha_segura_aqui}
  volumes:
    - postgres_data:/var/lib/postgresql/data
    - ./scripts/init-db.sql:/docker-entrypoint-initdb.d/init-db.sql
  # ports:
  #   - "5432:5432"  # REMOVIDO POR SEGURANÇA - BLOQUEIA ACESSO EXTERNO AO BANCO
  networks:
    - cadeia_network
```

#### Acesso ao Banco
- **Apenas interno**: Via rede Docker
- **Usuário**: cadeia_user (não postgres)
- **Acesso externo**: BLOQUEADO

### Monitoramento Implementado

#### Script de Monitoramento de Segurança
- **Arquivo**: `/usr/local/bin/monitor_security.sh`
- **Frequência**: A cada 5 minutos
- **Função**: Monitora tentativas de ataque

#### Logs Monitorados
- Tentativas de conexão com usuário postgres
- Tentativas de login SSH falhadas
- Logs de segurança salvos em `/var/log/security_monitor.log`

### Recomendações Adicionais

#### 1. Firewall Permanente
```bash
# Instalar e configurar ufw
apt install ufw
ufw default deny incoming
ufw default allow outgoing
ufw allow ssh
ufw allow 80/tcp
ufw allow 443/tcp
ufw enable
```

#### 2. Fail2ban
```bash
# Instalar fail2ban para proteção automática
apt install fail2ban
```

#### 3. Senhas Fortes
- Usar senhas complexas para todos os usuários
- Trocar senhas regularmente
- Não usar senhas padrão

#### 4. Backup de Segurança
- Manter backups regulares
- Testar restauração de backups
- Armazenar backups em local seguro

### Verificação de Segurança

#### Comandos para Verificar
```bash
# Verificar regras do iptables
iptables -L -n

# Verificar logs de segurança
tail -f /var/log/security_monitor.log

# Verificar tentativas de conexão
docker-compose logs db | grep "postgres"

# Verificar portas abertas
netstat -tulpn | grep :5432
```

### Status Atual
- ✅ IP atacante bloqueado
- ✅ Porta 5432 bloqueada externamente
- ✅ Docker configurado sem exposição da porta
- ✅ Monitoramento ativo
- ✅ Logs de segurança funcionando

### Próximos Passos
1. Implementar fail2ban
2. Configurar ufw permanentemente
3. Revisar todas as senhas
4. Implementar backup automático
5. Monitorar logs regularmente 