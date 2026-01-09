# Project Overview

## ⚠️ LEGACY SYSTEM NOTICE

> **This documentation describes the LEGACY Django-based system.**
>
> The Django application code has been moved to the `old/` directory as part of the v2 branch cleanup (PR #11).
>
> **New Architecture:** The system is being migrated to a modern TypeScript stack:
>
> - **Frontend:** React + Vite on Cloudflare Pages
> - **Backend:** Hono on Cloudflare Workers
> - **Database:** Cloudflare D1 (SQLite)
> - **Docs:** See [../MIGRATION_GUIDE.md](../MIGRATION_GUIDE.md) and [../ARCHITECTURE_DECISIONS.md](../ARCHITECTURE_DECISIONS.md)
>
> Refer to the [legacy-django](:docs/legacy-django/) documentation for understanding the original Django implementation during the migration process.

---

## Sistema de Cadeia Dominial (Legacy Django)

**Version:** Beta 1.0.0
**Status:** Legacy - Moved to `old/` directory
**License:** Private/Proprietary

## Purpose

Sistema de Cadeia Dominial is a specialized web-based application for managing and visualizing property ownership chains (cadeia dominial) of indigenous lands in Brazil. The system tracks the complete history of property ownership from origin to current state, enabling legal and administrative analysis of land titles.

## Core Problem Solved

Indigenous land rights in Brazil require careful documentation of property ownership history. This system:

- Tracks property ownership chains from historical origins to current state
- Manages complex relationships between documents, properties, and transactions
- Visualizes ownership chains for legal analysis
- Detects duplicate registrations across multiple notary offices (cartórios)
- Generates comprehensive reports in multiple formats (PDF, Excel)

## Technology Stack

### Backend

- **Framework:** Django 5.2.3
- **Language:** Python 3.8+
- **Database:** SQLite (development), PostgreSQL (production)
- **Server:** Gunicorn + Nginx
- **Geospatial:** GeoDjango with PostGIS support

### Frontend

- **Templates:** Django Templates (Jinja2-style)
- **CSS Framework:** Bootstrap 5.1.3
- **JavaScript:** Vanilla JS (no jQuery)
- **Visualization:** D3.js for tree diagrams

### Key Libraries

- **django-autocomplete-light** (3.12.1) - Smart autocomplete widgets
- **WeasyPrint** (62.2) - PDF generation
- **openpyxl** (3.1.5) - Excel export
- **requests** (2.31.0) - External API integration
- **python-decouple** (3.8) - Configuration management
- **whitenoise** (6.6.0) - Static file serving

## Target Users

- Legal professionals analyzing indigenous land claims
- Government administrators managing indigenous territories
- Researchers studying property ownership history
- FUNAI (Fundação Nacional do Índio) personnel

## Key Terminology

- **Cadeia Dominial:** Property ownership chain/title chain
- **Terra Indígena (TI):** Indigenous land/territory
- **Imóvel:** Property/real estate
- **Matrícula:** Property registration document
- **Transcrição:** Historical transcription (pre-1976)
- **Lançamento:** Registration/transaction entry
- **Averbação:** Annotation (non-ownership changes)
- **Registro:** Registration (ownership changes)
- **Cartório (CRI):** Notary office / Property Registry Office
- **Transmitente:** Seller/transferor
- **Adquirente:** Buyer/acquirer
- **Tronco Principal:** Main property chain
- **Tronco Secundário:** Secondary/branch chain

## Project Structure (Legacy)

The legacy Django codebase has been moved to `old/` directory. The structure below represents the organization before the v2 cleanup.

```
old/                             # Legacy Django application (moved in PR #11)
├── cadeia_dominial/             # Django project configuration
├── dominial/                    # Main application
│   ├── models/                  # Database models (7 modules)
│   ├── views/                   # View controllers (7 modules)
│   ├── services/                # Business logic (30+ services)
│   ├── forms/                   # Form definitions
│   ├── utils/                   # Utility functions
│   └── management/              # Custom commands
├── templates/                   # HTML templates (40+)
├── static/                      # CSS, JavaScript, images
├── docs/                        # Original documentation (now in docs/legacy-django/)
├── tests_scripts/               # Testing scripts
└── migrations/                  # Database migrations

docs/legacy-django/              # Legacy system documentation
├── 01-project-overview.md       # This file
├── 02-architecture.md
├── 03-database-models.md
├── 04-services.md               # Updated to reflect service cleanup
├── 05-views-urls-api.md
├── 06-frontend.md
├── 07-core-features-workflows.md
└── 08-configuration-deployment.md
```

## Data Flow Overview

1. **Data Input**
   - Indigenous lands (TIs) registered
   - Properties (imóveis) linked to TIs
   - Documents (matrículas/transcrições) created for properties
   - Transactions (lançamentos) recorded on documents

2. **Processing**
   - Hierarchy calculation (main and secondary chains)
   - Origin detection (automatic and manual)
   - Duplicate verification
   - Validation and integrity checks

3. **Output**
   - Interactive tree visualization (D3.js)
   - Structured table view
   - PDF reports
   - Excel exports
   - Admin interface for data management

## Development Approach

- **Service Layer Pattern:** Business logic separated into specialized services
- **Domain-Driven Design:** Code organized by business domains
- **Component-Based Templates:** Reusable template fragments
- **Test-Driven Development:** Comprehensive test suite
- **Docker Support:** Containerized deployment
- **Environment-Based Configuration:** Dev/staging/production settings

## Deployment Options

- **Development:** SQLite database, Django dev server
- **Production:** PostgreSQL, Gunicorn, Nginx, Docker
- **Platform:** Designed for Linux servers (Ubuntu/Debian)
- **Cloud-Ready:** Docker Compose configuration included

## Current Status

### Django Application (Legacy)

- ✅ Core features implemented and tested
- ✅ Chain visualization working (tree and table views)
- ✅ PDF and Excel export functional
- ✅ Duplicate detection implemented
- ✅ Admin interface customized
- ✅ Production deployment ready
- ⚠️ Moved to `old/` directory (PR #11, v2 branch)
- 🔄 Superseded by TypeScript migration

### TypeScript Migration (Current)

See [../MIGRATION_GUIDE.md](../MIGRATION_GUIDE.md) for the new architecture:

- React + Vite frontend
- Hono API on Cloudflare Workers
- D1 database (SQLite at the edge)
- Full-stack TypeScript

## Documentation

### Legacy Django Documentation (This Directory)

- `01-project-overview.md` - This file
- `02-architecture.md` - Django application architecture
- `03-database-models.md` - PostgreSQL/SQLite schema
- `04-services.md` - Business logic layer (30+ services)
- `05-views-urls-api.md` - HTTP layer and routing
- `06-frontend.md` - Django Templates and D3.js
- `07-core-features-workflows.md` - Feature documentation
- `08-configuration-deployment.md` - Deployment guides

### Migration Documentation

- `../MIGRATION_GUIDE.md` - TypeScript migration guide
- `../ARCHITECTURE_DECISIONS.md` - Architecture decisions (ADRs)
- `../MIGRATION_CHECKLIST.md` - Migration checklist

## References

**For historical reference and migration purposes only.**

The legacy Django code remains available in the `old/` directory for:

- Understanding the original business logic during migration
- Referencing complex algorithms (hierarchy calculation, origin detection)
- Validating the new TypeScript implementation
- Data migration from PostgreSQL to D1
