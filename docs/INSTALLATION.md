# 📦 Guia de Instalação

Guia completo para instalar e configurar o Sistema de Cadeia Dominial.

---

## 📋 Pré-requisitos

### Requisitos Obrigatórios
- **Python 3.8+** (recomendado Python 3.11 ou superior)
- **Git** para clonar o repositório
- **4 GB RAM** mínimo (8 GB recomendado)
- **500 MB** de espaço em disco

### Requisitos Opcionais
- **PostgreSQL 12+** para produção (desenvolvimento usa SQLite)
- **Docker** e **Docker Compose** para deployment containerizado

---

## ⚡ Método 1: Usando uv (Recomendado)

[uv](https://github.com/astral-sh/uv) é um instalador de pacotes Python extremamente rápido (10-100x mais rápido que pip).

### Por que usar uv?
- ⚡ **Extremamente rápido** - Instalação de dependências em segundos
- 🔒 **Confiável** - Lock files automáticos
- 🎯 **Simples** - Comandos intuitivos
- 🔄 **Compatível** - Funciona com pip, venv, e requirements.txt

### 1. Instale o uv

**Linux / macOS:**
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**Windows (PowerShell):**
```powershell
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

**Alternativa (via pip):**
```bash
pip install uv
```

### 2. Clone o Repositório

```bash
git clone https://github.com/transistir/CadeiaDominial.git
cd CadeiaDominial
```

### 3. Crie o Ambiente Virtual e Instale Dependências

```bash
# Crie o ambiente virtual
uv venv

# Ative o ambiente virtual
source .venv/bin/activate  # Linux/macOS
# .venv\Scripts\activate   # Windows

# Instale as dependências (super rápido!)
uv pip install -r requirements.txt

# Opcional: instale dependências de teste
uv pip install -r requirements-test.txt
```

### 4. Configure as Variáveis de Ambiente

```bash
# Copie o arquivo de exemplo
cp env.example .env

# Edite o arquivo .env
nano .env  # ou seu editor preferido
```

**Variáveis obrigatórias:**
```bash
# Segurança
SECRET_KEY=sua-chave-secreta-aqui-use-50-caracteres-aleatorios
ADMIN_PASSWORD=senha-forte-para-admin

# Ambiente
DEBUG=True  # False em produção

# Database (opcional - SQLite é padrão em desenvolvimento)
# DB_NAME=cadeia_dominial
# DB_USER=postgres
# DB_PASSWORD=sua-senha
# DB_HOST=localhost
# DB_PORT=5432
```

**Dica:** Para gerar uma SECRET_KEY segura:
```bash
uv run python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

### 5. Inicialize o Banco de Dados

```bash
# Execute as migrações
uv run python manage.py migrate

# Crie os tipos de documento (Matrícula, Transcrição)
uv run python manage.py criar_tipos_documento

# Crie os tipos de lançamento (Registro, Averbação, etc.)
uv run python manage.py criar_tipos_lancamento

# Crie o superusuário (admin)
uv run python manage.py createsuperuser
```

### 6. Inicie o Servidor

```bash
uv run python manage.py runserver
```

**Pronto!** Acesse: http://localhost:8000

Use as credenciais do superusuário criado para fazer login.

---

## 🐍 Método 2: Usando pip Tradicional

Se preferir usar o pip tradicional ao invés do uv:

### 1. Clone o Repositório

```bash
git clone https://github.com/transistir/CadeiaDominial.git
cd CadeiaDominial
```

### 2. Crie um Ambiente Virtual

```bash
# Crie o ambiente virtual
python -m venv venv

# Ative o ambiente virtual
source venv/bin/activate  # Linux/macOS
# venv\Scripts\activate   # Windows
```

### 3. Instale as Dependências

```bash
# Atualize pip
pip install --upgrade pip

# Instale as dependências
pip install -r requirements.txt

# Opcional: instale dependências de teste
pip install -r requirements-test.txt
```

### 4. Configure o Ambiente

```bash
cp env.example .env
# Edite .env conforme necessário (veja seção de configuração acima)
```

### 5. Inicialize o Banco de Dados

```bash
# Execute as migrações
uv run python manage.py migrate

# Crie os tipos de documento
uv run python manage.py criar_tipos_documento

# Crie os tipos de lançamento
uv run python manage.py criar_tipos_lancamento

# Crie o superusuário
uv run python manage.py createsuperuser
```

### 6. Inicie o Servidor

```bash
uv run python manage.py runserver
```

---

## 🐳 Método 3: Usando Docker

Para instalação com Docker, consulte:
- **[README_DOCKER.md](../README_DOCKER.md)** - Configuração Docker completa
- **[deploy/README.md](deploy/README.md)** - Guias de deployment

**Quick Start com Docker:**
```bash
# Clone o repositório
git clone https://github.com/transistir/CadeiaDominial.git
cd CadeiaDominial

# Configure variáveis de ambiente
cp env.example .env
# Edite .env

# Inicie com Docker Compose
docker-compose up -d

# Execute migrações
docker-compose exec web python manage.py migrate

# Crie superusuário
docker-compose exec web python manage.py createsuperuser
```

Acesse: http://localhost:8000

---

## 🔧 Configuração Avançada

### PostgreSQL (Produção)

Para ambientes de produção, recomendamos PostgreSQL:

**1. Instale o PostgreSQL:**
```bash
# Ubuntu/Debian
sudo apt install postgresql postgresql-contrib

# macOS (Homebrew)
brew install postgresql

# Windows
# Baixe de https://www.postgresql.org/download/windows/
```

**2. Crie o banco de dados:**
```bash
sudo -u postgres psql
```
```sql
CREATE DATABASE cadeia_dominial;
CREATE USER cadeia_user WITH PASSWORD 'sua-senha-forte';
ALTER ROLE cadeia_user SET client_encoding TO 'utf8';
ALTER ROLE cadeia_user SET default_transaction_isolation TO 'read committed';
ALTER ROLE cadeia_user SET timezone TO 'America/Sao_Paulo';
GRANT ALL PRIVILEGES ON DATABASE cadeia_dominial TO cadeia_user;
\q
```

**3. Configure o .env:**
```bash
DB_ENGINE=postgresql
DB_NAME=cadeia_dominial
DB_USER=cadeia_user
DB_PASSWORD=sua-senha-forte
DB_HOST=localhost
DB_PORT=5432
```

**4. Instale o driver PostgreSQL:**
```bash
uv pip install psycopg2-binary
```

### GeoDjango (Funcionalidades Geoespaciais)

Se precisar de funcionalidades geoespaciais:

**Ubuntu/Debian:**
```bash
sudo apt install gdal-bin libgdal-dev
sudo apt install binutils libproj-dev
```

**macOS:**
```bash
brew install gdal
brew install proj
```

### Arquivos Estáticos (Produção)

Para servir arquivos estáticos em produção:

```bash
# Colete arquivos estáticos
uv run python manage.py collectstatic --noinput
```

---

## 🧪 Verificação da Instalação

### Execute os Testes

```bash
# Execute todos os testes
uv run python manage.py test

# Ou use pytest
uv run pytest
```

### Verifique os Comandos Personalizados

```bash
# Liste os comandos disponíveis
uv run python manage.py help

# Comandos personalizados devem aparecer:
# - criar_tipos_documento
# - criar_tipos_lancamento
```

### Acesse a Interface Admin

1. Inicie o servidor: `uv run python manage.py runserver`
2. Acesse: http://localhost:8000/admin
3. Login com credenciais do superusuário
4. Verifique se todos os modelos aparecem

---

## 🔍 Troubleshooting

### Erro: "ModuleNotFoundError: No module named 'django'"

**Solução:** Ative o ambiente virtual
```bash
source .venv/bin/activate  # Linux/macOS
.venv\Scripts\activate     # Windows
```

### Erro: "django.db.utils.OperationalError: no such table"

**Solução:** Execute as migrações
```bash
uv run python manage.py migrate
```

### Erro: "Secret key must not be empty"

**Solução:** Configure SECRET_KEY no arquivo .env
```bash
cp env.example .env
# Edite .env e adicione SECRET_KEY
```

### Erro: "Port 8000 is already in use"

**Solução:** Use outra porta ou mate o processo
```bash
# Use outra porta
uv run python manage.py runserver 8001

# Ou mate o processo na porta 8000 (Linux/macOS)
lsof -ti:8000 | xargs kill -9

# Windows
netstat -ano | findstr :8000
taskkill /PID <PID> /F
```

### Erro: "Permission denied" ao instalar uv

**Solução:** Use sudo ou instale via pip
```bash
# Linux com sudo
sudo curl -LsSf https://astral.sh/uv/install.sh | sh

# Ou via pip
pip install --user uv
```

### Erro de codificação (UnicodeDecodeError)

**Solução:** Configure a codificação UTF-8
```bash
# Linux/macOS (adicione ao ~/.bashrc ou ~/.zshrc)
export LANG=pt_BR.UTF-8
export LC_ALL=pt_BR.UTF-8

# Windows (PowerShell)
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
```

### Dependências faltando (erro de import)

**Solução:** Reinstale as dependências
```bash
uv pip install -r requirements.txt --force-reinstall
```

---

## 📱 Notas Específicas por Plataforma

### Linux (Ubuntu/Debian)

Pacotes adicionais que podem ser necessários:
```bash
sudo apt update
sudo apt install python3-dev python3-pip python3-venv
sudo apt install build-essential libpq-dev
```

### macOS

Use Homebrew para instalar Python:
```bash
brew install python@3.11
```

### Windows

**Recomendações:**
- Use **PowerShell** como administrador
- Considere usar **Windows Terminal**
- Instale **Git for Windows** para ter git bash

**Python no PATH:**
- Durante a instalação do Python, marque "Add Python to PATH"

---

## 🚀 Próximos Passos

Após a instalação bem-sucedida:

1. **Leia o Guia do Usuário:** [USER_GUIDE.md](USER_GUIDE.md)
2. **Configure dados iniciais:** Cadastre TIs, Cartórios, etc.
3. **Explore a documentação:** [docs/README.md](README.md)
4. **Para desenvolvimento:** [DEVELOPMENT.md](DEVELOPMENT.md)

---

## 🆘 Precisa de Ajuda?

- **Documentação:** [docs/README.md](README.md)
- **Issues:** [GitHub Issues](https://github.com/transistir/CadeiaDominial/issues)
- **Deploy em produção:** [deploy/CHECKLIST_PRODUCAO.md](deploy/CHECKLIST_PRODUCAO.md)

---

**[⬅️ Voltar ao README principal](../README.md)**
