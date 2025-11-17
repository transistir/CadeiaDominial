# Sistema de Cadeia Dominial - Developer Documentation

## Quick Start for AI Coding Agents

This documentation provides comprehensive context about the **Sistema de Cadeia Dominial** - a Django web application for managing and visualizing property ownership chains (cadeia dominial) of indigenous lands in Brazil.

**Version:** Beta 1.0.0
**Framework:** Django 5.2.3
**Language:** Python 3.8+
**Database:** PostgreSQL (production) / SQLite (development)

---

## 📚 Complete Documentation Index

### Core Documentation

1. **[Project Overview](context/01-project-overview.md)**
   - Purpose and goals
   - Technology stack
   - Key terminology
   - Project structure
   - Current status and features

2. **[Architecture and Design Patterns](context/02-architecture.md)**
   - Model-View-Service architecture
   - Service Layer Pattern
   - Domain-Driven Design
   - Directory structure
   - Layer responsibilities
   - Code organization principles

3. **[Database Models and Relationships](context/03-database-models.md)**
   - 13 core models across 7 modules
   - Entity relationship diagrams
   - Model descriptions and fields
   - Key relationships and constraints
   - Data integrity rules
   - Common query patterns

4. **[Services and Business Logic](context/04-services.md)**
   - 30+ specialized service classes
   - Hierarchy and chain services
   - Transaction services
   - Document services
   - Service dependencies
   - Common service patterns

5. **[Views, URLs, and API](context/05-views-urls-api.md)**
   - 94 URL patterns
   - 7 view modules
   - AJAX endpoints
   - Autocomplete views
   - Request/response handling
   - Common view patterns

6. **[Frontend: Templates, JavaScript, CSS](context/06-frontend.md)**
   - 40+ Django templates
   - Component-based architecture
   - D3.js tree visualization
   - 7 JavaScript files
   - 26 CSS files
   - Bootstrap 5 integration

7. **[Core Features and Workflows](context/07-core-features-workflows.md)**
   - 10 major features
   - User workflows
   - Data processing
   - Duplicate detection
   - Export functionality
   - Error handling

8. **[Configuration and Deployment](context/08-configuration-deployment.md)**
   - Environment configuration
   - Dependencies
   - Development setup
   - Docker deployment
   - Production deployment
   - Monitoring and maintenance

---

## 🎯 Quick Reference

### Project Purpose

The system tracks the complete history of property ownership (cadeia dominial) for indigenous lands, enabling legal analysis of land titles. It manages:
- Indigenous territories (TIs)
- Properties (imóveis) within TIs
- Property documents (matrículas and transcrições)
- Transactions (lançamentos) on documents
- Complete ownership chains from origin to current state

### Key Business Concepts

- **Cadeia Dominial:** Property ownership chain/title chain
- **Terra Indígena (TI):** Indigenous land/territory
- **Imóvel:** Property/real estate
- **Matrícula:** Modern property registration (post-1976)
- **Transcrição:** Historical transcription (pre-1976)
- **Lançamento:** Transaction entry (Averbação, Registro, or Início de Matrícula)
- **Cartório (CRI):** Notary office / Property Registry Office
- **Transmitente:** Seller/transferor
- **Adquirente:** Buyer/acquirer

### Data Model Hierarchy

```
TI (Indigenous Land)
  └─ Imovel (Property)
      └─ Documento (Document)
          └─ Lancamento (Transaction)
              └─ documento_origem → Documento (origin link)
```

This chain structure allows traversing backwards through ownership history.

---

## 🗂️ File Location Quick Reference

### Models
- **Location:** `dominial/models/`
- **Files:** `tis_models.py`, `pessoa_models.py`, `imovel_models.py`, `documento_models.py`, `lancamento_models.py`, `alteracao_models.py`, `documento_importado_models.py`
- **Key Models:** `TIs`, `Pessoas`, `Imovel`, `Cartorios`, `Documento`, `Lancamento`

### Services (Business Logic)
- **Location:** `dominial/services/`
- **Key Services:**
  - `hierarquia_arvore_service.py` - Tree building (351 lines)
  - `cadeia_dominial_tabela_service.py` - Table generation (554 lines)
  - `cadeia_completa_service.py` - Complete chain (423 lines)
  - `lancamento_criacao_service.py` - Transaction creation (423 lines)
  - `lancamento_origem_service.py` - Origin detection (517 lines)
  - `lancamento_campos_service.py` - Field processing (352 lines)
  - `lancamento_duplicata_service.py` - Duplicate detection (252 lines)

### Views
- **Location:** `dominial/views/`
- **Files:**
  - `tis_views.py` - Indigenous land views
  - `imovel_views.py` - Property views
  - `documento_views.py` - Document views
  - `lancamento_views.py` - Transaction views (34KB - most complex)
  - `cadeia_dominial_views.py` - Chain visualization (35KB)
  - `api_views.py` - AJAX/REST endpoints
  - `autocomplete_views.py` - Autocomplete endpoints

### Templates
- **Location:** `templates/dominial/`
- **Key Templates:**
  - `cadeia_dominial_d3.html` - D3.js tree visualization
  - `cadeia_dominial_tabela.html` - Table view
  - `lancamento_form.html` - Transaction form
  - `components/` - Reusable template fragments

### Static Files
- **JavaScript:** `static/dominial/js/`
  - `cadeia_dominial_d3.js` - D3 tree (600+ lines)
  - `lancamento_form.js` - Form behavior (400+ lines)
  - `cadeia_dominial_tabela.js` - Table interactivity
- **CSS:** `static/dominial/css/`
  - 26 feature-specific stylesheets

### URLs
- **Main Routing:** `dominial/urls.py` (94 URL patterns)
- **Project Config:** `cadeia_dominial/urls.py`

---

## 🔑 Key Technical Decisions

### Architecture Choices

1. **Service Layer Pattern**
   - Business logic separated from views
   - Reusable across different views
   - Easier to test and maintain
   - See: `context/02-architecture.md`

2. **Domain-Driven Design**
   - Code organized by business domains
   - Models, views, services grouped by entity
   - Clear module boundaries
   - See: `context/02-architecture.md`

3. **Component-Based Templates**
   - Reusable template fragments in `components/`
   - DRY principle for forms
   - Easier maintenance
   - See: `context/06-frontend.md`

### Data Structure Decisions

1. **Documento-Centric Chain**
   - Documents are the core entity
   - Lançamentos link to origin documents via `documento_origem`
   - Allows traversing complete ownership history
   - See: `context/03-database-models.md`

2. **Dynamic Field Requirements**
   - Transaction types have different required fields
   - `LancamentoTipo` model defines requirements
   - `LancamentoCamposService` enforces dynamically
   - See: `context/04-services.md` and `context/03-database-models.md`

3. **Multiple Origin Support**
   - Documents can have multiple potential origins
   - `OrigemFimCadeia` model tracks per-origin end-of-chain info
   - Session storage for user-selected origins
   - See: `context/03-database-models.md` and `context/07-core-features-workflows.md`

---

## 🚀 Common Development Tasks

### Adding a New Field to Lancamento

1. **Update Model:** `dominial/models/lancamento_models.py:43`
2. **Create Migration:** `python manage.py makemigrations`
3. **Update Form:** `dominial/forms/lancamento_forms.py`
4. **Update Service:** `dominial/services/lancamento_campos_service.py`
5. **Update Template:** `templates/dominial/components/_lancamento_*_form.html`
6. **Update Validation:** `dominial/services/lancamento_validacao_service.py`
7. **Apply Migration:** `python manage.py migrate`

### Adding a New Service

1. **Create File:** `dominial/services/my_new_service.py`
2. **Define Class:**
   ```python
   class MyNewService:
       @staticmethod
       def do_something(params):
           # Business logic
           return result
   ```
3. **Use in View:** Import and call from view
4. **Add Tests:** `dominial/tests/test_my_new_service.py`

### Adding a New View

1. **Create View:** `dominial/views/my_views.py`
2. **Add URL Pattern:** `dominial/urls.py`
3. **Create Template:** `templates/dominial/my_template.html`
4. **Add CSS (optional):** `static/dominial/css/my_template.css`
5. **Add JavaScript (optional):** `static/dominial/js/my_feature.js`

### Adding a New API Endpoint

1. **Create View:** `dominial/views/api_views.py`
2. **Add URL:** `dominial/urls.py` (prefix with `api/`)
3. **Return JSON:** Use `JsonResponse`
4. **Handle CSRF:** Include CSRF token for POST
5. **Document in:** `context/05-views-urls-api.md`

---

## 🧪 Testing

### Run Tests
```bash
python manage.py test
```

### Test Files
- **Location:** `dominial/tests/`
- **Key Tests:**
  - `test_documento_lancamento.py` (23KB)
  - `test_duplicata_verificacao.py` (14KB)
  - `test_fase2_duplicata_integracao.py` (13KB)

### Test Coverage
```bash
coverage run --source='.' manage.py test
coverage report
```

---

## 🐛 Debugging Tips

### Enable Debug Toolbar (Development)
```python
# settings.py
INSTALLED_APPS += ['debug_toolbar']
MIDDLEWARE += ['debug_toolbar.middleware.DebugToolbarMiddleware']
INTERNAL_IPS = ['127.0.0.1']
```

### Log SQL Queries
```python
# In view or service
from django.db import connection
print(connection.queries)
```

### Check Service Call Flow
```python
# Add logging
import logging
logger = logging.getLogger(__name__)
logger.debug(f"Processing with data: {data}")
```

### Inspect Template Context
```django
{# In template #}
{{ debug }}
```

---

## 📊 Database Schema Quick Reference

### Core Tables

| Table | Purpose | Key Fields |
|-------|---------|------------|
| `dominial_tis` | Indigenous lands | codigo, nome, etnia, area |
| `dominial_pessoas` | People | nome, cpf |
| `dominial_imovel` | Properties | matricula, proprietario_id, terra_indigena_id |
| `dominial_cartorios` | Notary offices | cns, nome, cidade, estado |
| `dominial_documento` | Documents | numero, tipo_id, cartorio_id, imovel_id |
| `dominial_lancamento` | Transactions | tipo_id, documento_id, documento_origem_id |
| `dominial_lancamentopessoa` | Transaction people | lancamento_id, pessoa_id, tipo |

### Key Relationships

```sql
-- Property chain
Imovel.terra_indigena_id → TIs.id
Documento.imovel_id → Imovel.id
Lancamento.documento_id → Documento.id
Lancamento.documento_origem_id → Documento.id  -- CHAIN LINK

-- People
Lancamento.transmitente_id → Pessoas.id
Lancamento.adquirente_id → Pessoas.id

-- Cartórios
Documento.cartorio_id → Cartorios.id
Lancamento.cartorio_origem_id → Cartorios.id
```

---

## 🔧 Configuration Files

### Environment Variables
- **File:** `.env` (create from `env.example`)
- **Key Variables:**
  - `DEBUG` - Debug mode (False in production)
  - `SECRET_KEY` - Django secret key
  - `DB_NAME`, `DB_USER`, `DB_PASSWORD` - Database credentials
  - `ALLOWED_HOSTS` - Allowed domain names

### Settings Files
- **Base:** `cadeia_dominial/settings.py`
- **Development:** `cadeia_dominial/settings_dev.py`
- **Production:** `cadeia_dominial/settings_prod.py`

### Dependencies
- **File:** `requirements.txt`
- **Key Dependencies:**
  - Django 5.2.3
  - django-autocomplete-light 3.12.1
  - WeasyPrint 62.2 (PDF generation)
  - openpyxl 3.1.5 (Excel export)
  - psycopg2-binary 2.9.9 (PostgreSQL)
  - gunicorn 21.2.0 (WSGI server)

---

## 🎨 UI/UX Patterns

### Bootstrap Components
- Navbar for navigation
- Modals for dialogs (origin selection, cartório selection)
- Alerts for flash messages
- Forms with validation
- Tables for data display
- Cards for content grouping

### JavaScript Libraries
- **D3.js v7** - Tree visualization
- **Bootstrap 5.1.3** - UI components
- **django-autocomplete-light** - Autocomplete widgets (uses Select2)

### Color Coding
- **Green (#4CAF50):** Matrícula
- **Blue (#2196F3):** Transcrição
- **Yellow (#FFC107):** Origem/inconclusa
- **Red (#dc3545):** Sem origem

---

## 📝 Coding Conventions

### Python Style
- Follow PEP 8
- 4 spaces for indentation
- Maximum line length: 119 characters
- Class names: PascalCase
- Function/variable names: snake_case

### Django Conventions
- Models: Singular names (Pessoa, Imovel, Documento)
- Services: End with "Service" (LancamentoCriacaoService)
- Views: Descriptive function names (novo_lancamento, editar_lancamento)
- Templates: Snake case (lancamento_form.html)

### JavaScript Style
- camelCase for variables and functions
- PascalCase for classes
- Use const/let (not var)
- ES6+ features encouraged

### CSS/SCSS
- BEM-like naming convention
- Component-specific files
- Mobile-first responsive design

---

## 🔐 Security Considerations

### Authentication
- All pages require login (except login page)
- Middleware: `dominial/middleware.py`
- Django built-in authentication

### Data Validation
- Model-level (model.clean())
- Form-level (form.clean())
- Service-level (validation services)
- Database constraints (unique, foreign keys)

### CSRF Protection
- Enabled globally
- All POST forms require {% csrf_token %}
- AJAX requests include CSRF token in headers

### SQL Injection Prevention
- Django ORM parameterizes all queries
- Raw SQL avoided

---

## 🚀 Performance Optimizations

### Database
- `select_related()` for foreign keys
- `prefetch_related()` for reverse relationships
- Database indexes on frequently queried fields
- Pagination for large lists

### Caching
- Expensive calculations cached (hierarchy, tree building)
- Cache invalidation on data changes
- Session-based user preferences

### Frontend
- Static files compressed (WhiteNoise)
- Browser caching enabled
- D3 rendering optimized (only update changed nodes)
- Lazy loading where appropriate

---

## 📖 Additional Resources

### External Documentation
- **Django:** https://docs.djangoproject.com/en/5.2/
- **D3.js:** https://d3js.org/
- **Bootstrap 5:** https://getbootstrap.com/docs/5.1/
- **WeasyPrint:** https://weasyprint.org/
- **django-autocomplete-light:** https://django-autocomplete-light.readthedocs.io/

### Project Documentation
- **User Guides:** `/docs/` directory
- **API Documentation:** `context/05-views-urls-api.md`
- **Deployment Guide:** `context/08-configuration-deployment.md`

---

## 🤝 Contributing Guidelines

### Before Making Changes
1. Read relevant context documentation
2. Understand the service layer pattern
3. Check existing similar implementations
4. Consider impact on chain integrity

### Making Changes
1. Create feature branch from main
2. Update models if needed (with migrations)
3. Update/create services for business logic
4. Update/create views (thin controllers)
5. Update/create templates
6. Add/update tests
7. Update relevant documentation in `context/`
8. Test thoroughly

### Code Review Checklist
- [ ] Business logic in services (not views)
- [ ] Views are thin controllers
- [ ] Models have proper relationships
- [ ] Forms validate input
- [ ] Templates use components
- [ ] JavaScript is modular
- [ ] Tests cover new functionality
- [ ] Documentation updated
- [ ] Migrations created and tested
- [ ] No security vulnerabilities

---

## 📞 Support and Contact

For questions about this documentation or the codebase:
1. Check relevant context file first
2. Search existing code for similar patterns
3. Review test files for usage examples
4. Consult Django/D3.js documentation for framework-specific questions

---

## 🗺️ Navigation Tips for AI Agents

When working on this codebase:

1. **Always start** with the context documentation in this file
2. **For models:** Read `context/03-database-models.md` for complete schema
3. **For business logic:** Check `context/04-services.md` for existing services
4. **For views:** See `context/05-views-urls-api.md` for URL patterns
5. **For frontend:** Review `context/06-frontend.md` for templates and JS
6. **For workflows:** Consult `context/07-core-features-workflows.md`
7. **For deployment:** Use `context/08-configuration-deployment.md`

### Quick Code Location Tips

- **"Where is X model?"** → `dominial/models/{domain}_models.py`
- **"Where is Y service?"** → `dominial/services/{feature}_service.py`
- **"Where is Z view?"** → `dominial/views/{domain}_views.py`
- **"Where is the template for W?"** → `templates/dominial/{feature}.html`
- **"Where are the tests?"** → `dominial/tests/test_{feature}.py`

---

## 📋 Version Information

**Current Version:** Beta 1.0.0
**Django Version:** 5.2.3
**Python Version:** 3.8+
**Database:** PostgreSQL 12+ (production), SQLite (development)
**Last Documentation Update:** 2025

---

**Ready to code!** This comprehensive documentation gives you everything needed to understand and work effectively with the Sistema de Cadeia Dominial codebase. Start with the project overview and architecture, then dive into specific areas as needed.
