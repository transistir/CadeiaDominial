# Project Overview

## Sistema de Cadeia Dominial

**Version:** Beta 1.0.0
**Status:** Production-ready
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

## Project Structure

```
CadeiaDominial/
├── cadeia_dominial/     # Django project configuration
├── dominial/            # Main application
│   ├── models/          # Database models (7 modules)
│   ├── views/           # View controllers (7 modules)
│   ├── services/        # Business logic (30+ services)
│   ├── forms/           # Form definitions
│   ├── utils/           # Utility functions
│   └── management/      # Custom commands
├── templates/           # HTML templates (40+)
├── static/              # CSS, JavaScript, images
├── docs/                # Documentation
├── tests_scripts/       # Testing scripts
└── context/             # This documentation folder
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

- ✅ Core features implemented and tested
- ✅ Chain visualization working (tree and table views)
- ✅ PDF and Excel export functional
- ✅ Duplicate detection implemented
- ✅ Admin interface customized
- ✅ Production deployment ready
- ⚠️ Beta release - ongoing refinements
- 🔄 GeoDjango integration planned (spatial features)

## Documentation

Comprehensive documentation available in `/docs` directory:
- User guides
- API documentation
- Development guides
- Deployment instructions
- Feature documentation

## Contact and Support

Refer to project documentation in `/docs` for detailed information on all features and workflows.
