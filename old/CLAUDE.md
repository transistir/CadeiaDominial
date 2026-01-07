# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Cadeia Dominial** - A Django 5.2 web application for managing and visualizing chains of land ownership ("cadeia dominial") for Indigenous Lands (Terras Indígenas) in Brazil. The system tracks properties, documents (matrículas/transcrições), and their historical transactions through an interactive tree visualization.

## Development Commands

```bash
# Setup and run development server
python -m venv venv && source venv/bin/activate  # Create venv
pip install -r requirements.txt                  # Install dependencies
python manage.py migrate                         # Run migrations
python manage.py createsuperuser                 # Create admin user
python manage.py criar_tipos_documento           # Create document types
python manage.py criar_tipos_lancamento          # Create transaction types
python manage.py runserver                       # Start dev server (localhost:8000)

# Production (uses settings_prod.py with PostgreSQL)
export DJANGO_SETTINGS_MODULE=cadeia_dominial.settings_prod
python manage.py collectstatic --noinput

# Run tests
python manage.py test

# Create migrations
python manage.py makemigrations

# Docker development
docker-compose -f docker-compose.dev.yml up -d
docker-compose up -d  # Production stack with nginx/postgres

# Management commands
python manage.py importar_terras_indigenas       # Import indigenous lands
python manage.py importar_cartorios_estado <UF>  # Import registry offices
```

## Architecture

### Project Structure
```
cadeia_dominial/       # Django project settings (settings.py, settings_prod.py, urls.py)
dominial/              # Main Django app with all models/views
├── models/            # Data models organized by domain
├── views/             # Views organized by feature (tis_views, documento_views, etc.)
├── forms/             # Django forms
├── services/          # Business logic (cartorio_service, lancamento_service, etc.)
├── management/commands/  # Custom management commands
└── tests/             # Test files
templates/             # HTML templates
static/                # CSS, JS, images
scripts/               # Automation scripts
```

### Key Models
- **TIs**: Indigenous Lands (linked to TerraIndigenaReferencia for reference data)
- **Imovel**: Properties belonging to TIs, linked to Cartorios
- **Documento**: Property documents (matrícula/transcrição) - unique by (numero, cartorio)
- **Lancamento**: Transactions/annotations on documents
- **LancamentoPessoa**: Links between Lancamentos and Pessoas (owners)
- **Cartorios**: Brazilian registry offices (Cartório de Registro de Imóveis)

### URL Patterns
- `/admin/` - Django admin
- `/dominial/` - Main application routes
  - `/dominial/tis/<id>/` - Indigenous land detail
  - `/dominial/tis/<id>/imovel/<id>/cadeia-dominial/` - Chain visualization (D3.js)
  - `/dominial/tis/<id>/imovel/<id>/novo-documento/` - Add document
  - `/dominial/tis/<id>/imovel/<id>/novo-lancamento/` - Add transaction

### Settings
- **Development**: `cadeia_dominial.settings` (SQLite, DEBUG=True)
- **Production**: `cadeia_dominial.settings_prod` (PostgreSQL, DEBUG=False, env vars)
- Feature flags: `DUPLICATA_VERIFICACAO_ENABLED` for duplicate checking

### Key Services
- `dominial/services/cartorio_verificacao_service.py` - Cartório validation
- `dominial/services/lancamento_heranca_service.py` - Inheritance transaction logic
- `dominial/services/cri_service.py` - CRI (current registry office) tracking
- `dominial/services/regra_petrea_service.py` - Petrea rules processing

## Dependencies

- **Django 5.2.3** with django-extensions, django-autocomplete-light
- **Database**: SQLite (dev), PostgreSQL (prod) with psycopg2-binary
- **Frontend**: Vanilla JavaScript, D3.js for tree visualization
- **PDF**: WeasyPrint for exports
- **Server**: Gunicorn + Nginx (Docker)

## Commit Convention

Follow Conventional Commits with Portuguese descriptions:

```
<tipo>(<escopo>): <descrição>

Tipos: feat, fix, docs, style, refactor, perf, test, chore
Escopos: auth, api, ui, models, admin, migrations, docs, test, ci, deps

Exemplos:
feat(ui): adiciona zoom na visualização da árvore
fix(api): corrige erro de validação em documentos
refactor(models): reorganiza estrutura de documentos
```

## Key Patterns

1. **Document Uniqueness**: Documento uses `unique_together = ('numero', 'cartorio')` - matrículas must be unique per cartório
2. **Cascade Deletion**: Imovel deletion cascades to Documentos and Lançamentos
3. **Autocomplete Views**: Use DAL (Django Autocomplete Light) for searchable selects
4. **Management Commands**: Use `python manage.py <command>` for data imports and utilities
5. **Admin Customization**: Admin site header customized to "Sistema de Cadeia Dominial"

## Feature Flags

- `DUPLICATA_VERIFICACAO_ENABLED`: Toggle duplicate document verification
