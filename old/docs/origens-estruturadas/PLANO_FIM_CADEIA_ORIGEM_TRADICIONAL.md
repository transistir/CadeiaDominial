# 🎯 PLANO: FIM DE CADEIA NA ORIGEM TRADICIONAL

## 📋 **RESUMO EXECUTIVO**

Implementação de um **toggle "Fim de Cadeia"** na origem tradicional existente. Quando ativado, o usuário poderá selecionar a classificação da origem (Imóvel com Origem Lídima, Imóvel sem Origem, Situação Inconclusa) e adicionar observações.

## 🎯 **OBJETIVOS**

### **Primários:**
- ✅ **Simplicidade máxima** - Usar origem tradicional existente
- ✅ **Toggle simples** - Checkbox "Fim de Cadeia"
- ✅ **Classificação** - 3 opções de classificação
- ✅ **Observações** - Campo para observações
- ✅ **Retrocompatibilidade** - Não quebrar sistema existente

### **Secundários:**
- ✅ **Destaque visual** - Marcar origens que terminam cadeia
- ✅ **Validação** - Garantir classificação quando fim de cadeia
- ✅ **Interface intuitiva** - UX clara e objetiva

## 🏗️ **ARQUITETURA SIMPLES**

### **Componentes:**

```
┌─────────────────────────────────────────────────────────────┐
│                    ORIGEM TRADICIONAL                       │
├─────────────────────────────────────────────────────────────┤
│ • Campo origem (texto)                                      │
│ • Campo cartório (autocomplete)                             │
│ • Campo livro (texto)                                       │
│ • Campo folha (texto)                                       │
│ • ✅ NOVO: Toggle "Fim de Cadeia"                          │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼ (se ativado)
┌─────────────────────────────────────────────────────────────┐
│                TIPO DE FIM DE CADEIA                       │
├─────────────────────────────────────────────────────────────┤
│ • Select: Destacamento do Patrimônio Público               │
│ • Select: Outra                                             │
│ • Select: Sem Origem                                        │
│ • Textarea: Especificação (se "Outra")                     │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼ (após selecionar tipo)
┌─────────────────────────────────────────────────────────────┐
│                CLASSIFICAÇÃO FIM DE CADEIA                 │
├─────────────────────────────────────────────────────────────┤
│ • Select: Imóvel com Origem Lídima                         │
│ • Select: Imóvel sem Origem                                │
│ • Select: Situação Inconclusa                              │
│ • Textarea: Observações                                    │
└─────────────────────────────────────────────────────────────┘
```

## 🔄 **FASE 1: MODELO DE DADOS**

### **1.1 Extensão do Modelo Lancamento**

```python
# dominial/models/lancamento_models.py

class Lancamento(models.Model):
    # ... campos existentes ...
    
    # NOVOS CAMPOS PARA FIM DE CADEIA
    fim_cadeia = models.BooleanField(
        default=False,
        verbose_name="Fim de Cadeia",
        help_text="Indica se esta origem termina a cadeia dominial"
    )
    
    tipo_fim_cadeia = models.CharField(
        max_length=50,
        choices=[
            ('destacamento_publico', 'Destacamento do Patrimônio Público'),
            ('outra', 'Outra'),
            ('sem_origem', 'Sem Origem')
        ],
        null=True,
        blank=True,
        verbose_name="Tipo do Fim de Cadeia"
    )
    
    especificacao_fim_cadeia = models.TextField(
        null=True,
        blank=True,
        verbose_name="Especificação do Fim de Cadeia",
        help_text="Detalhes quando o tipo é 'Outra'"
    )
    
    classificacao_fim_cadeia = models.CharField(
        max_length=50,
        choices=[
            ('origem_lidima', 'Imóvel com Origem Lídima'),
            ('sem_origem', 'Imóvel sem Origem'),
            ('inconclusa', 'Situação Inconclusa')
        ],
        null=True,
        blank=True,
        verbose_name="Classificação do Fim de Cadeia"
    )
    
    observacoes_fim_cadeia = models.TextField(
        null=True,
        blank=True,
        verbose_name="Observações sobre o Fim de Cadeia"
    )
    
    class Meta:
        # ... meta existente ...
        pass
    
    def is_fim_cadeia(self) -> bool:
        """Verifica se este lançamento marca fim de cadeia"""
        return self.fim_cadeia and self.tipo_fim_cadeia is not None and self.classificacao_fim_cadeia is not None
    
    def get_tipo_fim_cadeia_display(self) -> str:
        """Retorna o tipo de fim de cadeia formatado"""
        if self.tipo_fim_cadeia:
            return dict(self._meta.get_field('tipo_fim_cadeia').choices)[self.tipo_fim_cadeia]
        return ""
    
    def get_classificacao_display(self) -> str:
        """Retorna a classificação formatada"""
        if self.classificacao_fim_cadeia:
            return dict(self._meta.get_field('classificacao_fim_cadeia').choices)[self.classificacao_fim_cadeia]
        return ""
```

### **1.2 Migração**

```python
# dominial/migrations/0033_lancamento_fim_cadeia.py

from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [
        ('dominial', '0032_origem_estruturada'),
    ]

    operations = [
        migrations.AddField(
            model_name='lancamento',
            name='fim_cadeia',
            field=models.BooleanField(
                default=False,
                help_text='Indica se esta origem termina a cadeia dominial',
                verbose_name='Fim de Cadeia'
            ),
        ),
        migrations.AddField(
            model_name='lancamento',
            name='tipo_fim_cadeia',
            field=models.CharField(
                blank=True,
                choices=[
                    ('destacamento_publico', 'Destacamento do Patrimônio Público'),
                    ('outra', 'Outra'),
                    ('sem_origem', 'Sem Origem')
                ],
                help_text='Tipo do fim de cadeia',
                max_length=50,
                null=True,
                verbose_name='Tipo do Fim de Cadeia'
            ),
        ),
        migrations.AddField(
            model_name='lancamento',
            name='especificacao_fim_cadeia',
            field=models.TextField(
                blank=True,
                help_text='Especificação quando o tipo é "Outra"',
                null=True,
                verbose_name='Especificação do Fim de Cadeia'
            ),
        ),
        migrations.AddField(
            model_name='lancamento',
            name='classificacao_fim_cadeia',
            field=models.CharField(
                blank=True,
                choices=[
                    ('origem_lidima', 'Imóvel com Origem Lídima'),
                    ('sem_origem', 'Imóvel sem Origem'),
                    ('inconclusa', 'Situação Inconclusa')
                ],
                help_text='Classificação quando a origem termina a cadeia',
                max_length=50,
                null=True,
                verbose_name='Classificação do Fim de Cadeia'
            ),
        ),
        migrations.AddField(
            model_name='lancamento',
            name='observacoes_fim_cadeia',
            field=models.TextField(
                blank=True,
                help_text='Observações sobre o fim de cadeia',
                null=True,
                verbose_name='Observações sobre o Fim de Cadeia'
            ),
        ),
    ]
```

## 🔄 **FASE 2: FORMULÁRIO**

### **2.1 Template da Origem Tradicional**

```html
<!-- templates/dominial/components/_area_origem_form.html -->
<div class="area-origem-group">
    <h5>Área e Origem</h5>
    
    <!-- ... campos existentes ... -->
    
    <div id="{{ container_id|default:'origens-container' }}">
        <div class="origem-labels">
            <label>Origem{% if origem_obrigatorio %} *{% endif %}</label>
            <label>Cartório de Registro da Origem{% if origem_obrigatorio %} *{% endif %}</label>
            <label>Livro da Origem</label>
            <label>Folha da Origem</label>
            <label>Fim de Cadeia</label>
        </div>
        
        <!-- Template para origem individual -->
        <div class="origem-item">
            <div class="form-group origem-field">
                <input type="text" name="origem_completa[]" class="origem-texto" 
                       placeholder="Ex: Número do registro anterior, descrição, etc.">
            </div>
            <div class="form-group cartorio-field">
                <div class="autocomplete-container">
                    <input type="text" name="cartorio_origem_nome[]" class="cartorio-origem-nome" 
                           placeholder="Digite o nome do cartório" autocomplete="off">
                    <input type="hidden" name="cartorio_origem[]" class="cartorio-origem-id">
                    <div class="autocomplete-suggestions cartorio-origem-suggestions"></div>
                </div>
            </div>
            <div class="form-group livro-field">
                <input type="text" name="livro_origem[]" class="livro-origem" 
                       placeholder="Ex: 1, 2, A, etc.">
            </div>
            <div class="form-group folha-field">
                <input type="text" name="folha_origem[]" class="folha-origem" 
                       placeholder="Ex: 1, 2, A, etc.">
            </div>
            <div class="form-group fim-cadeia-field">
                <div class="form-check">
                    <input type="checkbox" name="fim_cadeia[]" class="form-check-input fim-cadeia-toggle" 
                           id="fim_cadeia_0">
                    <label class="form-check-label" for="fim_cadeia_0">
                        <i class="fas fa-stop-circle"></i>
                        Fim de Cadeia
                    </label>
                </div>
            </div>
            <button type="button" class="btn btn-sm btn-danger remove-origem" title="Remover origem">×</button>
        </div>
        
        <!-- Container para tipo de fim de cadeia (inicialmente oculto) -->
        <div class="tipo-fim-cadeia-container" style="display: none;">
            <div class="card border-warning">
                <div class="card-header bg-warning">
                    <h6 class="mb-0">
                        <i class="fas fa-exclamation-triangle"></i>
                        Tipo do Fim de Cadeia
                    </h6>
                </div>
                <div class="card-body">
                    <div class="form-group">
                        <label for="tipo_fim_cadeia">Tipo do Fim de Cadeia *</label>
                        <select name="tipo_fim_cadeia" id="tipo_fim_cadeia" class="form-control" required>
                            <option value="">Selecione o tipo</option>
                            <option value="destacamento_publico">Destacamento do Patrimônio Público</option>
                            <option value="outra">Outra</option>
                            <option value="sem_origem">Sem Origem</option>
                        </select>
                    </div>
                    <div class="form-group especificacao-container" style="display: none;">
                        <label for="especificacao_fim_cadeia">Especificação *</label>
                        <textarea name="especificacao_fim_cadeia" id="especificacao_fim_cadeia" 
                                  class="form-control" rows="3" 
                                  placeholder="Especifique o tipo de origem (ex: sentença judicial, processo, etc.)..."></textarea>
                    </div>
                </div>
            </div>
        </div>
        
        <!-- Container para classificação (inicialmente oculto) -->
        <div class="classificacao-fim-cadeia-container" style="display: none;">
            <div class="card border-info">
                <div class="card-header bg-info">
                    <h6 class="mb-0">
                        <i class="fas fa-info-circle"></i>
                        Classificação do Fim de Cadeia
                    </h6>
                </div>
                <div class="card-body">
                    <div class="form-group">
                        <label for="classificacao_fim_cadeia">Classificação *</label>
                        <select name="classificacao_fim_cadeia" id="classificacao_fim_cadeia" class="form-control" required>
                            <option value="">Selecione a classificação</option>
                            <option value="origem_lidima">Imóvel com Origem Lídima</option>
                            <option value="sem_origem">Imóvel sem Origem</option>
                            <option value="inconclusa">Situação Inconclusa</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label for="observacoes_fim_cadeia">Observações</label>
                        <textarea name="observacoes_fim_cadeia" id="observacoes_fim_cadeia" 
                                  class="form-control" rows="3" 
                                  placeholder="Observações sobre o fim de cadeia..."></textarea>
                    </div>
                </div>
            </div>
        </div>
    </div>
    
    <button type="button" class="btn btn-sm btn-outline" onclick="adicionarOrigem()">
        ➕ Adicionar Origem
    </button>
</div>
```

### **2.2 JavaScript para Toggle**

```javascript
// static/dominial/js/lancamento_form.js

// Função para adicionar origem (modificada)
function adicionarOrigem() {
    const container = document.getElementById('origens-container');
    if (!container) return;
    
    const existingOrigins = container.querySelectorAll('.origem-item');
    const newIndex = existingOrigins.length;
    
    const origemDiv = document.createElement('div');
    origemDiv.className = 'origem-item';
    origemDiv.innerHTML = `
        <div class="form-group origem-field">
            <input type="text" name="origem_completa[]" id="origem_completa_${newIndex}" class="origem-texto" 
                   placeholder="Ex: Número do registro anterior, descrição, etc." required>
        </div>
        <div class="form-group cartorio-field">
            <div class="autocomplete-container">
                <input type="text" name="cartorio_origem_nome[]" id="cartorio_origem_nome_${newIndex}" class="cartorio-origem-nome" 
                       placeholder="Digite o nome do cartório" autocomplete="off" required>
                <input type="hidden" name="cartorio_origem[]" id="cartorio_origem_${newIndex}" class="cartorio-origem-id">
                <div class="autocomplete-suggestions cartorio-origem-suggestions"></div>
            </div>
        </div>
        <div class="form-group livro-field">
            <input type="text" name="livro_origem[]" id="livro_origem_${newIndex}" class="livro-origem" 
                   placeholder="Ex: 1, 2, A, etc.">
        </div>
        <div class="form-group folha-field">
            <input type="text" name="folha_origem[]" id="folha_origem_${newIndex}" class="folha-origem" 
                   placeholder="Ex: 1, 2, A, etc.">
        </div>
        <div class="form-group fim-cadeia-field">
            <div class="form-check">
                <input type="checkbox" name="fim_cadeia[]" class="form-check-input fim-cadeia-toggle" 
                       id="fim_cadeia_${newIndex}">
                <label class="form-check-label" for="fim_cadeia_${newIndex}">
                    <i class="fas fa-stop-circle"></i>
                    Fim de Cadeia
                </label>
            </div>
        </div>
        <button type="button" class="btn btn-sm btn-danger remove-origem" onclick="removeOrigem(this)" title="Remover origem">×</button>
    `;
    
    container.appendChild(origemDiv);
    
    // Configurar autocomplete para o novo campo de cartório
    setupCartorioAutocomplete(origemDiv.querySelector('.cartorio-origem-nome'));
    
    // Configurar toggle de fim de cadeia
    setupFimCadeiaToggle(origemDiv.querySelector('.fim-cadeia-toggle'));
}

// Função para configurar toggle de fim de cadeia
function setupFimCadeiaToggle(toggleElement) {
    if (!toggleElement) return;
    
    toggleElement.addEventListener('change', function() {
        const tipoContainer = document.querySelector('.tipo-fim-cadeia-container');
        const classificacaoContainer = document.querySelector('.classificacao-fim-cadeia-container');
        const tipoSelect = document.getElementById('tipo_fim_cadeia');
        const classificacaoSelect = document.getElementById('classificacao_fim_cadeia');
        const observacoesTextarea = document.getElementById('observacoes_fim_cadeia');
        
        if (this.checked) {
            // Mostrar container de tipo
            tipoContainer.style.display = 'block';
            
            // Marcar campos como obrigatórios
            tipoSelect.required = true;
            
            // Adicionar classe visual
            this.closest('.origem-item').classList.add('fim-cadeia-ativo');
            
        } else {
            // Ocultar containers
            tipoContainer.style.display = 'none';
            classificacaoContainer.style.display = 'none';
            
            // Remover obrigatoriedade e limpar campos
            tipoSelect.required = false;
            classificacaoSelect.required = false;
            tipoSelect.value = '';
            classificacaoSelect.value = '';
            observacoesTextarea.value = '';
            
            // Ocultar especificação
            document.querySelector('.especificacao-container').style.display = 'none';
            document.getElementById('especificacao_fim_cadeia').value = '';
            
            // Remover classe visual
            this.closest('.origem-item').classList.remove('fim-cadeia-ativo');
        }
    });
}

// Função para configurar select de tipo
function setupTipoFimCadeiaSelect() {
    const tipoSelect = document.getElementById('tipo_fim_cadeia');
    if (!tipoSelect) return;
    
    tipoSelect.addEventListener('change', function() {
        const classificacaoContainer = document.querySelector('.classificacao-fim-cadeia-container');
        const especificacaoContainer = document.querySelector('.especificacao-container');
        const especificacaoTextarea = document.getElementById('especificacao_fim_cadeia');
        const classificacaoSelect = document.getElementById('classificacao_fim_cadeia');
        
        if (this.value) {
            // Mostrar container de classificação
            classificacaoContainer.style.display = 'block';
            classificacaoSelect.required = true;
            
            // Mostrar especificação se for "Outra"
            if (this.value === 'outra') {
                especificacaoContainer.style.display = 'block';
                especificacaoTextarea.required = true;
            } else {
                especificacaoContainer.style.display = 'none';
                especificacaoTextarea.required = false;
                especificacaoTextarea.value = '';
            }
        } else {
            // Ocultar containers
            classificacaoContainer.style.display = 'none';
            especificacaoContainer.style.display = 'none';
            
            // Remover obrigatoriedade
            classificacaoSelect.required = false;
            especificacaoTextarea.required = false;
            classificacaoSelect.value = '';
            especificacaoTextarea.value = '';
        }
    });
}

// Configurar toggles existentes na inicialização
document.addEventListener('DOMContentLoaded', function() {
    const toggles = document.querySelectorAll('.fim-cadeia-toggle');
    toggles.forEach(setupFimCadeiaToggle);
    
    // Configurar select de tipo
    setupTipoFimCadeiaSelect();
});
```

### **2.3 CSS para Destaque Visual**

```css
/* static/dominial/css/lancamento_form.css */

/* Destaque para origem com fim de cadeia */
.origem-item.fim-cadeia-ativo {
    border: 2px solid #ffc107;
    background-color: #fff3cd;
    border-radius: 8px;
    padding: 10px;
    margin-bottom: 10px;
}

.origem-item.fim-cadeia-ativo .fim-cadeia-field {
    background-color: #ffc107;
    color: #856404;
    padding: 5px 10px;
    border-radius: 4px;
    font-weight: bold;
}

/* Container de classificação */
.classificacao-fim-cadeia-container {
    margin-top: 15px;
    margin-bottom: 15px;
}

.classificacao-fim-cadeia-container .card {
    border-left: 4px solid #ffc107;
}

/* Toggle de fim de cadeia */
.fim-cadeia-toggle:checked + label {
    color: #856404;
    font-weight: bold;
}

.fim-cadeia-toggle:checked + label i {
    color: #ffc107;
}

/* Responsividade */
@media (max-width: 768px) {
    .origem-labels {
        display: none;
    }
    
    .origem-item {
        flex-direction: column;
    }
    
    .origem-item > div {
        margin-bottom: 10px;
    }
}
```

## 🔄 **FASE 3: PROCESSAMENTO DE DADOS**

### **3.1 Service de Processamento**

```python
# dominial/services/lancamento_form_service.py

class LancamentoFormService:
    @staticmethod
    def processar_dados_lancamento(request, tipo_lanc):
        # ... código existente ...
        
        # Processar dados de fim de cadeia
        fim_cadeia = request.POST.get('fim_cadeia') == 'on'
        tipo_fim_cadeia = request.POST.get('tipo_fim_cadeia')
        especificacao_fim_cadeia = request.POST.get('especificacao_fim_cadeia')
        classificacao_fim_cadeia = request.POST.get('classificacao_fim_cadeia')
        observacoes_fim_cadeia = request.POST.get('observacoes_fim_cadeia')
        
        # Validação: se fim_cadeia está marcado, tipo e classificação são obrigatórios
        if fim_cadeia:
            if not tipo_fim_cadeia:
                raise ValidationError("Tipo do Fim de Cadeia é obrigatório quando 'Fim de Cadeia' está marcado")
            if not classificacao_fim_cadeia:
                raise ValidationError("Classificação é obrigatória quando 'Fim de Cadeia' está marcado")
            if tipo_fim_cadeia == 'outra' and not especificacao_fim_cadeia:
                raise ValidationError("Especificação é obrigatória quando o tipo é 'Outra'")
        
        # Se não é fim de cadeia, limpar campos
        if not fim_cadeia:
            tipo_fim_cadeia = None
            especificacao_fim_cadeia = None
            classificacao_fim_cadeia = None
            observacoes_fim_cadeia = None
        
        return {
            # ... dados existentes ...
            'fim_cadeia': fim_cadeia,
            'tipo_fim_cadeia': tipo_fim_cadeia,
            'especificacao_fim_cadeia': especificacao_fim_cadeia,
            'classificacao_fim_cadeia': classificacao_fim_cadeia,
            'observacoes_fim_cadeia': observacoes_fim_cadeia,
        }
```

### **3.2 Validação no Modelo**

```python
# dominial/models/lancamento_models.py

class Lancamento(models.Model):
    # ... campos existentes ...
    
    def clean(self):
        super().clean()
        
        # Validação: se fim_cadeia está marcado, tipo e classificação são obrigatórios
        if self.fim_cadeia:
            if not self.tipo_fim_cadeia:
                raise ValidationError({
                    'tipo_fim_cadeia': 'Tipo do Fim de Cadeia é obrigatório quando "Fim de Cadeia" está marcado'
                })
            if not self.classificacao_fim_cadeia:
                raise ValidationError({
                    'classificacao_fim_cadeia': 'Classificação é obrigatória quando "Fim de Cadeia" está marcado'
                })
            if self.tipo_fim_cadeia == 'outra' and not self.especificacao_fim_cadeia:
                raise ValidationError({
                    'especificacao_fim_cadeia': 'Especificação é obrigatória quando o tipo é "Outra"'
                })
        
        # Se não é fim de cadeia, limpar campos
        if not self.fim_cadeia:
            self.tipo_fim_cadeia = None
            self.especificacao_fim_cadeia = None
            self.classificacao_fim_cadeia = None
            self.observacoes_fim_cadeia = None
```

## 🔄 **FASE 4: VISUALIZAÇÃO**

### **4.1 CadeiaDominialTabelaService - Adaptação**

```python
# dominial/services/cadeia_dominial_tabela_service.py

class CadeiaDominialTabelaService:
    @staticmethod
    def preparar_dados_tabela(documento_ativo: Documento) -> List[Dict[str, Any]]:
        # ... código existente ...
        
        # Enriquecer com informações de fim de cadeia
        for item in dados:
            lancamento = item.get('lancamento')
            if lancamento and lancamento.is_fim_cadeia():
                item['is_fim_cadeia'] = True
                item['tipo_fim_cadeia'] = lancamento.get_tipo_fim_cadeia_display()
                item['especificacao_fim_cadeia'] = lancamento.especificacao_fim_cadeia
                item['classificacao_fim_cadeia'] = lancamento.get_classificacao_display()
                item['observacoes_fim_cadeia'] = lancamento.observacoes_fim_cadeia
            else:
                item['is_fim_cadeia'] = False
        
        return dados
```

### **4.2 Template da Tabela**

```html
<!-- templates/dominial/cadeia_dominial_tabela.html -->
<tr class="documento-row {% if item.is_fim_cadeia %}fim-cadeia{% endif %}">
    <td>
        <button class="documento-btn {% if item.is_fim_cadeia %}fim-cadeia-btn{% endif %}">
            {{ item.documento.numero }}
            
            {% if item.is_fim_cadeia %}
                <span class="badge badge-warning fim-cadeia-badge">
                    <i class="fas fa-stop-circle"></i>
                    Fim de Cadeia
                </span>
                <span class="badge badge-secondary tipo-badge">
                    {{ item.tipo_fim_cadeia }}
                </span>
                <span class="badge badge-info classificacao-badge">
                    {{ item.classificacao_fim_cadeia }}
                </span>
            {% endif %}
        </button>
    </td>
</tr>
```

### **4.3 HierarquiaArvoreService - Adaptação**

```python
# dominial/services/hierarquia_arvore_service.py

class HierarquiaArvoreService:
    @staticmethod
    def construir_arvore(documento_ativo: Documento) -> Dict[str, Any]:
        # ... código existente ...
        
        # Enriquecer nós com informações de fim de cadeia
        def enriquecer_no(no):
            lancamento = no.get('lancamento')
            if lancamento and lancamento.is_fim_cadeia():
                no['is_fim_cadeia'] = True
                no['tipo_fim_cadeia'] = lancamento.get_tipo_fim_cadeia_display()
                no['especificacao_fim_cadeia'] = lancamento.especificacao_fim_cadeia
                no['classificacao_fim_cadeia'] = lancamento.get_classificacao_display()
                no['observacoes_fim_cadeia'] = lancamento.observacoes_fim_cadeia
            
            # Recursivamente processar filhos
            for filho in no.get('children', []):
                enriquecer_no(filho)
        
        enriquecer_no(arvore)
        return arvore
```

### **4.4 JavaScript D3 - Destaque**

```javascript
// static/dominial/js/cadeia_dominial_d3.js

function renderArvoreD3(data, svgGroup, width, height) {
    // ... código existente ...
    
    // Adicionar destaque para fim de cadeia
    node.append('rect')
        .attr('class', 'node-card')
        .attr('rx', 8)
        .attr('ry', 8)
        .attr('width', 140)
        .attr('height', 80)
        .style('fill', d => {
            if (d.data.is_fim_cadeia) {
                return '#fff3cd'; // Amarelo claro para fim de cadeia
            }
            return '#ffffff';
        })
        .style('stroke', d => {
            if (d.data.is_fim_cadeia) {
                return '#ffc107'; // Borda amarela
            }
            return '#dee2e6';
        })
        .style('stroke-width', d => {
            if (d.data.is_fim_cadeia) {
                return 3; // Borda mais grossa
            }
            return 1;
        });
    
    // Adicionar badge para fim de cadeia
    node.filter(d => d.data.is_fim_cadeia)
        .append('text')
        .attr('class', 'fim-cadeia-badge')
        .attr('x', 70)
        .attr('y', -15)
        .attr('text-anchor', 'middle')
        .style('font-size', '10px')
        .style('fill', '#856404')
        .text('FIM DE CADEIA');
    
    // Adicionar tipo
    node.filter(d => d.data.tipo_fim_cadeia)
        .append('text')
        .attr('class', 'tipo-badge')
        .attr('x', 70)
        .attr('y', -5)
        .attr('text-anchor', 'middle')
        .style('font-size', '9px')
        .style('fill', '#6c757d')
        .text(d => d.data.tipo_fim_cadeia.toUpperCase());
    
    // Adicionar classificação
    node.filter(d => d.data.classificacao_fim_cadeia)
        .append('text')
        .attr('class', 'classificacao-badge')
        .attr('x', 70)
        .attr('y', 95)
        .attr('text-anchor', 'middle')
        .style('font-size', '9px')
        .style('fill', '#17a2b8')
        .text(d => d.data.classificacao_fim_cadeia.toUpperCase());
}
```

## 🚀 **PLANO DE IMPLEMENTAÇÃO**

### **Fase 1: Modelo e Migração (1 dia)**
- [ ] Adicionar campos ao modelo `Lancamento`
- [ ] Criar migração
- [ ] Testes unitários do modelo

### **Fase 2: Formulário (1 dia)**
- [ ] Modificar template `_area_origem_form.html`
- [ ] Implementar JavaScript para toggle
- [ ] Adicionar CSS para destaque visual

### **Fase 3: Processamento (1 dia)**
- [ ] Adaptar `LancamentoFormService`
- [ ] Implementar validações
- [ ] Testes de processamento

### **Fase 4: Visualização (1 dia)**
- [ ] Adaptar `CadeiaDominialTabelaService`
- [ ] Adaptar `HierarquiaArvoreService`
- [ ] Implementar destaque visual na árvore

### **Fase 5: Testes (1 dia)**
- [ ] Testes de integração
- [ ] Testes de interface
- [ ] Validação de retrocompatibilidade

## 🎯 **BENEFÍCIOS**

### **✅ Simplicidade:**
- **Implementação rápida** - 5 dias vs semanas
- **Código mínimo** - Apenas extensão da origem tradicional
- **Manutenção fácil** - Sem complexidade adicional

### **✅ Retrocompatibilidade:**
- **100% segura** - Não afeta dados existentes
- **Campos opcionais** - Só preenchidos quando necessário
- **Fallback automático** - Sistema funciona sem os novos campos

### **✅ Funcionalidade:**
- **Destaque visual** - Fim de cadeia claramente identificado
- **Classificação** - 3 opções conforme solicitado
- **Observações** - Campo para detalhes adicionais
- **Validação** - Garante classificação quando necessário

## 🎯 **RESULTADO ESPERADO**

Ao final da implementação, o sistema terá:

1. **Toggle simples** "Fim de Cadeia" na origem tradicional
2. **Classificação obrigatória** quando fim de cadeia está ativo
3. **Campo de observações** para detalhes adicionais
4. **Destaque visual** em tabela e árvore
5. **Retrocompatibilidade total** com sistema existente
6. **Implementação rápida** e manutenção simples

**🎉 Esta solução é muito mais simples, rápida e eficaz!** 