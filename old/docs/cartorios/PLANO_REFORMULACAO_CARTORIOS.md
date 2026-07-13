# Plano de Reformulação do Sistema de Cartórios

## Nova Estratégia (Atualizada)

### 1. Cartório de Registro de Imóveis (CRI)
- **Tipo**: Lista fixa do banco de dados
- **Seleção**: Obrigatória via dropdown
- **Origem**: Dados existentes + importação de cartórios de registro
- **Uso**: Documentos principais (Matrícula, Transcrição)

### 2. Cartório de Transmissão
- **Tipo**: Campo de texto livre
- **Entrada**: Input de texto para digitação manual
- **Armazenamento**: Campo `cartorio` simples no banco
- **Uso**: Transmissões em averbações de documentos

## Vantagens da Nova Abordagem

### Simplicidade
- ✅ Implementação mais rápida
- ✅ Menos complexidade técnica
- ✅ Flexibilidade total para cartórios de transmissão
- ✅ Não precisa importar todos os cartórios de notas

### Preservação de Dados
- ✅ Migração segura dos dados existentes
- ✅ Não perde informações históricas
- ✅ Compatibilidade com dados de produção

### Usabilidade
- ✅ CRI padronizado e confiável
- ✅ Transmissão flexível para casos especiais
- ✅ Interface mais intuitiva

## Implementação Técnica

### 1. Modelo de Dados
```python
# Manter estrutura atual
class Cartorio(models.Model):
    nome = models.CharField(max_length=255)
    cns = models.CharField(max_length=20, unique=True)
    cidade = models.CharField(max_length=100)
    estado = models.CharField(max_length=2)
    tipo = models.CharField(max_length=20, choices=[
        ('CRI', 'Cartório de Registro de Imóveis'),
        ('OUTRO', 'Outro')
    ])
    
class Lancamento(models.Model):
    # ... outros campos
    cartorio_registro = models.ForeignKey(Cartorio, on_delete=models.SET_NULL, null=True, blank=True)
    cartorio_transmissao = models.CharField(max_length=255, blank=True)  # Campo livre
```

### 2. Formulários
- **CRI**: Select com autocomplete dos cartórios de registro
- **Transmissão**: Input de texto simples

### 3. Migração de Dados
```python
# Migração para preservar dados existentes
def migrate_cartorios_data(apps, schema_editor):
    Lancamento = apps.get_model('dominical', 'Lancamento')
    
    for lancamento in Lancamento.objects.all():
        if lancamento.cartorio:
            # Se já tem cartório, manter como CRI
            lancamento.cartorio_registro = lancamento.cartorio
            lancamento.cartorio_transmissao = ""
        lancamento.save()
```

## Cronograma Atualizado

### Semana 1: Preparação
- [x] Análise dos dados atuais ✅
- [ ] Limpeza de dados problemáticos
- [ ] Preparação da migração

### Semana 2: Implementação Base
- [ ] Atualização do modelo
- [ ] Migração de dados
- [ ] Formulários básicos

### Semana 3: Interface
- [ ] Templates atualizados
- [ ] JavaScript para autocomplete CRI
- [ ] Validações

### Semana 4: Testes e Deploy
- [ ] Testes completos
- [ ] Deploy em produção
- [ ] Documentação

## Benefícios da Nova Abordagem

1. **Implementação Mais Rápida**: Menos complexidade técnica
2. **Flexibilidade**: Transmissão pode ser qualquer cartório
3. **Preservação de Dados**: Migração segura
4. **Usabilidade**: Interface mais intuitiva
5. **Manutenibilidade**: Código mais simples

## Riscos Mitigados

1. **Perda de Dados**: Migração cuidadosa preserva tudo
2. **Complexidade**: Abordagem simplificada
3. **Performance**: Menos joins e consultas complexas
4. **Usabilidade**: Interface mais clara

## Próximos Passos

1. **Limpeza de Dados**: Remover duplicatas e dados problemáticos
2. **Migração**: Criar script de migração segura
3. **Implementação**: Atualizar modelo e formulários
4. **Testes**: Validar em ambiente de desenvolvimento
5. **Deploy**: Aplicar em produção com backup

## Conclusão

A nova estratégia é mais prática e flexível, mantendo a precisão onde é necessária (CRI) e permitindo flexibilidade onde é útil (transmissão). A implementação será mais rápida e segura. 