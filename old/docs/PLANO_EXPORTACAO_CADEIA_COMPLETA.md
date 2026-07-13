# 📋 Plano: Exportar Cadeia Completa

## 🎯 **Objetivo**
Criar um botão "Exportar Cadeia Completa" que gera um PDF com **todos os documentos** da cadeia dominial, organizados hierarquicamente, sem repetição.

## 🔄 **Diferenças do PDF Atual**

### **PDF Atual (Cadeia Visível)**
- ✅ Mostra apenas documentos visíveis na página
- ✅ Usa escolhas de origem da sessão do usuário
- ✅ Expande apenas uma origem por documento
- ✅ Baseado no tronco principal + importados escolhidos

### **PDF Cadeia Completa (Nova Funcionalidade)**
- ✅ Mostra **TODOS** os documentos da cadeia
- ✅ **Não usa** escolhas de sessão
- ✅ Expande **TODAS** as origens de cada documento
- ✅ Inclui **tronco principal + troncos secundários**
- ✅ Organização hierárquica completa

## 🏗️ **Arquitetura da Solução**

### **1. Novo Service: `CadeiaCompletaService`**
```python
# dominial/services/cadeia_completa_service.py
class CadeiaCompletaService:
    """
    Service para gerar a cadeia dominial completa
    """
    
    def get_cadeia_completa(self, tis_id, imovel_id):
        """
        Obtém TODOS os documentos da cadeia dominial organizados hierarquicamente
        """
        pass
    
    def _obter_tronco_principal_completo(self, imovel):
        """
        Obtém o tronco principal expandindo TODAS as origens
        """
        pass
    
    def _obter_troncos_secundarios_completos(self, imovel):
        """
        Obtém todos os troncos secundários expandindo TODAS as origens
        """
        pass
    
    def _expandir_todas_origens_documento(self, documento):
        """
        Expande todas as origens de um documento (não apenas uma)
        """
        pass
```

### **2. Nova View: `exportar_cadeia_completa_pdf`**
```python
# dominial/views/cadeia_dominial_views.py
@login_required
def exportar_cadeia_completa_pdf(request, tis_id, imovel_id):
    """
    Exporta a cadeia dominial COMPLETA em formato PDF
    """
    pass
```

### **3. Novo Template: `cadeia_completa_pdf.html`**
```html
<!-- templates/dominial/cadeia_completa_pdf.html -->
<!-- Template específico para cadeia completa -->
```

### **4. Novo CSS: `cadeia_completa_pdf.css`**
```css
/* static/dominial/css/cadeia_completa_pdf.css */
/* Estilos específicos para cadeia completa */
```

## 📋 **Plano de Implementação**

### **FASE 1: Service de Cadeia Completa**

#### **1.1 Criar `CadeiaCompletaService`**
```python
# dominial/services/cadeia_completa_service.py

class CadeiaCompletaService:
    def __init__(self):
        self.hierarquia_service = HierarquiaService()
    
    def get_cadeia_completa(self, tis_id, imovel_id):
        """
        Obtém a cadeia dominial completa organizada hierarquicamente
        """
        tis = get_object_or_404(TIs, id=tis_id)
        imovel = get_object_or_404(Imovel, id=imovel_id)
        
        # 1. Obter tronco principal completo
        tronco_principal = self._obter_tronco_principal_completo(imovel)
        
        # 2. Obter troncos secundários completos
        troncos_secundarios = self._obter_troncos_secundarios_completos(imovel)
        
        # 3. Organizar hierarquicamente
        cadeia_organizada = self._organizar_cadeia_hierarquica(
            tronco_principal, troncos_secundarios
        )
        
        return {
            'tis': tis,
            'imovel': imovel,
            'cadeia_completa': cadeia_organizada,
            'estatisticas': self._calcular_estatisticas_completas(cadeia_organizada)
        }
    
    def _obter_tronco_principal_completo(self, imovel):
        """
        Obtém o tronco principal expandindo TODAS as origens
        """
        # Usar HierarquiaArvoreService para obter todos os documentos
        from .hierarquia_arvore_service import HierarquiaArvoreService
        arvore = HierarquiaArvoreService.construir_arvore_cadeia_dominial(imovel)
        
        # Extrair todos os documentos da árvore
        todos_documentos = []
        for doc_node in arvore['documentos']:
            documento = Documento.objects.get(id=doc_node['id'])
            todos_documentos.append(documento)
        
        # Ordenar por data
        todos_documentos.sort(key=lambda x: x.data)
        
        # Expandir todas as origens de cada documento
        tronco_expandido = []
        documentos_processados = set()
        
        for documento in todos_documentos:
            if documento.id not in documentos_processados:
                tronco_expandido.append(documento)
                documentos_processados.add(documento.id)
                
                # Expandir todas as origens deste documento
                origens_expandidas = self._expandir_todas_origens_documento(documento)
                for origem in origens_expandidas:
                    if origem.id not in documentos_processados:
                        tronco_expandido.append(origem)
                        documentos_processados.add(origem.id)
        
        return tronco_expandido
    
    def _expandir_todas_origens_documento(self, documento):
        """
        Expande TODAS as origens de um documento (não apenas uma)
        """
        documentos_origem = []
        
        # Buscar lançamentos com origens
        lancamentos = documento.lancamentos.filter(
            origem__isnull=False
        ).exclude(origem='')
        
        for lancamento in lancamentos:
            if lancamento.origem:
                # Extrair todas as origens (separadas por ';')
                origens = [o.strip() for o in lancamento.origem.split(';') if o.strip()]
                
                for origem_numero in origens:
                    # Buscar documento de origem
                    doc_origem = Documento.objects.filter(
                        numero=origem_numero
                    ).select_related('cartorio', 'tipo').first()
                    
                    if doc_origem and doc_origem not in documentos_origem:
                        documentos_origem.append(doc_origem)
                        
                        # Recursivamente expandir origens deste documento
                        sub_origens = self._expandir_todas_origens_documento(doc_origem)
                        for sub_origem in sub_origens:
                            if sub_origem not in documentos_origem:
                                documentos_origem.append(sub_origem)
        
        return documentos_origem
    
    def _organizar_cadeia_hierarquica(self, tronco_principal, troncos_secundarios):
        """
        Organiza a cadeia em estrutura hierárquica para o template
        """
        cadeia_organizada = []
        
        # 1. Tronco Principal
        if tronco_principal:
            cadeia_organizada.append({
                'tipo': 'tronco_principal',
                'titulo': '🌳 TRONCO PRINCIPAL',
                'documentos': self._processar_documentos_para_template(tronco_principal)
            })
        
        # 2. Troncos Secundários
        for i, tronco in enumerate(troncos_secundarios, 1):
            if tronco:
                cadeia_organizada.append({
                    'tipo': 'tronco_secundario',
                    'titulo': f'🌿 TRONCO SECUNDÁRIO {i}',
                    'documentos': self._processar_documentos_para_template(tronco)
                })
        
        return cadeia_organizada
    
    def _processar_documentos_para_template(self, documentos):
        """
        Processa documentos para o formato do template
        """
        documentos_processados = []
        
        for documento in documentos:
            # Carregar lançamentos
            lancamentos = documento.lancamentos.select_related('tipo').prefetch_related(
                'pessoas__pessoa'
            ).order_by('id')
            
            # Verificar se é importado
            is_importado = documento.imovel != self.imovel_atual
            
            documentos_processados.append({
                'documento': documento,
                'lancamentos': lancamentos,
                'is_importado': is_importado,
                'origens_disponiveis': self._obter_origens_documento(documento)
            })
        
        return documentos_processados
    
    def _calcular_estatisticas_completas(self, cadeia_organizada):
        """
        Calcula estatísticas da cadeia completa
        """
        total_documentos = 0
        total_lancamentos = 0
        total_troncos = len(cadeia_organizada)
        documentos_importados = 0
        
        for tronco in cadeia_organizada:
            for item in tronco['documentos']:
                total_documentos += 1
                total_lancamentos += len(item['lancamentos'])
                if item['is_importado']:
                    documentos_importados += 1
        
        return {
            'total_documentos': total_documentos,
            'total_lancamentos': total_lancamentos,
            'total_troncos': total_troncos,
            'documentos_importados': documentos_importados,
            'percentual_importados': (documentos_importados / total_documentos * 100) if total_documentos > 0 else 0
        }
```

### **FASE 2: Nova View**

#### **2.1 Criar View `exportar_cadeia_completa_pdf`**
```python
# dominial/views/cadeia_dominial_views.py

@login_required
def exportar_cadeia_completa_pdf(request, tis_id, imovel_id):
    """
    Exporta a cadeia dominial COMPLETA em formato PDF
    """
    try:
        tis = get_object_or_404(TIs, id=tis_id)
        imovel = get_object_or_404(Imovel, id=imovel_id, terra_indigena_id=tis)
        
        # Obter dados da cadeia completa
        service = CadeiaCompletaService()
        context = service.get_cadeia_completa(tis_id, imovel_id)
        
        # Renderizar template HTML para PDF
        html_string = render_to_string('dominial/cadeia_completa_pdf.html', context)
        
        # Configurar CSS para PDF
        css_path = os.path.join(settings.STATIC_ROOT, 'dominial', 'css', 'cadeia_completa_pdf.css')
        if not os.path.exists(css_path):
            css_path = os.path.join(settings.STATICFILES_DIRS[0], 'dominial', 'css', 'cadeia_completa_pdf.css')
        
        # Gerar PDF
        pdf = HTML(string=html_string, base_url=request.build_absolute_uri('/')).write_pdf(
            stylesheets=[css_path] if os.path.exists(css_path) else None
        )
        
        # Configurar resposta HTTP
        response = HttpResponse(pdf, content_type='application/pdf')
        filename = f"cadeia_completa_{imovel.matricula}_{date.today().strftime('%Y%m%d')}.pdf"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        return response
        
    except Exception as e:
        # Em caso de erro, retornar uma página de erro simples
        error_html = f"""
        <html>
        <head><title>Erro na Geração do PDF</title></head>
        <body>
            <h1>Erro na Geração do PDF</h1>
            <p>Ocorreu um erro ao gerar o PDF da cadeia dominial completa.</p>
            <p>Erro: {str(e)}</p>
            <p><a href="javascript:history.back()">Voltar</a></p>
        </body>
        </html>
        """
        return HttpResponse(error_html, content_type='text/html')
```

### **FASE 3: URL e Template**

#### **3.1 Adicionar URL**
```python
# dominial/urls.py
path('tis/<int:tis_id>/imovel/<int:imovel_id>/cadeia-completa/pdf/', 
     exportar_cadeia_completa_pdf, 
     name='exportar_cadeia_completa_pdf'),
```

#### **3.2 Criar Template `cadeia_completa_pdf.html`**
```html
<!-- templates/dominial/cadeia_completa_pdf.html -->
{% load dominial_extras %}
{% load static %}

<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Cadeia Dominial Completa - {{ imovel.nome }}</title>
    <link rel="stylesheet" href="{% static 'dominial/css/cadeia_completa_pdf.css' %}">
</head>
<body>
    <div class="header">
        <h1>CADEIA DOMINIAL COMPLETA</h1>
        <p><strong>Imóvel:</strong> {{ imovel.nome }} | <strong>Matrícula:</strong> {{ imovel.matricula }}</p>
        <p>Relatório completo gerado em {{ "now"|date:"d/m/Y H:i" }} | Sistema Cadeia Dominial</p>
    </div>

    <div class="imovel-info">
        <!-- Informações do imóvel -->
    </div>

    {% if not cadeia_completa %}
        <div class="empty-state">
            <h3>Nenhum documento encontrado</h3>
            <p>Esta cadeia dominial ainda não possui documentos registrados.</p>
        </div>
    {% else %}
        {% for tronco in cadeia_completa %}
            <div class="tronco-section">
                <h2>{{ tronco.titulo }}</h2>
                
                {% for item in tronco.documentos %}
                    <div class="documento-section {% if item.is_importado %}documento-importado{% endif %}">
                        <div class="documento-header">
                            📄 {{ item.documento.tipo.get_tipo_display }}: {{ item.documento.numero }}
                            {% if item.is_importado %}
                                <span class="badge-importado">📥 Importado</span>
                            {% endif %}
                            <br>
                            <small>
                                Data: {{ item.documento.data|date:"d/m/Y" }} | 
                                Cartório: {{ item.documento.cartorio.nome }} | 
                                Lançamentos: {{ item.lancamentos.count }}
                            </small>
                        </div>
                        
                        {% if item.lancamentos %}
                        <table class="lancamentos-table">
                            <!-- Tabela de lançamentos -->
                        </table>
                        {% endif %}
                    </div>
                {% endfor %}
            </div>
        {% endfor %}
        
        {% if estatisticas %}
        <div class="estatisticas">
            <h3>📈 Estatísticas da Cadeia Completa</h3>
            <div class="estatisticas-grid">
                <div class="estatisticas-item">
                    <div class="estatisticas-valor">{{ estatisticas.total_documentos }}</div>
                    <div class="estatisticas-label">Documentos</div>
                </div>
                <div class="estatisticas-item">
                    <div class="estatisticas-valor">{{ estatisticas.total_lancamentos }}</div>
                    <div class="estatisticas-label">Lançamentos</div>
                </div>
                <div class="estatisticas-item">
                    <div class="estatisticas-valor">{{ estatisticas.total_troncos }}</div>
                    <div class="estatisticas-label">Troncos</div>
                </div>
                <div class="estatisticas-item">
                    <div class="estatisticas-valor">{{ estatisticas.documentos_importados }}</div>
                    <div class="estatisticas-label">Importados</div>
                </div>
            </div>
        </div>
        {% endif %}
    {% endif %}
</body>
</html>
```

### **FASE 4: CSS e Botão**

#### **4.1 Criar CSS `cadeia_completa_pdf.css`**
```css
/* static/dominial/css/cadeia_completa_pdf.css */

@page {
    size: A4 landscape;
    margin: 1.5cm;
    @top-center {
        content: "Cadeia Dominial Completa";
        font-size: 9pt;
        color: #666;
    }
    @bottom-center {
        content: "Página " counter(page) " de " counter(pages);
        font-size: 9pt;
        color: #666;
    }
}

body {
    font-family: 'Arial', sans-serif;
    font-size: 8pt;
    line-height: 1.3;
    color: #333;
    margin: 0;
    padding: 0;
}

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

.tronco-section {
    margin-bottom: 40px;
    page-break-inside: avoid;
}

.tronco-section h2 {
    background-color: #2c5aa0;
    color: white;
    padding: 10px;
    border-radius: 5px;
    font-size: 12pt;
    margin-bottom: 20px;
}

.documento-section {
    margin-bottom: 30px;
    page-break-inside: avoid;
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

.badge-importado {
    background-color: #ffc107;
    color: #856404;
    padding: 2px 6px;
    border-radius: 3px;
    font-size: 8pt;
    margin-left: 10px;
}

.lancamentos-table {
    width: 100%;
    border-collapse: collapse;
    margin-top: 8px;
    font-size: 6pt;
}

.lancamentos-table th {
    background-color: #f8f9fa;
    border: 1px solid #ddd;
    padding: 3px;
    text-align: center;
    font-weight: bold;
    font-size: 6pt;
}

.lancamentos-table td {
    border: 1px solid #ddd;
    padding: 2px;
    text-align: left;
    vertical-align: top;
}

.estatisticas {
    margin-top: 30px;
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
```

#### **4.2 Adicionar Botão na Interface**
```html
<!-- templates/dominial/cadeia_dominial_tabela.html -->
<!-- Adicionar após o botão "Voltar" -->

<div class="export-buttons">
    <a href="{% url 'exportar_cadeia_dominial_pdf' tis_id=tis.id imovel_id=imovel.id %}" 
       class="btn btn-success" target="_blank">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M14 2H6C5.46957 2 4.96086 2.21071 4.58579 2.58579C4.21071 2.96086 4 3.46957 4 4V20C4 20.5304 4.21071 21.0391 4.58579 21.4142C4.96086 21.7893 5.46957 22 6 22H18C18.5304 22 19.0391 21.7893 19.4142 21.4142C19.7893 21.0391 20 20.5304 20 20V8L14 2Z" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
            <path d="M14 2V8H20" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
            <path d="M16 13H8" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
            <path d="M16 17H8" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
            <path d="M10 9H8" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
        Exportar PDF (Visível)
    </a>
    
    <a href="{% url 'exportar_cadeia_completa_pdf' tis_id=tis.id imovel_id=imovel.id %}" 
       class="btn btn-primary" target="_blank">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M14 2H6C5.46957 2 4.96086 2.21071 4.58579 2.58579C4.21071 2.96086 4 3.46957 4 4V20C4 20.5304 4.21071 21.0391 4.58579 21.4142C4.96086 21.7893 5.46957 22 6 22H18C18.5304 22 19.0391 21.7893 19.4142 21.4142C19.7893 21.0391 20 20.5304 20 20V8L14 2Z" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
            <path d="M14 2V8H20" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
            <path d="M16 13H8" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
            <path d="M16 17H8" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
            <path d="M10 9H8" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
        Exportar Cadeia Completa
    </a>
    
    <button class="btn btn-secondary" onclick="limparEscolhas()">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M3 6H5H21" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
            <path d="M8 6V4C8 3.46957 8.21071 2.96086 8.58579 2.58579C8.96086 2.21071 9.46957 2 10 2H14C14.5304 2 15.0391 2.21071 15.4142 2.58579C15.7893 2.96086 16 3.46957 16 4V6M19 6V20C19 20.5304 18.7893 21.0391 18.4142 21.4142C18.0391 21.7893 17.5304 22 17 22H7C6.46957 22 5.96086 21.7893 5.58579 21.4142C5.21071 21.0391 5 20.5304 5 20V6H19Z" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
        Voltar
    </button>
</div>
```

## 🎯 **Características da Cadeia Completa**

### **1. Organização Hierárquica**
- **Tronco Principal**: Documentos principais do imóvel
- **Troncos Secundários**: Outras ramificações da cadeia
- **Todas as Origens**: Cada documento expande todas suas origens

### **2. Preferências de Ordenação**
- **Matrículas primeiro**: M999 > M888 > M777
- **Transcrições depois**: T999 > T888 > T777
- **Ordem cronológica**: Dentro de cada tipo

### **3. Sem Repetições**
- **Controle de documentos processados**: `set()` para evitar duplicatas
- **Verificação de IDs**: Não processa o mesmo documento duas vezes

### **4. Estatísticas Completas**
- **Total de documentos**: Todos os documentos da cadeia
- **Total de lançamentos**: Soma de todos os lançamentos
- **Total de troncos**: Quantidade de ramificações
- **Documentos importados**: Quantidade de documentos de outros imóveis

## 🚀 **Cronograma de Implementação**

### **Dia 1: Service e View**
- ✅ Criar `CadeiaCompletaService`
- ✅ Implementar `get_cadeia_completa()`
- ✅ Criar view `exportar_cadeia_completa_pdf`

### **Dia 2: Template e CSS**
- ✅ Criar template `cadeia_completa_pdf.html`
- ✅ Criar CSS `cadeia_completa_pdf.css`
- ✅ Adicionar URL

### **Dia 3: Interface e Testes**
- ✅ Adicionar botão na interface
- ✅ Testar funcionalidade
- ✅ Ajustar layout e formatação

## 🎯 **Resultado Esperado**

O usuário terá dois botões de exportação:

1. **"Exportar PDF (Visível)"**: PDF atual com documentos visíveis na página
2. **"Exportar Cadeia Completa"**: PDF completo com todos os documentos da cadeia

O PDF da cadeia completa será mais abrangente e adequado para análises jurídicas completas! 🎉
