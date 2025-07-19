# Planejamento Estruturado - Reformulação dos Cartórios

## Análise da Estrutura Atual

### 1. Modelos que usam Cartórios

#### 1.1 Imovel (dominial/models/imovel_models.py)
```python
class Imovel(models.Model):
    cartorio = models.ForeignKey('Cartorios', on_delete=models.PROTECT, null=True, blank=True)
```
- **Uso**: Cartório onde o imóvel está registrado
- **Impacto**: Formulário de cadastro de imóveis

#### 1.2 Documento (dominial/models/documento_models.py)
```python
class Documento(models.Model):
    cartorio = models.ForeignKey('Cartorios', on_delete=models.PROTECT)
```
- **Uso**: Cartório responsável pelo documento
- **Impacto**: Formulário de documentos, visualizações

#### 1.3 Lancamento (dominial/models/lancamento_models.py)
```python
class Lancamento(models.Model):
    cartorio_origem = models.ForeignKey('Cartorios', ...)  # Cartório de origem
    cartorio_transacao = models.ForeignKey('Cartorios', ...)  # Cartório de transação
```
- **Uso**: Cartórios de origem e transação
- **Impacto**: Formulário de lançamentos, visualizações

#### 1.4 Alteracoes (dominial/models/alteracao_models.py)
```python
class Alteracoes(models.Model):
    cartorio = models.ForeignKey('Cartorios', on_delete=models.CASCADE)
    cartorio_origem = models.ForeignKey('Cartorios', on_delete=models.CASCADE, related_name='cartorio_responsavel')
```
- **Uso**: Cartórios de alterações
- **Impacto**: Formulário de alterações

### 2. Formulários e Templates Afetados

#### 2.1 Cadastro de Imóveis
- **Template**: `templates/dominial/imovel_form.html`
- **Form**: `dominial/forms/imovel_forms.py`
- **View**: `dominial/views/imovel_views.py`
- **Status**: Campo cartório obrigatório

#### 2.2 Formulário de Documentos
- **Template**: `templates/dominial/documento_form.html`
- **View**: `dominial/views/documento_views.py`
- **Status**: Campo cartório obrigatório

#### 2.3 Formulário de Lançamentos
- **Template**: `templates/dominial/lancamento_form.html`
- **Componente**: `templates/dominial/components/_lancamento_basico_form.html`
- **View**: `dominial/views/lancamento_views.py`
- **Status**: Campos cartorio_origem e cartorio_transacao

#### 2.4 Visualizações
- **Cadeia Dominial**: `templates/dominial/cadeia_dominial.html`
- **Tabela**: `templates/dominial/cadeia_dominial_tabela.html`
- **Detalhes**: `templates/dominial/lancamento_detail.html`

### 3. Serviços e APIs

#### 3.1 Autocomplete
- **API**: `dominial/views/api_views.py`
- **Endpoints**: `/cartorio-autocomplete/`, `/cartorio-imoveis-autocomplete/`

#### 3.2 Serviços
- **LancamentoCamposService**: Processa campos de cartório
- **LancamentoFormService**: Processa formulários
- **CartorioVerificacaoService**: Verifica cartórios

## Plano de Implementação Estruturado

### Fase 1: Preparação e Análise (Semana 1)

#### 1.1 Análise Completa da Estrutura
- [x] Mapeamento de todos os modelos que usam cartórios ✅
- [x] Identificação de formulários e templates afetados ✅
- [x] Análise de serviços e APIs ✅
- [ ] Criação de testes para validar mudanças
- [ ] Backup completo do banco

#### 1.2 Definição da Nova Estratégia
- **CRI (Cartório de Registro de Imóveis)**: Lista fixa, seleção obrigatória
- **Cartório de Transmissão**: Campo livre para digitação
- **Migração**: Preservar dados existentes

### Fase 2: Implementação dos Modelos (Semana 2)

#### 2.1 Atualização do Modelo Cartorios
```python
class Cartorios(models.Model):
    # ... campos existentes ...
    tipo = models.CharField(
        max_length=10, 
        choices=[('CRI', 'Cartório de Registro de Imóveis'), ('OUTRO', 'Outro')],
        default='CRI'
    )
```

#### 2.2 Novos Campos no Modelo Lancamento
```python
class Lancamento(models.Model):
    # ... campos existentes ...
    cartorio_registro = models.ForeignKey('Cartorios', ...)  # CRI obrigatório
    cartorio_transmissao = models.CharField(max_length=255, blank=True)  # Campo livre
```

#### 2.3 Migração de Dados
- Criar migration para adicionar novos campos
- Script para migrar dados existentes
- Preservar compatibilidade com dados antigos

### Fase 3: Implementação por Módulos (Semana 3-4)

#### 3.1 Módulo 1: Cadastro de Imóveis
**Objetivo**: Implementar nova lógica de cartórios no cadastro de imóveis

**Arquivos a modificar**:
- `dominial/models/imovel_models.py` - Adicionar campo tipo
- `dominial/forms/imovel_forms.py` - Atualizar formulário
- `templates/dominial/imovel_form.html` - Atualizar template
- `dominial/views/imovel_views.py` - Atualizar view

**Mudanças**:
- Campo cartório: Seleção obrigatória de CRI
- Autocomplete: Apenas cartórios de registro
- Validação: Cartório deve ser do tipo CRI

#### 3.2 Módulo 2: Formulário de Documentos
**Objetivo**: Implementar nova lógica no formulário de documentos

**Arquivos a modificar**:
- `dominial/models/documento_models.py` - Adicionar campo tipo
- `templates/dominial/documento_form.html` - Atualizar template
- `dominial/views/documento_views.py` - Atualizar view

**Mudanças**:
- Campo cartório: Seleção obrigatória de CRI
- Autocomplete: Apenas cartórios de registro
- Validação: Cartório deve ser do tipo CRI

#### 3.3 Módulo 3: Formulário de Lançamentos
**Objetivo**: Implementar nova lógica no formulário de lançamentos

**Arquivos a modificar**:
- `dominial/models/lancamento_models.py` - Novos campos
- `templates/dominial/lancamento_form.html` - Atualizar template
- `templates/dominial/components/_lancamento_basico_form.html` - Atualizar componente
- `dominial/views/lancamento_views.py` - Atualizar view
- `dominial/services/lancamento_campos_service.py` - Atualizar serviço

**Mudanças**:
- Campo cartório_registro: Seleção obrigatória de CRI
- Campo cartorio_transmissao: Input livre
- Validação: CRI obrigatório para documentos principais

#### 3.4 Módulo 4: Visualizações
**Objetivo**: Atualizar todas as visualizações para usar novos campos

**Arquivos a modificar**:
- `templates/dominial/cadeia_dominial.html`
- `templates/dominial/cadeia_dominial_tabela.html`
- `templates/dominial/lancamento_detail.html`
- `dominial/views/cadeia_dominial_views.py`

**Mudanças**:
- Exibir cartório_registro como CRI
- Exibir cartorio_transmissao como campo livre
- Manter compatibilidade com dados antigos

### Fase 4: APIs e Autocomplete (Semana 5)

#### 4.1 Atualização das APIs
**Arquivos a modificar**:
- `dominial/views/api_views.py`
- `dominial/views/autocomplete_views.py`

**Mudanças**:
- Autocomplete para CRI: Apenas cartórios de registro
- Autocomplete para transmissão: Campo livre
- Novos endpoints para diferentes tipos

#### 4.2 Atualização dos Serviços
**Arquivos a modificar**:
- `dominial/services/cartorio_verificacao_service.py`
- `dominial/services/lancamento_cartorio_service.py`

**Mudanças**:
- Validação de tipos de cartório
- Processamento de novos campos
- Migração de dados

### Fase 5: Testes e Validação (Semana 6)

#### 5.1 Testes Unitários
- Testes para novos modelos
- Testes para formulários atualizados
- Testes para validações

#### 5.2 Testes de Integração
- Testes de fluxo completo
- Testes de migração de dados
- Testes de compatibilidade

#### 5.3 Testes de Interface
- Testes de formulários
- Testes de autocomplete
- Testes de validação

### Fase 6: Deploy e Monitoramento (Semana 7)

#### 6.1 Deploy Gradual
- Deploy em ambiente de desenvolvimento
- Testes em ambiente de staging
- Deploy em produção com rollback

#### 6.2 Monitoramento
- Monitoramento de erros
- Monitoramento de performance
- Monitoramento de dados

## Cronograma Detalhado

### Semana 1: Preparação
- [ ] Análise completa da estrutura
- [ ] Criação de testes
- [ ] Backup do banco
- [ ] Definição da estratégia

### Semana 2: Modelos e Migração
- [ ] Atualização do modelo Cartorios
- [ ] Novos campos no modelo Lancamento
- [ ] Criação da migration
- [ ] Script de migração de dados

### Semana 3: Módulo 1 - Cadastro de Imóveis
- [ ] Atualização do modelo Imovel
- [ ] Atualização do formulário
- [ ] Atualização do template
- [ ] Atualização da view
- [ ] Testes do módulo

### Semana 4: Módulo 2 - Documentos
- [ ] Atualização do modelo Documento
- [ ] Atualização do template
- [ ] Atualização da view
- [ ] Testes do módulo

### Semana 5: Módulo 3 - Lançamentos
- [ ] Atualização do modelo Lancamento
- [ ] Atualização dos templates
- [ ] Atualização das views
- [ ] Atualização dos serviços
- [ ] Testes do módulo

### Semana 6: Módulo 4 - Visualizações
- [ ] Atualização de todos os templates de visualização
- [ ] Atualização das views
- [ ] Testes de visualização

### Semana 7: APIs e Serviços
- [ ] Atualização das APIs
- [ ] Atualização dos serviços
- [ ] Testes de integração

### Semana 8: Deploy e Monitoramento
- [ ] Deploy em desenvolvimento
- [ ] Deploy em staging
- [ ] Deploy em produção
- [ ] Monitoramento

## Benefícios Esperados

### 1. Simplicidade
- Interface mais clara e intuitiva
- Menos complexidade técnica
- Implementação mais rápida

### 2. Flexibilidade
- Cartório de transmissão livre
- Não precisa importar todos os cartórios
- Adaptável a casos especiais

### 3. Preservação de Dados
- Migração segura
- Compatibilidade com dados existentes
- Sem perda de informações

### 4. Manutenibilidade
- Código mais organizado
- Validações centralizadas
- Fácil manutenção

## Riscos e Mitigações

### 1. Riscos
- Quebra de compatibilidade
- Perda de dados
- Problemas de performance

### 2. Mitigações
- Testes extensivos
- Migração gradual
- Backup completo
- Monitoramento contínuo

## Próximos Passos

1. **Aprovação do plano**: Revisar e aprovar este planejamento
2. **Criação de branch**: Criar branch específica para esta feature
3. **Implementação gradual**: Seguir cronograma proposto
4. **Testes contínuos**: Testar cada módulo antes de prosseguir
5. **Documentação**: Atualizar documentação conforme implementação

---

**Status**: Planejamento criado
**Próximo**: Aguardando aprovação para iniciar implementação 