# Análise de Impacto - Migração de Constraint de Matrícula

## 📋 Resumo da Mudança

**Antes**: Matrícula era única globalmente (`unique=True`)
**Depois**: Matrícula é única por cartório (`UniqueConstraint` em `(matricula, cartorio)`)

## ✅ Verificações Realizadas

### 1. Comandos de Management Corrigidos

#### ✅ `testar_correcao_arvore.py`
- **Problema**: Usava `Imovel.objects.get(matricula=matricula)` que pode lançar `MultipleObjectsReturned`
- **Solução**: Alterado para `filter().first()` com aviso quando múltiplos imóveis são encontrados
- **Status**: ✅ Corrigido

#### ✅ `testar_construcao_arvore.py`
- **Problema**: Mesmo problema acima
- **Solução**: Alterado para `filter().first()` com listagem de imóveis encontrados
- **Status**: ✅ Corrigido

### 2. Relacionamentos e Foreign Keys

#### ✅ Documentos → Imóveis
- **Relacionamento**: `ForeignKey('Imovel')` via campo `imovel`
- **Impacto**: ✅ Nenhum - relacionamento usa ID do imóvel, não matrícula
- **Status**: Seguro

#### ✅ Lançamentos → Documentos → Imóveis
- **Relacionamento**: `ForeignKey('Documento')` → `ForeignKey('Imovel')`
- **Impacto**: ✅ Nenhum - relacionamento usa IDs, não matrícula
- **Status**: Seguro

#### ✅ TIs → Imóveis
- **Relacionamento**: `ForeignKey('TIs')` no modelo Imovel
- **Impacto**: ✅ Nenhum - relacionamento usa ID da TI
- **Status**: Seguro

### 3. Queries e Filtros

#### ✅ Autocomplete de Imóveis
- **Código**: `Imovel.objects.filter(matricula__icontains=query)`
- **Impacto**: ✅ Nenhum - retorna múltiplos resultados, o que é esperado
- **Status**: Seguro

#### ✅ Buscas por Matrícula
- **Código**: Vários lugares usam `filter(matricula=...)` ou `filter(matricula__icontains=...)`
- **Impacto**: ✅ Nenhum - `filter()` retorna queryset, não assume unicidade
- **Status**: Seguro

#### ✅ Serviços de Hierarquia
- **Código**: Usa `imovel.matricula` para buscar documentos relacionados
- **Impacto**: ✅ Nenhum - trabalha com o objeto imóvel específico, não busca por matrícula
- **Status**: Seguro

### 4. Views e APIs

#### ✅ Views de Detalhe de Imóvel
- **Código**: Usa `imovel_id` (ID do imóvel) nas URLs
- **Impacto**: ✅ Nenhum - URLs usam ID, não matrícula
- **Status**: Seguro

#### ✅ Views de Cadeia Dominial
- **Código**: Recebe `imovel_id` como parâmetro
- **Impacto**: ✅ Nenhum - usa ID do imóvel
- **Status**: Seguro

### 5. Validações e Formulários

#### ✅ ImovelForm
- **Código**: Adicionada validação customizada `clean_matricula()`
- **Impacto**: ✅ Melhorado - agora valida unicidade por cartório
- **Status**: ✅ Implementado e testado

## ⚠️ Pontos de Atenção

### 1. Comandos de Management
- **Status**: ✅ Corrigidos
- **Ação**: Comandos agora usam `filter().first()` e avisam quando múltiplos imóveis são encontrados
- **Recomendação**: Em produção, sempre especificar cartório ao buscar por matrícula

### 2. Imóveis sem Cartório
- **Status**: ⚠️ Requer atenção
- **Problema**: A constraint permite múltiplos registros com `cartorio=NULL` e mesma matrícula
- **Solução**: O formulário exige cartório, então novos registros sempre terão cartório
- **Recomendação**: Atribuir cartórios a imóveis existentes sem cartório antes da migração

### 3. Dados Existentes
- **Status**: ⚠️ Requer verificação
- **Ação**: Execute `python manage.py verificar_matricula_constraint` antes da migração
- **Recomendação**: Fazer backup do banco antes de aplicar a migração

## 🔒 Segurança da Migração

### Passos da Migração

1. **Remover constraint única antiga**
   - Remove `UNIQUE` do campo `matricula`
   - ✅ Seguro - não afeta dados existentes

2. **Adicionar constraint única composta**
   - Adiciona `UNIQUE (matricula, cartorio)`
   - ⚠️ Pode falhar se houver duplicatas no mesmo cartório
   - **Solução**: Execute verificação antes

3. **Adicionar índice**
   - Adiciona índice em `(matricula, cartorio)`
   - ✅ Seguro - apenas melhora performance

### Verificação Pré-Migração

Execute antes de aplicar a migração:
```bash
python manage.py verificar_matricula_constraint
```

Este comando verifica:
- ✅ Matrículas duplicadas no mesmo cartório (problema)
- ✅ Matrículas em múltiplos cartórios (esperado)
- ✅ Imóveis sem cartório
- ✅ Estatísticas gerais

## 📝 Checklist para Produção

### Antes da Migração

- [ ] Fazer backup completo do banco de dados
- [ ] Executar `verificar_matricula_constraint` e verificar resultados
- [ ] Resolver qualquer duplicata no mesmo cartório encontrada
- [ ] Atribuir cartórios a imóveis sem cartório (se necessário)
- [ ] Testar a migração em ambiente de staging

### Durante a Migração

- [ ] Aplicar migração: `python manage.py migrate`
- [ ] Verificar se a migração foi aplicada com sucesso
- [ ] Verificar constraints no banco de dados

### Após a Migração

- [ ] Testar cadastro de novo imóvel com matrícula existente em outro cartório
- [ ] Testar cadastro de novo imóvel com matrícula existente no mesmo cartório (deve falhar)
- [ ] Verificar se comandos de management ainda funcionam
- [ ] Verificar se visualizações de cadeia dominial ainda funcionam
- [ ] Monitorar logs por erros relacionados a matrícula

## 🎯 Conclusão

### ✅ Mudanças Seguras
- Relacionamentos (Foreign Keys) não são afetados
- Queries que usam `filter()` continuam funcionando
- Views que usam IDs continuam funcionando
- Serviços que trabalham com objetos imóvel continuam funcionando

### ⚠️ Requer Atenção
- Comandos de management foram corrigidos
- Imóveis sem cartório podem precisar de atualização
- Verificação pré-migração é obrigatória

### ✅ Pronto para Produção
Após executar as verificações e correções acima, a migração pode ser aplicada com segurança.

## 📚 Referências

- Modelo `Documento` já usa `unique_together = ('numero', 'cartorio')` - mesma lógica
- Migração: `dominial/migrations/0042_fix_matricula_unique_constraint.py`
- Comando de verificação: `dominial/management/commands/verificar_matricula_constraint.py`

