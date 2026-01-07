# 🚀 Deploy Automatizado - Cadeia Dominial

Este documento descreve o processo de deploy automatizado do sistema Cadeia Dominial, que inclui setup completo automático.

## 📋 O que é automatizado

O sistema agora inclui um **script de inicialização automática** que executa:

1. ✅ **Migrações do banco de dados**
2. ✅ **Criação de tipos padrão** (documentos, lançamentos)
3. ✅ **Criação de usuário admin padrão**
4. ✅ **Importação automática de terras indígenas** da FUNAI
5. ✅ **Coleta de arquivos estáticos**
6. ✅ **Inicialização do servidor Gunicorn**

## 🔧 Como funciona

### Script de Inicialização (`scripts/init.sh`)

O script verifica se cada etapa já foi executada anteriormente e só executa se necessário:

```bash
# Verifica se já existe superusuário
if python manage.py shell -c "from django.contrib.auth.models import User; print('Superusuário existe:', User.objects.filter(is_superuser=True).exists())" | grep -q "True"; then
    echo "✅ Superusuário já existe, pulando criação..."
    return
fi
```

### Usuário Padrão Criado

- **Usuário**: Definido via `ADMIN_USERNAME` (padrão: `admin`)
- **Senha**: **OBRIGATÓRIO** - Definida via `ADMIN_PASSWORD` (mínimo 8 caracteres)
- **Email**: Definido via `ADMIN_EMAIL` (padrão: `admin@cadeiadominial.com.br`)
- **Tipo**: Superusuário (acesso total ao sistema)

**🔒 Segurança**: A senha é obrigatória e deve ser definida via variável de ambiente!

### Terras Indígenas Importadas

- **Fonte**: GeoServer da FUNAI
- **Quantidade**: ~620 terras indígenas
- **Dados**: Nome, código, etnia, estado, área, fase, datas importantes

## 🚀 Deploy Completo

### 1. **Preparar o servidor**

```bash
# Instalar Docker e Docker Compose
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER

# Instalar Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/download/v2.20.0/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose
```

### 2. **Clonar e configurar**

```bash
# Clonar repositório
git clone https://github.com/transistir/CadeiaDominial.git
cd CadeiaDominial

# Copiar arquivo de ambiente
cp env.example .env

# Editar variáveis de ambiente (OBRIGATÓRIO)
nano .env

# ⚠️  IMPORTANTE: Defina a senha do usuário admin no arquivo .env:
# ADMIN_PASSWORD=sua_senha_muito_segura_aqui
```

### 3. **Configurar domínio (opcional)**

Se tiver domínio próprio:
- Aponte o DNS para o IP do servidor
- Configure as variáveis no `.env`:
  ```
  DOMAIN_NAME=cadeiadominial.com.br
  CERTBOT_EMAIL=seu-email@exemplo.com
  ```

### 4. **Validar configuração**

```bash
# Validar variáveis de ambiente
./scripts/validate_env.sh

# Se houver erros, corrija e execute novamente
```

### 5. **Executar deploy**

```bash
# Build e inicialização
docker-compose build --no-cache
docker-compose up -d

# Verificar logs
docker-compose logs -f web
```

### 5. **Configurar SSL (se tiver domínio)**

```bash
# Gerar certificado SSL
docker-compose run --rm certbot

# Reiniciar nginx
docker-compose restart nginx
```

## 📊 Monitoramento

### Verificar status dos containers

```bash
docker-compose ps
```

### Ver logs em tempo real

```bash
# Logs do Django
docker-compose logs -f web

# Logs do Nginx
docker-compose logs -f nginx

# Logs do banco
docker-compose logs -f db
```

### Verificar dados importados

```bash
# Acessar shell do Django
docker-compose exec web python manage.py shell

# Verificar terras indígenas
from dominial.models import TIs, TerraIndigenaReferencia
print(f"TIs: {TIs.objects.count()}")
print(f"Referências: {TerraIndigenaReferencia.objects.count()}")

# Verificar usuários
from django.contrib.auth.models import User
print(f"Usuários: {User.objects.count()}")
```

## 🔒 Segurança

### Configurar senha do usuário admin

**OBRIGATÓRIO**: Defina a senha do usuário admin antes do deploy:

#### Opção 1 - Arquivo .env (Recomendado)
```bash
# Editar arquivo .env
nano .env

# Adicionar/editar a linha:
ADMIN_PASSWORD=sua_senha_muito_segura_aqui
```

#### Opção 2 - Variável de ambiente
```bash
export ADMIN_PASSWORD='sua_senha_muito_segura_aqui'
docker-compose up -d
```

#### Opção 3 - Linha de comando
```bash
ADMIN_PASSWORD='sua_senha_muito_segura_aqui' docker-compose up -d
```

**⚠️  IMPORTANTE**: 
- Use uma senha forte com pelo menos 8 caracteres
- A senha é obrigatória para o deploy funcionar
- Nunca commite a senha no repositório

### Configurações de segurança

O sistema já inclui:
- ✅ HTTPS forçado
- ✅ Headers de segurança
- ✅ CSRF protection
- ✅ Configurações de SSL/TLS

## 🛠️ Manutenção

### Backup do banco

```bash
# Backup
docker-compose exec db pg_dump -U cadeia_user cadeia_dominial > backup_$(date +%Y%m%d).sql

# Restore
docker-compose exec -T db psql -U cadeia_user cadeia_dominial < backup.sql
```

### Atualizar sistema

```bash
# Parar containers
docker-compose down

# Atualizar código
git pull origin main

# Rebuild e reiniciar
docker-compose build --no-cache
docker-compose up -d
```

### Limpar dados (se necessário)

```bash
# Limpar dados de teste
docker-compose exec web python manage.py limpar_dados_teste

# Limpar cartórios
docker-compose exec web python manage.py limpar_cartorios
```

## 📞 Suporte

### Problemas comuns

1. **Erro de permissão**: `chmod +x scripts/init.sh`
2. **Porta ocupada**: Verificar se porta 80/443 está livre
3. **SSL não funciona**: Verificar DNS e certificado
4. **Banco não conecta**: Verificar variáveis de ambiente

### Logs de erro

```bash
# Ver logs detalhados
docker-compose logs web | grep ERROR
docker-compose logs nginx | grep error
```

## 🎯 Resultado Final

Após o deploy automatizado, você terá:

- 🌐 **Sistema web funcionando** em HTTPS
- 👤 **Usuário admin** pronto para uso
- 🏞️ **620+ terras indígenas** importadas
- 📋 **Tipos padrão** configurados
- 🔒 **Segurança** configurada
- 📊 **Monitoramento** disponível

**Acesso imediato**: `https://cadeiadominial.com.br` (ou IP do servidor) 