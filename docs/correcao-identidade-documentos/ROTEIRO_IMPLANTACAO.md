# T30 — Roteiro de implantação e rollback

Documento oficial de implantação da branch `feature/identidade-documento-cartorio`
no servidor de teste. Substitui qualquer versão informal discutida em
conversa. Não aplicar em produção sem repetir este roteiro à parte, com o
mesmo rigor.

## Escopo do que está sendo implantado

- T01–T29 completas (ver `TAREFAS.md`): identidade canônica de `Documento`
  (tipo+número normalizado+cartório), `Imovel` e `LancamentoOrigem`;
  correções de resolução/criação automática por cartório; T25 (identidade
  completa nas opções), T26 (seleção inequívoca por ID), T27 (teste de
  regressão do fluxo de duplicata), e três dívidas técnicas corrigidas
  (`hierarquia_arvore_service.py`, `documento_views.py`,
  `lancamento_views.py`).
- Migrações novas: `0043` a `0049` (constraints canônicas de `Documento` e
  `Imovel`, `Imovel.cartorio` `NOT NULL`, modelo `LancamentoOrigem` e sua
  constraint canônica). Nenhuma delas reescreve dados; todas auditam e
  interrompem diante de conflito.
- T07 (homologação manual de homônimos cross-cartório na tabela) e a
  homologação geral com dados reais acontecem _depois_ deste deploy, não
  antes — esse é justamente o objetivo de ir ao servidor de teste.

## Estado conhecido antes de começar (levantado nesta sessão)

- A branch **não foi enviada ao GitHub** ainda (só existe local).
- O servidor de teste (`188.245.225.127`, `/root/CadeiaDominial`) está hoje
  na branch `hotfix/arvore-duplicacao-cards`, com **duas alterações locais
  não commitadas**: `cadeia_dominial/settings_prod.py` (CSRF_TRUSTED_HOSTS
  parametrizado via env) e `docker-compose.yml` (formatação + variável nova).
  Precisam ser preservadas.
- O repo do servidor de teste acumula dezenas de arquivos não rastreados
  (dumps `.sql`, backups, scripts de debug) — não tocar, não usar
  `git add -A`.
- `scripts/init.sh` roda `python manage.py migrate` em **todo** restart do
  container `web` — ou seja, o simples `docker compose up -d web` após
  trocar de branch já aplica as migrações pendentes automaticamente.
- Auditoria somente leitura já executada contra o banco real de teste em
  2026-07-14: `auditar_identidade_documentos --fail-on-conflict --json`
  (comando de T15) rodou via `docker cp` temporário para dentro do container
  `cadeia_dominial_web`, sem alterar código/git/banco, e reportou **2524
  documentos, zero conflitos, zero inválidos, zero sem cartório**. Isso cobre
  só `Documento` (tipo+número+cartório); não há comando equivalente dedicado
  para `Imovel.matricula` nem para `LancamentoOrigem` — essas duas contam
  com a auditoria embutida nas próprias migrações 0048/0049, que abortam sem
  reescrever dados em caso de conflito.
- Containers ativos: `cadeia_dominial_web`, `cadeia_dominial_nginx`,
  `cadeia_dominial_db` (Postgres 15). O serviço `web` usa `build: .` (código
  entra na imagem, não é bind mount) — só `staticfiles/` e `media/` são
  volumes.

## Fase 0 — Antes de tocar no servidor

1. Confirmar que a documentação está no estado desejado (`CHECKPOINT_ATUAL.md`,
   `TAREFAS.md`, `DIARIO.md` já refletem T01–T29 concluídas nesta sessão).
2. `git push -u origin feature/identidade-documento-cartorio` — publica a
   branch. **Ação visível/compartilhada: só executar com confirmação
   explícita do usuário no momento, não antecipar.**

## Fase 1 — Backup do banco de teste (obrigatório)

```bash
ssh root@188.245.225.127
docker exec cadeia_dominial_db pg_dump -U cadeia_user -d cadeia_dominial -F c \
  -f /tmp/backup_pre_identidade_$(date +%Y%m%d_%H%M%S).dump
```

Copiar o dump para **fora** do servidor (outra máquina/storage) antes de
prosseguir — um dump que só existe no mesmo host não protege contra falha
de disco/host.

## Fase 2 — Preservar config local do servidor

```bash
cd /root/CadeiaDominial
git stash push -m "csrf/compose pre-deploy-identidade"
git status   # precisa ficar limpo antes do checkout
```

## Fase 3 — Trocar de branch

```bash
git fetch origin
git checkout feature/identidade-documento-cartorio   # ou checkout -b a partir de origin/...
git stash pop   # reaplica settings_prod.py/docker-compose.yml
```

Resolver conflito manualmente se houver (improvável — esta branch não
mexe nesses dois arquivos).

## Fase 4 — Rebuild e subida controlada

```bash
docker compose build web
docker compose up -d web
docker compose logs -f web   # acompanhar o run_migrations do init.sh em tempo real
```

Se aparecer erro de migração no log (`CommandError`, conflito de
constraint), **parar imediatamente** e ir para a Fase 6 (rollback) — não
tentar "consertar na mão" em produção/teste compartilhado.

## Fase 5 — Verificação pós-deploy

```bash
docker exec cadeia_dominial_web python manage.py verificar_estrutura_ambiente --json
docker exec cadeia_dominial_web python manage.py auditar_identidade_documentos --json
```

Confirmar `migracoes_pendentes: []`, `migracoes_aplicadas_desconhecidas: []`,
e que os totais de conflito/inválido continuam zero.

Smoke test funcional em `https://teste.cadeiadominial.com.br`:

1. Login.
2. Abrir um imóvel com múltiplos documentos e a árvore D3 — confirmar que
   carrega sem erro 500 e sem duplicar cards.
3. Repetir o roteiro de homologação manual de T25/T26 com dados **reais**
   do banco de teste (procurar homônimos de verdade entre cartórios —
   `SELECT numero, COUNT(*) FROM dominial_documento GROUP BY numero HAVING COUNT(*) > 1`
   ou usar o filtro `NumeroDocumentoFilter` do admin para achar candidatos).
4. Executar a homologação pendente da T07 (ver seção própria no
   `CHECKPOINT_ATUAL.md`): abrir `/tis/<tis_id>/imovel/<imovel_id>/cadeia-tabela/`
   para um imóvel com homônimos cross-cartório e confirmar que só o
   documento do `cartorio_origem` aparece.
5. Testar a edição de um lançamento de documento compartilhado
   (`editar_lancamento`) para validar a correção feita em T28 — confirmar
   que só é possível editar lançamentos de documentos realmente
   referenciados nesta cadeia.

## Fase 6 — Rollback

**Código:**

```bash
git checkout hotfix/arvore-duplicacao-cards
git stash pop   # se a config ainda estiver no stash
docker compose build web && docker compose up -d web
```

**Migrations** (0043–0049 têm reversão testada, segundo os testes de
migração de cada uma):

```bash
docker exec cadeia_dominial_web python manage.py migrate dominial 0042_fix_matricula_unique_constraint
```

**Dado** (só se o passo acima não bastar — ação destrutiva, confirmar
explicitamente antes):

```bash
docker exec -i cadeia_dominial_db pg_restore -U cadeia_user -d cadeia_dominial --clean /tmp/backup_pre_identidade_*.dump
```

## O que este roteiro não cobre

- `migrar_origens_estruturadas` (T23) é um comando manual com `--dry-run`,
  separado deste deploy — não deve rodar automaticamente; revisar o
  relatório antes de decidir executá-lo no ambiente real.
- Nenhum teste de tempo/carga das migrações contra o volume real de dados
  (2524 documentos — volume pequeno, risco baixo, mas não medido).
- Merge para `main`/produção: fora de escopo. Este roteiro é só para o
  servidor de teste; produção exige uma decisão e um roteiro à parte,
  inclusive quanto a quando/se fazer o merge desta branch.

## Critério de conclusão da T30

Este documento existe e cobre: backup, preservação de config local,
troca de branch, subida controlada com acompanhamento de migração,
verificação pós-deploy (estrutural + funcional + homologação com dados
reais) e rollback de código/migração/dado. T30 fica `CONCLUÍDA` quando este
arquivo for revisado pelo usuário — a _execução_ do roteiro (deploy real)
é uma ação separada, ainda pendente de autorização explícita.
