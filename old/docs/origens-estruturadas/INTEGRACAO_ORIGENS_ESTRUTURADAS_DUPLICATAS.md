# 🔄 INTEGRAÇÃO: ORIGENS ESTRUTURADAS + DUPLICATAS E IMPORTAÇÃO

## 📋 **RESUMO EXECUTIVO**

Este documento descreve a integração entre o novo sistema de **Origens Estruturadas** e o sistema existente de **Verificação de Duplicatas e Importação**. A integração é essencial para manter a consistência dos dados e oferecer uma experiência completa ao usuário.

## 🎯 **OBJETIVOS**

### **Primários:**
- ✅ **Detectar duplicatas** em origens estruturadas
- ✅ **Importar cadeias** preservando contexto estruturado
- ✅ **Destacar fim de matrícula** em documentos importados
- ✅ **Manter retrocompatibilidade** com sistema existente

### **Secundários:**
- ✅ **Melhorar precisão** da detecção de duplicatas
- ✅ **Preservar classificação** de origens
- ✅ **Otimizar performance** com relacionamentos
- ✅ **Enriquecer visualização** com contexto

## 🏗️ **ARQUITETURA DA INTEGRAÇÃO**

### **Componentes Principais:**

```
┌─────────────────────────────────────────────────────────────┐
│                    ORIGENS ESTRUTURADAS                     │
├─────────────────────────────────────────────────────────────┤
│ • TipoOrigem (continua_cadeia: boolean)                    │
│ • OrigemEstruturada (numero, cartorio, tipo_origem)        │
│ • ClassificacaoOrigem (origem_lidima, sem_origem, etc.)    │
│ • ClassificacaoImovel (relacionamento final)               │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                SISTEMA DE DUPLICATAS                        │
├─────────────────────────────────────────────────────────────┤
│ • DuplicataVerificacaoService (adaptado)                   │
│ • LancamentoDuplicataService (estendido)                   │
│ • ImportacaoCadeiaService (compatível)                     │
│ • DocumentoImportado (modelo existente)                    │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                VISUALIZAÇÃO ENRIQUECIDA                     │
├─────────────────────────────────────────────────────────────┤
│ • CadeiaDominialTabelaService (destacado)                  │
│ • HierarquiaArvoreService (marcado)                        │
│ • D3.js (badges e cores)                                   │
│ • CSS (estilos específicos)                                │
└─────────────────────────────────────────────────────────────┘
```

## 🔄 **FASE 1: ADAPTAÇÃO DO SISTEMA DE DUPLICATAS**

### **1.1 DuplicataVerificacaoService - Novas Funções**

```python
class DuplicataVerificacaoService:
    @staticmethod
    def verificar_duplicata_origem_estruturada(origem_estruturada, imovel_atual_id: int) -> Dict[str, Any]:
        """
        Verifica duplicatas para origens estruturadas
        
        Args:
            origem_estruturada: Objeto OrigemEstruturada
            imovel_atual_id: ID do imóvel atual
            
        Returns:
            Dict com informações sobre a duplicata encontrada
        """
        if not getattr(settings, 'DUPLICATA_VERIFICACAO_ENABLED', False):
            return {'tem_duplicata': False}
        
        # Buscar documento com mesmo número e cartório em outros imóveis
        documento_existente = Documento.objects.filter(
            numero=origem_estruturada.numero,
            cartorio=origem_estruturada.cartorio
        ).exclude(
            imovel_id=imovel_atual_id
        ).select_related('imovel', 'cartorio', 'tipo').first()
        
        if not documento_existente:
            return {'tem_duplicata': False}
        
        # Calcular documentos importáveis
        documentos_importaveis = DuplicataVerificacaoService.calcular_documentos_importaveis_estruturada(
            documento_existente, origem_estruturada
        )
        
        return {
            'tem_duplicata': True,
            'documento_origem': documento_existente,
            'documentos_importaveis': documentos_importaveis,
            'tipo_origem': origem_estruturada.tipo_origem.tipo,
            'continua_cadeia': origem_estruturada.tipo_origem.continua_cadeia
        }
    
    @staticmethod
    def calcular_documentos_importaveis_estruturada(documento_origem: Documento, origem_estruturada) -> List[Documento]:
        """
        Calcula documentos importáveis considerando origens estruturadas
        """
        documentos_importaveis = []
        documentos_processados = set()
        
        def buscar_cadeia_recursiva_estruturada(documento):
            if documento.id in documentos_processados:
                return
            
            documentos_processados.add(documento.id)
            
            # Buscar origens estruturadas deste documento
            lancamentos = Lancamento.objects.filter(documento=documento)
            
            for lancamento in lancamentos:
                origens_estruturadas = lancamento.origens_estruturadas.all()
                
                for origem in origens_estruturadas:
                    # Só expandir se a origem continua a cadeia
                    if origem.tipo_origem.continua_cadeia and origem.numero:
                        documento_anterior = Documento.objects.filter(
                            numero=origem.numero,
                            cartorio=origem.cartorio
                        ).first()
                        
                        if documento_anterior and not DocumentoImportado.objects.filter(
                            documento=documento_anterior,
                            imovel_origem=documento_origem.imovel
                        ).exists():
                            documentos_importaveis.append(documento_anterior)
                            buscar_cadeia_recursiva_estruturada(documento_anterior)
        
        # Iniciar busca recursiva
        buscar_cadeia_recursiva_estruturada(documento_origem)
        
        return documentos_importaveis
```

### **1.2 LancamentoDuplicataService - Extensão**

```python
class LancamentoDuplicataService:
    @staticmethod
    def verificar_duplicatas_origens_estruturadas(lancamento, imovel_atual_id: int) -> Dict[str, Any]:
        """
        Verifica duplicatas para todas as origens estruturadas de um lançamento
        """
        duplicatas_encontradas = []
        
        # Verificar cada origem estruturada
        for origem_estruturada in lancamento.origens_estruturadas.all():
            resultado = DuplicataVerificacaoService.verificar_duplicata_origem_estruturada(
                origem_estruturada, imovel_atual_id
            )
            
            if resultado['tem_duplicata']:
                duplicatas_encontradas.append({
                    'origem_estruturada': origem_estruturada,
                    'resultado': resultado
                })
        
        return {
            'tem_duplicatas': len(duplicatas_encontradas) > 0,
            'duplicatas': duplicatas_encontradas,
            'total_duplicatas': len(duplicatas_encontradas)
        }
    
    @staticmethod
    def processar_importacao_origens_estruturadas(request, lancamento, usuario) -> Dict[str, Any]:
        """
        Processa importação considerando origens estruturadas
        """
        duplicatas = LancamentoDuplicataService.verificar_duplicatas_origens_estruturadas(
            lancamento, lancamento.documento.imovel.id
        )
        
        if not duplicatas['tem_duplicatas']:
            return {'sucesso': False, 'mensagem': 'Nenhuma duplicata encontrada'}
        
        documentos_para_importar = []
        
        for duplicata in duplicatas['duplicatas']:
            documentos_para_importar.extend(duplicata['resultado']['documentos_importaveis'])
        
        # Remover duplicatas da lista
        documentos_para_importar = list(set(doc.id for doc in documentos_para_importar))
        
        # Importar cadeia
        resultado = ImportacaoCadeiaService.importar_cadeia_com_origens_estruturadas(
            imovel_destino_id=lancamento.documento.imovel.id,
            documento_origem_id=duplicatas['duplicatas'][0]['resultado']['documento_origem'].id,
            documentos_importaveis_ids=documentos_para_importar,
            usuario_id=usuario.id
        )
        
        return resultado
```

## 🔄 **FASE 2: IMPORTAÇÃO COM ORIGENS ESTRUTURADAS**

### **2.1 Novo Modelo para Rastreamento**

```python
# dominial/models/importacao_origem_estruturada_models.py

class ImportacaoOrigemEstruturada(models.Model):
    """
    Rastreia importações feitas a partir de origens estruturadas
    """
    origem_estruturada = models.ForeignKey(
        'OrigemEstruturada',
        on_delete=models.CASCADE,
        verbose_name="Origem Estruturada",
        related_name='importacoes'
    )
    
    documento_origem = models.ForeignKey(
        'Documento',
        on_delete=models.CASCADE,
        verbose_name="Documento de Origem"
    )
    
    importado_por = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        verbose_name="Importado por"
    )
    
    data_importacao = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Data de Importação"
    )
    
    documentos_importados = models.JSONField(
        help_text="Lista de IDs dos documentos importados"
    )
    
    class Meta:
        verbose_name = "Importação de Origem Estruturada"
        verbose_name_plural = "Importações de Origens Estruturadas"
        db_table = 'dominial_importacaoorigemestruturada'
        ordering = ['-data_importacao']
    
    def __str__(self):
        return f"Importação de {self.origem_estruturada} em {self.data_importacao.strftime('%d/%m/%Y')}"
```

### **2.2 ImportacaoCadeiaService - Extensão**

```python
class ImportacaoCadeiaService:
    @staticmethod
    def importar_cadeia_com_origens_estruturadas(
        imovel_destino_id: int,
        documento_origem_id: int,
        documentos_importaveis_ids: List[int],
        usuario_id: int,
        origem_estruturada_id: int = None
    ) -> Dict[str, Any]:
        """
        Importa cadeia dominial preservando informações de origens estruturadas
        """
        try:
            with transaction.atomic():
                # Importação básica
                resultado_basico = ImportacaoCadeiaService.importar_cadeia_dominial(
                    imovel_destino_id, documento_origem_id, documentos_importaveis_ids, usuario_id
                )
                
                # Se há origem estruturada específica, registrar a relação
                if origem_estruturada_id:
                    origem_estruturada = OrigemEstruturada.objects.get(id=origem_estruturada_id)
                    
                    # Criar registro de importação estruturada
                    ImportacaoOrigemEstruturada.objects.create(
                        origem_estruturada=origem_estruturada,
                        documento_origem_id=documento_origem_id,
                        importado_por_id=usuario_id,
                        documentos_importados=documentos_importaveis_ids
                    )
                
                return resultado_basico
                
        except Exception as e:
            return {
                'sucesso': False,
                'erro': str(e)
            }
```

## 🔄 **FASE 3: DESTAQUE DE FIM DE MATRÍCULA**

### **3.1 Extensão do DocumentoImportado**

```python
class DocumentoImportado(models.Model):
    # ... campos existentes ...
    
    def is_fim_matricula(self) -> bool:
        """
        Verifica se este documento importado marca fim de matrícula
        """
        # Buscar lançamentos com origens estruturadas
        lancamentos = self.documento.lancamentos.filter(
            tipo__tipo='inicio_matricula'
        )
        
        for lancamento in lancamentos:
            origens_estruturadas = lancamento.origens_estruturadas.all()
            
            for origem in origens_estruturadas:
                if not origem.tipo_origem.continua_cadeia:
                    return True
        
        return False
    
    def get_classificacao_origem(self) -> Optional[str]:
        """
        Retorna a classificação da origem se aplicável
        """
        lancamentos = self.documento.lancamentos.filter(
            tipo__tipo='inicio_matricula'
        )
        
        for lancamento in lancamentos:
            origens_estruturadas = lancamento.origens_estruturadas.all()
            
            for origem in origens_estruturadas:
                if not origem.tipo_origem.continua_cadeia:
                    if hasattr(origem, 'classificacao') and origem.classificacao:
                        return origem.classificacao.classificacao
        
        return None
    
    def get_tipo_origem_estruturada(self) -> Optional[str]:
        """
        Retorna o tipo da origem estruturada se aplicável
        """
        lancamentos = self.documento.lancamentos.filter(
            tipo__tipo='inicio_matricula'
        )
        
        for lancamento in lancamentos:
            origens_estruturadas = lancamento.origens_estruturadas.all()
            
            for origem in origens_estruturadas:
                if not origem.tipo_origem.continua_cadeia:
                    return origem.tipo_origem.get_tipo_display()
        
        return None
```

### **3.2 CadeiaDominialTabelaService - Adaptação**

```python
class CadeiaDominialTabelaService:
    @staticmethod
    def preparar_dados_tabela_com_origens_estruturadas(documento_ativo: Documento) -> List[Dict[str, Any]]:
        """
        Prepara dados para tabela considerando origens estruturadas
        """
        dados = CadeiaDominialTabelaService.preparar_dados_tabela(documento_ativo)
        
        # Enriquecer com informações de origens estruturadas
        for item in dados:
            if item.get('is_importado'):
                documento = item['documento']
                
                # Verificar se é fim de matrícula
                item['is_fim_matricula'] = DocumentoImportado.is_fim_matricula(documento)
                
                # Obter classificação se aplicável
                item['classificacao_origem'] = DocumentoImportado.get_classificacao_origem(documento)
                
                # Obter tipo de origem estruturada
                item['tipo_origem_estruturada'] = DocumentoImportado.get_tipo_origem_estruturada(documento)
        
        return dados
```

### **3.3 HierarquiaArvoreService - Adaptação**

```python
class HierarquiaArvoreService:
    @staticmethod
    def construir_arvore_com_origens_estruturadas(documento_ativo: Documento) -> Dict[str, Any]:
        """
        Constrói árvore considerando origens estruturadas
        """
        arvore = HierarquiaArvoreService.construir_arvore(documento_ativo)
        
        # Enriquecer nós com informações de origens estruturadas
        def enriquecer_no(no):
            if no.get('is_importado'):
                documento = no['documento']
                
                no['is_fim_matricula'] = DocumentoImportado.is_fim_matricula(documento)
                no['classificacao_origem'] = DocumentoImportado.get_classificacao_origem(documento)
                no['tipo_origem_estruturada'] = DocumentoImportado.get_tipo_origem_estruturada(documento)
            
            # Recursivamente processar filhos
            for filho in no.get('children', []):
                enriquecer_no(filho)
        
        enriquecer_no(arvore)
        return arvore
```

## 🎨 **FASE 4: VISUALIZAÇÃO ENRIQUECIDA**

### **4.1 CSS para Destaques**

```css
/* static/dominial/css/cadeia_dominial_estruturada.css */

/* Documentos importados com fim de matrícula */
.documento-importado.fim-matricula {
    border: 3px solid #ffc107 !important;
    background-color: #fff3cd !important;
    position: relative;
}

.documento-importado.fim-matricula::before {
    content: "🛑";
    position: absolute;
    top: -10px;
    right: -10px;
    background: #ffc107;
    color: #856404;
    border-radius: 50%;
    width: 24px;
    height: 24px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 12px;
    font-weight: bold;
}

/* Badges específicos */
.badge.fim-matricula-badge {
    background-color: #ffc107;
    color: #856404;
    font-weight: bold;
}

.badge.classificacao-badge {
    background-color: #17a2b8;
    color: white;
    font-size: 0.8em;
}

.badge.importado-estruturado-badge {
    background-color: #28a745;
    color: white;
    border: 2px solid #20c997;
}

/* Árvore D3 - nós especiais */
.node-fim-matricula {
    stroke: #ffc107 !important;
    stroke-width: 3px !important;
}

.node-importado-estruturado {
    stroke: #17a2b8 !important;
    stroke-width: 2px !important;
}

.node-fim-matricula-importado {
    stroke: #ffc107 !important;
    stroke-width: 4px !important;
    stroke-dasharray: 5,5 !important;
}
```

### **4.2 JavaScript D3 - Extensão**

```javascript
// static/dominial/js/cadeia_dominial_d3_estruturada.js

function renderArvoreD3Estruturada(data, svgGroup, width, height) {
    // ... código base existente ...
    
    // Adicionar destaque para documentos importados com fim de matrícula
    node.append('rect')
        .attr('class', 'node-card')
        .attr('rx', 8)
        .attr('ry', 8)
        .attr('width', 140)
        .attr('height', 80)
        .style('fill', d => {
            if (d.data.is_importado && d.data.is_fim_matricula) {
                return '#fff3cd'; // Amarelo claro para fim de matrícula importado
            } else if (d.data.is_importado) {
                return '#d1ecf1'; // Azul claro para importado
            } else if (d.data.is_fim_matricula) {
                return '#fff3cd'; // Amarelo claro para fim de matrícula
            }
            return '#ffffff';
        })
        .style('stroke', d => {
            if (d.data.is_importado && d.data.is_fim_matricula) {
                return '#ffc107'; // Borda amarela
            } else if (d.data.is_importado) {
                return '#17a2b8'; // Borda azul
            } else if (d.data.is_fim_matricula) {
                return '#ffc107'; // Borda amarela
            }
            return '#dee2e6';
        })
        .style('stroke-width', d => {
            if (d.data.is_importado || d.data.is_fim_matricula) {
                return 3; // Borda mais grossa
            }
            return 1;
        });
    
    // Adicionar badges
    node.filter(d => d.data.is_importado)
        .append('text')
        .attr('class', 'importado-badge')
        .attr('x', 70)
        .attr('y', -15)
        .attr('text-anchor', 'middle')
        .style('font-size', '10px')
        .style('fill', '#17a2b8')
        .text('IMPORTADO');
    
    node.filter(d => d.data.is_fim_matricula)
        .append('text')
        .attr('class', 'fim-matricula-badge')
        .attr('x', 70)
        .attr('y', -5)
        .attr('text-anchor', 'middle')
        .style('font-size', '10px')
        .style('fill', '#856404')
        .text('FIM DE MATRÍCULA');
    
    node.filter(d => d.data.classificacao_origem)
        .append('text')
        .attr('class', 'classificacao-badge')
        .attr('x', 70)
        .attr('y', 95)
        .attr('text-anchor', 'middle')
        .style('font-size', '9px')
        .style('fill', '#17a2b8')
        .text(d => d.data.classificacao_origem.toUpperCase());
}
```

## 🔄 **FASE 5: VALIDAÇÃO E PREVENÇÃO**

### **5.1 Validação de Duplicatas em Origens Estruturadas**

```python
class OrigemEstruturadaForm(forms.ModelForm):
    def clean(self):
        cleaned_data = super().clean()
        
        # Verificar duplicatas se não estamos após importação
        if not self.data.get('apos_importacao'):
            numero = cleaned_data.get('numero')
            cartorio = cleaned_data.get('cartorio')
            
            if numero and cartorio:
                # Verificar duplicata
                resultado = DuplicataVerificacaoService.verificar_duplicata_origem_estruturada(
                    self.instance, self.instance.lancamento.documento.imovel.id
                )
                
                if resultado['tem_duplicata']:
                    raise forms.ValidationError(
                        f"Origem {numero} no cartório {cartorio.nome} já existe em outra cadeia dominial. "
                        "Considere importar a cadeia existente."
                    )
        
        return cleaned_data
```

### **5.2 Modal de Duplicata para Origens Estruturadas**

```html
<!-- templates/dominial/components/_modal_duplicata_estruturada.html -->
<div class="modal fade" id="modalDuplicataEstruturada" tabindex="-1">
    <div class="modal-dialog modal-lg">
        <div class="modal-content">
            <div class="modal-header bg-warning">
                <h5 class="modal-title">
                    <i class="fas fa-exclamation-triangle"></i>
                    Duplicatas Encontradas - Origens Estruturadas
                </h5>
                <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
            </div>
            <div class="modal-body">
                <div class="alert alert-info">
                    <i class="fas fa-info-circle"></i>
                    <strong>Origens estruturadas com duplicatas foram encontradas:</strong>
                </div>
                
                <div id="duplicatas-estruturadas-lista">
                    <!-- Preenchido via JavaScript -->
                </div>
                
                <div class="alert alert-warning">
                    <i class="fas fa-exclamation-triangle"></i>
                    <strong>Atenção:</strong> Se você importar estas cadeias, os documentos serão marcados como importados 
                    e você poderá continuar com o lançamento.
                </div>
            </div>
            <div class="modal-footer">
                <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">
                    Cancelar
                </button>
                <button type="button" class="btn btn-success" id="btnImportarDuplicatasEstruturadas">
                    <i class="fas fa-download"></i>
                    Importar Cadeias
                </button>
            </div>
        </div>
    </div>
</div>
```

### **5.3 JavaScript para Modal de Duplicatas Estruturadas**

```javascript
// static/dominial/js/duplicata_estruturada.js

class DuplicataEstruturadaHandler {
    constructor() {
        this.modal = document.getElementById('modalDuplicataEstruturada');
        this.listaContainer = document.getElementById('duplicatas-estruturadas-lista');
        this.btnImportar = document.getElementById('btnImportarDuplicatasEstruturadas');
        
        this.setupEventListeners();
    }
    
    setupEventListeners() {
        this.btnImportar.addEventListener('click', () => {
            this.processarImportacao();
        });
    }
    
    mostrarDuplicatas(duplicatas) {
        this.listaContainer.innerHTML = '';
        
        duplicatas.forEach((duplicata, index) => {
            const origem = duplicata.origem_estruturada;
            const resultado = duplicata.resultado;
            
            const card = document.createElement('div');
            card.className = 'card mb-3';
            card.innerHTML = `
                <div class="card-header">
                    <h6 class="mb-0">
                        <i class="fas fa-file-alt"></i>
                        Origem ${index + 1}: ${origem.numero} - ${origem.cartorio.nome}
                    </h6>
                </div>
                <div class="card-body">
                    <p><strong>Tipo:</strong> ${origem.tipo_origem.get_tipo_display()}</p>
                    <p><strong>Continua Cadeia:</strong> ${origem.tipo_origem.continua_cadeia ? 'Sim' : 'Não'}</p>
                    <p><strong>Documentos Importáveis:</strong> ${resultado.documentos_importaveis.length}</p>
                    <p><strong>Imóvel de Origem:</strong> ${resultado.documento_origem.imovel.matricula}</p>
                </div>
            `;
            
            this.listaContainer.appendChild(card);
        });
        
        // Mostrar modal
        const modal = new bootstrap.Modal(this.modal);
        modal.show();
    }
    
    async processarImportacao() {
        try {
            const response = await fetch('/dominial/api/importar-duplicatas-estruturadas/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCSRFToken()
                },
                body: JSON.stringify({
                    duplicatas: this.duplicatasAtuais
                })
            });
            
            const resultado = await response.json();
            
            if (resultado.sucesso) {
                // Fechar modal e recarregar página
                const modal = bootstrap.Modal.getInstance(this.modal);
                modal.hide();
                
                window.location.reload();
            } else {
                alert('Erro na importação: ' + resultado.mensagem);
            }
            
        } catch (error) {
            console.error('Erro ao processar importação:', error);
            alert('Erro ao processar importação');
        }
    }
    
    getCSRFToken() {
        return document.querySelector('[name=csrfmiddlewaretoken]').value;
    }
}

// Inicializar handler
const duplicataEstruturadaHandler = new DuplicataEstruturadaHandler();
```

## 📊 **BENEFÍCIOS DA INTEGRAÇÃO**

### **✅ Para Duplicatas:**
- **Detecção precisa**: Baseada em dados estruturados
- **Validação robusta**: Previne duplicatas reais
- **Contexto completo**: Sabe se origem continua ou termina cadeia
- **Classificação integrada**: Preserva informações de classificação

### **✅ Para Importação:**
- **Rastreabilidade**: Registra origem estruturada da importação
- **Destaque visual**: Fim de matrícula claramente identificado
- **Classificação preservada**: Mantém informações de origem lídima
- **Performance**: Queries otimizadas com relacionamentos

### **✅ Para Visualização:**
- **Destaque duplo**: Importado + Fim de Matrícula
- **Informações contextuais**: Classificação sempre visível
- **Navegação intuitiva**: Filtros por tipo de origem
- **Histórico completo**: Rastreamento de importações

## 🚀 **PLANO DE IMPLEMENTAÇÃO**

### **Fase 1: Estrutura Base (1-2 dias)**
- [ ] Criar modelo `ImportacaoOrigemEstruturada`
- [ ] Implementar funções de verificação estruturada
- [ ] Criar migrações

### **Fase 2: Serviços (2-3 dias)**
- [ ] Adaptar `DuplicataVerificacaoService`
- [ ] Estender `LancamentoDuplicataService`
- [ ] Implementar `ImportacaoCadeiaService` estruturado

### **Fase 3: Visualização (2-3 dias)**
- [ ] Adaptar `CadeiaDominialTabelaService`
- [ ] Estender `HierarquiaArvoreService`
- [ ] Implementar CSS e JavaScript para destaque

### **Fase 4: Interface (1-2 dias)**
- [ ] Criar modal de duplicatas estruturadas
- [ ] Implementar validação em formulários
- [ ] Testar integração completa

### **Fase 5: Testes e Otimização (1-2 dias)**
- [ ] Testes unitários
- [ ] Testes de integração
- [ ] Otimização de performance

## 🎯 **RESULTADO ESPERADO**

Ao final da implementação, o sistema terá:

1. **Detecção automática** de duplicatas em origens estruturadas
2. **Importação inteligente** preservando contexto estruturado
3. **Destaque visual** de fim de matrícula em documentos importados
4. **Classificação preservada** de origens lídimas
5. **Retrocompatibilidade total** com sistema existente
6. **Performance otimizada** com relacionamentos estruturados

**🎉 Esta integração transformará o sistema em uma ferramenta muito mais poderosa e informativa!** 