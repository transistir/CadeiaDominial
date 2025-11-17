# Architecture and Design Patterns

## Architectural Overview

Sistema de Cadeia Dominial follows a **Model-View-Service (MVS)** architecture pattern, an evolution of the traditional Django MVT (Model-View-Template) pattern that extracts business logic into dedicated service classes.

```
┌─────────────────────────────────────────────────────────┐
│                     Web Browser                         │
│              (HTML, CSS, JavaScript, D3.js)            │
└─────────────────┬───────────────────────────────────────┘
                  │ HTTP Requests
                  ▼
┌─────────────────────────────────────────────────────────┐
│                 Django URLs Router                      │
│                 (dominial/urls.py)                      │
└─────────────────┬───────────────────────────────────────┘
                  │ Route to View
                  ▼
┌─────────────────────────────────────────────────────────┐
│                  View Controllers                       │
│    (views/*.py - thin controllers, coordination)        │
└─────────────────┬───────────────────────────────────────┘
                  │ Delegate Business Logic
                  ▼
┌─────────────────────────────────────────────────────────┐
│               Service Layer (30+ services)              │
│  (services/*.py - business logic, calculations)         │
└─────────────────┬───────────────────────────────────────┘
                  │ Data Operations
                  ▼
┌─────────────────────────────────────────────────────────┐
│              Database Models (ORM)                      │
│        (models/*.py - domain entities)                  │
└─────────────────┬───────────────────────────────────────┘
                  │ SQL Queries
                  ▼
┌─────────────────────────────────────────────────────────┐
│           Database (PostgreSQL/SQLite)                  │
└─────────────────────────────────────────────────────────┘
```

## Design Patterns

### 1. Service Layer Pattern

**Purpose:** Separate business logic from presentation layer

**Implementation:**
- All complex business logic extracted into service classes
- Views become thin controllers that coordinate services
- Services are reusable across different views
- Easier to test and maintain

**Example:**
```python
# View (thin controller)
def criar_lancamento(request):
    if request.method == 'POST':
        form = LancamentoForm(request.POST)
        if form.is_valid():
            # Delegate to service
            lancamento = LancamentoCriacaoService.criar(form.cleaned_data)
            return redirect('lancamento_detail', pk=lancamento.pk)
    # ...

# Service (business logic)
class LancamentoCriacaoService:
    @staticmethod
    def criar(dados):
        # Complex business logic
        # Validation
        # Duplicate checking
        # Data transformation
        # Database operations
        return lancamento
```

### 2. Domain-Driven Design (DDD)

**Organization by Business Domain:**

```
dominial/
├── models/
│   ├── tis_models.py              # Indigenous lands domain
│   ├── pessoa_models.py            # Person/people domain
│   ├── imovel_models.py            # Property domain
│   ├── documento_models.py         # Document domain
│   └── lancamento_models.py        # Transaction domain
├── views/
│   ├── tis_views.py
│   ├── imovel_views.py
│   ├── documento_views.py
│   └── lancamento_views.py
└── services/
    ├── hierarquia_service.py
    ├── lancamento_criacao_service.py
    └── cadeia_dominial_tabela_service.py
```

**Benefits:**
- Code organized around business concepts
- Easier for domain experts to understand
- Related functionality grouped together
- Clear module boundaries

### 3. Repository Pattern (via Django ORM)

**Implementation:**
- Models act as repositories for data access
- Service classes use models to retrieve and persist data
- Query optimization in service layer
- Custom managers for complex queries

### 4. Template Composition Pattern

**Component-Based Templates:**

```
templates/
├── base.html                           # Master template
├── lancamento_form.html                # Feature template
└── components/                         # Reusable components
    ├── _lancamento_basico_form.html
    ├── _lancamento_averbacao_form.html
    ├── _pessoa_form.html
    └── _cartorio_form.html
```

**Usage:**
```django
{% extends "base.html" %}

{% block content %}
    {% include "components/_lancamento_basico_form.html" %}
    {% include "components/_pessoa_form.html" %}
{% endblock %}
```

### 5. Strategy Pattern (Form Field Management)

**Dynamic Field Display Based on Type:**

```python
# LancamentoCamposService determines which fields to show/require
class LancamentoCamposService:
    @staticmethod
    def obter_campos_obrigatorios(tipo_lancamento):
        if tipo_lancamento == 'Averbação':
            return ['tipo', 'data', 'descricao']
        elif tipo_lancamento == 'Registro':
            return ['tipo', 'data', 'transmitente', 'adquirente']
        # ...
```

## Directory Structure

### Root Level
```
/
├── cadeia_dominial/       # Project configuration
│   ├── settings.py        # Base settings
│   ├── settings_dev.py    # Development overrides
│   ├── settings_prod.py   # Production overrides
│   ├── urls.py            # Main URL configuration
│   └── wsgi.py            # WSGI entry point
├── dominial/              # Main application
├── templates/             # Global templates
├── static/                # Static files (CSS, JS, images)
├── staticfiles/           # Collected static files (production)
├── media/                 # User-uploaded files
├── docs/                  # Documentation
├── tests_scripts/         # Test and analysis scripts
├── context/               # This documentation
├── manage.py              # Django management script
├── requirements.txt       # Python dependencies
├── Dockerfile             # Docker image definition
└── docker-compose.yml     # Docker orchestration
```

### Application Structure (dominial/)
```
dominial/
├── __init__.py
├── admin.py                    # Admin interface customization (15KB)
├── apps.py                     # App configuration
├── signals.py                  # Django signal handlers
├── middleware.py               # Custom middleware
├── urls.py                     # App-specific URLs (94 patterns)
│
├── models/                     # Domain models (7 modules)
│   ├── __init__.py
│   ├── tis_models.py
│   ├── pessoa_models.py
│   ├── imovel_models.py
│   ├── documento_models.py
│   ├── lancamento_models.py
│   ├── alteracao_models.py
│   └── documento_importado_models.py
│
├── views/                      # View controllers (7 modules)
│   ├── __init__.py
│   ├── tis_views.py
│   ├── imovel_views.py
│   ├── documento_views.py
│   ├── lancamento_views.py      # Largest: 34KB
│   ├── cadeia_dominial_views.py # 35KB
│   ├── api_views.py
│   └── autocomplete_views.py
│
├── services/                   # Business logic (30+ services)
│   ├── __init__.py
│   ├── hierarquia_service.py
│   ├── hierarquia_arvore_service.py
│   ├── cadeia_dominial_tabela_service.py
│   ├── cadeia_completa_service.py
│   ├── lancamento_criacao_service.py
│   ├── lancamento_origem_service.py
│   ├── lancamento_campos_service.py
│   ├── lancamento_validacao_service.py
│   ├── lancamento_duplicata_service.py
│   ├── lancamento_consulta_service.py
│   ├── lancamento_pessoa_service.py
│   ├── lancamento_form_service.py
│   ├── documento_service.py
│   ├── duplicata_verificacao_service.py
│   ├── cartorio_verificacao_service.py
│   ├── cri_service.py
│   └── cache_service.py
│
├── forms/                      # Django forms
│   ├── __init__.py
│   ├── tis_forms.py
│   ├── imovel_forms.py
│   ├── documento_forms.py
│   ├── lancamento_forms.py
│   └── pessoa_forms.py
│
├── utils/                      # Utility functions
│   ├── __init__.py
│   ├── hierarquia_utils.py
│   ├── validacao_utils.py
│   └── formatacao_utils.py
│
├── management/
│   └── commands/               # Custom management commands (18+)
│       ├── criar_tipos_documento.py
│       ├── criar_tipos_lancamento.py
│       ├── importar_terras_indigenas.py
│       ├── importar_cartorios_estado.py
│       └── ...
│
├── templatetags/               # Custom template tags
│   ├── __init__.py
│   └── custom_filters.py
│
├── migrations/                 # Database migrations
│   ├── 0001_initial.py
│   └── ...
│
├── tests/                      # Test suite (8 test files)
│   ├── __init__.py
│   ├── test_documento_lancamento.py
│   ├── test_duplicata_verificacao.py
│   └── ...
│
└── static/
    └── admin/                  # Admin interface customizations
```

## Layer Responsibilities

### 1. Models Layer (models/)
**Responsibility:** Data structure and basic data access

- Define database schema using Django ORM
- Basic field validation
- Model relationships (ForeignKey, ManyToMany)
- Custom model methods for simple operations
- Custom managers for common queries

**What NOT to do in models:**
- Complex business logic
- Multi-step operations
- External API calls
- Complex calculations

### 2. Service Layer (services/)
**Responsibility:** Business logic and complex operations

- Complex business rules
- Multi-step workflows
- Data validation beyond field constraints
- Calculations and algorithms
- External service integration
- Transaction management
- Data aggregation and reporting

**Examples:**
- `LancamentoCriacaoService` - Multi-step registration creation
- `HierarquiaService` - Complex chain calculations
- `DuplicataVerificacaoService` - Duplicate detection logic

### 3. View Layer (views/)
**Responsibility:** Request handling and response generation

- HTTP request/response handling
- Form instantiation and validation
- Delegating to services
- Template rendering
- Error handling
- Redirects and messaging

**What NOT to do in views:**
- Complex business logic (delegate to services)
- Direct complex database queries (use services)
- Data transformation (use services)

### 4. Template Layer (templates/)
**Responsibility:** Presentation logic only

- HTML structure
- Display formatting
- Conditional rendering
- Loops for data display
- Form rendering

**What NOT to do in templates:**
- Business logic
- Database queries
- Complex calculations

### 5. Form Layer (forms/)
**Responsibility:** Data input validation

- Field definitions
- Basic validation rules
- Widgets configuration
- Cleaned data preparation

## Request Flow Example

**Creating a New Lançamento:**

1. **User** submits form via browser
2. **URL Router** (`urls.py`) matches URL to `lancamento_views.criar_lancamento`
3. **View** (`lancamento_views.py`):
   - Instantiates form with POST data
   - Validates form
   - Delegates to `LancamentoCriacaoService.criar()`
4. **Service** (`lancamento_criacao_service.py`):
   - Validates business rules
   - Checks for duplicates via `LancamentoDuplicataService`
   - Processes fields via `LancamentoCamposService`
   - Determines origin via `LancamentoOrigemService`
   - Creates database record
   - Returns created object
5. **View** redirects to detail page
6. **Template** renders the result

## Separation of Concerns

### Clear Boundaries

```
┌──────────────────────────────────────────────────────────┐
│  Templates (Presentation)                                 │
│  - HTML structure, CSS styling, JavaScript interactivity │
└──────────────────────────────────────────────────────────┘
                        ▲
                        │ Context data
                        │
┌──────────────────────────────────────────────────────────┐
│  Views (Controllers)                                      │
│  - Request handling, form validation, delegation         │
└──────────────────────────────────────────────────────────┘
                        ▲
                        │ Domain objects
                        │
┌──────────────────────────────────────────────────────────┐
│  Services (Business Logic)                                │
│  - Complex operations, workflows, calculations           │
└──────────────────────────────────────────────────────────┘
                        ▲
                        │ Data access
                        │
┌──────────────────────────────────────────────────────────┐
│  Models (Domain & Persistence)                            │
│  - Data structure, relationships, basic queries          │
└──────────────────────────────────────────────────────────┘
```

## Code Organization Principles

1. **Single Responsibility:** Each module/class does one thing well
2. **DRY (Don't Repeat Yourself):** Reusable components and services
3. **KISS (Keep It Simple):** Straightforward solutions preferred
4. **Explicit Over Implicit:** Clear naming and structure
5. **Domain-Driven:** Code organized by business concepts

## Testing Architecture

```
tests/
├── test_models.py              # Model tests (fields, relationships)
├── test_services.py            # Service layer tests (business logic)
├── test_views.py               # View tests (request/response)
├── test_integration.py         # End-to-end workflow tests
└── test_duplicata_verificacao.py  # Specific feature tests
```

## Scalability Considerations

- **Service layer** makes it easy to extract microservices later
- **Clear boundaries** allow independent scaling of components
- **Caching layer** (`CacheService`) for performance optimization
- **Database indexing** on frequently queried fields
- **Pagination** for large data sets
- **Async processing** potential for heavy operations

## Security Architecture

- **Authentication:** Django built-in authentication system
- **Authorization:** Custom middleware for route protection
- **CSRF Protection:** Django CSRF middleware
- **SQL Injection:** Django ORM parameterized queries
- **XSS Protection:** Django template auto-escaping
- **Environment Variables:** Sensitive config in `.env` file
- **Secret Key:** Separate for dev/prod environments
