# Frontend: Templates, JavaScript, and CSS

## Overview

The frontend uses:
- **Django Templates** (40+ templates)
- **Bootstrap 5.1.3** CSS framework
- **Vanilla JavaScript** (no jQuery)
- **D3.js v7** for tree visualization
- **Component-based architecture** for reusable template fragments

## Template Structure

### Template Hierarchy

```
templates/
├── base.html                          # Master template
├── registration/
│   └── login.html                     # Login page
└── dominial/
    ├── Main Feature Templates (20+)
    └── components/                    # Reusable components
        ├── _lancamento_basico_form.html
        ├── _lancamento_averbacao_form.html
        ├── _lancamento_registro_form.html
        ├── _lancamento_inicio_matricula_form.html
        ├── _pessoa_form.html
        ├── _cartorio_form.html
        ├── _area_form.html
        ├── _area_origem_form.html
        ├── _observacoes_form.html
        └── _documento_resumo.html
```

## Master Template

### base.html

**File:** `templates/base.html`

**Purpose:** Master template for all pages with consistent layout.

**Structure:**
```html
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}Sistema de Cadeia Dominial{% endblock %}</title>

    <!-- Bootstrap 5.1.3 CSS -->
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css">

    <!-- Base CSS -->
    <link rel="stylesheet" href="{% static 'dominial/css/base.css' %}">

    <!-- Page-specific CSS -->
    {% block extra_css %}{% endblock %}
</head>
<body>
    <!-- Header -->
    <header class="navbar navbar-expand-lg navbar-dark bg-primary">
        <div class="container-fluid">
            <a class="navbar-brand" href="{% url 'home' %}">
                Cadeia Dominial
            </a>
            <nav>
                <!-- Navigation links -->
                <a href="{% url 'home' %}">Terras Indígenas</a>
                <a href="{% url 'lancamentos' %}">Lançamentos</a>
                <a href="{% url 'cartorios' %}">Cartórios</a>
                {% if user.is_authenticated %}
                    <a href="{% url 'logout' %}">Sair ({{ user.username }})</a>
                {% endif %}
            </nav>
        </div>
    </header>

    <!-- Messages (flash messages) -->
    {% if messages %}
        <div class="container mt-3">
            {% for message in messages %}
                <div class="alert alert-{{ message.tags }} alert-dismissible">
                    {{ message }}
                    <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
                </div>
            {% endfor %}
        </div>
    {% endif %}

    <!-- Main content -->
    <main class="container-fluid mt-4">
        {% block content %}{% endblock %}
    </main>

    <!-- Footer -->
    <footer class="mt-5 py-3 bg-light text-center">
        <p>Sistema de Cadeia Dominial - Beta v1.0.0</p>
    </footer>

    <!-- Bootstrap JS -->
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>

    <!-- Page-specific JS -->
    {% block extra_js %}{% endblock %}
</body>
</html>
```

**Blocks:**
- `{% block title %}` - Page title
- `{% block extra_css %}` - Page-specific CSS
- `{% block content %}` - Main page content
- `{% block extra_js %}` - Page-specific JavaScript

**CSS:** `static/dominial/css/base.css`

---

## Feature Templates

### 1. TI Templates

#### tis_form.html
- **Purpose:** Create/list indigenous territories
- **Extends:** `base.html`
- **Key Features:**
  - Form for new TI creation
  - List of existing TIs
  - Link to reference data (FUNAI)
- **CSS:** `tis_form.css`

#### tis_detail.html
- **Purpose:** View/edit TI details
- **Key Features:**
  - TI information display
  - Edit form
  - List of linked properties
  - Statistics
- **CSS:** `tis_detail.css`

---

### 2. Property Templates

#### imovel_form.html
- **Purpose:** Create/edit property
- **Key Features:**
  - Property details form
  - Autocomplete for cartório
  - Link to TI
- **CSS:** `imovel_form.css`
- **JavaScript:** `imovel_form.js`

**JavaScript Features (`imovel_form.js`):**
- Cartório autocomplete integration
- Form validation
- Dynamic field enabling/disabling

---

### 3. Document Templates

#### documento_form.html
- **Purpose:** Create/edit document
- **Key Features:**
  - Document type selection (matrícula/transcrição)
  - Cartório selection with autocomplete
  - Book, page, date fields
  - Origin information
- **CSS:** `documento_form.css`

#### documento_lancamentos.html
- **Purpose:** View document with all transactions
- **Key Features:**
  - Document summary card
  - Grouped transactions by type
  - Add new transaction button
  - Statistics
- **CSS:** `documento_lancamentos.css`

#### documento_detalhado.html
- **Purpose:** Detailed document view (modal/standalone)
- **Key Features:**
  - Complete document information
  - All transactions listed
  - Links to edit/delete
- **CSS:** `documento_detalhado.css`

---

### 4. Transaction Templates

#### lancamento_form.html
- **Purpose:** Create/edit transaction (MOST COMPLEX FORM)
- **Extends:** `base.html`
- **Key Features:**
  - Dynamic form based on transaction type
  - Type-specific field visibility
  - Autocomplete for people and cartórios
  - Multiple component includes
  - Origin selection
- **CSS:** `forms.css`
- **JavaScript:** `lancamento_form.js` (most complex JS file)

**Template Structure:**
```django
{% extends "base.html" %}

{% block content %}
<div class="container">
    <h1>{% if lancamento %}Editar{% else %}Novo{% endif %} Lançamento</h1>

    <form method="post" id="lancamento-form">
        {% csrf_token %}

        <!-- Basic fields (always visible) -->
        {% include "dominial/components/_lancamento_basico_form.html" %}

        <!-- Type-specific fields (conditionally visible) -->
        <div id="averbacao-fields" style="display: none;">
            {% include "dominial/components/_lancamento_averbacao_form.html" %}
        </div>

        <div id="registro-fields" style="display: none;">
            {% include "dominial/components/_lancamento_registro_form.html" %}
        </div>

        <div id="inicio-matricula-fields" style="display: none;">
            {% include "dominial/components/_lancamento_inicio_matricula_form.html" %}
        </div>

        <!-- Person fields -->
        {% include "dominial/components/_pessoa_form.html" %}

        <!-- Area and origin -->
        {% include "dominial/components/_area_origem_form.html" %}

        <!-- Observations -->
        {% include "dominial/components/_observacoes_form.html" %}

        <button type="submit" class="btn btn-primary">Salvar</button>
    </form>
</div>
{% endblock %}

{% block extra_js %}
<script src="{% static 'dominial/js/lancamento_form.js' %}"></script>
{% endblock %}
```

**JavaScript Features (`lancamento_form.js`):**
- Dynamic field visibility based on transaction type
- Required field management
- Autocomplete integration
- Form validation
- Date validation
- Duplicate checking (AJAX)
- Origin selection UI

**Key Functions:**
```javascript
// Show/hide fields based on transaction type
function updateFieldVisibility(tipo) {
    // Hide all type-specific sections
    document.querySelectorAll('[id$="-fields"]').forEach(el => {
        el.style.display = 'none';
    });

    // Show relevant section
    if (tipo === 'averbacao') {
        document.getElementById('averbacao-fields').style.display = 'block';
    } else if (tipo === 'registro') {
        document.getElementById('registro-fields').style.display = 'block';
    } else if (tipo === 'inicio_matricula') {
        document.getElementById('inicio-matricula-fields').style.display = 'block';
    }

    // Update required fields
    updateRequiredFields(tipo);
}

// Validate form before submission
function validateForm() {
    const tipo = document.getElementById('id_tipo').value;
    const errors = [];

    // Type-specific validation
    if (tipo === 'registro') {
        if (!document.getElementById('id_transmitente').value) {
            errors.push('Transmitente é obrigatório para Registro');
        }
        if (!document.getElementById('id_adquirente').value) {
            errors.push('Adquirente é obrigatório para Registro');
        }
    }

    // Show errors if any
    if (errors.length > 0) {
        alert(errors.join('\n'));
        return false;
    }

    return true;
}

// Autocomplete initialization
$(document).ready(function() {
    // Initialize person autocomplete
    $('#id_transmitente').select2({
        ajax: {
            url: '{% url "pessoa-autocomplete" %}',
            dataType: 'json',
            delay: 250
        }
    });
});
```

#### lancamento_detail.html
- **Purpose:** View transaction details
- **Key Features:**
  - Complete transaction information
  - Transmitter/acquirer display
  - Origin document link
  - Edit/delete buttons
- **CSS:** `lancamento_detail.css`

---

### 5. Chain Visualization Templates

#### cadeia_dominial_d3.html (PRIMARY VISUALIZATION)
- **Purpose:** Interactive D3.js tree visualization
- **Extends:** `base.html`
- **Key Features:**
  - SVG-based tree diagram
  - Interactive zoom and pan
  - Click nodes for details
  - Origin selection modal
  - Legend
  - Export buttons
- **CSS:** `cadeia_dominial_d3.css`
- **JavaScript:** `cadeia_dominial_d3.js` (largest and most complex JS)

**Template Structure:**
```django
{% extends "base.html" %}

{% block content %}
<div class="container-fluid">
    <h1>Cadeia Dominial - {{ imovel.nome }}</h1>

    <!-- Controls -->
    <div class="controls mb-3">
        <button id="zoom-in" class="btn btn-sm btn-secondary">Zoom +</button>
        <button id="zoom-out" class="btn btn-sm btn-secondary">Zoom -</button>
        <button id="reset-zoom" class="btn btn-sm btn-secondary">Resetar</button>
        <button id="export-pdf" class="btn btn-sm btn-primary">Exportar PDF</button>
        <button id="export-excel" class="btn btn-sm btn-success">Exportar Excel</button>
    </div>

    <!-- Legend -->
    <div class="legend">
        <div class="legend-item">
            <div class="legend-color" style="background: #4CAF50;"></div>
            <span>Matrícula</span>
        </div>
        <div class="legend-item">
            <div class="legend-color" style="background: #2196F3;"></div>
            <span>Transcrição</span>
        </div>
        <div class="legend-item">
            <div class="legend-color" style="background: #FFC107;"></div>
            <span>Origem</span>
        </div>
    </div>

    <!-- SVG Container -->
    <div id="tree-container">
        <svg id="tree-svg"></svg>
    </div>

    <!-- Origin Selection Modal -->
    <div class="modal fade" id="origin-modal" tabindex="-1">
        <div class="modal-dialog">
            <div class="modal-content">
                <div class="modal-header">
                    <h5 class="modal-title">Escolher Origem</h5>
                    <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                </div>
                <div class="modal-body" id="origin-options">
                    <!-- Populated dynamically -->
                </div>
            </div>
        </div>
    </div>
</div>
{% endblock %}

{% block extra_js %}
<!-- D3.js Library -->
<script src="https://d3js.org/d3.v7.min.js"></script>

<!-- Tree data from backend -->
<script>
    const treeData = {{ tree_data|safe }};
    const imovelId = {{ imovel.id }};
    const tisId = {{ tis.id }};
</script>

<!-- Tree visualization script -->
<script src="{% static 'dominial/js/cadeia_dominial_d3.js' %}"></script>
{% endblock %}
```

**JavaScript Features (`cadeia_dominial_d3.js`):**

```javascript
// Main tree rendering
class CadeiaDominialTree {
    constructor(containerId, data) {
        this.container = d3.select(containerId);
        this.data = data;
        this.width = 1200;
        this.height = 800;
        this.zoom = d3.zoom().scaleExtent([0.1, 3]);

        this.init();
    }

    init() {
        // Create SVG
        this.svg = this.container.append('svg')
            .attr('width', '100%')
            .attr('height', this.height)
            .call(this.zoom.on('zoom', (event) => {
                this.g.attr('transform', event.transform);
            }));

        this.g = this.svg.append('g');

        // Create tree layout
        this.treeLayout = d3.tree()
            .size([this.height - 100, this.width - 200])
            .nodeSize([100, 300]);

        // Convert data to hierarchy
        this.root = d3.hierarchy(this.data);

        // Render
        this.render();
    }

    render() {
        // Calculate positions
        this.treeLayout(this.root);

        // Draw links (connections between nodes)
        this.drawLinks();

        // Draw nodes (documents)
        this.drawNodes();
    }

    drawLinks() {
        const links = this.root.links();

        this.g.selectAll('.link')
            .data(links)
            .join('path')
            .attr('class', 'link')
            .attr('d', d => {
                // Create curved path from parent to child
                return `M${d.source.y},${d.source.x}
                        C${(d.source.y + d.target.y) / 2},${d.source.x}
                         ${(d.source.y + d.target.y) / 2},${d.target.x}
                         ${d.target.y},${d.target.x}`;
            })
            .attr('fill', 'none')
            .attr('stroke', '#ccc')
            .attr('stroke-width', 2);
    }

    drawNodes() {
        const nodes = this.root.descendants();

        const node = this.g.selectAll('.node')
            .data(nodes)
            .join('g')
            .attr('class', 'node')
            .attr('transform', d => `translate(${d.y},${d.x})`);

        // Draw rectangles for documents
        node.append('rect')
            .attr('width', d => this.getNodeWidth(d))
            .attr('height', d => this.getNodeHeight(d))
            .attr('x', d => -this.getNodeWidth(d) / 2)
            .attr('y', d => -this.getNodeHeight(d) / 2)
            .attr('fill', d => this.getNodeColor(d))
            .attr('stroke', '#333')
            .attr('stroke-width', 2)
            .attr('rx', 5);

        // Add text labels
        node.append('text')
            .attr('dy', 5)
            .attr('text-anchor', 'middle')
            .text(d => d.data.numero)
            .style('fill', '#fff')
            .style('font-weight', 'bold');

        // Add click handlers
        node.on('click', (event, d) => {
            this.handleNodeClick(d);
        });
    }

    getNodeColor(d) {
        if (d.data.tipo === 'matricula') return '#4CAF50';
        if (d.data.tipo === 'transcricao') return '#2196F3';
        if (d.data.tipo === 'origem') return '#FFC107';
        return '#999';
    }

    getNodeWidth(d) {
        // Dynamic width based on transaction count
        const baseWidth = 150;
        const lancamentoCount = d.data.lancamentos ? d.data.lancamentos.length : 0;
        return baseWidth + Math.min(lancamentoCount * 10, 100);
    }

    getNodeHeight(d) {
        // Dynamic height
        const baseHeight = 80;
        const lancamentoCount = d.data.lancamentos ? d.data.lancamentos.length : 0;
        return baseHeight + Math.min(lancamentoCount * 5, 50);
    }

    handleNodeClick(d) {
        // Show document details or origin selection modal
        if (d.data.tem_multiplas_origens) {
            this.showOriginModal(d);
        } else {
            this.showDocumentDetails(d);
        }
    }

    showOriginModal(d) {
        // Populate modal with origin options
        const modalBody = document.getElementById('origin-options');
        modalBody.innerHTML = '';

        d.data.origens.forEach((origem, index) => {
            const button = document.createElement('button');
            button.className = 'btn btn-outline-primary m-2';
            button.textContent = origem.numero;
            button.onclick = () => this.selectOrigin(d.data.id, index);
            modalBody.appendChild(button);
        });

        // Show modal
        new bootstrap.Modal(document.getElementById('origin-modal')).show();
    }

    selectOrigin(documentoId, origemIndex) {
        // AJAX call to store choice and rebuild tree
        fetch('/api/escolher-origem-documento/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCsrfToken()
            },
            body: JSON.stringify({
                documento_id: documentoId,
                origem_escolhida: origemIndex
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                // Rebuild tree with new data
                this.data = data.arvore;
                this.root = d3.hierarchy(this.data);
                this.render();
            }
        });
    }

    // Zoom controls
    zoomIn() {
        this.svg.transition().call(this.zoom.scaleBy, 1.3);
    }

    zoomOut() {
        this.svg.transition().call(this.zoom.scaleBy, 0.7);
    }

    resetZoom() {
        this.svg.transition().call(this.zoom.transform, d3.zoomIdentity);
    }
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    const tree = new CadeiaDominialTree('#tree-svg', treeData);

    // Bind zoom controls
    document.getElementById('zoom-in').addEventListener('click', () => tree.zoomIn());
    document.getElementById('zoom-out').addEventListener('click', () => tree.zoomOut());
    document.getElementById('reset-zoom').addEventListener('click', () => tree.resetZoom());
});
```

---

#### cadeia_dominial_tabela.html
- **Purpose:** Table format view with filtering
- **Key Features:**
  - Structured table layout
  - Filter controls (document type, transaction type)
  - Sort options
  - Export buttons
  - Session-based filter persistence
- **CSS:** `cadeia_dominial_tabela.css`
- **JavaScript:** `cadeia_dominial_tabela.js`

**Table Structure:**
```html
<table class="table table-striped">
    <thead>
        <tr>
            <th>Documento</th>
            <th>Tipo</th>
            <th>Cartório</th>
            <th>Data</th>
            <th>Lançamentos</th>
            <th>Ações</th>
        </tr>
    </thead>
    <tbody>
        {% for documento in documentos %}
        <tr class="documento-row">
            <td colspan="6">
                <strong>{{ documento.tipo }} {{ documento.numero }}</strong>
            </td>
        </tr>
        {% for lancamento in documento.lancamentos %}
        <tr class="lancamento-row">
            <td></td>
            <td>{{ lancamento.tipo }}</td>
            <td>{{ lancamento.cartorio }}</td>
            <td>{{ lancamento.data|date:"d/m/Y" }}</td>
            <td>{{ lancamento.descricao }}</td>
            <td>
                <a href="{% url 'lancamento_detail' lancamento.id %}">Ver</a>
            </td>
        </tr>
        {% endfor %}
        {% endfor %}
    </tbody>
</table>
```

**JavaScript Features (`cadeia_dominial_tabela.js`):**
- Filter form handling
- AJAX filter updates
- Table sorting
- Expand/collapse groups

---

### 6. PDF Export Templates

#### cadeia_completa_pdf.html
- **Purpose:** PDF export template (rendered by WeasyPrint)
- **Key Features:**
  - Print-optimized layout
  - Page breaks
  - Headers and footers
  - Complete chain data
  - Statistics
- **CSS:** `cadeia_completa_pdf.css` (print-specific styles)

**Print CSS:**
```css
@page {
    size: A4;
    margin: 2cm;
}

@page :first {
    margin-top: 3cm;
}

.page-break {
    page-break-before: always;
}

.no-break {
    page-break-inside: avoid;
}

/* Print-optimized colors */
.documento-card {
    border: 2px solid #000;
    background: #f5f5f5;
    padding: 10px;
    margin-bottom: 15px;
}
```

---

### 7. Component Templates

These are reusable template fragments included in larger forms.

#### _lancamento_basico_form.html
- Basic fields for all transaction types
- Fields: tipo, documento, data, numero_lancamento

#### _lancamento_averbacao_form.html
- Averbação-specific fields
- Fields: descricao, detalhes

#### _lancamento_registro_form.html
- Registro-specific fields
- Fields: titulo, forma, cartorio_transmissao, livro_transacao, folha_transacao

#### _lancamento_inicio_matricula_form.html
- Início de matrícula-specific fields
- Fields: cartorio_origem, livro_origem, folha_origem, data_origem

#### _pessoa_form.html
- Person selection fields
- Fields: transmitente, adquirente (with autocomplete)
- "Add person" quick-create link

#### _cartorio_form.html
- Cartório selection with autocomplete
- Validation and verification
- "Create cartório" quick-link

#### _area_origem_form.html (295 lines - largest component)
- Area and origin information
- Fields: area, valor_transacao, origem
- Origin parsing and validation

#### _observacoes_form.html
- Observations textarea
- Character counter

---

## CSS Organization

### Global Styles

#### base.css
- Global layout
- Header/footer styling
- Navigation
- Flash messages
- Common utilities

**Key Styles:**
```css
/* Layout */
body {
    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    min-height: 100vh;
    display: flex;
    flex-direction: column;
}

main {
    flex: 1;
}

/* Header */
.navbar {
    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}

/* Flash messages */
.alert {
    border-left: 4px solid;
    animation: slideIn 0.3s ease-out;
}

@keyframes slideIn {
    from {
        transform: translateY(-20px);
        opacity: 0;
    }
    to {
        transform: translateY(0);
        opacity: 1;
    }
}

/* Buttons */
.btn {
    transition: all 0.2s;
}

.btn:hover {
    transform: translateY(-2px);
    box-shadow: 0 2px 8px rgba(0,0,0,0.15);
}
```

---

### Feature-Specific Styles

#### forms.css
- Form layouts
- Field styling
- Validation states
- Help text

#### cadeia_dominial_d3.css
- SVG styling
- Node styles
- Link styles
- Legend
- Controls

```css
#tree-svg {
    border: 1px solid #ddd;
    background: #fafafa;
    cursor: move;
}

.node rect {
    transition: fill 0.3s;
}

.node:hover rect {
    filter: brightness(1.1);
    cursor: pointer;
}

.link {
    fill: none;
    stroke: #999;
    stroke-width: 2;
}

.legend {
    position: absolute;
    top: 100px;
    right: 20px;
    background: white;
    padding: 15px;
    border: 1px solid #ddd;
    border-radius: 4px;
}
```

---

## JavaScript Organization

### 1. lancamento_form.js (Most Complex)
**Lines:** ~400
**Purpose:** Dynamic form behavior for transaction creation/editing

**Key Functions:**
- `updateFieldVisibility(tipo)` - Show/hide type-specific fields
- `updateRequiredFields(tipo)` - Mark fields as required/optional
- `validateForm()` - Client-side validation
- `checkDuplicate()` - AJAX duplicate check
- `initAutocomplete()` - Initialize autocomplete widgets
- `handleOrigemParsing()` - Parse origin text for document references

---

### 2. cadeia_dominial_d3.js (Largest)
**Lines:** ~600
**Purpose:** D3.js tree visualization

**Classes:**
- `CadeiaDominialTree` - Main tree rendering class

**Key Methods:**
- `init()` - Initialize SVG and layout
- `render()` - Render tree
- `drawNodes()` - Draw document nodes
- `drawLinks()` - Draw connections
- `handleNodeClick(d)` - Node interaction
- `zoomIn()`, `zoomOut()`, `resetZoom()` - Zoom controls

---

### 3. cartorio_verificacao.js
**Purpose:** Cartório verification and validation

**Functions:**
- `verificarCartorio(cidade, estado)` - Verify cartório exists
- `buscarCartorios(query)` - Search cartórios
- `validarCNS(cns)` - Validate CNS format

---

### 4. imovel_form.js
**Purpose:** Property form enhancements

**Functions:**
- `initCartorioAutocomplete()` - Setup autocomplete
- `validateMatricula()` - Validate matricula format

---

### 5. cadeia_dominial_tabela.js
**Purpose:** Table view interactivity

**Functions:**
- `applyFilters()` - Apply table filters
- `sortTable(column)` - Sort by column
- `toggleDocumento(id)` - Expand/collapse document group

---

### 6. cartorio_modal.js
**Purpose:** Cartório selection modal

**Functions:**
- `showCartorioModal()` - Display modal
- `selectCartorio(id)` - Select cartório from modal
- `filterCartorios(query)` - Filter modal list

---

### 7. origem_simples.js
**Purpose:** Simplified origin selection

**Functions:**
- `parseOrigem(text)` - Parse origin text
- `highlightMatches()` - Highlight found documents

---

## Bootstrap Components Used

- **Navbar** - Header navigation
- **Alerts** - Flash messages
- **Modals** - Dialogs (origin selection, cartório selection)
- **Forms** - Form controls and layout
- **Buttons** - Action buttons with various styles
- **Cards** - Content containers
- **Tables** - Data tables
- **Badges** - Labels and counts
- **Collapse** - Expandable sections
- **Tooltips** - Help text
- **Spinners** - Loading indicators

## Autocomplete Integration

Using `django-autocomplete-light` (DAL):

**HTML:**
```django
{{ form.media }}

<div class="form-group">
    <label for="{{ form.transmitente.id_for_label }}">Transmitente</label>
    {{ form.transmitente }}
</div>
```

**Form Field:**
```python
from dal import autocomplete

class LancamentoForm(forms.ModelForm):
    transmitente = forms.ModelChoiceField(
        queryset=Pessoas.objects.all(),
        widget=autocomplete.ModelSelect2(
            url='pessoa-autocomplete',
            attrs={'data-placeholder': 'Digite o nome...'}
        )
    )
```

**JavaScript:**
```javascript
// DAL automatically initializes Select2
// Custom configuration if needed:
$('#id_transmitente').on('select2:select', function(e) {
    const pessoa = e.params.data;
    console.log('Selected:', pessoa.text);
});
```

## Responsive Design

All templates use Bootstrap's responsive grid system:

```html
<div class="container-fluid">
    <div class="row">
        <div class="col-12 col-md-6 col-lg-4">
            <!-- Content -->
        </div>
    </div>
</div>
```

**Breakpoints:**
- `col-12` - Full width on mobile
- `col-md-6` - Half width on tablets
- `col-lg-4` - Third width on desktops

## Frontend Best Practices in This Project

1. **Component-Based Templates** - Reusable template fragments
2. **Vanilla JavaScript** - No jQuery dependency
3. **Progressive Enhancement** - Works without JavaScript, enhanced with it
4. **Accessibility** - Proper ARIA labels and keyboard navigation
5. **Performance** - Minimized DOM manipulation, efficient D3 rendering
6. **Separation of Concerns** - Logic in JS, presentation in templates
7. **Consistent Naming** - BEM-like CSS naming convention
8. **Mobile-First** - Responsive design from the start

## Asset Loading

**Development:**
```python
# settings.py
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
```

**Production:**
```python
# Collected with: python manage.py collectstatic
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'
```

## Browser Compatibility

- **Modern Browsers:** Chrome, Firefox, Safari, Edge (latest)
- **D3.js v7:** Requires modern JavaScript features
- **Bootstrap 5:** No IE11 support
- **CSS Grid/Flexbox:** Fully utilized

## Performance Optimizations

1. **Asset Minification** - CSS/JS minified in production
2. **Caching** - Static assets cached with WhiteNoise
3. **Lazy Loading** - Images and heavy components lazy-loaded
4. **Debounced Autocomplete** - 250ms delay to reduce requests
5. **Efficient D3 Rendering** - Only re-render changed nodes

## Future Frontend Enhancements

- [ ] Add print stylesheets for better printing
- [ ] Implement service worker for offline support
- [ ] Add more chart types (beyond D3 tree)
- [ ] Enhance mobile experience
- [ ] Add dark mode
- [ ] Implement real-time updates with WebSockets
