# ✅ Checklist para Deploy em Produção - Correção de Constraint de Matrícula

## 📋 Resumo da Mudança

**Problema**: Matrícula era única globalmente, impedindo cadastro de mesma matrícula em cartórios diferentes
**Solução**: Matrícula agora é única por cartório (mesma lógica do modelo Documento)

## ✅ Verificações Realizadas

### 1. Código Corrigido
- ✅ Modelo `Imovel`: Removido `unique=True`, adicionado `UniqueConstraint` composta
- ✅ Formulário `ImovelForm`: Validação customizada para unicidade por cartório
- ✅ Comandos de management: Corrigidos para lidar com múltiplos imóveis
- ✅ Migração: Criada com verificação de segurança

### 2. Impacto em Outras Funcionalidades
- ✅ **Relacionamentos**: Nenhum impacto - Foreign Keys usam IDs, não matrícula
- ✅ **Queries**: Nenhum impacto - `filter()` retorna queryset, não assume unicidade
- ✅ **Views**: Nenhum impacto - URLs usam IDs de imóvel, não matrícula
- ✅ **Serviços**: Nenhum impacto - trabalham com objetos imóvel específicos
- ✅ **Autocomplete**: Funciona normalmente - retorna múltiplos resultados quando apropriado

### 3. Comandos de Management
- ✅ `testar_correcao_arvore.py`: Corrigido
- ✅ `testar_construcao_arvore.py`: Corrigido
- ✅ `verificar_matricula_constraint.py`: Criado para verificação pré-migração

## 🚀 Passos para Deploy em Produção

### Fase 1: Preparação (ANTES da migração)

1. **Backup do Banco de Dados**
   ```bash
   # Fazer backup completo
   docker-compose exec db pg_dump -U $DB_USER $DB_NAME > backup_antes_migracao_matricula_$(date +%Y%m%d_%H%M%S).sql
   ```

2. **Verificação de Dados**
   ```bash
   # Executar comando de verificação
   docker-compose exec web python manage.py verificar_matricula_constraint
   ```
   
   **Resultado esperado**: 
   - ✅ Nenhuma duplicata no mesmo cartório
   - ⚠️ Se houver duplicatas, resolver antes de continuar

3. **Teste em Staging** (se disponível)
   - Aplicar migração em ambiente de staging
   - Testar cadastro de novos imóveis
   - Verificar funcionalidades críticas

### Fase 2: Aplicação da Migração

1. **Aplicar Migração**
   ```bash
   docker-compose exec web python manage.py migrate
   ```

2. **Verificar Aplicação**
   ```bash
   # Verificar se a migração foi aplicada
   docker-compose exec web python manage.py showmigrations dominial | grep 0042
   ```

3. **Verificar Constraints no Banco**
   ```bash
   docker-compose exec db psql -U $DB_USER -d $DB_NAME -c "\d dominial_imovel"
   ```
   
   Deve mostrar:
   - Constraint `unique_matricula_por_cartorio` em `(matricula, cartorio)`
   - Índice `dominial_im_matricu_idx` em `(matricula, cartorio)`

### Fase 3: Validação Pós-Migração

1. **Teste de Cadastro**
   - ✅ Cadastrar imóvel com matrícula existente em OUTRO cartório (deve funcionar)
   - ✅ Tentar cadastrar imóvel com matrícula existente no MESMO cartório (deve dar erro)
   - ✅ Verificar mensagem de erro é clara e informativa

2. **Teste de Funcionalidades**
   - ✅ Visualização de cadeia dominial
   - ✅ Listagem de imóveis
   - ✅ Busca e autocomplete
   - ✅ Exportação de dados

3. **Monitoramento**
   - Monitorar logs por 24-48h após deploy
   - Verificar se há erros relacionados a matrícula
   - Verificar performance de queries

## ⚠️ Pontos de Atenção

### 1. Imóveis sem Cartório
- Se houver imóveis com `cartorio=NULL`, a constraint permitirá múltiplos registros
- **Recomendação**: Atribuir cartórios a esses imóveis antes da migração (se possível)

### 2. Comandos de Management
- Comandos que buscam por matrícula agora podem encontrar múltiplos resultados
- **Solução**: Comandos foram corrigidos para usar `filter().first()` e avisar quando múltiplos são encontrados

### 3. Rollback (se necessário)
- Se precisar reverter, restaure o backup do banco
- A migração não altera dados, apenas constraints
- Rollback é seguro

## 📊 Arquivos Modificados

### Modelos
- `dominial/models/imovel_models.py` - Constraint única composta

### Formulários
- `dominial/forms/imovel_forms.py` - Validação customizada

### Migrações
- `dominial/migrations/0042_fix_matricula_unique_constraint.py` - Migração com verificação

### Comandos de Management
- `dominial/management/commands/testar_correcao_arvore.py` - Corrigido
- `dominial/management/commands/testar_construcao_arvore.py` - Corrigido
- `dominial/management/commands/verificar_matricula_constraint.py` - Novo

### Documentação
- `docs/ANALISE_MIGRACAO_MATRICULA.md` - Análise completa
- `CHECKLIST_PRODUCAO_MATRICULA.md` - Este arquivo

## ✅ Conclusão

### Pronto para Produção
Após executar as verificações acima, a migração pode ser aplicada com segurança.

### Benefícios
- ✅ Permite cadastro de mesma matrícula em cartórios diferentes
- ✅ Mantém integridade: mesma matrícula não pode existir duas vezes no mesmo cartório
- ✅ Alinha com a lógica do modelo Documento
- ✅ Melhora a experiência do usuário

### Riscos
- ⚠️ Baixo risco - mudança apenas em constraint, não em dados
- ⚠️ Migração pode falhar se houver duplicatas (mas isso é detectado antes)
- ⚠️ Comandos de management precisam especificar cartório em alguns casos

## 📞 Suporte

Se encontrar problemas:
1. Verificar logs: `docker-compose logs web`
2. Executar verificação: `python manage.py verificar_matricula_constraint`
3. Consultar documentação: `docs/ANALISE_MIGRACAO_MATRICULA.md`

