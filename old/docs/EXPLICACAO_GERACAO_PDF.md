# 📋 Explicação Detalhada da Geração de PDF - Cadeia Dominial

## 🔄 **Fluxo Completo de Geração do PDF**

### **1. Início do Processo**
```
Usuário clica no botão "Exportar PDF" 
    ↓
URL: /tis/{tis_id}/imovel/{imovel_id}/cadeia-tabela/pdf/
    ↓
View: exportar_cadeia_dominial_pdf()
```

### **2. View Principal (`exportar_cadeia_dominial_pdf`)**

```python
@login_required
def exportar_cadeia_dominial_pdf(request, tis_id, imovel_id):
    """
    Exporta a cadeia dominial em formato PDF
    """
    try:
        # 1. VALIDAÇÃO E BUSCA DE DADOS
        tis = get_object_or_404(TIs, id=tis_id)
        imovel = get_object_or_404(Imovel, id=imovel_id, terra_indigena_id=tis)
        
        # 2. OBTENÇÃO DOS DADOS DA CADEIA DOMINIAL
        service = CadeiaDominialTabelaService()
        context = service.get_cadeia_dominial_tabela(tis_id, imovel_id, request.session)
        
        # 3. ADIÇÃO DE ESTATÍSTICAS
        if context['cadeia']:
            context['estatisticas'] = service.get_estatisticas_cadeia(context['cadeia'])
        
        # 4. RENDERIZAÇÃO DO TEMPLATE HTML
        html_string = render_to_string('dominial/cadeia_dominial_pdf.html', context)
        
        # 5. CONFIGURAÇÃO DO CSS
        css_path = os.path.join(settings.STATIC_ROOT, 'dominial', 'css', 'cadeia_dominial_pdf.css')
        if not os.path.exists(css_path):
            css_path = os.path.join(settings.STATICFILES_DIRS[0], 'dominial', 'css', 'cadeia_dominial_pdf.css')
        
        # 6. GERAÇÃO DO PDF COM WEASYPRINT
        pdf = HTML(string=html_string, base_url=request.build_absolute_uri('/')).write_pdf(
            stylesheets=[css_path] if os.path.exists(css_path) else None
        )
        
        # 7. CONFIGURAÇÃO DA RESPOSTA HTTP
        response = HttpResponse(pdf, content_type='application/pdf')
        filename = f"cadeia_dominial_{imovel.matricula}_{date.today().strftime('%Y%m%d')}.pdf"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        return response
        
    except Exception as e:
        # 8. TRATAMENTO DE ERROS
        return HttpResponse(error_html, content_type='text/html')
```

## 📄 **Template HTML (`cadeia_dominial_pdf.html`)**

### **Estrutura do Template:**

```html
{# ===================================================== #}
{# TEMPLATE PARA GERAÇÃO DE PDF - CADEIA DOMINIAL      #}
{# ===================================================== #}

{# 1. CARREGAMENTO DE FILTROS E ESTÁTICOS #}
{% load dominial_extras %}  {# Filtros customizados (split, strip) #}
{% load static %}           {# Arquivos estáticos (CSS) #}

{# 2. CABEÇALHO HTML #}
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <title>Cadeia Dominial - {{ imovel.nome }}</title>
    <link rel="stylesheet" href="{% static 'dominial/css/cadeia_dominial_pdf.css' %}">
</head>

{# 3. ESTRUTURA DO CORPO #}
<body>
    {# 3.1 CABEÇALHO DO PDF #}
    <div class="header">
        <h1>RELATÓRIO DE CADEIA DOMINIAL</h1>
        <p><strong>Imóvel:</strong> {{ imovel.nome }} | <strong>Matrícula:</strong> {{ imovel.matricula }}</p>
        <p>Relatório gerado em {{ "now"|date:"d/m/Y H:i" }} | Sistema Cadeia Dominial</p>
    </div>

    {# 3.2 TABELA DE INFORMAÇÕES DO IMÓVEL #}
    <div class="imovel-info">
        <!-- Dados básicos do imóvel -->
    </div>

    {# 3.3 VERIFICAÇÕES DE DADOS #}
    {% if not cadeia %}
        <!-- Estado vazio: sem documentos -->
    {% elif not tem_lancamentos %}
        <!-- Estado vazio: sem lançamentos -->
    {% else %}
        {# 3.4 CONTEÚDO PRINCIPAL #}
        <h2>📊 Cronologia de Lançamentos</h2>
        
        {# 3.5 LOOP PRINCIPAL: DOCUMENTOS #}
        {% for item in cadeia %}
            {# 3.5.1 CABEÇALHO DE GRUPO DE IMPORTAÇÃO #}
            {% if item.is_importado and item.is_primeiro_grupo %}
                <!-- Informações de importação -->
            {% endif %}
            
            {# 3.5.2 SEÇÃO DE DOCUMENTO #}
            <div class="documento-section">
                {# 3.5.2.1 CABEÇALHO DO DOCUMENTO #}
                <div class="documento-header">
                    📄 {{ item.documento.tipo.get_tipo_display }}: {{ item.documento.numero }}
                    <!-- Badge para documentos importados -->
                </div>
                
                {# 3.5.2.2 TABELA DE LANÇAMENTOS #}
                {% if item.lancamentos %}
                <table class="lancamentos-table">
                    <thead>
                        <!-- Cabeçalho da tabela com agrupamentos -->
                    </thead>
                    <tbody>
                        {# 3.5.2.3 LOOP DOS LANÇAMENTOS #}
                        {% for lancamento in item.lancamentos %}
                        <tr class="{% cycle 'linha-par' 'linha-impar' %}">
                            {# COLUNAS DA MATRÍCULA #}
                            <td>{{ lancamento.numero_lancamento }}</td>
                            <td>{{ item.documento.livro|default_if_none:"-" }}</td>
                            <td>{{ item.documento.folha|default_if_none:"-" }}</td>
                            <td>{{ item.documento.cartorio.nome }}</td>
                            <td>{{ lancamento.data|date:'d/m/Y' }}</td>
                            
                            {# COLUNAS DE PESSOAS #}
                            <td>
                                {% for pessoa in lancamento.transmitentes.all %}
                                    {{ pessoa.pessoa.nome }}{% if not forloop.last %}, {% endif %}
                                {% empty %}-{% endfor %}
                            </td>
                            <td>
                                {% for pessoa in lancamento.adquirentes.all %}
                                    {{ pessoa.pessoa.nome }}{% if not forloop.last %}, {% endif %}
                                {% empty %}-{% endfor %}
                            </td>
                            
                            {# COLUNAS DA TRANSMISSÃO #}
                            {% if lancamento.tipo.tipo == 'averbacao' and item.documento.tipo.tipo != 'transcricao' %}
                                <td colspan="6">{{ lancamento.descricao|default_if_none:"-" }}</td>
                            {% else %}
                                <td>{{ lancamento.forma|default_if_none:"-" }}</td>
                                <td>{{ lancamento.titulo|default_if_none:"-" }}</td>
                                <td>{{ lancamento.cartorio_transmissao_compat.nome|default:"-" }}</td>
                                <td>{{ lancamento.livro_transacao|default_if_none:"-" }}</td>
                                <td>{{ lancamento.folha_transacao|default_if_none:"-" }}</td>
                                <td>{{ lancamento.data_transacao|date:'d/m/Y'|default:"-" }}</td>
                            {% endif %}
                            
                            {# COLUNAS ADICIONAIS #}
                            <td>{{ lancamento.area|default_if_none:"-" }}</td>
                            <td>
                                {% if lancamento.origem %}
                                    {% if ';' in lancamento.origem %}
                                        {% for origem in lancamento.origem|split:';' %}
                                            <div>{{ origem|strip }}</div>
                                        {% endfor %}
                                    {% else %}
                                        {{ lancamento.origem }}
                                    {% endif %}
                                {% else %}
                                    -
                                {% endif %}
                            </td>
                            <td>{{ lancamento.observacoes|default_if_none:"-" }}</td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
                {% endif %}
            </div>
        {% endfor %}
        
        {# 3.6 SEÇÃO DE ESTATÍSTICAS #}
        {% if estatisticas %}
        <div class="estatisticas">
            <!-- Estatísticas da cadeia dominial -->
        </div>
        {% endif %}
    {% endif %}
</body>
</html>
```

## 🎨 **CSS Específico para PDF (`cadeia_dominial_pdf.css`)**

### **Configurações Principais:**

```css
/* ===================================================== */
/* CONFIGURAÇÕES DA PÁGINA (FORMATO PAISAGEM)          */
/* ===================================================== */
@page {
    size: A4 landscape;        /* Formato paisagem para caber mais conteúdo */
    margin: 1.5cm;            /* Margens reduzidas */
    @top-center {
        content: "Cadeia Dominial";  /* Cabeçalho da página */
        font-size: 9pt;
        color: #666;
    }
    @bottom-center {
        content: "Página " counter(page) " de " counter(pages);  /* Numeração */
        font-size: 9pt;
        color: #666;
    }
}

/* ===================================================== */
/* ESTILOS DO CORPO                                     */
/* ===================================================== */
body {
    font-family: 'Arial', sans-serif;
    font-size: 8pt;           /* Fonte pequena para caber mais */
    line-height: 1.3;         /* Espaçamento compacto */
    color: #333;
    margin: 0;
    padding: 0;
}

/* ===================================================== */
/* CABEÇALHO DO PDF                                     */
/* ===================================================== */
.header {
    text-align: center;
    margin-bottom: 20px;
    border-bottom: 2px solid #2c5aa0;
    padding-bottom: 10px;
}

.header h1 {
    color: #2c5aa0;
    font-size: 18pt;
    margin: 0 0 10px 0;
}

/* ===================================================== */
/* TABELA DE INFORMAÇÕES DO IMÓVEL                     */
/* ===================================================== */
.imovel-info {
    display: table;
    width: 100%;
    margin-bottom: 20px;
    border: 1px solid #ddd;
    border-radius: 5px;
}

.imovel-info-row {
    display: table-row;
}

.imovel-info-cell {
    display: table-cell;
    padding: 8px;
    border-bottom: 1px solid #eee;
    vertical-align: top;
}

.imovel-info-cell:first-child {
    font-weight: bold;
    background-color: #f8f9fa;
    width: 30%;
}

/* ===================================================== */
/* SEÇÕES DE DOCUMENTOS                                 */
/* ===================================================== */
.documento-section {
    margin-bottom: 30px;
    page-break-inside: avoid;  /* Evita quebra de página no meio */
}

.documento-header {
    background-color: #e1edf7;
    padding: 10px;
    border-radius: 5px;
    margin-bottom: 10px;
    font-weight: bold;
    color: #2c5aa0;
}

.documento-importado {
    background-color: #fff3cd;
    border-left: 4px solid #ffc107;
}

/* ===================================================== */
/* TABELAS DE LANÇAMENTOS                               */
/* ===================================================== */
.lancamentos-table {
    width: 100%;
    border-collapse: collapse;
    margin-top: 8px;
    font-size: 6pt;           /* Fonte muito pequena para tabelas */
}

.lancamentos-table th {
    background-color: #f8f9fa;
    border: 1px solid #ddd;
    padding: 3px;             /* Padding reduzido */
    text-align: center;
    font-weight: bold;
    font-size: 6pt;
}

.lancamentos-table td {
    border: 1px solid #ddd;
    padding: 2px;             /* Padding reduzido */
    text-align: left;
    vertical-align: top;
}

.lancamentos-table .agrupamento {
    background-color: #e1edf7;
    font-weight: bold;
    text-align: center;
}

.linha-par {
    background-color: #f8f9fa;
}

.linha-impar {
    background-color: #ffffff;
}

/* ===================================================== */
/* CABEÇALHOS DE GRUPO DE IMPORTAÇÃO                   */
/* ===================================================== */
.grupo-importacao-header {
    background-color: #fff3cd;
    border: 1px solid #ffc107;
    padding: 8px;
    margin: 10px 0;
    border-radius: 5px;
    font-weight: bold;
    color: #856404;
}

/* ===================================================== */
/* SEÇÃO DE ESTATÍSTICAS                                */
/* ===================================================== */
.estatisticas {
    margin-top: 20px;
    padding: 15px;
    background-color: #f8f9fa;
    border-radius: 5px;
    border: 1px solid #ddd;
}

.estatisticas h3 {
    margin-top: 0;
    color: #2c5aa0;
    font-size: 12pt;
}

.estatisticas-grid {
    display: table;
    width: 100%;
}

.estatisticas-item {
    display: table-cell;
    padding: 5px;
    text-align: center;
}

.estatisticas-valor {
    font-size: 14pt;
    font-weight: bold;
    color: #2c5aa0;
}

.estatisticas-label {
    font-size: 8pt;
    color: #666;
}

/* ===================================================== */
/* ESTADOS VAZIOS                                       */
/* ===================================================== */
.empty-state {
    text-align: center;
    padding: 40px;
    color: #666;
}

/* ===================================================== */
/* CONTROLE DE QUEBRA DE PÁGINA                         */
/* ===================================================== */
.page-break {
    page-break-before: always;
}

@media print {
    .page-break {
        page-break-before: always;
    }
    
    .documento-section {
        page-break-inside: avoid;
    }
    
    .lancamentos-table {
        page-break-inside: avoid;
    }
}
```

## 🔧 **Componentes Técnicos**

### **1. WeasyPrint**
- **Biblioteca**: `weasyprint==62.2`
- **Função**: Converte HTML+CSS em PDF
- **Vantagens**: Preserva estilos CSS, suporta layouts complexos

### **2. Filtros Customizados (`dominial_extras`)**
```python
# Exemplo de filtros usados:
{{ lancamento.origem|split:';' }}  # Quebra string por ';'
{{ origem|strip }}                 # Remove espaços extras
```

### **3. Service Layer (`CadeiaDominialTabelaService`)**
- **Responsabilidade**: Buscar e organizar dados da cadeia dominial
- **Métodos principais**:
  - `get_cadeia_dominial_tabela()`: Dados principais
  - `get_estatisticas_cadeia()`: Estatísticas

### **4. Contexto Passado para o Template**
```python
context = {
    'tis': tis,                    # Terra Indígena
    'imovel': imovel,              # Imóvel específico
    'cadeia': cadeia,              # Lista de documentos/lançamentos
    'tem_lancamentos': True,       # Flag se há lançamentos
    'estatisticas': estatisticas,  # Dados estatísticos
}
```

## 🎯 **Características Especiais**

### **1. Formato Paisagem**
- **Objetivo**: Caber mais informações na página
- **Configuração**: `@page { size: A4 landscape; }`

### **2. Fontes Compactas**
- **Body**: 8pt
- **Tabelas**: 6pt
- **Objetivo**: Maximizar espaço para dados

### **3. Tratamento de Dados Importados**
- **Identificação**: `item.is_importado`
- **Visual**: Background amarelo, badge "📥 Importado"
- **Agrupamento**: Cabeçalhos especiais para grupos de importação

### **4. Lógica Condicional para Tipos de Documento**
```html
{% if lancamento.tipo.tipo == 'averbacao' and item.documento.tipo.tipo != 'transcricao' %}
    <!-- Para averbações: descrição em todas as colunas -->
    <td colspan="6">{{ lancamento.descricao }}</td>
{% else %}
    <!-- Para transcrições: dados detalhados -->
    <td>{{ lancamento.forma }}</td>
    <td>{{ lancamento.titulo }}</td>
    <!-- ... mais colunas ... -->
{% endif %}
```

### **5. Múltiplas Origens**
```html
{% if ';' in lancamento.origem %}
    {% for origem in lancamento.origem|split:';' %}
        <div>{{ origem|strip }}</div>
    {% endfor %}
{% else %}
    {{ lancamento.origem }}
{% endif %}
```

## 🚀 **Processo de Geração**

1. **Usuário clica** no botão "Exportar PDF"
2. **View é chamada** com parâmetros (tis_id, imovel_id)
3. **Dados são buscados** via service layer
4. **Template é renderizado** com contexto completo
5. **CSS é aplicado** para formatação específica
6. **WeasyPrint gera** o PDF final
7. **Arquivo é retornado** como download

## 📊 **Resultado Final**

O PDF gerado contém:
- ✅ **Cabeçalho** com informações do imóvel
- ✅ **Tabela de dados** do imóvel
- ✅ **Cronologia completa** de documentos e lançamentos
- ✅ **Identificação** de documentos importados
- ✅ **Estatísticas** da cadeia dominial
- ✅ **Formato paisagem** otimizado
- ✅ **Layout compacto** para máximo de informações
- ✅ **Adequado para uso jurídico**
