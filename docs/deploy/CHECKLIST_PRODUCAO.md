# Checklist de Produção - Cadeia Dominial

## 📋 Pré-Deploy

### ✅ Backup e Segurança
- [ ] **Backup completo do banco de dados**
  ```bash
  pg_dump -U usuario -d cadeia_dominial > backup_pre_deploy_$(date +%Y%m%d_%H%M%S).sql
  ```
- [ ] **Backup dos arquivos de configuração** (nginx, ssl, etc.)
- [ ] **Verificar variáveis de ambiente** (DEBUG=False, SECRET_KEY, etc.)
- [ ] **Testar em ambiente de staging** (se disponível)

### ✅ Verificações de Dependências
- [ ] **Requirements atualizados** (`requirements.txt`)
- [ ] **Docker images atualizadas** (se usando Docker)
- [ ] **Node modules atualizados** (se houver frontend)
- [ ] **Verificar compatibilidade de versões** (Python, Django, PostgreSQL)

## 🚀 Deploy

### ✅ Migrations
- [ ] **Verificar migrations pendentes**
  ```bash
  python manage.py showmigrations
  ```
- [ ] **Aplicar migrations**
  ```bash
  python manage.py migrate
  ```
- [ ] **Verificar se não há conflitos** (especialmente em campos de cartório)

### ✅ Campos de Cartório (CRÍTICO)
- [ ] **Verificar campo `cartorio_transmissao`**
  ```sql
  SELECT column_name, is_nullable 
  FROM information_schema.columns 
  WHERE table_name = 'dominial_lancamento' 
  AND column_name = 'cartorio_transmissao';
  ```
- [ ] **Se `is_nullable = 'NO'`, executar:**
  ```sql
  ALTER TABLE dominial_lancamento ALTER COLUMN cartorio_transmissao DROP NOT NULL;
  ```
- [ ] **Verificar campo `cartorio_transacao`** (legado)
- [ ] **Testar criação de lançamentos** (averbação, registro, início de matrícula)
- [ ] **Verificar formulário de lançamento** (campo cartório de transmissão)
- [ ] **Testar visualização na cadeia dominial** (cartório aparece corretamente)

### ✅ Configurações Django
- [ ] **DEBUG = False**
- [ ] **ALLOWED_HOSTS configurado**
- [ ] **SECRET_KEY definida**
- [ ] **Database configurado** (produção)
- [ ] **Static files coletados**
  ```bash
  python manage.py collectstatic --noinput
  ```

### ✅ Serviços
- [ ] **Nginx configurado e testado**
- [ ] **SSL/HTTPS funcionando**
- [ ] **Gunicorn/UWSGI configurado**
- [ ] **Supervisor/systemd configurado**
- [ ] **Logs configurados**

## 🔍 Pós-Deploy

### ✅ Testes Funcionais
- [ ] **Login de administrador**
- [ ] **Criação de lançamentos** (todos os tipos)
- [ ] **Cadeia dominial funcionando**
- [ ] **Importação de dados** (se aplicável)
- [ ] **APIs funcionando**
- [ ] **Upload de arquivos** (se houver)

### ✅ Performance
- [ ] **Tempo de resposta** (< 3s para páginas principais)
- [ ] **Uso de memória** (dentro dos limites)
- [ ] **Conexões de banco** (pool configurado)
- [ ] **Cache funcionando** (se implementado)

### ✅ Monitoramento
- [ ] **Logs sendo gerados**
- [ ] **Alertas configurados**
- [ ] **Backup automático funcionando**
- [ ] **Health checks configurados**

## 🚨 Problemas Conhecidos

### Campo `cartorio_transmissao` NOT NULL
**Sintoma:** Erro ao criar lançamentos de averbação
```
null value in column "cartorio_transmissao" violates not-null constraint
```

**Solução:**
```sql
ALTER TABLE dominial_lancamento ALTER COLUMN cartorio_transmissao DROP NOT NULL;
```

### Migrations de Cartório
**Ordem correta das migrations:**
1. `0028_add_cartorio_transmissao` - Adiciona campo
2. `0029_sync_cartorio_transmissao_data` - Sincroniza dados
3. `0030_fix_cartorio_transmissao_null` - Permite NULL

### Campo de Cartório não aparece na Cadeia Dominial
**Sintoma:** Cartório de transmissão não aparece na tabela da cadeia dominial
**Causa:** Formulário usando nome antigo do campo (`cartorio_transacao` em vez de `cartorio_transmissao`)
**Solução:** 
- Verificar se o template `lancamento_form.html` usa `cartorio_transmissao`
- Verificar se o JavaScript `lancamento_form.js` usa `cartorio_transmissao`
- Recarregar página e testar criação de novo lançamento

## 📞 Contatos de Emergência
- **DBA:** [contato]
- **DevOps:** [contato]
- **Desenvolvedor:** [contato]

## 📝 Log de Deploy
- **Data:** _____
- **Versão:** _____
- **Responsável:** _____
- **Problemas encontrados:** _____
- **Soluções aplicadas:** _____

---

**⚠️ IMPORTANTE:** Sempre testar em ambiente de desenvolvimento antes do deploy em produção! 