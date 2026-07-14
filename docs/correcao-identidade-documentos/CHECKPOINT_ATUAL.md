# Checkpoint para retomada

Atualizado em: 2026-07-14 T30 concluída — T01–T30 completas (America/Sao_Paulo).

## Resumo executivo

O commit reconstruído `0ff36d3` preserva o trabalho realizado até a T21. A
revisão posterior reabriu T03, T11, T14, T17, T18 e T21; a fila corretiva
R01–R07 foi executada e todas essas tarefas voltaram a `CONCLUÍDA` com nova
evidência. T22–T24 também foram concluídas; T25 (identidade completa nas
opções, 7 testes novos) e T26 (seleção inequívoca por ID + validação backend
da importação de duplicata, 6 testes novos) foram homologadas manualmente
pelo usuário em 2026-07-14 e estão `CONCLUÍDA`.

**Correção de rumo em T27 (2026-07-14, tarde):** uma primeira implementação de
T27 (bloco de prévia CRIAR/IMPORTAR/REUTILIZAR em `duplicata_importacao.html`)
foi **descartada**. O usuário apontou, antes de testar, que essa funcionalidade
já existe no baseline (detectar duplicata → avisar → confirmar → importar
cadeia + gerar aresta + recalcular hierarquia é anterior a esta branch) e que
esta branch deve se limitar a corrigir a identidade por cartório, não inventar
uma UI nova. Consulta ao Codex confirmou o diagnóstico e recomendou descartar
o código. Os três arquivos alterados foram revertidos via `git checkout --`
para o estado de T26 e o teste novo foi removido; nada da tentativa
permanece. T27 foi **redefinida** como um teste de regressão (sem novo código
de produção) confirmando que o fluxo de confirmação de duplicata já existente
usa a identidade de cartório ponta a ponta (lançamento → `LancamentoOrigem` →
aresta da árvore por ID → níveis). O teste (`test_t27_regressao_cartorio_duplicata.py`)
**passou na primeira execução, sem nenhuma mudança em código de produção**,
confirmando a previsão do Codex de que R03/R04/T14/T22/T26 já cobrem esse
caminho. T27 está `CONCLUÍDA`. Ver `TAREFAS.md` (entrada "T27 — histórico") e
`DIARIO.md` para o relato completo.

**Dívidas técnicas pré-T28 corrigidas (2026-07-14, tarde):** as duas dívidas
registradas (`hierarquia_arvore_service.py:237` e `documento_views.py:199`,
ambas com `Cartorios.objects.first()` em vez do cartório real da origem)
foram corrigidas. Ver seção "Dívidas conhecidas" abaixo para o detalhe.

**T28 concluída (2026-07-14, tarde):** auditoria estática final (mesma
técnica de T01/R07) sobre `dominial/services/`, `dominial/views/`,
`dominial/utils/`, `dominial/admin.py` e `dominial/management/commands/`.
Encontrou uma **terceira dívida real e ativa**, não registrada antes:
`editar_lancamento` (`lancamento_views.py`) autorizava editar um lançamento
de outro imóvel usando `origem__icontains=lancamento.documento.numero` — um
match textual de número sem checar cartório, permitindo que um homônimo não
referenciado de fato passasse por coincidência de texto. Corrigido: a
checagem agora usa `LancamentoOrigemLeituraService.obter_origens` e compara
tipo + número normalizado + cartório. Demais ocorrências de busca por número
isolado classificadas como código morto (3 arquivos não importados por
nada), diagnóstico de script isolado, comandos de management
somente-leitura, ou pesquisa administrativa textual (não relacionamento de
negócio) — nenhuma alimenta resolução ativa. Ver `TAREFAS.md` (seção "T28")
para o detalhe completo.

Suíte combinada (T25+T26+T27+identidade canônica+as três correções): 88/88;
suíte global 173 testes, baseline de 47 erros + 1 falha legados inalterado.

**T29 concluída (2026-07-14, tarde):** suíte global repetida (173 testes,
47 erros + 1 falha, baseline idêntico ao de antes de T22) e suíte focada
combinada de 14 módulos de teste de identidade/migração/T25-T28: **116/116**.
`check`, `makemigrations --check --dry-run` e `git diff --check` limpos.

**T30 concluída (2026-07-14, tarde):** roteiro de implantação/rollback
formalizado em `docs/correcao-identidade-documentos/ROTEIRO_IMPLANTACAO.md`
— cobre backup do banco de teste, preservação da config local não
commitada do servidor, troca de branch, subida controlada (migrations
0043–0049 aplicam automaticamente via `scripts/init.sh`), verificação
pós-deploy estrutural e funcional (incluindo a homologação pendente de
T07 e o roteiro manual de T25/T26 com dados reais), e rollback de
código/migração/dado. A execução real do deploy é uma ação separada,
ainda pendente de autorização explícita.

**T01–T30 completas.** T07 permanece separadamente em revisão por depender
de homologação manual própria (cross-cartorio no servidor de teste com
dados reais) — só é possível concluí-la durante/depois do deploy real no
servidor de teste, seguindo o roteiro acima. Próximos passos: revisão do
usuário sobre o roteiro → commit → PR → execução do deploy no servidor de
teste → homologação com dados reais (T07 + validação geral).

Decisão registrada (consulta ao Codex em 2026-07-14): não fazer deploy
incremental de T25/T26 no servidor de teste agora. Concluir T27–T30
localmente primeiro e só então fazer um único deploy/homologação estruturado
no servidor de teste, cobrindo migrations 0043–0049, dados reais, T25–T27,
auditoria final (T28) e regressão (T29) de uma vez. Ver `DIARIO.md`.

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
- T25: CONCLUÍDA; identidade completa nas opções implementada, testada (7/7) e homologada manualmente pelo usuário em 2026-07-14.
- T26: CONCLUÍDA; seleção inequívoca por ID e validação backend da importação de duplicata implementadas, testadas (6/6) e homologadas manualmente pelo usuário em 2026-07-14.
- T27: CONCLUÍDA (redefinida); tentativa anterior de "prévia" foi descartada por scope creep — ver Resumo executivo. Teste de regressão (`test_t27_regressao_cartorio_duplicata.py`) passou sem alteração de código. T28–T30 pendentes.
- R01: concluída; decisão arquitetural registrada.
- R02: concluída; CR-01 a CR-04 aprovados.
- R03: concluída; CR-05 aprovado.
- R04: concluída; CR-06 aprovado.
- R05: concluída; CR-07 aprovado.
- R06: concluída; CR-08/CR-09 aprovados.
- R07: concluída; regressão e auditoria consolidadas.

## Próxima tarefa: dívidas técnicas pré-T28

T25 está CONCLUÍDA: identidade completa (tipo, número, cartório com CNS e
localização, imóvel) passou a ser exibida nas opções documentais
(duplicata/importação e seleção de documento), sem mudar o contrato de seleção.
7 testes novos passaram; canônica 67/67; baseline global (47 erros + 1 falha
legados) inalterado; sem migrações. Homologada manualmente pelo usuário em
2026-07-14 (roteiro com homônimos M123 em cartórios A/B).

T26 está CONCLUÍDA: o botão de seleção de documento agora usa
`novo_lancamento_documento` com `documento_id` explícito, e essa view valida
com `get_object_or_404(Documento, id=documento_id, imovel=imovel)` que o
documento pertence ao imóvel da URL (404 caso contrário, em vez de renderizar
com imóvel/documento incompatíveis). A importação de duplicata
(`LancamentoDuplicataService.processar_importacao_duplicata`) não confia mais
apenas nos PKs do POST: reprocessa `origem_completa[]`/`cartorio_origem[]`
(já preservados como campos ocultos) pelo mesmo fluxo de detecção de
duplicata e só aceita `documento_origem_id`/`documentos_importaveis[]` que
batam exatamente com a duplicata recalculada no servidor. 6 testes novos
passaram; baseline global inalterado; sem migrações. Homologada manualmente
pelo usuário em 2026-07-14 (mesma sessão de teste local).

T27 está CONCLUÍDA (redefinida): não é uma interface nova, é um teste de
regressão confirmando que o fluxo já existente de confirmação de duplicata
(aviso → confirmar → `ImportacaoCadeiaService.importar_cadeia_dominial` →
criação do lançamento via `LancamentoCriacaoService`) usa a identidade
completa de cartório ponta a ponta, não só na detecção (já coberta por
T08/T26). O teste (`test_t27_regressao_cartorio_duplicata.py`) criou dois
documentos homônimos em cartórios diferentes, confirmou a duplicata do
cartório A e verificou: o `LancamentoOrigem` gravado guarda `cartorio_a` e
`numero_normalizado="123"`; a árvore reconstruída liga o documento ativo ao
documento do cartório A por ID; o homônimo do cartório B não aparece nem
como aresta nem como nó; o nível do nó importado é 1. **Passou na primeira
execução, sem nenhuma mudança em código de produção** — confirma que
R03/R04/T14/T22/T26 já cobrem esse caminho. 1 teste novo; combinado com
T25/T26/identidade canônica, 81/81; suíte global (166 testes, 47 erros + 1
falha legados, baseline inalterado); sem migrações.

Próxima tarefa após T27: tratar as duas dívidas técnicas pré-T28 listadas
abaixo.

Decisão de sequenciamento (2026-07-14, consulta ao Codex): não fazer deploy
incremental de T25/T26 no servidor de teste agora. A auditoria somente
leitura (`auditar_identidade_documentos --fail-on-conflict --json`) já foi
executada contra o banco real de teste (2524 documentos, zero conflitos,
zero inválidos, zero sem cartório), o que reduz a urgência de antecipar um
deploy parcial. Concluído T27, tratar as duas dívidas técnicas pré-T28,
depois T28 (auditoria final) e T29 (regressão), depois formalizar T30
(roteiro de implantação/rollback — rascunho já existe fora deste diretório,
ver entrada correspondente no `DIARIO.md`), e só então um único
deploy/homologação estruturado no servidor de teste.

## Dívidas conhecidas (pré-T28) — CORRIGIDAS em 2026-07-14

Revisão de 2026-07-14 (Codex, verificadas no código); ver seção em `TAREFAS.md`.

1. `hierarquia_arvore_service.py:237` criava documento com `Cartorios.objects.first()`
   quando uma origem não resolve; acionado por `cadeia_dominial_views.py:64`
   (`criar_documentos_automaticos=True`) ao renderizar a árvore D3 (write-on-read).
   **Corrigido:** `_criar_documento_automatico` agora recebe o cartório da
   própria origem (`origem.cartorio`); sem cartório, não cria o documento.
   Teste: `test_divida_cartorio_arbitrario_arvore.py` (2/2).
2. `documento_views.py:199` (`criar_documento_automatico`) checava existência por
   `imovel + numero` bruto, sem tipo/cartório canônicos, e tinha os mesmos dois
   fallbacks para `Cartorios.objects.first()`.
   **Corrigido:** existência verificada por tipo + número normalizado; sem
   cartório resolvível pelo contexto, a criação é recusada (erro), nunca
   adivinha um cartório. View não é referenciada por nenhum template/JS ativo
   (endpoint só alcançável por URL direta), mas a rota nomeada permanece e foi
   corrigida mesmo assim. Teste: `test_divida_criar_documento_automatico_view.py` (3/3).
3. **Encontrada na auditoria T28** (não estava nesta lista original):
   `editar_lancamento` (`lancamento_views.py`) autorizava edição de
   lançamento de outro imóvel via `origem__icontains=lancamento.documento.numero`
   — match textual sem cartório. **Corrigido:** usa
   `LancamentoOrigemLeituraService.obter_origens` e compara tipo + número
   normalizado + cartório. Teste: `test_divida_edicao_lancamento_homonimo.py` (2/2).

Suíte combinada (T25+T26+T27+identidade canônica+as três correções): 88/88.
Suíte global: 173 testes, 47 erros + 1 falha legados (baseline inalterado).
Não bloqueiam mais nada; T28 concluída, T29 desbloqueada.

## Ordem de continuidade

1. T25 e T26 fechadas após revisão do usuário (2026-07-14).
2. T27 — concluída como teste de regressão de cartório ponta a ponta (tentativa anterior de UI nova foi descartada; teste passou sem mudança de código).
3. Dívidas técnicas pré-T28 — corrigidas (`hierarquia_arvore_service.py:237`, `documento_views.py:199`, e uma terceira encontrada na própria auditoria: `lancamento_views.py` `editar_lancamento`).
4. T28 (auditoria final) — concluída.
5. T29 (teste integrado de regressão) — concluída (173 global + 116/116 focado).
6. T30 — concluída (`ROTEIRO_IMPLANTACAO.md`).
7. Próximo: revisão do usuário → commit → PR → executar o deploy no servidor de teste seguindo o roteiro → homologação com dados reais (T07 + validação geral).

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

### T27 — tentativa descartada (2026-07-14)

Implementação de uma "prévia" CRIAR/IMPORTAR/REUTILIZAR (contrato confirmado
com o usuário antes de codificar; 7/7 testes novos; suíte combinada 87/87)
foi **revertida** após o usuário apontar, antes de testar, que essa
funcionalidade já existe no baseline e que esta branch deve se limitar à
identidade por cartório. Consulta ao Codex confirmou o diagnóstico. Reversão:
`git checkout --` em `dominial/services/lancamento_duplicata_service.py`,
`dominial/views/lancamento_views.py`, `templates/dominial/duplicata_importacao.html`
(voltam ao estado exato do commit `b67d368`, T26); `dominial/tests/test_t27_previa_duplicata.py`
removido. Confirmado após a reversão: `git diff --stat` só mostra mudanças em
documentação; suíte T25/T26/identidade canônica volta a 80/80. T27 foi
redefinida como teste de regressão (ver `TAREFAS.md` e Resumo executivo
acima) — nenhum código de produção desta tentativa permanece.

## Restrições operacionais

- Não aplicar migrações 0043–0049 em ambiente compartilhado sem a auditoria e o roteiro de implantação previstos.
- Não apagar, unir ou corrigir identidades ambíguas automaticamente.
- Não alterar arquivos não rastreados nem usar `git add -A`.
- Não marcar CT/CR como aprovado sem executar o cenário correspondente.
- Não declarar a suíte global aprovada enquanto os débitos legados registrados não forem saneados.

## Ponto seguro de versionamento

- Branch de continuidade: `feature/identidade-documento-cartorio`.
- Commit funcional seguro: `b67d368` (`feat(dominial): exibe identidade completa e valida seleção por ID (T25/T26)`), local, sem push.
- Escopo do commit:
  - T25: `dominial/services/lancamento_duplicata_service.py` (DTO de identidade), `templates/dominial/duplicata_importacao.html`, `templates/dominial/selecionar_documento_lancamento.html`, `dominial/tests/test_t25_identidade_opcoes.py`.
  - T26: `dominial/views/lancamento_views.py` (`novo_lancamento_documento` escopado por imóvel), `templates/dominial/selecionar_documento_lancamento.html` (botão usa `novo_lancamento_documento`), `dominial/services/lancamento_duplicata_service.py` (`_validar_identidade_duplicata`), `dominial/tests/test_t26_selecao_inequivoca.py`.
  - Docs: `CHECKPOINT_ATUAL.md`, `TAREFAS.md`, `DIARIO.md`.
  - T27 (ainda não commitado, working tree): `dominial/tests/test_t27_regressao_cartorio_duplicata.py` (novo); nenhum arquivo de produção (a tentativa de UI anterior foi revertida antes deste ponto).
  - Dívidas pré-T28 (ainda não commitado, working tree): `dominial/services/hierarquia_arvore_service.py` (`_criar_documento_automatico` recebe cartório da origem), `dominial/views/documento_views.py` (`criar_documento_automatico` verifica por tipo+número normalizado e recusa criar sem cartório resolvível), `dominial/views/lancamento_views.py` (`editar_lancamento` autoriza por identidade completa, não por texto), `dominial/tests/test_divida_cartorio_arbitrario_arvore.py`, `dominial/tests/test_divida_criar_documento_automatico_view.py`, `dominial/tests/test_divida_edicao_lancamento_homonimo.py` (todos novos).
- Estado funcional salvo: R01–R07, T22–T29 concluídas; as três dívidas técnicas pré-T28 corrigidas (duas do checkpoint original + uma encontrada na própria auditoria T28). Próxima tarefa: T30 (roteiro de implantação/rollback).
- T07 continua em revisão exclusivamente pela homologação manual documentada.
- `last.md` foi removido por ser uma resposta informal e desatualizada; este arquivo é a fonte oficial de retomada.
- O banco compartilhado não recebeu as migrações 0043–0049 nem o comando de migração histórica.
- A suíte global ainda possui o baseline conhecido de 47 erros e 1 falha legados; os portões focados atuais passaram (173 testes, baseline inalterado).
- Arquivos não rastreados fora do escopo (dumps SQL, `node_modules/`, `packages/`, `.turbo/`, `pnpm-lock.yaml`, `docs/.project`, `docs/db/`, `db.sqlite3.new`, `scripts/d1_dump_filtered.sh`) permanecem intocados; não pertencem a T25/T26/T27 e não devem ser adicionados com `git add -A`.

Se surgir uma tarefa urgente, não reutilize esta árvore com alterações soltas.
Confirme primeiro que o checkpoint está commitado, crie uma branch separada para
a urgência e retorne depois a esta branch. Nunca use `git add -A`: existem dumps,
bancos, caches e dependências locais não rastreados que não pertencem ao escopo.
