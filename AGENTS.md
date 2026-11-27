# AGENTS.md — Cadeia Dominial

Ponto de entrada para qualquer agente de código (Hermes, Claude Code, Codex) neste repositório.
Leia antes de alterar código. Este arquivo aponta para as fontes de verdade; não as replica.

## Arquitetura vigente

- **V1 Django** é a arquitetura ativa do produto. Código em `manage.py`, `cadeia_dominial/` (configuração),
  `dominial/` (aplicação principal), `ia_ocr/` (extração assistida), `templates/` e `static/`.
- Dependências: `requirements.txt`. Versão de Python: `runtime.txt` (3.11).
- Ambiente local e de teste: `docker-compose.yml` e `docker-compose.dev.yml`.
- **V2** (Cloudflare Workers, D1, pnpm, backlog #61–#72) está **arquivada**. Não é mantida na `develop`.
  O histórico está na branch remota `v2` (ponta `d6226621`). Restos locais em `packages/` de checkouts
  antigos devem ser ignorados. Não planeje, implemente nem revisite a V2 sem autorização explícita na sessão.

## Fila de trabalho — obrigatória no início de cada sessão

- **`docs/produto-3/ROADMAP.md` é a fonte única do que fazer.** Siga a fila (R1–R10) na ordem e com as
  exceções de gate definidas ali. Não escolha issue por recência ou preferência.
- Os gates (GATE-CLIENTE, GATE-LUANDRO, GATE-PRODUTO) e o que cada um bloqueia estão definidos no roadmap.
  Não os reinterprete aqui.
- Reordenar a fila exige aprovação explícita do usuário, registrada no próprio roadmap.
- `docs/PLANO_SPRINTS.md` é histórico. Não planeje a partir dele.
- O escopo do Produto 3 (FADESP 019/2026) está em `docs/produto-3/LEVANTAMENTO_PRODUTO3_CONTRATO.md`.
  A trilha de IA/OCR do contrato FUNAPE aparece na seção F3 do roadmap, marcada como outro contrato.

## Papéis e modelos de desenvolvimento

- Quem implementa, quem revisa e quais modelos ou rotas podem ser usados são definidos pelo **harness vigente**,
  declarado no `harness-state` do Hermes, seção `projects.cadeia_dominial` (no servidor: `~/.hermes/harness-state.yaml`).
- Este repositório não replica essa tabela. Se algum texto aqui divergir do harness, **vale o harness**;
  corrija este arquivo, não o harness, em um PR separado.
- A regra de custo e rota por modelo (`model_access`) também vale somente pelo harness.

## Fluxo de branch e PR

- Branch, worktree e PR seguem o `branch_policy` de `projects.cadeia_dominial` no harness vigente (PR para `develop`).
- `main` recebe apenas merge de `develop` com tag de release (`vX.Y.Z`). Não abra PR de feature para `main`.
- Merge segue o `merge_delegation` do harness vigente: sem a condição descrita ali, exige consentimento humano.
- Tag, deploy de produção, mudança de banco e comandos destrutivos exigem autorização humana explícita.

## Limite de 400 linhas por arquivo (CI)

- Nenhum arquivo de código (.py, .js, .html, .css) pode passar de 400 linhas. Arquivos legados acima do limite
  estão em `scripts/file_size_baseline.json`, que só pode encolher.
- Verificar: `python scripts/check_file_size.py`. Testes do verificador:
  `python -m unittest discover -s scripts/tests -v`.
- Atualizar o baseline quando um arquivo legado diminuiu: `python scripts/check_file_size.py --write-baseline`.
  Nunca use `--write-baseline` para aceitar um arquivo novo acima do limite.
- Comparação com a base do PR: `python scripts/check_file_size.py --base-ref origin/develop`.
- Hook de pre-commit: `git config core.hooksPath .githooks` (o hook só checa tamanho).
- Contexto e plano de redução: `docs/refatoracao/PLANO_400_LINHAS.md`.
- O CI de PR executa esse check (`.github/workflows/file-size.yml`). O workflow de deploy de testes
  (`.github/workflows/deploy-develop.yml`) não executa suíte de testes.

## Decisões de dados

- Decisões de persistência canônica: `docs/correcao-identidade-documentos/DECISAO_PERSISTENCIA_CANONICA.md`.
- Schemas de extração: `ia_ocr/schemas/`. Antes de alterar um campo, confira o schema e os testes em `ia_ocr/tests/`.
- Antes de adicionar coluna ou campo, leia a decisão correspondente. Se a decisão não existir, pergunte; não invente.

## Testes

- Suíte Django: `python manage.py test` (comando padrão do projeto; o CI não a executa).
- Antes de declarar pronto, rode os testes do módulo alterado.

## Regras gerais

- Não leia nem commite `.env`. Credenciais não entram em commit nem em log.
- Não use `--no-verify` para contornar hook. Corrija a causa.
- Ao criar commit, use mensagem em Conventional Commits.
