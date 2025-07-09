# Plano de Reformulação do Sistema de Cartórios

## 1. Contexto e Mudanças Fundamentais

### 1.1 Tipos de Cartórios
- **CRI (Cartório de Registro de Imóveis)**: Sigla CRI
  - Usado no cadastro de imóveis
  - Usado na inserção de origens
  - Filtros específicos para cartórios de imóveis
- **Cartório de Notas**: 
  - Usado em transações (tipo registro)
  - Para registros de compra e venda, doações, etc.

### 1.2 Mudanças Principais
- **Eliminação de inserção manual**: Usuário não pode mais digitar cartórios
- **Seleção obrigatória**: Sempre escolher de uma lista existente
- **Modal de criação**: Opção para criar novo cartório via modal
- **Separação clara**: CRI vs Cartório de Notas

## 2. Análise da Situação Atual

### 2.1 Onde Cartórios são Usados
1. **Cadastro de Imóveis** (`imovel_form.html`)
   - Campo: `novo-cartorio-nome`
   - Modal para criar novo cartório
   - Autocomplete existente

2. **Formulário de Documentos** (`documento_form.html`)
   - Campo: `cartorio` (input text)
   - Autocomplete: `/cartorio-imoveis-autocomplete/`
   - Criação automática se não existir

3. **Formulário de Lançamentos** (`lancamento_form.html`)
   - Campo básico: `cartorio_nome` (input text)
   - Campo transação: `cartorio_transacao_nome` (input text)
   - Campo origem: `cartorio_origem_nome[]` (múltiplos inputs)
   - Autocomplete: `/dominial/cartorio-autocomplete/`
   - Criação automática em múltiplos serviços

4. **Origem de Lançamentos** (`_area_origem_form.html`)
   - Campos múltiplos para cartórios de origem
   - Criação automática

### 2.2 Problemas Identificados
- Criação automática inconsistente
- Falta de separação entre tipos de cartórios
- Usuário pode digitar qualquer coisa
- Validações dispersas
- Código duplicado em múltiplos serviços

## 3. Plano de Implementação

### Fase 1: Modelagem e Estrutura Base

#### 3.1 Modificar Modelo Cartorios
```python
class Cartorios(models.Model):
    TIPO_CHOICES = [
        ('cri', 'Cartório de Registro de Imóveis (CRI)'),
        ('notas', 'Cartório de Notas'),
    ]
    
    nome = models.CharField(max_length=200)
    cns = models.CharField(max_length=20, unique=True)
    tipo = models.CharField(max_length=10, choices=TIPO_CHOICES, default='cri')
    endereco = models.CharField(max_length=200, null=True, blank=True)
    telefone = models.CharField(max_length=20, null=True, blank=True)
    email = models.EmailField(null=True, blank=True)
    estado = models.CharField(max_length=2, null=True, blank=True)
    cidade = models.CharField(max_length=100, null=True, blank=True)
    
    class Meta:
        verbose_name = 'Cartório'
        verbose_name_plural = 'Cartórios'
        ordering = ['tipo', 'estado', 'cidade', 'nome']
```

#### 3.2 Criar CartorioService Centralizado
```python
class CartorioService:
    @staticmethod
    def obter_cartorios_por_tipo(tipo):
        """Obtém cartórios por tipo (cri ou notas)"""
        
    @staticmethod
    def criar_cartorio_via_modal(dados):
        """Cria cartório via modal com validações"""
        
    @staticmethod
    def validar_cartorio_existente(nome, tipo):
        """Valida se cartório existe no tipo especificado"""
        
    @staticmethod
    def obter_cartorio_por_id(id):
        """Obtém cartório por ID com validações"""
```

### Fase 2: Migração de Dados

#### 3.3 Script de Migração
```python
# management/commands/migrar_tipos_cartorio.py
class Command(BaseCommand):
    def handle(self, *args, **kwargs):
        # 1. Adicionar campo tipo aos cartórios existentes
        # 2. Classificar cartórios existentes baseado em regras
        # 3. Criar cartórios de notas a partir de dados existentes
        # 4. Validar consistência dos dados
```

#### 3.4 Regras de Classificação
- **CRI**: Cartórios que contêm palavras-chave de imóveis
- **Cartório de Notas**: Cartórios que contêm palavras-chave de notas
- **Padrão**: CRI para cartórios sem classificação clara

### Fase 3: Atualização das Views de Autocomplete

#### 3.5 Novas Views de Autocomplete
```python
def cartorio_cri_autocomplete(request):
    """Autocomplete para Cartórios de Registro de Imóveis"""
    
def cartorio_notas_autocomplete(request):
    """Autocomplete para Cartórios de Notas"""
    
def cartorio_modal_cri(request):
    """Modal para criar novo CRI"""
    
def cartorio_modal_notas(request):
    """Modal para criar novo Cartório de Notas"""
```

### Fase 4: Atualização dos Templates

#### 3.6 Padrão de Campo de Cartório
```html
<!-- Novo padrão para todos os campos de cartório -->
<div class="form-group">
    <label for="cartorio">Cartório</label>
    <div class="cartorio-select-container">
        <select name="cartorio" id="cartorio" required>
            <option value="">Selecione um cartório...</option>
            <!-- Opções carregadas via AJAX -->
        </select>
        <button type="button" class="btn btn-sm btn-outline-primary" 
                onclick="abrirModalCartorio('cri')">
            + Novo Cartório
        </button>
    </div>
</div>
```

#### 3.7 Modal Unificado
```html
<!-- templates/dominial/components/_cartorio_modal.html -->
<div class="modal fade" id="cartorioModal" tabindex="-1">
    <div class="modal-dialog">
        <div class="modal-content">
            <div class="modal-header">
                <h5 class="modal-title">Novo Cartório</h5>
                <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
            </div>
            <div class="modal-body">
                <form id="cartorioForm">
                    <div class="form-group">
                        <label for="tipo_cartorio">Tipo</label>
                        <select name="tipo" id="tipo_cartorio" required>
                            <option value="cri">Cartório de Registro de Imóveis (CRI)</option>
                            <option value="notas">Cartório de Notas</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label for="nome_cartorio">Nome</label>
                        <input type="text" name="nome" id="nome_cartorio" required>
                    </div>
                    <div class="form-group">
                        <label for="cidade_cartorio">Cidade</label>
                        <input type="text" name="cidade" id="cidade_cartorio">
                    </div>
                    <div class="form-group">
                        <label for="estado_cartorio">Estado</label>
                        <input type="text" name="estado" id="estado_cartorio" maxlength="2">
                    </div>
                </form>
            </div>
            <div class="modal-footer">
                <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancelar</button>
                <button type="button" class="btn btn-primary" onclick="salvarCartorio()">Salvar</button>
            </div>
        </div>
    </div>
</div>
```

### Fase 5: Atualização dos JavaScript

#### 3.8 Novo JavaScript Unificado
```javascript
// static/dominial/js/cartorio_service.js
class CartorioService {
    static async carregarCartorios(tipo, selectElement) {
        // Carrega cartórios por tipo via AJAX
    }
    
    static abrirModalCartorio(tipo) {
        // Abre modal para criar novo cartório
    }
    
    static async salvarCartorio(formData) {
        // Salva novo cartório via AJAX
    }
    
    static atualizarSelect(selectElement, cartorios) {
        // Atualiza select com novos dados
    }
}
```

### Fase 6: Atualização dos Serviços

#### 3.9 Remover Criação Automática
```python
# Remover de todos os serviços:
# - LancamentoCamposService
# - LancamentoFormService  
# - DocumentoService
# - HierarquiaOrigemService

# Substituir por:
def processar_cartorio(request, campo_nome, tipo_cartorio):
    cartorio_id = request.POST.get(campo_nome)
    if not cartorio_id:
        raise ValidationError(f"Cartório é obrigatório")
    
    try:
        return Cartorios.objects.get(id=cartorio_id, tipo=tipo_cartorio)
    except Cartorios.DoesNotExist:
        raise ValidationError(f"Cartório inválido")
```

### Fase 7: Atualização dos Comandos de Importação

#### 3.10 Comandos de Importação Separados
```python
# management/commands/importar_cartorios_cri.py
class Command(BaseCommand):
    def handle(self, *args, **kwargs):
        # Importar apenas cartórios de registro de imóveis
        # Aplicar filtros específicos para CRI

# management/commands/importar_cartorios_notas.py  
class Command(BaseCommand):
    def handle(self, *args, **kwargs):
        # Importar apenas cartórios de notas
        # Aplicar filtros específicos para notas
```

## 4. Cronograma de Implementação

### Semana 1: Estrutura Base
- [ ] Modificar modelo Cartorios
- [ ] Criar CartorioService
- [ ] Implementar migração de dados
- [ ] Criar novas views de autocomplete

### Semana 2: Templates e JavaScript
- [ ] Criar modal unificado
- [ ] Implementar JavaScript unificado
- [ ] Atualizar templates de formulários
- [ ] Testar funcionalidades básicas

### Semana 3: Serviços e Validações
- [ ] Remover criação automática
- [ ] Implementar validações centralizadas
- [ ] Atualizar todos os serviços
- [ ] Testar fluxos completos

### Semana 4: Importação e Finalização
- [ ] Atualizar comandos de importação
- [ ] Testes de integração
- [ ] Documentação
- [ ] Deploy

## 5. Benefícios Esperados

### 5.1 Para o Usuário
- **Clareza**: Separação clara entre tipos de cartórios
- **Consistência**: Mesmo padrão em todos os formulários
- **Controle**: Não pode inserir dados inválidos
- **Facilidade**: Modal simplificado para criar novos cartórios

### 5.2 Para o Sistema
- **Integridade**: Dados mais consistentes
- **Performance**: Menos queries desnecessárias
- **Manutenibilidade**: Código centralizado e organizado
- **Escalabilidade**: Fácil adicionar novos tipos de cartórios

## 6. Riscos e Mitigações

### 6.1 Riscos
- **Dados existentes**: Cartórios mal classificados
- **Usabilidade**: Usuários acostumados com digitação livre
- **Performance**: Muitas queries de autocomplete

### 6.2 Mitigações
- **Script de migração robusto**: Classificar dados existentes
- **Interface intuitiva**: Modal fácil de usar
- **Cache**: Implementar cache para autocomplete
- **Testes**: Testes extensivos antes do deploy

## 7. Próximos Passos

1. **Aprovação do plano**: Revisar e aprovar este planejamento
2. **Criação de branch**: Criar branch específica para esta feature
3. **Implementação gradual**: Seguir cronograma proposto
4. **Testes contínuos**: Testar cada fase antes de prosseguir
5. **Documentação**: Atualizar documentação conforme implementação

---

**Status**: Planejamento criado
**Próximo**: Aguardando aprovação para iniciar implementação 