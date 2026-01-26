# D3 Chain Visualization Flow

This document describes the complete flow for creating the "Árvore da Cadeia Dominial" (Ownership Chain Tree) visualization using D3.js.

## Overview

The system renders an interactive hierarchical tree showing the ownership chain of an immovable property (imovel). The tree displays documents (matrículas, transcrições) connected through their origins, with support for:

- Imported documents (from other properties)
- Shared documents (across multiple chains)
- End-of-chain markers (origem lídima, sem origem)
- Zoom/pan controls
- Click navigation to document details

## Architecture

```
User Request
    ↓
Django View (cadeia_dominial_arvore)
    ↓
HierarquiaArvoreService (builds tree structure)
    ↓
JSON Response (documentos + conexoes)
    ↓
JavaScript (converterParaArvoreD3)
    ↓
D3.js Rendering (renderArvoreD3)
    ↓
Interactive SVG Tree
```

---

## 1. URL Routing

**File:** `dominial/urls.py:42`

```python
path('cadeia-dominial/<int:tis_id>/<int:imovel_id>/arvore/',
     cadeia_dominial_arvore,
     name='cadeia_dominial_arvore')
```

- **URL Pattern:** `/cadeia-dominial/{tis_id}/{imovel_id}/arvore/`
- **View Function:** `cadeia_dominial_arvore` in `cadeia_dominial_views.py`
- **Returns:** JSON data for D3 rendering

---

## 2. Backend Views

### File: `dominial/views/cadeia_dominial_views.py`

#### `cadeia_dominial_d3(request, tis_id, imovel_id)` - Line 201

Renders the D3 template page.

```python
@login_required
def cadeia_dominial_d3(request, tis_id, imovel_id):
    """Nova visualização D3.js da árvore da cadeia dominial"""
    tis = get_object_or_404(TIs, id=tis_id)
    imovel = get_object_or_404(Imovel, id=imovel_id, terra_indigena_id=tis)
    documentos = Documento.objects.filter(imovel=imovel)\
        .select_related('cartorio', 'tipo')\
        .prefetch_related('lancamentos', 'lancamentos__tipo')\
        .order_by('data')
    # ... context setup
    return render(request, 'dominial/cadeia_dominial_d3.html', context)
```

#### `cadeia_dominial_arvore(request, tis_id, imovel_id)` - Line 58

**Main API endpoint** - Returns tree data as JSON.

```python
@login_required
def cadeia_dominial_arvore(request, tis_id, imovel_id):
    """Retorna os dados da cadeia dominial em formato de árvore para o diagrama"""
    try:
        tis = get_object_or_404(TIs, id=tis_id)
        imovel = get_object_or_404(Imovel, id=imovel_id, terra_indigena_id=tis)
        # Delegar a construção da árvore para um service/utilitário
        arvore = HierarquiaArvoreService.construir_arvore_cadeia_dominial(
            imovel, criar_documentos_automaticos=True
        )

        # Adicionar headers para evitar cache
        response = JsonResponse(arvore, safe=False)
        response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response['Pragma'] = 'no-cache'
        response['Expires'] = '0'
        return response
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({'error': str(e)}, status=500)
```

---

## 3. Backend Services

### File: `dominial/services/hierarquia_arvore_service.py`

This is the **core service** for building the tree structure.

#### `construir_arvore_cadeia_dominial(imovel, criar_documentos_automaticos=False)` - Line 21

Main entry point. Builds the complete tree structure.

```python
@staticmethod
def construir_arvore_cadeia_dominial(imovel, criar_documentos_automaticos=False):
    """
    Constrói a estrutura de árvore da cadeia dominial para visualização
    Lógica corrigida: filho -> pai (esquerda -> direita)
    """
    # 1. Identificar documento principal do imóvel
    documento_principal = HierarquiaArvoreService._identificar_documento_principal(imovel)

    if not documento_principal:
        return {
            'imovel': {...},
            'documentos': [],
            'origens_identificadas': [],
            'conexoes': [],
            'erro': 'Nenhum documento principal encontrado para este imóvel'
        }

    # 2. Construir árvore a partir do documento principal
    arvore = HierarquiaArvoreService._construir_arvore_a_partir_documento(
        documento_principal, imovel, criar_documentos_automaticos
    )

    return arvore
```

**Returns:**

```json
{
  "imovel": {
    "id": 1,
    "matricula": "6700",
    "nome": "Imóvel X",
    "proprietario": "Nome"
  },
  "documentos": [...],  // Array of document nodes
  "origens_identificadas": [...],
  "conexoes": [...]      // Array of {from, to, tipo}
}
```

#### `_identificar_documento_principal(imovel)` - Line 55

Finds the main document for the property.

```python
@staticmethod
def _identificar_documento_principal(imovel):
    """
    Identifica o documento principal do imóvel
    Prioridade: 1) Documento com número igual à matrícula, 2) Primeiro documento do imóvel
    """
    # Primeiro, tentar encontrar documento com número igual à matrícula
    documento_principal = Documento.objects.filter(
        imovel=imovel,
        numero=imovel.matricula
    ).first()

    if documento_principal:
        return documento_principal

    # Se não encontrar, tentar documento que contenha a matrícula
    documento_principal = Documento.objects.filter(
        imovel=imovel,
        numero__icontains=imovel.matricula
    ).first()

    if documento_principal:
        return documento_principal

    # Se não encontrar, usar o primeiro documento do imóvel
    documento_principal = Documento.objects.filter(imovel=imovel).first()

    return documento_principal
```

#### `_construir_arvore_a_partir_documento(documento_principal, imovel, criar_documentos_automaticos)` - Line 84

Builds the tree using BFS (Breadth-First Search).

```python
@staticmethod
def _construir_arvore_a_partir_documento(documento_principal, imovel, criar_documentos_automaticos):
    """
    Constrói a árvore a partir do documento principal
    """
    arvore = {
        'imovel': {...},
        'documentos': [],
        'origens_identificadas': [],
        'conexoes': []
    }

    documentos_processados = set()
    documentos_por_numero = {}
    fila = deque([(documento_principal, 0)])  # (documento, nível)

    while fila:
        documento_atual, nivel = fila.popleft()

        if documento_atual.id in documentos_processados:
            continue

        documentos_processados.add(documento_atual.id)

        # Criar nó do documento
        doc_node = HierarquiaArvoreService._criar_no_documento(
            documento_atual, imovel, nivel
        )
        documentos_por_numero[documento_atual.numero] = doc_node
        arvore['documentos'].append(doc_node)

        # Buscar documentos pais (origens) deste documento
        documentos_pais = HierarquiaArvoreService._buscar_documentos_pais(
            documento_atual, imovel, criar_documentos_automaticos
        )

        # Adicionar conexões diretas e documentos pais à fila
        for doc_pai in documentos_pais:
            conexao = {
                'from': documento_atual.numero,   # filho
                'to': doc_pai.numero,             # pai
                'tipo': 'origem_lancamento'
            }

            if not any(c['from'] == documento_atual.numero and c['to'] == doc_pai.numero
                      for c in arvore['conexoes']):
                arvore['conexoes'].append(conexao)

            if doc_pai.id not in documentos_processados:
                fila.append((doc_pai, nivel + 1))

    # Recalcular níveis baseado na hierarquia real
    HierarquiaArvoreService._recalcular_niveis(arvore, documento_principal.numero)

    return arvore
```

**Logic:** `from` = child, `to` = parent (esquerda -> direita)

#### `_buscar_documentos_pais(documento, imovel, criar_documentos_automaticos)` - Line 150

Finds parent documents by parsing the `origem` field of lançamentos.

```python
@staticmethod
def _buscar_documentos_pais(documento, imovel, criar_documentos_automaticos):
    """
    Busca documentos pais (origens) de um documento
    """
    documentos_pais = []
    documentos_processados = set()

    # Buscar lançamentos com origens
    lancamentos = documento.lancamentos.filter(
        origem__isnull=False
    ).exclude(origem='')

    for lancamento in lancamentos:
        # Extrair origens do lançamento (formato: "M123, T456")
        origens = re.findall(r'[MT]\d+', lancamento.origem)

        for origem_numero in origens:
            if origem_numero in documentos_processados:
                continue

            documentos_processados.add(origem_numero)

            # Buscar documento com este número
            doc_pai = Documento.objects.filter(numero=origem_numero).first()

            if doc_pai:
                documentos_pais.append(doc_pai)
            elif criar_documentos_automaticos:
                # Criar documento automaticamente se solicitado
                doc_pai = HierarquiaArvoreService._criar_documento_automatico(
                    origem_numero, imovel
                )
                if doc_pai:
                    documentos_pais.append(doc_pai)

    return documentos_pais
```

#### `_criar_no_documento(documento, imovel_atual, nivel)` - Line 254

Creates a node dictionary for a document.

```python
@staticmethod
def _criar_no_documento(documento, imovel_atual, nivel):
    """
    Cria um nó de documento para a árvore
    """
    is_documento_atual = documento.imovel.id == imovel_atual.id
    is_compartilhado = not is_documento_atual

    return {
        'id': documento.id,
        'numero': documento.numero,
        'tipo': documento.tipo.tipo,
        'tipo_display': documento.tipo.get_tipo_display(),
        'tipo_documento': documento.tipo.tipo,
        'data': documento.data.strftime('%d/%m/%Y'),
        'cartorio': documento.cartorio.nome,
        'livro': documento.livro,
        'folha': documento.folha,
        'origem': documento.origem or '',
        'observacoes': documento.observacoes or '',
        'total_lancamentos': documento.lancamentos.count(),
        'x': 0,  # Posição X (será calculada pelo frontend)
        'y': 0,  # Posição Y (será calculada pelo frontend)
        'nivel': nivel,
        'nivel_manual': documento.nivel_manual,
        'is_importado': False,
        'is_compartilhado': is_compartilhado,
        'is_documento_atual': is_documento_principal,
        'imoveis_compartilhando': [],
        'info_importacao': '',
        'tooltip_importacao': '',
        'cadeias_dominiais': [],
        'total_cadeias': 0
    }
```

#### `_recalcular_niveis(arvore, documento_principal_numero)` - Line 298

Recalculates levels based on actual hierarchy.

```python
@staticmethod
def _recalcular_niveis(arvore, documento_principal_numero):
    """
    Recalcula níveis baseado na hierarquia real
    Mantém apenas conexões diretas pai-filho
    """
    # Mapear conexões diretas
    filhos_por_pai = {}  # pai -> [filhos]
    pais_por_filho = {}  # filho -> [pais]

    for conexao in arvore['conexoes']:
        filho = conexao['from']
        pai = conexao['to']

        if pai not in filhos_por_pai:
            filhos_por_pai[pai] = []
        filhos_por_pai[pai].append(filho)

        if filho not in pais_por_filho:
            pais_por_filho[filho] = []
        pais_por_filho[filho].append(pai)

    # Calcular níveis usando busca em largura
    niveis = {}
    fila = deque([(documento_principal_numero, 0)])
    visitados = set()

    while fila:
        doc_numero, nivel = fila.popleft()

        if doc_numero in visitados:
            continue
        visitados.add(doc_numero)

        niveis[doc_numero] = nivel

        # Adicionar pais diretos à fila (nível + 1)
        if doc_numero in pais_por_filho:
            for pai in pais_por_filho[doc_numero]:
                if pai not in visitados:
                    fila.append((pai, nivel + 1))

    # Aplicar níveis aos documentos
    for doc_node in arvore['documentos']:
        nivel_calculado = niveis.get(doc_node['numero'], 0)
        doc_node['nivel'] = doc_node['nivel_manual'] if doc_node['nivel_manual'] is not None else nivel_calculado
```

---

## 4. Frontend JavaScript

### File: `static/dominial/js/cadeia_dominial_d3.js`

#### Main Entry Point - `DOMContentLoaded` - Line 69

Initializes the D3 visualization.

```javascript
document.addEventListener("DOMContentLoaded", function () {
  const svg = d3.select("#arvore-d3-svg");
  const containerWidth =
    document.getElementById("arvore-d3-svg").clientWidth || 1000;
  const width = Math.max(containerWidth, 2000); // Allow wider for extensive trees
  const height = 600;
  svg.attr("width", width).attr("height", height);

  // Create zoom group
  const zoomGroup = svg.append("g").attr("id", "zoom-group");

  // Setup zoom/pan behavior
  const zoom = d3
    .zoom()
    .scaleExtent([0.2, 3.0])
    .wheelDelta((event) => -event.deltaY * 0.002)
    .on("zoom", (event) => {
      zoomGroup.attr("transform", event.transform);
      window._zoomTransform = event.transform;
    });
  svg.call(zoom);

  // Store references globally
  window._d3zoom = zoom;
  window._d3svg = svg;
  window._zoomGroup = zoomGroup;
  window._zoomTransform = d3.zoomIdentity;

  // Fetch tree data
  fetch(
    `/dominial/cadeia-dominial/${window.tisId}/${window.imovelId}/arvore/?t=${timestamp}`,
  )
    .then((response) => response.json())
    .then((data) => {
      const arvore = converterParaArvoreD3(data);
      renderArvoreD3(arvore, zoomGroup, width, height);
      // Frame tree after rendering
      setTimeout(
        () => enquadrarArvoreNoSVG(svg, zoomGroup, width, height),
        100,
      );
    });
});
```

#### `converterParaArvoreD3(data)` - Line 179

Converts flat document/connection data into a hierarchical tree structure for D3.

```javascript
function converterParaArvoreD3(data) {
  // Mapear documentos por número
  const docMap = {};
  data.documentos.forEach((doc) => {
    doc.children = [];
    docMap[doc.numero] = doc;
  });

  // Encontrar a matrícula principal (raiz)
  let raiz = data.documentos.find(
    (doc) => doc.nivel === 0 || doc.origem === "" || doc.origem == null,
  );
  if (!raiz) raiz = data.documentos[0];

  // Build tree without duplication
  const visitados = new Set();

  function construirArvoreSimples(node) {
    if (!node || visitados.has(node.numero)) {
      return;
    }

    visitados.add(node.numero);

    // Buscar filhos deste nó nas conexões (from = filho, to = pai)
    const filhos = data.conexoes
      .filter((con) => con.from === node.numero)
      .map((con) => docMap[con.to])
      .filter((doc) => doc);

    filhos.forEach((filho) => {
      if (!visitados.has(filho.numero)) {
        node.children.push(filho);
        construirArvoreSimples(filho);
      }
    });
  }

  construirArvoreSimples(raiz);

  // Create secondary connections for imported docs
  const conexoesSecundarias = [];
  data.conexoes.forEach((conexao) => {
    const pai = docMap[conexao.to];
    const filho = docMap[conexao.from];

    if (pai && filho) {
      // Check if connection already represented
      if (!verificarConexaoExiste(raiz, conexao.from, conexao.to)) {
        conexoesSecundarias.push({
          from: conexao.from,
          to: conexao.to,
          tipo: "conexao_secundaria",
        });
      }
    }
  });

  raiz.conexoesExtras = conexoesSecundarias;

  // Sort children by document number (descending)
  ordenarFilhosPorNumeroDesc(raiz);

  return raiz;
}
```

#### `renderArvoreD3(data, svgGroup, width, height)` - Line 547

**Main rendering function** - Renders the D3 tree visualization.

```javascript
function renderArvoreD3(data, svgGroup, width, height) {
  // Convert to d3.hierarchy
  const root = d3.hierarchy(data);

  // Setup tree layout (horizontal orientation)
  const treeLayout = d3
    .tree()
    .size([height, width - 20])
    .nodeSize([80, 200]) // [height, width] - 200px between levels
    .separation((a, b) => {
      const irmaos = a.parent ? a.parent.children.length : 1;
      let separacaoBase = 2.0;
      if (irmaos > 15) separacaoBase = 4.0;
      else if (irmaos > 10) separacaoBase = 3.5;
      else if (irmaos > 6) separacaoBase = 3.0;
      else if (irmaos > 3) separacaoBase = 2.5;
      return separacaoBase;
    });

  treeLayout(root);

  // Apply positioning based on backend level
  ajustarPosicoesPorNivel(root);

  // Fix overlaps
  corrigirSobreposicoes(root);

  // Draw links (connections)
  const links = svgGroup
    .selectAll("path.link")
    .data(root.links(), (d) => d.target.id)
    .join("path")
    .attr("class", "link")
    .attr("fill", "none")
    .attr("stroke", "#28a745")
    .attr("stroke-width", 2)
    .attr("stroke-linecap", "round")
    .attr(
      "d",
      d3
        .linkHorizontal()
        .x((d) => d.y + 120)
        .y((d) => d.x + 20),
    );

  // Draw nodes (cards)
  const node = svgGroup
    .selectAll("g.node")
    .data(root.descendants(), (d) => d.id)
    .join("g")
    .attr("class", "node")
    .attr("transform", (d) => `translate(${d.y + 120},${d.x + 20})`);

  // Add card rectangles
  node
    .append("rect")
    .attr("width", 140)
    .attr("height", 80)
    .attr("x", -70)
    .attr("y", -40)
    .attr("rx", 12)
    .attr("fill", (d) => {
      if (d.data.is_fim_cadeia) {
        return d.data.classificacao_fim_cadeia === "origem_lidima"
          ? "#28a745" // Green for valid origin
          : "#dc3545"; // Red for no origin
      }
      if (d.data.tipo_documento === "transcricao") {
        return "#6f42c1"; // Purple for transcription
      }
      return "#007bff"; // Blue for registration
    })
    .attr("stroke", (d) => {
      if (d.data.is_importado) return "#ff8c00"; // Orange for imported
      if (d.data.is_compartilhado) return "#28a745"; // Green for shared
      return "#0056b3";
    })
    .attr("stroke-dasharray", (d) => {
      if (d.data.is_importado || d.data.is_compartilhado) return "5,5";
      return "none";
    });

  // Add document number
  node
    .append("text")
    .attr("text-anchor", "middle")
    .attr("y", -6)
    .attr("fill", "white")
    .attr("font-size", 20)
    .attr("font-weight", 700)
    .text((d) => d.data.numero || "FIM");

  // Add badge for imported docs
  node
    .filter((d) => d.data.is_importado)
    .append("circle")
    .attr("cx", 55)
    .attr("cy", -25)
    .attr("r", 8)
    .attr("fill", "#ff8c00");

  node
    .filter((d) => d.data.is_importado)
    .append("text")
    .attr("x", 55)
    .attr("y", -21)
    .attr("text-anchor", "middle")
    .attr("fill", "white")
    .attr("font-size", 10)
    .attr("font-weight", "bold")
    .text("✓");

  // Add click handler for navigation
  node.select("rect").on("click", (event, d) => {
    if (!d.data.is_fim_cadeia) {
      window.location.href = `/dominial/tis/${window.tisId}/imovel/${window.imovelId}/documento/${d.data.id}/detalhado/`;
    }
  });
}
```

#### Positioning Functions

| Function                          | Line | Purpose                                        |
| --------------------------------- | ---- | ---------------------------------------------- |
| `ajustarPosicoesPorNivel()`       | 478  | Positions nodes based on backend `nivel` field |
| `corrigirSobreposicoes()`         | 420  | Fixes overlaps at each depth level             |
| `aplicarEspacamentoAdicional()`   | 496  | Extra spacing for levels with imported docs    |
| `calcularEspacamentoAdaptativo()` | 366  | Calculates spacing based on node count         |

#### Zoom Controls

| Function           | Line | Purpose                |
| ------------------ | ---- | ---------------------- |
| `zoomIn()`         | 999  | Zoom in (1.2x)         |
| `zoomOut()`        | 1006 | Zoom out (0.8x)        |
| `resetZoom()`      | 1013 | Reset to fit all nodes |
| `fimDaArvore()`    | 1060 | Focus on last level    |
| `expandirArvore()` | 18   | Fit tree to viewport   |

---

## 5. Templates

### File: `templates/dominial/cadeia_dominial_d3.html`

```html
{% extends "base.html" %} {% load static %} {% block extra_css %}
<link
  rel="stylesheet"
  href="{% static 'dominial/css/cadeia_dominial_d3.css' %}"
/>
{% endblock %} {% block content %}
<div class="arvore-container">
  <!-- Zoom controls -->
  <div class="zoom-controls">
    <button onclick="zoomIn()">+</button>
    <button onclick="zoomOut()">-</button>
    <button onclick="resetZoom()">Reset</button>
    <button onclick="window.fimDaArvore()">Fim</button>
  </div>

  <!-- SVG container -->
  <svg id="arvore-d3-svg" width="100%" height="600"></svg>
</div>
{% endblock %} {% block extra_js %}
<script src="https://d3js.org/d3.v7.min.js"></script>
<script>
  window.tisId = {{ tis.id|safe }};
  window.imovelId = {{ imovel.id|safe }};
</script>
<script src="{% static 'dominial/js/cadeia_dominial_d3.js' %}"></script>
{% endblock %}
```

---

## 6. Data Structure

### API Response (JSON)

```json
{
  "imovel": {
    "id": 1,
    "matricula": "6700",
    "nome": "Imóvel X",
    "proprietario": "Nome do Proprietário"
  },
  "documentos": [
    {
      "id": 1,
      "numero": "M6700",
      "tipo": "matricula",
      "tipo_display": "Matrícula",
      "tipo_documento": "matricula",
      "data": "15/03/2000",
      "cartorio": "Cartório de Registro X",
      "livro": "123",
      "folha": "45",
      "origem": "",
      "total_lancamentos": 3,
      "nivel": 0,
      "nivel_manual": null,
      "is_importado": false,
      "is_compartilhado": false,
      "is_fim_cadeia": false,
      "classificacao_fim_cadeia": null
    },
    {
      "id": 2,
      "numero": "M6500",
      "tipo": "matricula",
      "tipo_display": "Matrícula",
      "data": "10/01/1995",
      "cartorio": "Cartório Y",
      "livro": "100",
      "folha": "20",
      "origem": "M6700",
      "total_lancamentos": 2,
      "nivel": 1,
      "is_importado": false,
      "is_compartilhado": false
    }
  ],
  "conexoes": [
    {
      "from": "M6700",
      "to": "M6500",
      "tipo": "origem_lancamento"
    }
  ],
  "origens_identificadas": []
}
```

### Node Colors

| Type          | Color              | Description                   |
| ------------- | ------------------ | ----------------------------- |
| Matrícula     | `#007bff` (Blue)   | Regular registration          |
| Transcrição   | `#6f42c1` (Purple) | Transcription document        |
| Origem Lídima | `#28a745` (Green)  | Valid end of chain            |
| Sem Origem    | `#dc3545` (Red)    | Invalid/no origin end         |
| Importado     | Orange border      | Document from other property  |
| Compartilhado | Green border       | Document shared across chains |

---

## 7. Related Files Summary

### Backend Files

| File                                             | Purpose                 |
| ------------------------------------------------ | ----------------------- |
| `dominial/urls.py`                               | URL routing             |
| `dominial/views/cadeia_dominial_views.py`        | View functions          |
| `dominial/services/hierarquia_arvore_service.py` | Tree construction       |
| `dominial/services/hierarquia_service.py`        | Hierarchical operations |

### Frontend Files

| File                                         | Purpose          |
| -------------------------------------------- | ---------------- |
| `static/dominial/js/cadeia_dominial_d3.js`   | D3 visualization |
| `static/dominial/css/cadeia_dominial_d3.css` | Tree styling     |
| `templates/dominial/cadeia_dominial_d3.html` | Main template    |

---

## 8. Key Algorithms

### Breadth-First Search (BFS) for Tree Construction

The tree is built using BFS starting from the main document:

```
1. Start with documento_principal (level 0)
2. For each document:
   a. Find its parents via lancamento.origem field
   b. Create connections (child → parent)
   c. Add unprocessed parents to queue with level + 1
3. Recalculate levels based on hierarchy
```

### Overlap Correction

```javascript
function corrigirSobreposicoes(root) {
  // Group nodes by depth level
  const niveis = {};
  root.descendants().forEach((node) => {
    if (!niveis[node.depth]) niveis[node.depth] = [];
    niveis[node.depth].push(node);
  });

  // For each level, fix overlaps
  Object.keys(niveis).forEach((depth) => {
    const nosNivel = niveis[depth];
    if (nosNivel.length > 1) {
      nosNivel.sort((a, b) => a.x - b.x);

      const espacamentoMinimo = 120; // Minimum spacing

      // Check for overlaps
      let temSobreposicao = false;
      for (let i = 0; i < nosNivel.length - 1; i++) {
        const distancia = Math.abs(nosNivel[i + 1].x - nosNivel[i].x);
        if (distancia < espacamentoMinimo) {
          temSobreposicao = true;
          break;
        }
      }

      // Fix overlaps if found
      if (temSobreposicao) {
        const larguraTotal = (nosNivel.length - 1) * espacamentoMinimo;
        const inicio = nosNivel[0].x - larguraTotal / 2;

        nosNivel.forEach((node, index) => {
          node.x = inicio + index * espacamentoMinimo;
        });
      }
    }
  });
}
```

---

## 9. Troubleshooting

### Common Issues

| Issue                     | Cause                        | Solution                                                |
| ------------------------- | ---------------------------- | ------------------------------------------------------- |
| Tree not rendering        | No main document found       | Check if document with número = matrícula exists        |
| Missing connections       | Empty origem field           | Ensure lançamentos have origem populated                |
| Overlapping nodes         | Too many nodes at same level | Increase `espacamentoMinimo` in `corrigirSobreposicoes` |
| Wrong level ordering      | Out of order documents       | Check `ordenarFilhosPorNumeroDesc` function             |
| Imported docs not showing | Cross-property documents     | Verify `DocumentoImportado` model is populated          |

### Debug Mode

Enable debug logging by checking browser console:

```javascript
// In converterParaArvoreD3:
console.log(
  `DEBUG: Iniciando conversão - Backend enviou ${data.documentos.length} documentos únicos`,
);
console.log(`DEBUG: Raiz identificada: ${raiz.numero}`);
```

---

## 10. Future Improvements

- [ ] Add lazy loading for large trees
- [ ] Implement search/filter functionality
- [ ] Add export to PDF/PNG
- [ ] Support for drag-and-drop reordering
- [ ] Animation controls for tree expansion
- [ ] Multiple tree layout options (radial, cluster, etc.)
