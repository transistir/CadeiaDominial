# 🔄 Desfazendo Merge - Guia

## 📋 Situação

O merge está no **repositório remoto** (`origin/main`), não no seu repositório local.

Seus commits locais:
- `cab9a96` - fix: Adiciona verificação de null
- `bdc0845` - fix: Corrige constraint de matrícula

O merge no remoto:
- `496f019` - Merge pull request #2 (com muitos commits de testes/CI/CD)

## 🎯 Opções

### Opção 1: Fazer Pull com Rebase (Recomendado)
Coloca seus commits **em cima** dos commits remotos, sem criar merge commit:

```bash
# 1. Fazer pull com rebase
git pull --rebase origin main

# 2. Se houver conflitos, resolver e continuar:
#    - Editar arquivos com conflitos
#    - git add <arquivos>
#    - git rebase --continue

# 3. Fazer push
git push origin main
```

**Resultado**: Seus commits aparecerão DEPOIS dos commits do merge, sem criar novo merge.

### Opção 2: Force Push (PERIGOSO - Só se você tiver certeza)
Se você realmente não quer os commits do merge no remoto:

```bash
# ⚠️ ATENÇÃO: Isso vai SOBRESCREVER o remoto
# ⚠️ Só faça se tiver certeza que ninguém mais está trabalhando nisso

git push --force origin main
```

**⚠️ CUIDADO**: Isso apaga o merge e todos os commits que vieram depois dele no remoto!

### Opção 3: Criar Branch Nova
Manter seus commits em uma branch separada:

```bash
# 1. Criar branch a partir dos seus commits
git checkout -b fix/matricula-constraint

# 2. Fazer push da branch
git push origin fix/matricula-constraint

# 3. Depois criar Pull Request quando estiver pronto
```

## ✅ Recomendação

**Use a Opção 1 (Pull com Rebase)**:
- Mantém todos os commits (seus e do remoto)
- Não cria merge commit desnecessário
- Histórico limpo e linear
- Seguro

## 📝 Passo a Passo Detalhado (Opção 1)

```bash
# 1. Verificar estado atual
git status

# 2. Se houver mudanças não commitadas, fazer stash
git stash

# 3. Fazer pull com rebase
git pull --rebase origin main

# 4. Se aparecer conflitos:
#    - Abrir arquivos com conflitos
#    - Resolver manualmente
#    - git add <arquivos_resolvidos>
#    - git rebase --continue

# 5. Se quiser cancelar o rebase:
#    git rebase --abort

# 6. Depois do rebase bem-sucedido, fazer push
git push origin main

# 7. Recuperar mudanças stashed (se aplicável)
git stash pop
```

