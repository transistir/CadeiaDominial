# Checkpoint para retomada

Atualizado em: 2026-07-14 noite (America/Sao_Paulo).

## Resumo executivo

O commit reconstruído `0ff36d3` preserva o trabalho realizado até a T21. A
revisão posterior reabriu T03, T11, T14, T17, T18 e T21; a fila corretiva
R01–R07 foi executada e todas essas tarefas voltaram a `CONCLUÍDA` com nova
evidência. T22–T24 também foram concluídas; T25 está EM REVISÃO (identidade
completa nas opções, 7 testes novos) e T26 também está EM REVISÃO (seleção
inequívoca por ID + validação backend da importação de duplicata, 6 testes
novos); a próxima tarefa funcional é T27. T07 permanece separadamente em
revisão por depender de homologação manual.

Leitura obrigatória antes de alterar código:

1. `REVISAO_GERAL_2026-07-13.md` — achados e evidências da revisão.
2. `DECISAO_PERSISTENCIA_CANONICA.md` — decisão obrigatória para R02.
3. `TAREFAS.md` — estados, dependências e ordem R01–R07.
4. `PLANO_TESTES.md` e `MATRIZ_TESTES.md` — novos casos CR-01 a CR-09.
5. Entrada mais recente de `DIARIO.md` — decisões e restrições.

## Estado por grupo

- T01–T02 e T04–T06: concluídas; fundação conceitual preservada.
- T03: concluída; lacuna canônica do formulário/banco corrigida na R02 e validada na R07.
- T07: em revisão; automação existente passa, homologação manual pendente.
- T08–T10 e T12–T13: concluídas.
- T11: concluída; múltiplas origens preservam livro/folha após R05/R07.
- T14: concluída; tronco, conexões e níveis corrigidos nas R03/R04 e regredidos na R07.
- T15–T16 e T19–T20: concluídas.
- T17–T18: concluídas; constraints canônicas corrigidas na R02 e validadas na R07.
- T21: concluída; invariável canônica independente de `full_clean()` após R06/R07.
- T22: concluída; escrita textual e estruturada reconciliadas pelo fluxo funcional.
- T23: concluída; comando histórico conservador, idempotente e auditável.
- T24: concluída; estrutura é preferida e o texto funciona como fallback exclusivo.
- T25: EM REVISÃO; identidade completa nas opções implementada e testada (7/7), aguardando revisão do usuário.
- T26: EM REVISÃO; seleção inequívoca por ID e validação backend da importação de duplicata implementadas e testadas (6/6), aguardando revisão do usuário. T27–T30 pendentes.
- R01: concluída; decisão arquitetural registrada.
- R02: concluída; CR-01 a CR-04 aprovados.
- R03: concluída; CR-05 aprovado.
- R04: concluída; CR-06 aprovado.
- R05: concluída; CR-07 aprovado.
- R06: concluída; CR-08/CR-09 aprovados.
- R07: concluída; regressão e auditoria consolidadas.

## Próxima tarefa: T27

T25 está EM REVISÃO: identidade completa (tipo, número, cartório com CNS e
localização, imóvel) passou a ser exibida nas opções documentais
(duplicata/importação e seleção de documento), sem mudar o contrato de seleção.
7 testes novos passaram; canônica 67/67; baseline global (47 erros + 1 falha
legados) inalterado; sem migrações. Aguarda revisão do usuário para fechar T25.

T26 está EM REVISÃO: o botão de seleção de documento agora usa
`novo_lancamento_documento` com `documento_id` explícito, e essa view valida
com `get_object_or_404(Documento, id=documento_id, imovel=imovel)` que o
documento pertence ao imóvel da URL (404 caso contrário, em vez de renderizar
com imóvel/documento incompatíveis). A importação de duplicata
(`LancamentoDuplicataService.processar_importacao_duplicata`) não confia mais
apenas nos PKs do POST: reprocessa `origem_completa[]`/`cartorio_origem[]`
(já preservados como campos ocultos) pelo mesmo fluxo de detecção de
duplicata e só aceita `documento_origem_id`/`documentos_importaveis[]` que
batam exatamente com a duplicata recalculada no servidor. 6 testes novos
passaram; baseline global inalterado; sem migrações. Aguarda revisão do
usuário para fechar T26.

Próxima tarefa funcional: T27 — prévia: criar, reutilizar ou importar.

## Dívidas conhecidas (pré-T28)

Revisão de 2026-07-14 (Codex, verificadas no código); ver seção em `TAREFAS.md`:

1. `hierarquia_arvore_service.py:237` cria documento com `Cartorios.objects.first()`
   quando uma origem não resolve; acionado por `cadeia_dominial_views.py:64`
   (`criar_documentos_automaticos=True`) ao renderizar a árvore D3 (write-on-read).
2. `documento_views.py:199` (`criar_documento_automatico`) checa existência por
   `imovel + numero`, sem tipo/cartório canônicos.

Não bloqueiam T25–T27; exigem reclassificação/correção antes de T28/T29.

## Ordem de continuidade

1. Fechar T25 e T26 após revisão do usuário.
2. T27–T30 — seguir dependências do backlog, tratando as dívidas em T28.

## Homologação pendente da T07

1. Usar servidor de testes com cópia controlada do banco.
2. Abrir uma cadeia cujo início de matrícula referencie homônimos em cartórios diferentes.
3. Acessar `/tis/<tis_id>/imovel/<imovel_id>/cadeia-tabela/`.
4. Confirmar que apenas o documento do `cartorio_origem` aparece.
5. Alternar múltiplas origens e recarregar a página.
6. Confirmar que nenhuma escolha depende da ordem dos registros ou altera cartório.
7. Registrar ambiente, usuário, IDs e resultado na matriz e no diário.

Não concluir T07 apenas com os testes automáticos.

## Última validação conhecida

```text
test_t26_selecao_inequivoca (novo): 6/6 PASSOU
test_t25_identidade_opcoes: 7/7 PASSOU
test_identidade_documento: 67/67 PASSOU
manage.py check: PASSOU
makemigrations --check --dry-run: PASSOU
git diff --check: PASSOU
suíte global dominial.tests (165 testes): 47 erros e 1 falha legados,
  contagem inalterada em relação ao baseline anterior (159 testes)
```

Os 47 erros/1 falha legados são pré-existentes (não causados por T25/T26);
o maior grupo conhecido é `test_fase2_duplicata_integracao` (12 erros no
`setUp`, campo `descricao` removido de `DocumentoTipo`).

### Verificação de continuidade (2026-07-14 tarde)

Repetida após a sessão anterior ter travado, sem nenhuma alteração de código:

```text
git status: escopo confere com T25 (service + 2 templates + docs + novo teste)
git diff --check: limpo
test_t25_identidade_opcoes isolado: 7/7 OK
suíte canônica (5 módulos de teste de identidade/migração): 82/84 OK
  2 erros em VerificarEstruturaAmbienteCommandTest (IndexError em
  _get_column_collations do introspector SQLite do Django) —
  reproduzidos também via `git stash` sobre o commit 3e94ee2 (árvore
  limpa, sem as mudanças da sessão), confirmando que é falha
  pré-existente do ambiente local, não regressão de T25.
```

### T26 — seleção inequívoca por ID e validação backend (2026-07-14 noite)

```text
git status: escopo confere com T25+T26 (view + service + 2 templates + docs
  + test_t25_identidade_opcoes.py + test_t26_selecao_inequivoca.py, novos)
git diff --check: limpo
test_t26_selecao_inequivoca isolado: 6/6 OK
test_t25_identidade_opcoes + test_identidade_documento combinados: 74/74 OK
manage.py check: OK
makemigrations --check --dry-run: sem mudanças
dominial.tests global: 165 testes, 47 erros + 1 falha legados (baseline
  inalterado; eram 159 testes antes, +6 novos de T26)
```

Consulta ao Codex confirmou, antes de iniciar T26, que o estado do código
batia com este checkpoint (T25 EM REVISÃO, 7/7) e que a próxima tarefa
mapeada era exatamente esta.

## Restrições operacionais

- Não aplicar migrações 0043–0049 em ambiente compartilhado sem a auditoria e o roteiro de implantação previstos.
- Não apagar, unir ou corrigir identidades ambíguas automaticamente.
- Não alterar arquivos não rastreados nem usar `git add -A`.
- Não marcar CT/CR como aprovado sem executar o cenário correspondente.
- Não declarar a suíte global aprovada enquanto os débitos legados registrados não forem saneados.

## Ponto seguro de versionamento

- Branch de continuidade: `feature/identidade-documento-cartorio`.
- Último commit no histórico: `3e94ee2` (`docs(dominial): registra checkpoint seguro de continuidade`). As mudanças de T25 e T26 abaixo ainda **não foram commitadas** — seguem como alterações de working tree neste checkpoint.
- Escopo das alterações não commitadas (confira com `git status` antes de continuar):
  - T25: `dominial/services/lancamento_duplicata_service.py` (DTO de identidade), `templates/dominial/duplicata_importacao.html`, `templates/dominial/selecionar_documento_lancamento.html`, `dominial/tests/test_t25_identidade_opcoes.py` (novo).
  - T26: `dominial/views/lancamento_views.py` (`novo_lancamento_documento` escopado por imóvel), `templates/dominial/selecionar_documento_lancamento.html` (botão usa `novo_lancamento_documento`), `dominial/services/lancamento_duplicata_service.py` (`_validar_identidade_duplicata`), `dominial/tests/test_t26_selecao_inequivoca.py` (novo).
  - Docs: `CHECKPOINT_ATUAL.md`, `TAREFAS.md`, `DIARIO.md`.
- Estado funcional salvo: R01–R07 e T22–T24 concluídas; T25 EM REVISÃO; T26 EM REVISÃO; T27 é a próxima tarefa.
- T07 continua em revisão exclusivamente pela homologação manual documentada.
- `last.md` foi removido por ser uma resposta informal e desatualizada; este arquivo é a fonte oficial de retomada.
- O banco compartilhado não recebeu as migrações 0043–0049 nem o comando de migração histórica.
- A suíte global ainda possui o baseline conhecido de 47 erros e 1 falha legados; os portões focados atuais passaram (165 testes, +6 de T26).
- Arquivos não rastreados fora do escopo (dumps SQL, `node_modules/`, `packages/`, `.turbo/`, `pnpm-lock.yaml`, `docs/.project`, `docs/db/`, `db.sqlite3.new`, `scripts/d1_dump_filtered.sh`) permanecem intocados; não pertencem a T25/T26 e não devem ser adicionados com `git add -A`.

Se surgir uma tarefa urgente, não reutilize esta árvore com alterações soltas.
Confirme primeiro que o checkpoint está commitado, crie uma branch separada para
a urgência e retorne depois a esta branch. Nunca use `git add -A`: existem dumps,
bancos, caches e dependências locais não rastreados que não pertencem ao escopo.
