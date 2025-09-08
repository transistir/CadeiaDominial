# 📋 Plano de Trabalho - 17 Melhorias do Sistema Cadeia Dominial

## 🎯 **Visão Geral**
Este documento apresenta um plano estruturado para implementar as 17 melhorias solicitadas pelo usuário, organizadas por prioridade e similaridade para otimizar o desenvolvimento.

## 📊 **Análise das Necessidades**

### **1. Melhorias de UX/Interface (Prioridade ALTA)**
- **1.1** Toggle para origens (M/T) em vez de digitação manual
- **1.2** Campo específico para matrícula/transcrição no cadastro de imóvel
- **1.3** Sugestão automática do cartório mais recente nos lançamentos
- **1.4** Ordenação dos imóveis por mais recentes
- **1.5** Navegação com TAB entre transmitente e adquirente
- **1.6** Reorganização dos lançamentos por número
- **1.7** Visualização da árvore completa ao abrir
- **1.8** Campos de origem sempre após outros campos e antes das observações

### **2. Melhorias de Funcionalidade (Prioridade MÉDIA)**
- **2.1** Impressão da árvore
- **2.2** Melhor diagramação do PDF para cadeias longas
- **2.3** Sistema de alertas por palavras-chave nas observações
- **2.4** Correção do espaço na sigla no PDF
- **2.5** Retorno automático para árvore quando lançamento chega no início da matrícula
- **2.6** Conversão de vírgula por ponto no campo área
- **2.7** Visualização de lançamentos anteriores durante cadastro
- **2.8** Conversão automática de imóvel modificado para atual
- **2.9** Remoção do destaque "importado" do PDF

## 🏗️ **Plano de Implementação**

### **FASE 1: Melhorias de UX/Interface (Semana 1-2)**

#### **1.1 Toggle para Origem (M/T)**
**Arquivos a modificar:**
- `templates/dominial/components/_lancamento_inicio_matricula_form.html`
- `static/dominial/js/lancamento_form.js`
- `dominial/services/lancamento_form_service.py`

**Implementação:**
```html
<!-- Substituir campo de texto por toggle -->
<div class="form-group">
    <label>Tipo de Origem</label>
    <div class="toggle-origem">
        <input type="radio" name="tipo_origem" value="M" id="origem_matricula">
        <label for="origem_matricula">Matrícula (M)</label>
        <input type="radio" name="tipo_origem" value="T" id="origem_transcricao">
        <label for="origem_transcricao">Transcrição (T)</label>
    </div>
    <input type="text" name="numero_origem" placeholder="Número da origem">
</div>
```

#### **1.2 Campo Matrícula/Transcrição no Cadastro de Imóvel**
**Arquivos a modificar:**
- `dominial/models/imovel_models.py`
- `dominial/forms.py`
- `templates/dominial/imovel_form.html`

**Implementação:**
```python
# Adicionar campo ao modelo
class Imovel(models.Model):
    # ... campos existentes ...
    tipo_documento_principal = models.CharField(
        max_length=20,
        choices=[('matricula', 'Matrícula'), ('transcricao', 'Transcrição')],
        default='matricula'
    )
```

#### **1.3 Sugestão Automática do Cartório Mais Recente**
**Arquivos a modificar:**
- `dominial/views/lancamento_views.py`
- `dominial/services/lancamento_service.py`

**Implementação:**
```python
def obter_cartorio_sugerido(imovel):
    """Obtém o cartório mais recente dos lançamentos do imóvel"""
    ultimo_lancamento = Lancamento.objects.filter(
        documento__imovel=imovel
    ).order_by('-data').first()
    
    if ultimo_lancamento:
        return ultimo_lancamento.cartorio_origem or ultimo_lancamento.cartorio_transacao
    return imovel.cartorio
```

#### **1.4 Ordenação dos Imóveis por Mais Recentes**
**Arquivos a modificar:**
- `dominial/views/imovel_views.py`
- `dominial/models/imovel_models.py`

**Implementação:**
```python
# No Meta do modelo Imovel
class Meta:
    ordering = ['-data_cadastro', 'nome']
```

#### **1.5 Navegação com TAB**
**Arquivos a modificar:**
- `templates/dominial/components/_lancamento_registro_form.html`
- `static/dominial/js/lancamento_form.js`

**Implementação:**
```javascript
// Adicionar tabindex nos campos
document.querySelectorAll('input[name*="transmitente"], input[name*="adquirente"]')
    .forEach((input, index) => {
        input.setAttribute('tabindex', index + 1);
    });
```

#### **1.6 Reorganização dos Lançamentos por Número**
**Arquivos a modificar:**
- `dominial/models/lancamento_models.py`
- `dominial/views/documento_views.py`

**Implementação:**
```python
# No Meta do modelo Lancamento
class Meta:
    ordering = ['numero_lancamento', 'data']
```

#### **1.7 Visualização da Árvore Completa**
**Arquivos a modificar:**
- `templates/dominial/cadeia_dominial_arvore.html`
- `static/dominial/js/cadeia_dominial_d3.js`

**Implementação:**
```javascript
// Modificar para mostrar árvore completa por padrão
function inicializarArvore() {
    // Expandir todos os nós automaticamente
    expandirTodosNos();
    // Centralizar a árvore
    centralizarArvore();
}
```

#### **1.8 Reorganização dos Campos de Origem**
**Arquivos a modificar:**
- `templates/dominial/lancamento_form.html`
- `templates/dominial/components/_lancamento_inicio_matricula_form.html`

**Implementação:**
```html
<!-- Mover campos de origem para depois dos outros campos -->
<div class="field-group">
    <!-- Campos de transação primeiro -->
    <!-- Campos de origem depois -->
    <!-- Observações por último -->
</div>
```

### **FASE 2: Melhorias de Funcionalidade (Semana 3-4)**

#### **2.1 Impressão da Árvore**
**Arquivos a modificar:**
- `templates/dominial/cadeia_dominial_arvore.html`
- `static/dominial/css/cadeia_dominial_arvore.css`
- `dominial/views/cadeia_dominial_views.py`

**Implementação:**
```html
<!-- Adicionar botão de impressão -->
<button onclick="imprimirArvore()" class="btn btn-primary">
    <i class="fas fa-print"></i> Imprimir Árvore
</button>
```

```css
/* CSS para impressão */
@media print {
    .no-print { display: none; }
    .arvore-container { 
        width: 100% !important;
        height: auto !important;
    }
}
```

#### **2.2 Melhor Diagramação do PDF para Cadeias Longas**
**Arquivos a modificar:**
- `templates/dominial/cadeia_dominial_pdf.html`
- `static/dominial/css/cadeia_dominial_pdf.css`
- `templates/dominial/cadeia_completa_pdf.html`

**Implementação:**
```css
/* Melhorar layout para cadeias longas */
.documento-item {
    page-break-inside: avoid;
    margin-bottom: 1em;
}

.lancamento-item {
    font-size: 0.9em;
    margin-left: 1em;
}

/* Quebra de página inteligente */
@media print {
    .documento-item:nth-child(5n) {
        page-break-before: auto;
    }
}
```

#### **2.3 Sistema de Alertas por Palavras-Chave**
**Arquivos a modificar:**
- `dominial/models/lancamento_models.py`
- `templates/dominial/components/_observacoes_form.html`
- `static/dominial/js/lancamento_form.js`

**Implementação:**
```python
# Adicionar campo para alertas
class Lancamento(models.Model):
    # ... campos existentes ...
    alerta_observacao = models.BooleanField(default=False)
    
    def verificar_alerta_observacao(self):
        """Verifica se há palavras-chave de alerta nas observações"""
        palavras_alerta = ['URGENTE', 'ATENÇÃO', 'PROBLEMA', 'INCONSISTÊNCIA']
        if self.observacoes:
            return any(palavra in self.observacoes.upper() for palavra in palavras_alerta)
        return False
```

#### **2.4 Correção do Espaço na Sigla no PDF**
**Arquivos a modificar:**
- `templates/dominial/cadeia_dominial_pdf.html`
- `dominial/services/lancamento_form_service.py`

**Implementação:**
```python
def gerar_numero_lancamento(numero_simples, tipo_lanc, sigla_matricula):
    """Gera número de lançamento com espaço correto na sigla"""
    # Garantir que não há espaços extras
    sigla_limpa = sigla_matricula.strip()
    return f"{sigla_limpa}-{numero_simples}"
```

#### **2.5 Retorno Automático para Árvore**
**Arquivos a modificar:**
- `dominial/views/lancamento_views.py`
- `dominial/services/lancamento_service.py`

**Implementação:**
```python
def verificar_inicio_matricula(lancamento):
    """Verifica se o lançamento chegou no início da matrícula"""
    if lancamento.tipo.tipo == 'inicio_matricula':
        return True
    return False

# Na view de criação de lançamento
if verificar_inicio_matricula(lancamento):
    messages.info(request, "Lançamento chegou no início da matrícula. Redirecionando para a árvore.")
    return redirect('cadeia_dominial', tis_id=tis.id, imovel_id=imovel.id)
```

#### **2.6 Conversão de Vírgula por Ponto no Campo Área**
**Arquivos a modificar:**
- `dominial/services/lancamento_form_service.py`
- `static/dominial/js/lancamento_form.js`

**Implementação:**
```python
def processar_campo_area(area_value):
    """Processa campo área convertendo vírgula para ponto"""
    if area_value:
        # Converter vírgula para ponto
        area_limpa = area_value.replace(',', '.')
        try:
            return float(area_limpa)
        except ValueError:
            return None
    return None
```

#### **2.7 Visualização de Lançamentos Anteriores**
**Arquivos a modificar:**
- `templates/dominial/lancamento_form.html`
- `dominial/views/lancamento_views.py`

**Implementação:**
```html
<!-- Adicionar seção de lançamentos anteriores -->
<div class="field-group">
    <h4>Lançamentos Anteriores</h4>
    <div class="lancamentos-anteriores">
        {% for lanc in lancamentos_anteriores %}
        <div class="lancamento-anterior">
            <strong>{{ lanc.numero_lancamento }}</strong> - {{ lanc.tipo.get_tipo_display }}
            <small>{{ lanc.data|date:"d/m/Y" }}</small>
        </div>
        {% endfor %}
    </div>
</div>
```

#### **2.8 Conversão Automática de Imóvel Modificado**
**Arquivos a modificar:**
- `dominial/models/imovel_models.py`
- `dominial/services/imovel_service.py`

**Implementação:**
```python
def verificar_modificacao_imovel(imovel):
    """Verifica se o imóvel teve modificações que o tornam atual"""
    # Lógica para detectar modificações significativas
    ultima_modificacao = Lancamento.objects.filter(
        documento__imovel=imovel
    ).order_by('-data').first()
    
    if ultima_modificacao and ultima_modificacao.data > imovel.data_cadastro:
        return True
    return False
```

#### **2.9 Remoção do Destaque "Importado" do PDF**
**Arquivos a modificar:**
- `templates/dominial/cadeia_dominial_pdf.html`
- `templates/dominial/cadeia_completa_pdf.html`

**Implementação:**
```html
<!-- Remover ou condicionar a exibição do destaque -->
{% if not is_pdf %}
<div class="documento-importado-alert">
    <!-- Destaque apenas na interface web -->
</div>
{% endif %}
```

## 📋 **Cronograma de Implementação**

### **Semana 1:**
- ✅ Implementar toggle para origem (1.1)
- ✅ Adicionar campo matrícula/transcrição no cadastro (1.2)
- ✅ Sugestão automática de cartório (1.3)
- ✅ Ordenação dos imóveis (1.4)

### **Semana 2:**
- ✅ Navegação com TAB (1.5)
- ✅ Reorganização dos lançamentos (1.6)
- ✅ Visualização da árvore completa (1.7)
- ✅ Reorganização dos campos (1.8)

### **Semana 3:**
- ✅ Impressão da árvore (2.1)
- ✅ Melhor diagramação do PDF (2.2)
- ✅ Sistema de alertas (2.3)
- ✅ Correção do espaço na sigla (2.4)

### **Semana 4:**
- ✅ Retorno automático para árvore (2.5)
- ✅ Conversão vírgula/ponto (2.6)
- ✅ Visualização de lançamentos anteriores (2.7)
- ✅ Conversão automática de imóvel (2.8)
- ✅ Remoção destaque importado (2.9)

## 🔧 **Considerações Técnicas**

### **Compatibilidade**
- ✅ Manter retrocompatibilidade com dados existentes
- ✅ Não quebrar funcionalidades atuais
- ✅ Implementar mudanças de forma incremental

### **Testes**
- ✅ Testar cada funcionalidade individualmente
- ✅ Validar integração entre componentes
- ✅ Verificar performance com grandes volumes de dados

### **Documentação**
- ✅ Atualizar documentação técnica
- ✅ Criar guias de usuário para novas funcionalidades
- ✅ Documentar mudanças no banco de dados

## 🎯 **Resultados Esperados**

### **Melhorias de UX:**
- Interface mais intuitiva e eficiente
- Redução de erros de entrada de dados
- Navegação mais fluida

### **Melhorias de Funcionalidade:**
- PDFs mais legíveis e organizados
- Sistema de alertas para observações importantes
- Melhor controle do fluxo de trabalho

### **Benefícios Gerais:**
- Aumento da produtividade dos usuários
- Redução de retrabalho
- Melhor experiência do usuário
