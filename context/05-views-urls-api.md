# Views, URLs, and API

## Overview

The system has **94 URL patterns** organized across **7 view modules**. Views follow the thin controller pattern, delegating business logic to services.

## View Organization

```
dominial/views/
├── tis_views.py              # Indigenous land views
├── imovel_views.py            # Property views
├── documento_views.py         # Document views
├── lancamento_views.py        # Transaction views (34KB - largest)
├── cadeia_dominial_views.py   # Chain visualization views (35KB)
├── api_views.py               # AJAX and REST API endpoints
├── autocomplete_views.py      # Autocomplete endpoints
└── duplicata_views.py         # Duplicate handling views
```

## URL Structure

URLs follow a hierarchical pattern based on data relationships:

```
/ (home)
└── tis/<tis_id>/
    ├── (TI detail/edit/delete)
    └── imovel/<imovel_id>/
        ├── (Imovel detail/edit/delete/archive)
        ├── novo-documento/
        ├── novo-lancamento/
        ├── cadeia-dominial/ (D3 tree view)
        ├── cadeia-tabela/ (table view)
        ├── cadeia-completa/pdf/
        └── documento/<documento_id>/
            ├── lancamentos/
            ├── editar/
            └── lancamento/<lancamento_id>/
                ├── (detail)
                ├── editar/
                └── excluir/
```

## URL Categories

### 1. Main Pages (2 URLs)

| URL | View | Purpose |
|-----|------|---------|
| `/` | `home` | Dashboard/home page |
| `/accounts/login/` | Django auth | Login page |

---

### 2. Indigenous Territories (4 URLs)

**File:** `dominial/views/tis_views.py`

| URL Pattern | View Function | Method | Purpose |
|-------------|---------------|--------|---------|
| `/tis/` | `tis_form` | GET/POST | Create or list TIs |
| `/tis/<tis_id>/` | `tis_detail` | GET/POST | View/edit TI details |
| `/tis/<tis_id>/excluir/` | `tis_delete` | POST | Delete TI |
| `/tis/<tis_id>/imoveis/` | `imoveis` | GET | List properties in TI |

**Key Views:**

#### `tis_form(request)`
- **Purpose:** Create new indigenous territory or list all TIs
- **Methods:** GET (show form/list), POST (create TI)
- **Template:** `tis_form.html`
- **Context:**
  ```python
  {
      'form': TIsForm,
      'tis_list': TIs.objects.all(),
      'referencia_list': TerraIndigenaReferencia.objects.all()
  }
  ```

#### `tis_detail(request, tis_id)`
- **Purpose:** View and edit TI details
- **Methods:** GET (view), POST (update)
- **Template:** `tis_detail.html`
- **Services Used:** None (simple CRUD)
- **Context:**
  ```python
  {
      'tis': TIs,
      'form': TIsForm,
      'imoveis': Imovel.objects.filter(terra_indigena_id=tis)
  }
  ```

---

### 3. Properties (6 URLs)

**File:** `dominial/views/imovel_views.py`

| URL Pattern | View Function | Method | Purpose |
|-------------|---------------|--------|---------|
| `/tis/<tis_id>/imovel/cadastro/` | `imovel_form` | GET/POST | Create property |
| `/tis/<tis_id>/imovel/<imovel_id>/` | `imovel_detail` | GET | View property |
| `/tis/<tis_id>/imovel/<imovel_id>/editar/` | `imovel_form` | GET/POST | Edit property |
| `/tis/<tis_id>/imovel/<imovel_id>/excluir/` | `imovel_delete` | POST | Delete property |
| `/tis/<tis_id>/imovel/<imovel_id>/arquivar/` | `arquivar_imovel` | POST | Archive property |
| `/imoveis/` | `imoveis` | GET | List all properties |

**Key Views:**

#### `imovel_form(request, tis_id, imovel_id=None)`
- **Purpose:** Create or edit property
- **Form:** `ImovelForm` with autocomplete for cartórios
- **Validation:** Uses `CartorioVerificacaoService`
- **Template:** `imovel_form.html`

#### `imovel_detail(request, tis_id, imovel_id)`
- **Purpose:** Display property with all documents
- **Context:**
  ```python
  {
      'imovel': Imovel,
      'tis': TIs,
      'documentos': Documento.objects.filter(imovel=imovel),
      'total_lancamentos': count
  }
  ```
- **Template:** `imovel_detail.html`

---

### 4. Documents (6 URLs)

**File:** `dominial/views/documento_views.py`

| URL Pattern | View Function | Method | Purpose |
|-------------|---------------|--------|---------|
| `/tis/<tis_id>/imovel/<imovel_id>/novo-documento/` | `novo_documento` | GET/POST | Create document |
| `/documento/<documento_id>/lancamentos/<tis_id>/<imovel_id>/` | `documento_lancamentos` | GET | View document with transactions |
| `/documento/<documento_id>/editar/<tis_id>/<imovel_id>/` | `editar_documento` | GET/POST | Edit document |
| `/documento/<documento_id>/ajustar-nivel/` | `ajustar_nivel_documento` | POST | Adjust hierarchy level |
| `/selecionar-documento-lancamento/<tis_id>/<imovel_id>/` | `selecionar_documento_lancamento` | GET | Select document for transaction |
| `/tis/<tis_id>/imovel/<imovel_id>/criar-documento/<codigo_origem>/` | `criar_documento_automatico` | POST | Auto-create origin document |

**Key Views:**

#### `novo_documento(request, tis_id, imovel_id)`
- **Purpose:** Create new document (matrícula or transcrição)
- **Form:** `DocumentoForm`
- **Services Used:** `DocumentoService`
- **Validation:** Unique document number per cartório
- **Template:** `documento_form.html`

#### `documento_lancamentos(request, documento_id, tis_id, imovel_id)`
- **Purpose:** View document with all its transactions
- **Services Used:** `LancamentoConsultaService`
- **Context:**
  ```python
  {
      'documento': Documento,
      'lancamentos': Lancamento.objects.filter(documento=documento),
      'lancamentos_agrupados': grouped_by_type,
      'estatisticas': {
          'total_registros': count,
          'total_averbacoes': count,
          'total_inicios': count
      }
  }
  ```
- **Template:** `documento_lancamentos.html`

#### `criar_documento_automatico(request, tis_id, imovel_id, codigo_origem)`
- **Purpose:** Auto-create origin document when referenced but missing
- **Services Used:** `DocumentoService`, `LancamentoOrigemService`
- **Logic:**
  1. Parse origin code
  2. Check if document exists
  3. Create new Documento with `cri_origem` set
  4. Return JSON response
- **Returns:** JSON `{'success': True, 'documento_id': id}`

---

### 5. Transactions/Lançamentos (7 URLs)

**File:** `dominial/views/lancamento_views.py` (34KB - most complex)

| URL Pattern | View Function | Method | Purpose |
|-------------|---------------|--------|---------|
| `/tis/<tis_id>/imovel/<imovel_id>/novo-lancamento/` | `novo_lancamento` | GET/POST | Create transaction |
| `/tis/<tis_id>/imovel/<imovel_id>/novo-lancamento/<documento_id>/` | `novo_lancamento` | GET/POST | Create transaction for specific document |
| `/tis/<tis_id>/imovel/<imovel_id>/lancamento/<lancamento_id>/` | `lancamento_detail` | GET | View transaction details |
| `/tis/<tis_id>/imovel/<imovel_id>/lancamento/<lancamento_id>/editar/` | `editar_lancamento` | GET/POST | Edit transaction |
| `/tis/<tis_id>/imovel/<imovel_id>/lancamento/<lancamento_id>/excluir/` | `excluir_lancamento` | POST | Delete transaction |
| `/lancamentos/` | `lancamentos` | GET | List all transactions |
| `/pessoas/` | `pessoas` | GET | List all people |

**Key Views:**

#### `novo_lancamento(request, tis_id, imovel_id, documento_id=None)`
- **Purpose:** Complex transaction creation workflow
- **Form:** `LancamentoForm` (dynamic fields based on type)
- **Services Used:**
  - `LancamentoCriacaoService` - Orchestrates creation
  - `LancamentoDuplicataService` - Check duplicates
  - `LancamentoCamposService` - Dynamic field handling
  - `LancamentoOrigemService` - Origin processing
  - `LancamentoPessoaService` - Person associations
- **Features:**
  - Dynamic form fields based on transaction type
  - Autocomplete for people and cartórios
  - Duplicate detection
  - Origin document linking
  - Multiple transmitters/acquirers
- **Template:** `lancamento_form.html` (uses component templates)

**Workflow:**
```
1. User selects document (if not pre-selected)
   ↓
2. User selects transaction type (Averbação/Registro/Início de Matrícula)
   ↓
3. Form dynamically shows/hides fields based on type
   ↓
4. User fills required fields
   ↓
5. On submit:
   - Validate form
   - Check for duplicates (LancamentoDuplicataService)
   - Process fields (LancamentoCamposService)
   - Determine origin (LancamentoOrigemService)
   - Create transaction (LancamentoCriacaoService)
   - Associate people (LancamentoPessoaService)
   ↓
6. Redirect to lancamento_detail
```

#### `editar_lancamento(request, tis_id, imovel_id, lancamento_id)`
- **Purpose:** Edit existing transaction
- **Complexity:** Must preserve relationships and validate changes
- **Services Used:** Same as `novo_lancamento`
- **Validation:** Prevent changes that would break chain integrity

#### `lancamento_detail(request, tis_id, imovel_id, lancamento_id)`
- **Purpose:** Display complete transaction details
- **Context:**
  ```python
  {
      'lancamento': Lancamento,
      'documento': Documento,
      'imovel': Imovel,
      'tis': TIs,
      'transmitentes': LancamentoPessoa.filter(tipo='transmitente'),
      'adquirentes': LancamentoPessoa.filter(tipo='adquirente'),
      'documento_origem': Documento if linked,
      'origens_fim_cadeia': OrigemFimCadeia.filter(lancamento=lancamento)
  }
  ```
- **Template:** `lancamento_detail.html`

---

### 6. Chain Visualization (10 URLs)

**File:** `dominial/views/cadeia_dominial_views.py` (35KB - 2nd largest)

| URL Pattern | View Function | Method | Purpose |
|-------------|---------------|--------|---------|
| `/tis/<tis_id>/imovel/<imovel_id>/cadeia-dominial/` | `cadeia_dominial_d3` | GET | D3.js tree visualization |
| `/tis/<tis_id>/imovel/<imovel_id>/ver-cadeia-dominial/` | `tronco_principal` | GET | Table view (legacy) |
| `/tis/<tis_id>/imovel/<imovel_id>/cadeia-tabela/` | `cadeia_dominial_tabela` | GET/POST | Advanced table view |
| `/tis/<tis_id>/imovel/<imovel_id>/arvore-cadeia-dominial/` | `obter_arvore_cadeia_dominial` | GET | AJAX tree data |
| `/tis/<tis_id>/imovel/<imovel_id>/cadeia-completa/pdf/` | `exportar_cadeia_completa_pdf` | GET | Export complete PDF |
| `/tis/<tis_id>/imovel/<imovel_id>/cadeia-tabela/pdf/` | `exportar_cadeia_dominial_pdf` | GET | Export table PDF |
| `/tis/<tis_id>/imovel/<imovel_id>/cadeia-tabela/excel/` | `exportar_cadeia_dominial_excel` | GET | Export Excel |
| `/tis/<tis_id>/imovel/<imovel_id>/documento/<documento_id>/detalhado/` | `documento_detalhado` | GET | Document detail modal |
| `/cadeia-dominial/<tis_id>/<imovel_id>/arvore/` | `cadeia_dominial_arvore` | GET | Alternative tree view |
| `/api/cadeia-dominial-atualizada/<tis_id>/<imovel_id>/` | `get_cadeia_dominial_atualizada` | GET | Updated chain data |

**Key Views:**

#### `cadeia_dominial_d3(request, tis_id, imovel_id)`
- **Purpose:** Interactive D3.js tree visualization (PRIMARY VIEW)
- **Services Used:**
  - `HierarquiaArvoreService.construir_arvore_cadeia_dominial()`
  - `CacheService` for performance
- **Features:**
  - Interactive tree diagram
  - Zoom and pan
  - Node click for details
  - Dynamic sizing based on transaction count
  - Color coding by document type
  - Origin selection UI
- **Template:** `cadeia_dominial_d3.html`
- **JavaScript:** `static/cadeia_dominial_d3.js`

**Data Flow:**
```
1. View loads imovel and documento_principal
   ↓
2. Call HierarquiaArvoreService.construir_arvore_cadeia_dominial()
   ↓
3. Service builds JSON tree structure
   ↓
4. Pass JSON to template
   ↓
5. D3.js renders interactive tree
   ↓
6. User interactions update tree dynamically
```

#### `cadeia_dominial_tabela(request, tis_id, imovel_id)`
- **Purpose:** Advanced table view with filtering
- **Services Used:**
  - `CadeiaDominialTabelaService.obter_dados_tabela()`
- **Features:**
  - Filter by document type (own, shared, all)
  - Filter by transaction type (registros, averbações, all)
  - Sort by date, number
  - Session-based filter persistence
  - Grouped by document
  - Transaction highlighting
- **Template:** `cadeia_dominial_tabela.html`
- **JavaScript:** `static/cadeia_dominial_tabela.js`

**Filter Options:**
```python
# Stored in session
request.session['filtros_cadeia'] = {
    'mostrar_documentos': 'todos',  # 'todos', 'proprios', 'compartilhados'
    'mostrar_lancamentos': 'todos',  # 'todos', 'registros', 'averbacoes'
    'ordenacao': 'data_desc'
}
```

#### `exportar_cadeia_completa_pdf(request, tis_id, imovel_id)`
- **Purpose:** Generate comprehensive PDF report
- **Services Used:**
  - `CadeiaCompletaService.obter_cadeia_completa()`
  - WeasyPrint for PDF rendering
- **Features:**
  - Complete chain (main + secondary)
  - All transactions detailed
  - Statistics summary
  - Professional formatting
- **Template:** `cadeia_completa_pdf.html`
- **Returns:** PDF file download

**PDF Generation:**
```python
from weasyprint import HTML, CSS

# Get complete chain data
cadeia = CadeiaCompletaService.obter_cadeia_completa(documento_id)

# Render template to HTML
html_string = render_to_string('cadeia_completa_pdf.html', context)

# Convert to PDF
html = HTML(string=html_string, base_url=request.build_absolute_uri())
pdf_file = html.write_pdf()

# Return as download
response = HttpResponse(pdf_file, content_type='application/pdf')
response['Content-Disposition'] = f'attachment; filename="cadeia_{imovel.matricula}.pdf"'
return response
```

#### `exportar_cadeia_dominial_excel(request, tis_id, imovel_id)`
- **Purpose:** Export complete chain to Excel
- **Services Used:**
  - `CadeiaCompletaService.obter_cadeia_completa()`
  - `openpyxl` for Excel generation
- **Features:**
  - Multiple sheets (summary, documents, transactions)
  - Professional formatting
  - Borders, colors, fonts
  - Statistics
- **Returns:** Excel (.xlsx) file download

**Excel Structure:**
```
Workbook
├── Summary Sheet
│   ├── TI information
│   ├── Property information
│   └── Chain statistics
├── Main Chain Sheet
│   ├── Document groups
│   └── Transaction details
└── Secondary Chains Sheet
    ├── Document groups
    └── Transaction details
```

---

### 7. API Endpoints (20 URLs)

**File:** `dominial/views/api_views.py`

| URL Pattern | View Function | Method | Returns |
|-------------|---------------|--------|---------|
| `/buscar-cidades/` | `buscar_cidades` | GET | JSON cities |
| `/buscar-cartorios/` | `buscar_cartorios` | GET | JSON cartórios |
| `/verificar-cartorios/` | `verificar_cartorios_estado` | GET | JSON status |
| `/importar-cartorios/` | `importar_cartorios_estado` | POST | JSON result |
| `/criar-cartorio/` | `criar_cartorio` | POST | JSON cartório |
| `/api/escolher-origem-documento/` | `escolher_origem_documento` | POST | JSON success |
| `/api/escolher-origem-lancamento/` | `escolher_origem_lancamento` | POST | JSON success |
| `/api/limpar-escolhas-origem/` | `limpar_escolhas_origem` | POST | JSON success |

**Key API Endpoints:**

#### `buscar_cartorios(request)`
- **Purpose:** Search cartórios for autocomplete
- **Parameters:**
  - `q` - Search query
  - `cidade` - Filter by city (optional)
  - `estado` - Filter by state (optional)
- **Services Used:** `CartorioVerificacaoService`
- **Returns:**
  ```json
  {
    "results": [
      {
        "id": 123,
        "text": "1º CRI Salvador - Salvador/BA",
        "nome": "1º Cartório de Registro de Imóveis",
        "cns": "BA0001",
        "cidade": "Salvador",
        "estado": "BA"
      },
      ...
    ]
  }
  ```

#### `escolher_origem_documento(request)`
- **Purpose:** User selects origin document for a transaction
- **Method:** POST (AJAX)
- **Parameters:**
  - `documento_id` - Current document ID
  - `origem_escolhida` - Selected origin document ID
- **Logic:**
  1. Store choice in session: `request.session['origem_documento_{documento_id}'] = origem_escolhida`
  2. Rebuild tree with selected origin
  3. Return updated tree JSON
- **Returns:**
  ```json
  {
    "success": true,
    "arvore": { /* updated D3 tree data */ }
  }
  ```

#### `importar_cartorios_estado(request)`
- **Purpose:** Import all cartórios for a state from CNJ API
- **Method:** POST
- **Parameters:** `estado` (2-letter code)
- **Services Used:** External CNJ API integration
- **Process:**
  1. Check if already imported
  2. Create `ImportacaoCartorios` record
  3. Fetch from CNJ API
  4. Parse and create `Cartorios` records
  5. Update import status
- **Returns:**
  ```json
  {
    "success": true,
    "total_importados": 25,
    "mensagem": "25 cartórios importados para BA"
  }
  ```

---

### 8. Autocomplete Endpoints (3 URLs)

**File:** `dominial/views/autocomplete_views.py`

Uses `django-autocomplete-light` library for smart autocomplete widgets.

| URL Pattern | View Class | Purpose |
|-------------|------------|---------|
| `/pessoa-autocomplete/` | `PessoaAutocomplete` | Search people |
| `/cartorio-autocomplete/` | `CartorioAutocomplete` | Search cartórios |
| `/cartorio-imoveis-autocomplete/` | `CartorioImoveisAutocomplete` | Search cartórios for properties |

**Key Autocomplete Views:**

#### `PessoaAutocomplete`
```python
class PessoaAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        if not self.request.user.is_authenticated:
            return Pessoas.objects.none()

        qs = Pessoas.objects.all()

        if self.q:
            qs = qs.filter(
                Q(nome__icontains=self.q) |
                Q(cpf__icontains=self.q)
            )

        return qs.order_by('nome')[:20]
```

**Features:**
- Search by name or CPF
- Returns top 20 matches
- Requires authentication
- Used in transaction forms for transmitente/adquirente

#### `CartorioAutocomplete`
```python
class CartorioAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        qs = Cartorios.objects.filter(tipo='CRI')

        if self.q:
            qs = qs.filter(
                Q(nome__icontains=self.q) |
                Q(cidade__icontains=self.q) |
                Q(cns__icontains=self.q)
            )

        # Optional filters from forwarded fields
        estado = self.forwarded.get('estado', None)
        if estado:
            qs = qs.filter(estado=estado)

        cidade = self.forwarded.get('cidade', None)
        if cidade:
            qs = qs.filter(cidade=cidade)

        return qs.order_by('estado', 'cidade', 'nome')[:20]
```

**Features:**
- Search by name, city, or CNS
- Filter by state/city (forwarded from form)
- Only CRI type cartórios
- Used throughout the application

---

### 9. Duplicate Handling (3 URLs)

**File:** `dominial/views/duplicata_views.py`

| URL Pattern | View Function | Method | Purpose |
|-------------|---------------|--------|---------|
| `/tis/<tis_id>/imovel/<imovel_id>/documento/<documento_id>/verificar-duplicata/` | `verificar_duplicata_ajax` | POST | Check for duplicates |
| `/tis/<tis_id>/imovel/<imovel_id>/documento/<documento_id>/importar-duplicata/` | `importar_duplicata` | POST | Import duplicate |
| `/tis/<tis_id>/imovel/<imovel_id>/documento/<documento_id>/cancelar-importacao/` | `cancelar_importacao_duplicata` | POST | Cancel import |

**Duplicate Workflow:**

```
1. User creates document
   ↓
2. System checks for duplicates via AJAX
   ↓
3. If duplicates found:
   - Show modal with duplicate options
   - User can:
     a) Import transactions from duplicate
     b) Ignore and continue
     c) Cancel creation
   ↓
4. If user chooses import:
   - Copy all transactions from duplicate
   - Link origin documents
   - Mark duplicate as merged
```

---

## Authentication and Authorization

### Middleware
**File:** `dominial/middleware.py`

```python
class LoginRequiredMiddleware:
    """Require login for all views except login page"""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Allow access to login page and static files
        if not request.user.is_authenticated:
            if not request.path.startswith('/accounts/login/'):
                if not request.path.startswith('/static/'):
                    return redirect('login')

        return self.get_response(request)
```

**Settings:**
```python
MIDDLEWARE = [
    # ...
    'dominial.middleware.LoginRequiredMiddleware',  # Custom
]

LOGIN_URL = '/accounts/login/'
LOGIN_REDIRECT_URL = '/'
```

---

## Common View Patterns

### 1. Service Delegation Pattern

```python
def criar_lancamento(request, tis_id, imovel_id):
    """Thin controller - delegates to service"""
    if request.method == 'POST':
        form = LancamentoForm(request.POST)
        if form.is_valid():
            # Delegate business logic to service
            lancamento = LancamentoCriacaoService.criar(
                dados=form.cleaned_data,
                documento_id=documento_id
            )
            messages.success(request, 'Lançamento criado com sucesso')
            return redirect('lancamento_detail', pk=lancamento.pk)
    else:
        form = LancamentoForm()

    return render(request, 'lancamento_form.html', {'form': form})
```

### 2. Context Building Pattern

```python
def imovel_detail(request, tis_id, imovel_id):
    """Build comprehensive context"""
    imovel = get_object_or_404(Imovel, pk=imovel_id)
    tis = get_object_or_404(TIs, pk=tis_id)

    # Use select_related to minimize queries
    documentos = Documento.objects.filter(imovel=imovel).select_related(
        'tipo', 'cartorio'
    ).prefetch_related('lancamentos')

    context = {
        'imovel': imovel,
        'tis': tis,
        'documentos': documentos,
        'total_lancamentos': sum(d.lancamentos.count() for d in documentos)
    }

    return render(request, 'imovel_detail.html', context)
```

### 3. AJAX Response Pattern

```python
def verificar_duplicata_ajax(request, tis_id, imovel_id, documento_id):
    """Return JSON for AJAX calls"""
    if request.method == 'POST':
        try:
            # Business logic
            duplicatas = DuplicataVerificacaoService.verificar(documento_id)

            return JsonResponse({
                'success': True,
                'duplicatas': [
                    {'id': d.id, 'numero': d.numero, 'cartorio': d.cartorio.nome}
                    for d in duplicatas
                ]
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'erro': str(e)
            }, status=400)

    return JsonResponse({'success': False, 'erro': 'Método não permitido'}, status=405)
```

### 4. Session Storage Pattern

```python
def escolher_origem_documento(request):
    """Store user choices in session"""
    if request.method == 'POST':
        documento_id = request.POST.get('documento_id')
        origem_escolhida = request.POST.get('origem_escolhida')

        # Store in session
        request.session[f'origem_documento_{documento_id}'] = origem_escolhida

        # Rebuild tree with choice
        arvore = HierarquiaArvoreService.construir_arvore_cadeia_dominial(
            documento_id=documento_id,
            origens_escolhidas={documento_id: origem_escolhida}
        )

        return JsonResponse({'success': True, 'arvore': arvore})
```

---

## Performance Optimizations

### 1. Query Optimization

```python
# Use select_related for foreign keys
documentos = Documento.objects.select_related(
    'tipo', 'cartorio', 'imovel', 'imovel__terra_indigena_id'
).all()

# Use prefetch_related for reverse foreign keys
documentos = Documento.objects.prefetch_related(
    'lancamentos',
    'lancamentos__tipo',
    'lancamentos__transmitente',
    'lancamentos__adquirente'
).all()
```

### 2. Caching

```python
# Cache expensive hierarchy calculations
cache_key = f"arvore_cadeia_{documento_id}"
arvore = cache.get(cache_key)

if not arvore:
    arvore = HierarquiaArvoreService.construir_arvore_cadeia_dominial(documento_id)
    cache.set(cache_key, arvore, timeout=3600)  # 1 hour

return arvore
```

### 3. Pagination

```python
from django.core.paginator import Paginator

lancamentos = Lancamento.objects.all()
paginator = Paginator(lancamentos, 25)  # 25 per page
page_number = request.GET.get('page')
page_obj = paginator.get_page(page_number)
```

---

## Error Handling

### Standard Error Flow

```python
def criar_lancamento(request, ...):
    try:
        lancamento = LancamentoCriacaoService.criar(dados)
        messages.success(request, 'Criado com sucesso')
        return redirect('lancamento_detail', pk=lancamento.pk)

    except ValidationError as e:
        messages.error(request, f'Erro de validação: {str(e)}')
        return render(request, 'lancamento_form.html', {'form': form})

    except IntegrityError as e:
        messages.error(request, 'Erro: registro duplicado')
        return render(request, 'lancamento_form.html', {'form': form})

    except Exception as e:
        logger.error(f"Erro ao criar lançamento: {str(e)}")
        messages.error(request, 'Erro inesperado. Contate o administrador.')
        return render(request, 'lancamento_form.html', {'form': form})
```

---

## Template Rendering

### Context Processors

Standard Django context processors plus custom ones (if any):

```python
# settings.py
TEMPLATES = [{
    'OPTIONS': {
        'context_processors': [
            'django.template.context_processors.debug',
            'django.template.context_processors.request',
            'django.contrib.auth.context_processors.auth',
            'django.contrib.messages.context_processors.messages',
        ],
    },
}]
```

### Common Context Variables

All views pass standard context:
- `user` - Current authenticated user
- `request` - HTTP request object
- `messages` - Flash messages
- Domain objects: `tis`, `imovel`, `documento`, `lancamento`

---

## URL Naming Conventions

- **List views:** `{model}_list` (e.g., `lancamentos`)
- **Detail views:** `{model}_detail` (e.g., `lancamento_detail`)
- **Create views:** `{model}_cadastro` or `novo_{model}` (e.g., `imovel_cadastro`, `novo_lancamento`)
- **Edit views:** `{model}_editar` or `editar_{model}` (e.g., `editar_lancamento`)
- **Delete views:** `{model}_excluir` or `{model}_delete` (e.g., `tis_delete`)
- **API views:** `{action}_{model}` (e.g., `buscar_cartorios`)
- **Export views:** `exportar_{type}` (e.g., `exportar_cadeia_completa_pdf`)

---

## View Testing

Views are tested in `dominial/tests/`:

```python
from django.test import TestCase, Client
from django.urls import reverse

class TestLancamentoViews(TestCase):
    def setUp(self):
        self.client = Client()
        # Create test data

    def test_criar_lancamento_valido(self):
        url = reverse('novo_lancamento', args=[tis_id, imovel_id])
        response = self.client.post(url, data={...})

        self.assertEqual(response.status_code, 302)  # Redirect
        self.assertTrue(Lancamento.objects.filter(...).exists())
```

---

## Summary

- **94 URL patterns** organized hierarchically
- **7 view modules** organized by domain
- **Thin controllers** delegating to services
- **AJAX endpoints** for dynamic interactions
- **Autocomplete** for better UX
- **Multiple export formats** (PDF, Excel)
- **Session-based state** for user preferences
- **Comprehensive error handling**
- **Performance optimizations** (caching, query optimization)
