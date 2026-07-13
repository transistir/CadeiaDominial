# 📋 Plano de Desenvolvimento - Origens Estruturadas

## 🎯 Visão Geral

Este documento descreve o plano de desenvolvimento para implementar a nova funcionalidade de **Origens Estruturadas** no sistema Cadeia Dominial. A funcionalidade permite que usuários escolham tipos específicos de origem para lançamentos do tipo "Início de Matrícula", controlando o fluxo da cadeia dominial e classificando a origem final dos imóveis.

## 📊 Requisitos Funcionais

### Tipos de Origem Disponíveis
1. **Matrícula** - Número da matrícula e CRI (continua cadeia)
2. **Transcrição** - Número da transcrição e CRI (continua cadeia)
3. **Outra** - Especificação livre (termina cadeia)
4. **Destacamento do Patrimônio Público** - Incra, governo estadual, etc. (termina cadeia)
5. **Registro** - Número, livro e cartório (termina cadeia)
6. **Sem Origem** - Reprodução de fala da transcrição (termina cadeia)

### Classificação Final da Origem
- **Imóvel com Origem Lídima**
- **Imóvel sem Origem**
- **Situação Inconclusa**

### Controle de Cadeia
- **Continua**: Tipos "Matrícula" e "Transcrição"
- **Termina**: Demais tipos (Outra, Destacamento, Registro, Sem Origem)

## 🏗️ Arquitetura da Solução

### Princípios de Design
- ✅ **Aditividade**: Não quebra funcionalidades existentes
- ✅ **Retrocompatibilidade**: Dados antigos continuam funcionando
- ✅ **Minimalismo**: Aproveita estrutura existente
- ✅ **Testabilidade**: Cobertura completa de testes

### Estrutura de Dados
```
Lancamento
├── origens_estruturadas (1:N)
│   ├── tipo_origem (FK)
│   ├── numero (opcional)
│   ├── cartorio (FK, opcional)
│   ├── livro (opcional)
│   └── descricao (opcional)
└── classificacao_origem (1:1)
    ├── classificacao (FK)
    └── observacoes (opcional)
```

## 📋 Fases de Desenvolvimento

### FASE 1: ESTRUTURA DE DADOS

#### Objetivos
- Criar modelos para origens estruturadas
- Implementar migrations seguras
- Criar comandos de inicialização

#### Componentes

**Modelos Principais:**
```python
# dominial/models/origem_estruturada_models.py
class TipoOrigem(models.Model):
    """Tipos de origem estruturada"""
    TIPO_CHOICES = [
        ('matricula', 'Matrícula'),
        ('transcricao', 'Transcrição'),
        ('outra', 'Outra'),
        ('destacamento_publico', 'Destacamento do Patrimônio Público'),
        ('registro', 'Registro'),
        ('sem_origem', 'Sem Origem')
    ]
    
    tipo = models.CharField(max_length=50, choices=TIPO_CHOICES)
    continua_cadeia = models.BooleanField(default=True)
    
    class Meta:
        verbose_name = "Tipo de Origem"
        verbose_name_plural = "Tipos de Origem"

class ClassificacaoOrigem(models.Model):
    """Classificação final da origem"""
    CLASSIFICACAO_CHOICES = [
        ('origem_lidima', 'Imóvel com Origem Lídima'),
        ('sem_origem', 'Imóvel sem Origem'),
        ('inconclusa', 'Situação Inconclusa')
    ]
    
    classificacao = models.CharField(max_length=50, choices=CLASSIFICACAO_CHOICES)
    
    class Meta:
        verbose_name = "Classificação de Origem"
        verbose_name_plural = "Classificações de Origem"

class OrigemEstruturada(models.Model):
    """Origem estruturada de um lançamento"""
    lancamento = models.ForeignKey('Lancamento', on_delete=models.CASCADE, related_name='origens_estruturadas')
    tipo_origem = models.ForeignKey(TipoOrigem, on_delete=models.PROTECT)
    numero = models.CharField(max_length=100, null=True, blank=True)
    cartorio = models.ForeignKey('Cartorios', on_delete=models.PROTECT, null=True, blank=True)
    livro = models.CharField(max_length=50, null=True, blank=True)
    descricao = models.TextField(null=True, blank=True)
    ordem = models.IntegerField(default=0)
    
    class Meta:
        verbose_name = "Origem Estruturada"
        verbose_name_plural = "Origens Estruturadas"
        ordering = ['ordem']

class ClassificacaoImovel(models.Model):
    """Classificação final de origem de um imóvel"""
    imovel = models.OneToOneField('Imovel', on_delete=models.CASCADE, related_name='classificacao_origem')
    classificacao = models.ForeignKey(ClassificacaoOrigem, on_delete=models.PROTECT)
    data_classificacao = models.DateTimeField(auto_now_add=True)
    observacoes = models.TextField(null=True, blank=True)
    
    class Meta:
        verbose_name = "Classificação de Origem do Imóvel"
        verbose_name_plural = "Classificações de Origem dos Imóveis"
```

**Migration:**
```python
# dominial/migrations/0032_origem_estruturada.py
class Migration(migrations.Migration):
    dependencies = [
        ('dominial', '0031_documentoimportado'),
    ]
    
    operations = [
        # Criar tabelas de tipos e classificações
        migrations.CreateModel(...),
        # Adicionar campos de origem estruturada
        migrations.CreateModel(...),
        # Adicionar classificação do imóvel
        migrations.CreateModel(...),
    ]
```

**Comando de Inicialização:**
```python
# dominial/management/commands/criar_tipos_origem_estruturada.py
class Command(BaseCommand):
    help = 'Cria os tipos de origem estruturada e classificações'
    
    def handle(self, *args, **kwargs):
        # Criar tipos de origem
        tipos_origem = [
            {'tipo': 'matricula', 'continua_cadeia': True},
            {'tipo': 'transcricao', 'continua_cadeia': True},
            {'tipo': 'outra', 'continua_cadeia': False},
            {'tipo': 'destacamento_publico', 'continua_cadeia': False},
            {'tipo': 'registro', 'continua_cadeia': False},
            {'tipo': 'sem_origem', 'continua_cadeia': False}
        ]
        
        # Criar classificações
        classificacoes = [
            'origem_lidima',
            'sem_origem', 
            'inconclusa'
        ]
```

#### Entregáveis
- [ ] Modelos de dados criados
- [ ] Migration implementada
- [ ] Comando de inicialização funcionando
- [ ] Testes unitários dos modelos

---

### FASE 2: SERVICES ESPECIALIZADOS

#### Objetivos
- Criar services para gerenciar origens estruturadas
- Implementar lógica de processamento
- Criar service de classificação

#### Componentes

**Service de Origem Estruturada:**
```python
# dominial/services/origem_estruturada_service.py
class OrigemEstruturadaService:
    """Service para gerenciar origens estruturadas"""
    
    @staticmethod
    def processar_origens_estruturadas(lancamento, dados_origens):
        """Processa origens estruturadas de um lançamento"""
        # Limpar origens existentes
        lancamento.origens_estruturadas.all().delete()
        
        # Processar cada origem
        for i, origem_data in enumerate(dados_origens):
            origem = OrigemEstruturada.objects.create(
                lancamento=lancamento,
                tipo_origem_id=origem_data['tipo_id'],
                numero=origem_data.get('numero'),
                cartorio_id=origem_data.get('cartorio_id'),
                livro=origem_data.get('livro'),
                descricao=origem_data.get('descricao'),
                ordem=i
            )
        
        # Verificar se cadeia termina
        return OrigemEstruturadaService._verificar_termino_cadeia(lancamento)
    
    @staticmethod
    def _verificar_termino_cadeia(lancamento):
        """Verifica se a cadeia termina baseado nas origens"""
        origens = lancamento.origens_estruturadas.all()
        return not any(origem.tipo_origem.continua_cadeia for origem in origens)
```

**Service de Classificação:**
```python
# dominial/services/classificacao_origem_service.py
class ClassificacaoOrigemService:
    """Service para gerenciar classificações de origem"""
    
    @staticmethod
    def classificar_imovel(imovel, classificacao_id, observacoes=None):
        """Classifica a origem de um imóvel"""
        classificacao, created = ClassificacaoImovel.objects.get_or_create(
            imovel=imovel,
            defaults={
                'classificacao_id': classificacao_id,
                'observacoes': observacoes
            }
        )
        
        if not created:
            classificacao.classificacao_id = classificacao_id
            classificacao.observacoes = observacoes
            classificacao.save()
        
        return classificacao
    
    @staticmethod
    def obter_imoveis_por_classificacao(classificacao_tipo):
        """Obtém imóveis por tipo de classificação"""
        return Imovel.objects.filter(
            classificacao_origem__classificacao__classificacao=classificacao_tipo
        ).select_related('classificacao_origem__classificacao')
```

#### Entregáveis
- [ ] Service de origem estruturada implementado
- [ ] Service de classificação implementado
- [ ] Testes unitários dos services
- [ ] Integração com services existentes

---

### FASE 3: FORMULÁRIO E INTERFACE

#### Objetivos
- Criar interface para origens estruturadas
- Implementar JavaScript especializado
- Integrar com formulário existente

#### Componentes

**Template de Origem Estruturada:**
```html
<!-- templates/dominial/components/_origem_estruturada_form.html -->
<div class="origem-estruturada-group">
    <h5>Origens Estruturadas</h5>
    
    <div id="origens-estruturadas-container">
        <!-- Origens serão adicionadas dinamicamente -->
    </div>
    
    <button type="button" class="btn btn-sm btn-outline" onclick="adicionarOrigemEstruturada()">
        ➕ Adicionar Origem
    </button>
</div>

<!-- Template para cada origem -->
<template id="template-origem-estruturada">
    <div class="origem-estruturada-item">
        <div class="form-group tipo-origem-field">
            <label>Tipo de Origem *</label>
            <select name="tipo_origem[]" class="tipo-origem-select" onchange="toggleCamposOrigem(this)">
                <option value="">Selecione...</option>
                <option value="matricula" data-continua="true">Matrícula</option>
                <option value="transcricao" data-continua="true">Transcrição</option>
                <option value="outra" data-continua="false">Outra</option>
                <option value="destacamento_publico" data-continua="false">Destacamento do Patrimônio Público</option>
                <option value="registro" data-continua="false">Registro</option>
                <option value="sem_origem" data-continua="false">Sem Origem</option>
            </select>
        </div>
        
        <!-- Campos específicos por tipo -->
        <div class="campos-especificos" style="display: none;">
            <!-- Serão preenchidos via JavaScript -->
        </div>
        
        <button type="button" class="btn btn-sm btn-danger remove-origem" onclick="removerOrigemEstruturada(this)">×</button>
    </div>
</template>
```

**JavaScript Especializado:**
```javascript
// static/dominial/js/origem_estruturada.js
class OrigemEstruturadaManager {
    constructor() {
        this.container = document.getElementById('origens-estruturadas-container');
        this.template = document.getElementById('template-origem-estruturada');
        this.contador = 0;
    }
    
    adicionarOrigem() {
        const clone = this.template.content.cloneNode(true);
        const item = clone.querySelector('.origem-estruturada-item');
        
        // Configurar IDs únicos
        this.configurarIds(item);
        
        // Adicionar ao container
        this.container.appendChild(clone);
        
        // Configurar autocomplete
        this.configurarAutocomplete(item);
        
        this.contador++;
    }
    
    toggleCamposOrigem(select) {
        const item = select.closest('.origem-estruturada-item');
        const camposEspecificos = item.querySelector('.campos-especificos');
        const tipo = select.value;
        
        // Limpar campos específicos
        camposEspecificos.innerHTML = '';
        
        // Adicionar campos baseado no tipo
        switch(tipo) {
            case 'matricula':
            case 'transcricao':
                this.adicionarCamposMatriculaTranscricao(camposEspecificos);
                break;
            case 'outra':
                this.adicionarCampoDescricao(camposEspecificos);
                break;
            case 'destacamento_publico':
                this.adicionarCampoDescricao(camposEspecificos);
                break;
            case 'registro':
                this.adicionarCamposRegistro(camposEspecificos);
                break;
            case 'sem_origem':
                this.adicionarCampoDescricao(camposEspecificos);
                break;
        }
        
        camposEspecificos.style.display = 'block';
    }
    
    verificarTerminoCadeia() {
        const origens = this.container.querySelectorAll('.tipo-origem-select');
        let terminaCadeia = false;
        
        for (const origem of origens) {
            const option = origem.options[origem.selectedIndex];
            if (option && option.dataset.continua === 'false') {
                terminaCadeia = true;
                break;
            }
        }
        
        // Mostrar/ocultar classificação final
        this.toggleClassificacaoFinal(terminaCadeia);
    }
}
```

#### Entregáveis
- [ ] Template de origem estruturada criado
- [ ] JavaScript especializado implementado
- [ ] Integração com formulário existente
- [ ] Validação de campos funcionando

---

### FASE 4: INTEGRAÇÃO COM CADEIA DOMINIAL

#### Objetivos
- Modificar service de hierarquia para origens estruturadas
- Implementar indicadores visuais na árvore
- Criar lista de imóveis por classificação

#### Componentes

**Service de Hierarquia Estruturada:**
```python
# dominial/services/hierarquia_estruturada_service.py
class HierarquiaEstruturadaService:
    """Service para hierarquia com origens estruturadas"""
    
    @staticmethod
    def obter_tronco_principal_estruturado(imovel, escolhas_origem=None):
        """Obtém tronco principal considerando origens estruturadas"""
        tronco = []
        documentos_processados = set()
        
        # Buscar documento atual
        documento_atual = imovel.documentos.filter(tipo__tipo='matricula').first()
        
        while documento_atual and documento_atual.id not in documentos_processados:
            tronco.append(documento_atual)
            documentos_processados.add(documento_atual.id)
            
            # Buscar próximo documento baseado em origens estruturadas
            proximo_documento = HierarquiaEstruturadaService._buscar_proximo_documento_estruturado(
                documento_atual, escolhas_origem
            )
            
            if not proximo_documento:
                break
                
            documento_atual = proximo_documento
        
        return tronco
    
    @staticmethod
    def _buscar_proximo_documento_estruturado(documento, escolhas_origem):
        """Busca próximo documento baseado em origens estruturadas"""
        # Buscar lançamentos com origens estruturadas
        lancamentos_estruturados = documento.lancamentos.filter(
            origens_estruturadas__isnull=False
        ).prefetch_related('origens_estruturadas__tipo_origem')
        
        for lancamento in lancamentos_estruturados:
            # Verificar se há origem que continua a cadeia
            for origem in lancamento.origens_estruturadas.all():
                if origem.tipo_origem.continua_cadeia and origem.numero:
                    # Buscar documento correspondente
                    proximo_documento = Documento.objects.filter(
                        numero=origem.numero,
                        cartorio=origem.cartorio
                    ).first()
                    
                    if proximo_documento:
                        return proximo_documento
        
        return None
```

**Indicadores Visuais na Árvore:**
```javascript
// static/dominial/js/cadeia_dominial_estruturada.js
class CadeiaDominialEstruturada {
    constructor() {
        this.indicadores = {
            termino_cadeia: '🔚',
            origem_lidima: '✅',
            sem_origem: '❌',
            inconclusa: '❓'
        };
    }
    
    renderizarDocumento(documento, dados) {
        const card = document.createElement('div');
        card.className = 'documento-card';
        
        // Adicionar indicadores baseado na classificação
        if (dados.termina_cadeia) {
            card.classList.add('termino-cadeia');
            card.innerHTML += `<div class="indicador-termino">${this.indicadores.termino_cadeia}</div>`;
        }
        
        if (dados.classificacao) {
            card.classList.add(`classificacao-${dados.classificacao}`);
            card.innerHTML += `<div class="indicador-classificacao">${this.indicadores[dados.classificacao]}</div>`;
        }
        
        return card;
    }
}
```

#### Entregáveis
- [ ] Service de hierarquia estruturada implementado
- [ ] Indicadores visuais na árvore funcionando
- [ ] Lista de imóveis por classificação criada
- [ ] Integração com visualização existente

---

### FASE 5: TESTES E VALIDAÇÃO

#### Objetivos
- Implementar testes unitários completos
- Criar testes de integração
- Validar funcionalidades

#### Componentes

**Testes Unitários:**
```python
# dominial/tests/test_origem_estruturada.py
class OrigemEstruturadaTestCase(TestCase):
    def setUp(self):
        # Criar dados de teste
        self.tipo_matricula = TipoOrigem.objects.create(
            tipo='matricula', continua_cadeia=True
        )
        self.tipo_outra = TipoOrigem.objects.create(
            tipo='outra', continua_cadeia=False
        )
    
    def test_processar_origens_estruturadas(self):
        """Testa processamento de origens estruturadas"""
        lancamento = self.criar_lancamento_teste()
        
        dados_origens = [
            {
                'tipo_id': self.tipo_matricula.id,
                'numero': 'M123',
                'cartorio_id': 1
            },
            {
                'tipo_id': self.tipo_outra.id,
                'descricao': 'Sentença judicial'
            }
        ]
        
        termina_cadeia = OrigemEstruturadaService.processar_origens_estruturadas(
            lancamento, dados_origens
        )
        
        self.assertTrue(termina_cadeia)
        self.assertEqual(lancamento.origens_estruturadas.count(), 2)
    
    def test_hierarquia_estruturada(self):
        """Testa hierarquia com origens estruturadas"""
        imovel = self.criar_imovel_teste()
        
        tronco = HierarquiaEstruturadaService.obter_tronco_principal_estruturado(imovel)
        
        self.assertIsNotNone(tronco)
        self.assertGreater(len(tronco), 0)
```

**Testes de Integração:**
```python
# dominial/tests/test_integracao_origem_estruturada.py
class IntegracaoOrigemEstruturadaTestCase(TestCase):
    def test_fluxo_completo_inicio_matricula(self):
        """Testa fluxo completo de início de matrícula com origens estruturadas"""
        # 1. Criar lançamento início de matrícula
        lancamento = self.criar_lancamento_inicio_matricula()
        
        # 2. Adicionar origens estruturadas
        dados_origens = [
            {'tipo_id': 1, 'numero': 'M123', 'cartorio_id': 1},  # Matrícula
            {'tipo_id': 3, 'descricao': 'Sentença judicial'}     # Outra
        ]
        
        # 3. Processar origens
        termina_cadeia = OrigemEstruturadaService.processar_origens_estruturadas(
            lancamento, dados_origens
        )
        
        # 4. Verificar que cadeia termina
        self.assertTrue(termina_cadeia)
        
        # 5. Classificar imóvel
        classificacao = ClassificacaoOrigemService.classificar_imovel(
            lancamento.documento.imovel, 1, 'Teste'
        )
        
        self.assertIsNotNone(classificacao)
```

#### Entregáveis
- [ ] Testes unitários implementados
- [ ] Testes de integração criados
- [ ] Cobertura de testes > 90%
- [ ] Validação de funcionalidades

---

### FASE 6: MIGRAÇÃO E DEPLOY

#### Objetivos
- Implementar migração de dados existentes
- Configurar feature flag
- Preparar deploy seguro

#### Componentes

**Script de Migração de Dados:**
```python
# dominial/management/commands/migrar_origens_estruturadas.py
class Command(BaseCommand):
    help = 'Migra origens existentes para estrutura estruturada'
    
    def handle(self, *args, **kwargs):
        # Migrar lançamentos existentes
        lancamentos_com_origem = Lancamento.objects.filter(
            origem__isnull=False
        ).exclude(origem='')
        
        for lancamento in lancamentos_com_origem:
            # Converter origem antiga para estruturada
            self.migrar_origem_antiga(lancamento)
    
    def migrar_origem_antiga(self, lancamento):
        """Migra origem antiga para estrutura estruturada"""
        if not lancamento.origem:
            return
        
        # Extrair origens do texto
        origens = [o.strip() for o in lancamento.origem.split(';')]
        
        for i, origem_texto in enumerate(origens):
            # Determinar tipo baseado no padrão
            tipo_origem = self.determinar_tipo_origem(origem_texto)
            
            # Criar origem estruturada
            OrigemEstruturada.objects.create(
                lancamento=lancamento,
                tipo_origem=tipo_origem,
                numero=self.extrair_numero(origem_texto),
                cartorio=lancamento.cartorio_origem,
                ordem=i
            )
```

**Feature Flag:**
```python
# settings.py
ORIGEM_ESTRUTURADA_ENABLED = os.getenv('ORIGEM_ESTRUTURADA_ENABLED', 'false').lower() == 'true'

# views.py
def lancamento_form(request):
    if settings.ORIGEM_ESTRUTURADA_ENABLED:
        return lancamento_form_estruturado(request)
    else:
        return lancamento_form_legado(request)
```

#### Entregáveis
- [ ] Script de migração implementado
- [ ] Feature flag configurado
- [ ] Deploy preparado
- [ ] Rollback testado

---

## 🎯 Critérios de Sucesso

### Funcionais
- [ ] Usuários podem escolher tipos de origem estruturada
- [ ] Sistema controla corretamente o fluxo da cadeia
- [ ] Classificação final é aplicada corretamente
- [ ] Indicadores visuais funcionam na árvore
- [ ] Lista de imóveis por classificação está disponível

### Técnicos
- [ ] Cobertura de testes > 90%
- [ ] Performance mantida ou melhorada
- [ ] Código segue padrões Django
- [ ] Documentação completa
- [ ] Feature flag funcionando

### Qualidade
- [ ] Zero regressões em funcionalidades existentes
- [ ] Interface intuitiva e responsiva
- [ ] Validações robustas
- [ ] Tratamento de erros adequado

---

## 🔄 Fluxo de Desenvolvimento

### 1. Preparação
```bash
# Criar branch de desenvolvimento
git checkout -b feature/origem-estruturada

# Instalar dependências
pip install -r requirements.txt

# Executar testes existentes
python manage.py test
```

### 2. Implementação por Fase
```bash
# Para cada fase:
# 1. Implementar código
# 2. Executar testes
# 3. Fazer commit
# 4. Documentar mudanças
```

### 3. Validação
```bash
# Executar todos os testes
python manage.py test

# Verificar cobertura
coverage run --source='.' manage.py test
coverage report

# Validar migrations
python manage.py makemigrations --dry-run
```

### 4. Deploy
```bash
# Ativar feature flag
export ORIGEM_ESTRUTURADA_ENABLED=true

# Executar migrations
python manage.py migrate

# Coletar arquivos estáticos
python manage.py collectstatic --noinput

# Reiniciar aplicação
sudo systemctl restart gunicorn
```

---

## 📚 Documentação Relacionada

- [Refatoração Fase 3](../refatoracao/REFATORACAO_FASE_3_COMPLETA.md)
- [Lógica da Cadeia Dominial](../LOGICA_CADEIA_DOMINIAL_TABELA.md)
- [Verificação de Duplicatas](../verificacao-duplicatas/RESUMO_VERIFICACAO_DUPLICATAS.md)
- [Reformulação dos Cartórios](../cartorios/RESUMO_REFORMULACAO_CARTORIOS.md)

---

## 🎉 Conclusão

Este plano garante uma implementação segura, aditiva e bem testada da funcionalidade de origens estruturadas. A abordagem por fases permite desenvolvimento incremental com validação contínua, mantendo a estabilidade do sistema em produção.

**Principais Benefícios:**
- ✅ Controle preciso do fluxo da cadeia dominial
- ✅ Classificação estruturada das origens
- ✅ Interface intuitiva para usuários
- ✅ Indicadores visuais claros
- ✅ Retrocompatibilidade total
- ✅ Código limpo e testável 