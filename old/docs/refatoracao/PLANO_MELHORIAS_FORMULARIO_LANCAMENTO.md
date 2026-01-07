# Plano de Melhorias - Formulário de Lançamento

## Análise da Situação Atual

### Tipos de Documento
- **Transcrição**: Documento que transcreve informações de outro documento
- **Matrícula**: Documento principal de registro do imóvel

### Tipos de Lançamento por Documento
- **Matrícula**: Averbação, Registro, Início de Matrícula
- **Transcrição**: Averbação, Início de Matrícula (não tem Registro)

### Estrutura Atual
- Formulário com campos básicos (livro, folha, data, cartório)
- Campos específicos por tipo de lançamento
- Sistema de autocomplete para pessoas e cartórios
- Geração automática de números de lançamento

## Demandas dos Usuários

### 1. Melhorias na Tela "Novo Lançamento"

#### 1.1 Destaque da Matrícula
- **Problema**: Matrícula não está em evidência
- **Solução**: Criar seção destacada no topo do formulário

#### 1.2 Abolir Livro e Folha em Lançamentos Repetidos
- **Problema**: Usuários precisam preencher livro/folha em todos os lançamentos
- **Solução**: 
  - Herdar automaticamente do documento pai
  - Permitir edição apenas quando necessário
  - Mostrar visualmente que são herdados

#### 1.3 Campo de Área
- **Problema**: Não existe campo de área
- **Solução**: Adicionar campo com 4 casas decimais

#### 1.4 Visualização de Lançamentos Anteriores
- **Problema**: Não é possível ver lançamentos já feitos
- **Solução**: Adicionar tabela/listagem dos lançamentos existentes

#### 1.5 Trocar "Cartório" por "Registro Imobiliário"
- **Problema**: Terminologia incorreta
- **Solução**: Alterar labels e textos

#### 1.6 Impedir Criação de Cartórios Novos
- **Problema**: Usuários podem criar cartórios inexistentes
- **Solução**: Forçar seleção apenas de cartórios existentes

#### 1.7 Separar Cartórios de Registro e Notas
- **Problema**: Cartórios de notas aparecem na lista de registros
- **Solução**: Criar categorização de cartórios

#### 1.8 Campos Opcionais para Averbação
- **Problema**: Averbação não tem campos de transmitentes/adquirentes
- **Solução**: Adicionar campos opcionais

### 2. Melhorias na Origem

#### 2.1 Opções de Origem Estruturadas
- **Problema**: Campo livre pode causar inconsistências
- **Solução**: Criar opções estruturadas:
  - Matrícula (número + CRI)
  - Transcrição (número + CRI)
  - Outra (especificação livre)
  - Destacamento do patrimônio público
  - Registro (número + livro + cartório)
  - Sem origem (reprodução de fala)

#### 2.2 Finalização da Cadeia
- **Problema**: Não há indicação clara quando a cadeia termina
- **Solução**: 
  - Marcar visualmente documentos finais
  - Solicitar classificação da origem:
    - Imóvel com origem lídima
    - Imóvel sem origem
    - Situação inconclusa

#### 2.3 Lista de Imóveis por Origem
- **Problema**: Não há relatório de imóveis por tipo de origem
- **Solução**: Criar relatório/listagem

## Plano de Implementação

### Fase 1: Melhorias Visuais e UX

#### 1.1 Destaque da Matrícula
```html
<!-- Novo componente: _documento_destaque.html -->
<div class="documento-destaque">
    <h3>📋 {{ documento.tipo.get_tipo_display }} {{ documento.numero }}</h3>
    <div class="documento-info">
        <span><strong>Registro Imobiliário:</strong> {{ documento.cartorio.nome }}</span>
        <span><strong>Livro:</strong> {{ documento.livro }}</span>
        <span><strong>Folha:</strong> {{ documento.folha }}</span>
    </div>
</div>
```

#### 1.2 Herança de Livro/Folha
```python
# Modificar LancamentoFormService
def processar_dados_lancamento(request, tipo_lanc):
    dados = {}
    # ... código existente ...
    
    # Herdar livro e folha do documento se não fornecidos
    if not dados.get('livro_origem'):
        dados['livro_origem'] = documento_ativo.livro
    if not dados.get('folha_origem'):
        dados['folha_origem'] = documento_ativo.folha
    
    return dados
```

#### 1.3 Campo de Área com 4 Casas Decimais
```python
# Modificar modelo Lancamento
area = models.DecimalField(
    max_digits=12, 
    decimal_places=4,  # Alterar de 2 para 4
    null=True, 
    blank=True,
    help_text="Área em hectares com 4 casas decimais"
)
```

### Fase 2: Melhorias na Interface

#### 2.1 Listagem de Lançamentos Existentes
```html
<!-- Novo componente: _lancamentos_existentes.html -->
<div class="lancamentos-existentes">
    <h4>Lançamentos Existentes</h4>
    <table class="table">
        <thead>
            <tr>
                <th>Número</th>
                <th>Tipo</th>
                <th>Data</th>
                <th>Área</th>
                <th>Ações</th>
            </tr>
        </thead>
        <tbody>
            {% for lanc in lancamentos_existentes %}
            <tr>
                <td>{{ lanc.numero_lancamento }}</td>
                <td>{{ lanc.tipo.get_tipo_display }}</td>
                <td>{{ lanc.data|date:'d/m/Y' }}</td>
                <td>{{ lanc.area|floatformat:4 }}</td>
                <td>
                    <a href="{% url 'editar_lancamento' ... %}" class="btn btn-sm btn-primary">Editar</a>
                </td>
            </tr>
            {% endfor %}
        </tbody>
    </table>
</div>
```

#### 2.2 Troca de Terminologia
```html
<!-- Modificar _lancamento_basico_form.html -->
<div class="form-group">
    <label for="cartorio">Registro Imobiliário *</label>
    <div class="autocomplete-container">
        <input type="text" name="cartorio_nome" id="cartorio_nome" 
               placeholder="Digite o nome do registro imobiliário" autocomplete="off" required>
        <!-- ... resto do código ... -->
    </div>
</div>
```

### Fase 3: Validações e Controles

#### 3.1 Impedir Criação de Cartórios
```javascript
// Modificar lancamento_form.js
function setupCartorioAutocomplete(input, hidden, suggestions) {
    // ... código existente ...
    
    // Impedir criação de novos cartórios
    input.addEventListener('blur', function() {
        const selectedValue = hidden.value;
        if (!selectedValue) {
            input.value = '';
            showError('Selecione um registro imobiliário existente');
        }
    });
}
```

#### 3.2 Categorização de Cartórios
```python
# Adicionar ao modelo Cartorios
TIPO_CHOICES = [
    ('registro', 'Registro Imobiliário'),
    ('notas', 'Cartório de Notas'),
    ('outro', 'Outro')
]
tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, default='registro')
```

### Fase 4: Sistema de Origem Estruturado

#### 4.1 Novo Modelo para Origem
```python
class OrigemTipo(models.Model):
    TIPO_CHOICES = [
        ('matricula', 'Matrícula'),
        ('transcricao', 'Transcrição'),
        ('outra', 'Outra'),
        ('destacamento', 'Destacamento do Patrimônio Público'),
        ('registro', 'Registro'),
        ('sem_origem', 'Sem Origem')
    ]
    
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES)
    descricao = models.TextField()
    especificacao = models.CharField(max_length=255, blank=True)
    
    class Meta:
        verbose_name = "Tipo de Origem"
        verbose_name_plural = "Tipos de Origem"

class OrigemClassificacao(models.Model):
    CLASSIFICACAO_CHOICES = [
        ('lídima', 'Imóvel com Origem Lídima'),
        ('sem_origem', 'Imóvel Sem Origem'),
        ('inconclusa', 'Situação Inconclusa')
    ]
    
    documento = models.OneToOneField('Documento', on_delete=models.CASCADE)
    classificacao = models.CharField(max_length=20, choices=CLASSIFICACAO_CHOICES)
    observacoes = models.TextField(blank=True)
    
    class Meta:
        verbose_name = "Classificação de Origem"
        verbose_name_plural = "Classificações de Origem"
```

#### 4.2 Formulário de Origem Estruturado
```html
<!-- Novo componente: _origem_estruturada.html -->
<div class="origem-estruturada">
    <h4>Origem do Documento</h4>
    
    <div class="form-group">
        <label>Tipo de Origem *</label>
        <select name="tipo_origem" id="tipo_origem" required>
            <option value="">Selecione...</option>
            <option value="matricula">Matrícula</option>
            <option value="transcricao">Transcrição</option>
            <option value="outra">Outra</option>
            <option value="destacamento">Destacamento do Patrimônio Público</option>
            <option value="registro">Registro</option>
            <option value="sem_origem">Sem Origem</option>
        </select>
    </div>
    
    <!-- Campos específicos por tipo -->
    <div id="campos-matricula" class="campos-origem hidden">
        <div class="grid-2">
            <div class="form-group">
                <label for="numero_matricula">Número da Matrícula</label>
                <input type="text" name="numero_matricula" id="numero_matricula">
            </div>
            <div class="form-group">
                <label for="cri_matricula">CRI</label>
                <input type="text" name="cri_matricula" id="cri_matricula">
            </div>
        </div>
    </div>
    
    <!-- Outros campos específicos... -->
</div>
```

### Fase 5: Relatórios e Listagens

#### 5.1 Relatório de Imóveis por Origem
```python
# Nova view
@login_required
def relatorio_origem_imoveis(request, tis_id):
    tis = get_object_or_404(TIs, id=tis_id)
    
    # Agrupar imóveis por classificação de origem
    imoveis_por_origem = {}
    
    for imovel in tis.imoveis.all():
        documentos = imovel.documentos.all()
        for documento in documentos:
            try:
                classificacao = documento.origemclassificacao.classificacao
                if classificacao not in imoveis_por_origem:
                    imoveis_por_origem[classificacao] = []
                imoveis_por_origem[classificacao].append(imovel)
            except:
                # Documento sem classificação
                if 'sem_classificacao' not in imoveis_por_origem:
                    imoveis_por_origem['sem_classificacao'] = []
                imoveis_por_origem['sem_classificacao'].append(imovel)
    
    context = {
        'tis': tis,
        'imoveis_por_origem': imoveis_por_origem
    }
    
    return render(request, 'dominial/relatorio_origem_imoveis.html', context)
```

## Cronograma de Implementação

### Semana 1: Preparação
- [ ] Criar branch de desenvolvimento
- [ ] Revisar estrutura atual dos modelos
- [ ] Definir migrações necessárias

### Semana 2: Melhorias Visuais
- [ ] Implementar destaque da matrícula
- [ ] Adicionar campo de área com 4 casas decimais
- [ ] Trocar terminologia "Cartório" por "Registro Imobiliário"

### Semana 3: Funcionalidades de UX
- [ ] Implementar herança de livro/folha
- [ ] Adicionar listagem de lançamentos existentes
- [ ] Implementar validações para cartórios existentes

### Semana 4: Sistema de Origem
- [ ] Criar modelos para origem estruturada
- [ ] Implementar formulário de origem
- [ ] Adicionar classificação de origem

### Semana 5: Relatórios e Testes
- [ ] Implementar relatório de imóveis por origem
- [ ] Testes de integração
- [ ] Documentação das mudanças

### Semana 6: Refinamentos
- [ ] Ajustes baseados em feedback
- [ ] Otimizações de performance
- [ ] Deploy em ambiente de teste

## Considerações Técnicas

### Migrações Necessárias
1. Alterar campo `area` para 4 casas decimais
2. Adicionar campo `tipo` ao modelo `Cartorios`
3. Criar novos modelos `OrigemTipo` e `OrigemClassificacao`

### Impactos no Sistema
- Formulários existentes precisarão ser atualizados
- JavaScript precisa ser modificado para novas validações
- Templates precisam ser adaptados para nova terminologia

### Compatibilidade
- Manter compatibilidade com dados existentes
- Migração gradual dos dados
- Documentação das mudanças para usuários

## Próximos Passos

1. **Aprovação do Plano**: Revisar e aprovar este plano
2. **Priorização**: Definir quais melhorias são mais críticas
3. **Desenvolvimento**: Iniciar implementação seguindo o cronograma
4. **Testes**: Testes extensivos com usuários reais
5. **Deploy**: Implementação gradual em produção 