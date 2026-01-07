# ✅ Checklist Final - Commit e Deploy em Produção

## 📋 Status das Verificações

### ✅ Código
- [x] Modelo `Imovel` corrigido com constraint única composta
- [x] Formulário `ImovelForm` com validação customizada
- [x] Comandos de management corrigidos
- [x] Migração criada e testada
- [x] Sem erros de lint
- [x] System check passou (warnings são esperados em dev)

### ✅ Migrações
- [x] Migração `0042_fix_matricula_unique_constraint` criada
- [x] Migração aplicada em desenvolvimento
- [x] Nenhuma migração pendente
- [x] Verificação de duplicatas implementada na migração

### ✅ Testes Locais
- [x] Migração aplicada com sucesso
- [x] Verificação de dados executada
- [x] Sistema funcionando corretamente
- [x] Servidor rodando sem erros

## 📦 Arquivos para Commit

### Arquivos Modificados
```
modified:   docker-compose.dev.yml
modified:   dominial/forms/imovel_forms.py
modified:   dominial/models/imovel_models.py
modified:   dominial/views/imovel_views.py
modified:   scripts/dev.sh
modified:   templates/dominial/imovel_form.html
```

### Arquivos Novos
```
new file:   CHECKLIST_PRODUCAO_MATRICULA.md
new file:   docs/ANALISE_MIGRACAO_MATRICULA.md
new file:   dominial/management/commands/verificar_matricula_constraint.py
new file:   dominial/migrations/0042_fix_matricula_unique_constraint.py
new file:   scripts/create_admin_user.py
new file:   scripts/create_admin_user.sh
```

## 🚀 Passos para Commit e Deploy

### 1. Commit Local

```bash
# Adicionar todos os arquivos relacionados à correção
git add dominial/models/imovel_models.py
git add dominial/forms/imovel_forms.py
git add dominial/migrations/0042_fix_matricula_unique_constraint.py
git add dominial/views/imovel_views.py
git add dominial/management/commands/testar_correcao_arvore.py
git add dominial/management/commands/testar_construcao_arvore.py
git add dominial/management/commands/verificar_matricula_constraint.py
git add templates/dominial/imovel_form.html
git add docs/ANALISE_MIGRACAO_MATRICULA.md
git add CHECKLIST_PRODUCAO_MATRICULA.md

# Adicionar correções do docker-compose.dev.yml e scripts
git add docker-compose.dev.yml
git add scripts/create_admin_user.py
git add scripts/create_admin_user.sh
git add scripts/dev.sh

# Commit
git commit -m "fix: Corrige constraint de matrícula para ser única por cartório

- Remove unique=True do campo matricula
- Adiciona UniqueConstraint (matricula, cartorio)
- Adiciona validação customizada no formulário
- Corrige comandos de management para lidar com múltiplos imóveis
- Adiciona migração com verificação de segurança
- Adiciona comando de verificação pré-migração
- Corrige erro de indentação no docker-compose.dev.yml
- Adiciona script para criar usuário admin em dev

BREAKING CHANGE: Matrícula agora é única por cartório, não globalmente.
Isso permite cadastrar mesma matrícula em cartórios diferentes.

Fixes: Erro ao cadastrar TI com matrícula existente em outro cartório"
```

### 2. Push para Repositório

```bash
git push origin main
```

### 3. Deploy em Produção

#### Pré-requisitos
- [ ] Backup do banco de dados de produção
- [ ] Acesso ao servidor de produção
- [ ] Verificação de dados em produção

#### Passos no Servidor de Produção

```bash
# 1. Fazer backup do banco
docker-compose exec db pg_dump -U $DB_USER $DB_NAME > backup_antes_migracao_matricula_$(date +%Y%m%d_%H%M%S).sql

# 2. Verificar dados (se o comando estiver disponível)
docker-compose exec web python manage.py verificar_matricula_constraint

# 3. Atualizar código
git pull origin main

# 4. Aplicar migração
docker-compose exec web python manage.py migrate

# 5. Verificar se migração foi aplicada
docker-compose exec web python manage.py showmigrations dominial | grep 0042

# 6. Reiniciar serviços (se necessário)
docker-compose restart web

# 7. Verificar logs
docker-compose logs web --tail=50
```

## ⚠️ Avisos Importantes

### Warnings de Segurança (Esperados em Dev)
Os warnings do `check --deploy` são esperados em desenvolvimento:
- `SECURE_HSTS_SECONDS`: Configurado em `settings_prod.py`
- `SECURE_CONTENT_TYPE_NOSNIFF`: Configurado em `settings_prod.py`
- `SECURE_SSL_REDIRECT`: Configurado via Nginx em produção
- `SECRET_KEY`: Deve ser configurado via variável de ambiente em produção
- `SESSION_COOKIE_SECURE`: Configurado em `settings_prod.py`
- `CSRF_COOKIE_SECURE`: Configurado em `settings_prod.py`
- `DEBUG`: False em `settings_prod.py`

### Verificação em Produção
Antes de aplicar a migração em produção, execute:
```bash
python manage.py verificar_matricula_constraint
```

Isso garantirá que não há duplicatas que possam quebrar a migração.

## ✅ Validação Final

### Testes Recomendados Após Deploy

1. **Teste de Cadastro**
   - Cadastrar imóvel com matrícula existente em OUTRO cartório ✅
   - Tentar cadastrar imóvel com matrícula existente no MESMO cartório ❌

2. **Teste de Funcionalidades**
   - Visualização de cadeia dominial
   - Listagem de imóveis
   - Busca e autocomplete
   - Exportação de dados

3. **Monitoramento**
   - Verificar logs por 24-48h
   - Monitorar erros relacionados a matrícula
   - Verificar performance

## 📝 Notas de Commit Sugeridas

### Mensagem de Commit Principal
```
fix: Corrige constraint de matrícula para ser única por cartório

BREAKING CHANGE: Matrícula agora é única por cartório, não globalmente.

- Remove unique=True do campo matricula no modelo Imovel
- Adiciona UniqueConstraint (matricula, cartorio)
- Adiciona validação customizada no ImovelForm
- Corrige comandos de management para lidar com múltiplos imóveis
- Adiciona migração 0042 com verificação de segurança
- Adiciona comando verificar_matricula_constraint
- Adiciona documentação completa da mudança

Fixes: Erro "Imóvel with this Matricula already exists" ao cadastrar
imóvel com matrícula existente em outro cartório.

Documentação:
- docs/ANALISE_MIGRACAO_MATRICULA.md
- CHECKLIST_PRODUCAO_MATRICULA.md
```

### Arquivos Relacionados (Separados)
```
fix(dev): Corrige erro de indentação no docker-compose.dev.yml

- Cria script create_admin_user.sh para evitar problemas de indentação
- Adiciona script create_admin_user.py como alternativa
- Melhora exibição de erros no formulário de imóvel
```

## 🎯 Conclusão

✅ **PRONTO PARA COMMIT E DEPLOY**

Todas as verificações foram realizadas:
- ✅ Código corrigido e testado
- ✅ Migração criada e aplicada
- ✅ Dados validados
- ✅ Documentação completa
- ✅ Sem erros de lint
- ✅ Sistema funcionando

**Próximo passo**: Fazer commit seguindo as instruções acima.

