# Sistema de Cadeia Dominial

![Version](https://img.shields.io/badge/version-1.0.0--beta-blue)
![Python](https://img.shields.io/badge/python-3.8%2B-blue)
![Django](https://img.shields.io/badge/django-5.2.3-green)
![License](https://img.shields.io/badge/license-MIT-green)

Sistema web para gestão e visualização de cadeias dominiais de terras indígenas, desenvolvido em Django.

![Sistema de Cadeia Dominial](printpage.png)

---

## ✨ Principais Funcionalidades

- 🌳 **Visualização Interativa em Árvore** - Diagrama D3.js com zoom e pan
- 📊 **Gestão Completa** - TIs, Imóveis, Documentos (Matrículas/Transcrições) e Lançamentos
- 🔍 **Detecção de Duplicatas** - Prevenção automática de dados duplicados
- 🔗 **Rastreamento de Cadeia** - Histórico completo desde a origem até o presente
- 📤 **Exportação de Dados** - Excel, PDF e JSON
- 🏛️ **Base de Cartórios** - Gestão de Cartórios de Registro de Imóveis (CRI)
- 🎯 **Interface Moderna** - Design responsivo e intuitivo

---

## 🚀 Quick Start

### 1. Instale o uv (instalador Python ultra-rápido)

```bash
# Linux/macOS
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows (PowerShell)
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

### 2. Clone e configure

```bash
git clone https://github.com/transistir/CadeiaDominial.git
cd CadeiaDominial

# Crie ambiente e instale dependências
uv venv
source .venv/bin/activate  # Linux/macOS - Windows: .venv\Scripts\activate
uv pip install -r requirements.txt

# Configure ambiente
cp env.example .env
# Edite .env: configure SECRET_KEY e ADMIN_PASSWORD
```

### 3. Inicialize o banco de dados

```bash
uv run python manage.py migrate
uv run python manage.py criar_tipos_documento
uv run python manage.py criar_tipos_lancamento
uv run python manage.py createsuperuser
```

### 4. Inicie o servidor

```bash
uv run python manage.py runserver
```

**🎉 Pronto!** Acesse: http://localhost:8000

---

## 📚 Documentação

### Para Usuários
- **[Guia de Instalação](docs/INSTALLATION.md)** - Instruções detalhadas de instalação e configuração
- **[Guia do Usuário](docs/USER_GUIDE.md)** - Como usar o sistema completo
- **[Documentação Completa](docs/README.md)** - Índice de toda documentação

### Para Desenvolvedores
- **[Guia de Desenvolvimento](docs/DEVELOPMENT.md)** - Setup de dev, testes e debugging
- **[Arquitetura do Sistema](AGENTS.md)** - Arquitetura detalhada e padrões de código
- **[Roadmap](docs/ROADMAP.md)** - Planejamento de versões futuras
- **[Como Contribuir](CONTRIBUTING.md)** - Guia para contribuidores

### Deploy e Produção
- **[Deploy com Docker](README_DOCKER.md)** - Configuração Docker completa
- **[Checklist de Produção](docs/deploy/CHECKLIST_PRODUCAO.md)** - Guia para deploy em produção

---

## 🛠️ Tecnologias

**Backend:**
- Django 5.2.3
- Python 3.8+
- PostgreSQL (produção) / SQLite (desenvolvimento)

**Frontend:**
- HTML5, CSS3, JavaScript
- Bootstrap 5
- D3.js (visualização em árvore)
- django-autocomplete-light

**Outros:**
- WeasyPrint (geração de PDF)
- openpyxl (exportação Excel)

---

## 🧪 Executando Testes

```bash
# Instale dependências de teste
uv pip install -r requirements-test.txt

# Execute todos os testes
uv run pytest

# Com relatório de cobertura
uv run pytest --cov=dominial --cov-report=html

# Ou use Django test runner
uv run python manage.py test
```

Para mais detalhes sobre testes, veja [Guia de Desenvolvimento](docs/DEVELOPMENT.md).

---

## 🤝 Como Contribuir

Contribuições são bem-vindas! Por favor, leia o [Guia de Contribuição](CONTRIBUTING.md) para detalhes sobre:

- Como reportar bugs
- Como sugerir funcionalidades
- Processo de desenvolvimento
- Padrões de código
- Processo de Pull Request

**Issues boas para começar:**
- Procure labels `good first issue` e `help wanted`
- [Veja as issues abertas](https://github.com/transistir/CadeiaDominial/issues)

---

## 📋 Versão Atual: Beta 1.0.0

Esta é a primeira versão beta, disponível para testes com clientes.

**Status:** Em testes | **Próxima versão:** 1.0.0 (Março 2025)

Veja o [Roadmap](docs/ROADMAP.md) completo para funcionalidades planejadas.

---

## 📄 Licença

Este projeto está sob a licença MIT. Veja o arquivo [LICENSE](LICENSE) para mais detalhes.

---

## 📞 Suporte

- **Documentação:** [docs/README.md](docs/README.md)
- **Issues:** [GitHub Issues](https://github.com/transistir/CadeiaDominial/issues)
- **Discussões:** [GitHub Discussions](https://github.com/transistir/CadeiaDominial/discussions)

---

<div align="center">

**Desenvolvido pela equipe Transistir**

[Documentação](docs/README.md) • [Contribuir](CONTRIBUTING.md) • [Roadmap](docs/ROADMAP.md) • [Changelog](docs/ROADMAP.md#-changelog)

</div>
