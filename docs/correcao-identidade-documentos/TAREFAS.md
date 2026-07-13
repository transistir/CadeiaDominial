# Backlog e acompanhamento

Atualize a coluna **Estado** e a seção **Evidências** ao terminar cada tarefa. Não execute tarefas com dependências incompletas.

## Resumo

| ID | Entrega pequena | Depende de | Testes | Estado |
|---|---|---|---|---|
| T01 | Auditar consultas de `Documento` por número | — | revisão estática | CONCLUÍDA |
| T02 | Testes-base da identidade completa | — | CT-01 a CT-05 | CONCLUÍDA |
| T03 | Testes do cadastro de imóvel | — | CT-06 a CT-08 | CONCLUÍDA |
| T04 | Função isolada de normalização | T02 | CT-09 a CT-12 | CONCLUÍDA |
| T05 | Objeto imutável `DocumentoIdentidade` | T04 | CT-01 a CT-05 | CONCLUÍDA |
| T06 | `DocumentoIdentidadeService` | T05 | CT-13 a CT-15 | CONCLUÍDA |
| T07 | Corrigir origens disponíveis na tabela | T06 | CT-16 | EM REVISÃO |
| T08 | Corrigir verificação inicial de duplicata | T06 | CT-17 | CONCLUÍDA |
| T09 | Corrigir recursão de documentos importáveis | T08 | CT-18 | CONCLUÍDA |
| T10 | Corrigir obtenção da cadeia de origem | T09 | CT-18 | CONCLUÍDA |
| T11 | Corrigir criação automática de origem | T06 | CT-19 | CONCLUÍDA |
| T12 | Proibir alteração automática de cartório | T11 | CT-20 | CONCLUÍDA |
| T13 | Corrigir `HierarquiaOrigemService` | T06 | CT-16, CT-19 | CONCLUÍDA |
| T14 | Corrigir identidade nos serviços ativos de árvore | T13 | CT-18 | CONCLUÍDA |
| T15 | Comando somente leitura de auditoria de dados | T04 | testes do comando | CONCLUÍDA |
| T16 | Verificador de migrações e constraints por ambiente | T15 | testes do comando | CONCLUÍDA |
| T17 | Constraint de Documento: tipo+número+cartório | T02, T04, T15 | testes de migração | CONCLUÍDA |
| T18 | Constraint do documento principal do Imóvel | T03, T15 | testes de migração | CONCLUÍDA |
| T19 | Impedir novos registros sem cartório | T15 | CT-07 | CONCLUÍDA |
| T20 | Tornar cartório `NOT NULL` | T19 | teste de migração | CONCLUÍDA |
| T21 | Adicionar modelo `LancamentoOrigem` | T17 | testes do modelo | CONCLUÍDA |
| T22 | Gravar origens estruturadas | T21 | testes de integração | PENDENTE |
| T23 | Comando `--dry-run` para migrar origens antigas | T21 | testes do comando | PENDENTE |
| T24 | Consultar origens estruturadas com fallback | T22, T23 | CT-17, CT-18 | PENDENTE |
| T25 | Exibir identidade completa nas opções | T08 | teste de template/view | PENDENTE |
| T26 | Exigir seleção inequívoca por ID e validar backend | T25 | CT-15 | PENDENTE |
| T27 | Prévia: criar, reutilizar ou importar | T26 | teste de fluxo | PENDENTE |
| T28 | Auditoria final de buscas por número isolado | T07–T27 | revisão estática | PENDENTE |
| T29 | Teste integrado de regressão | T07–T27 | suíte CT completa | PENDENTE |
| T30 | Roteiro de implantação e rollback | T15–T29 | validação documental | PENDENTE |

## Critérios por grupo

### T01–T06 — Fundação

- T01 deve registrar arquivo, linha, fluxo e risco sem alterar código funcional.
- T04 não remove zeros à esquerda.
- T06 nunca recebe apenas número e nunca resolve ambiguidade com `.first()`.

### T07–T14 — Fluxos críticos

- Toda busca de relacionamento usa tipo, número normalizado e cartório.
- Conjuntos e dicionários da árvore usam ID ou identidade completa, nunca número sozinho.
- O cartório da origem vem de `lancamento.cartorio_origem` quando informado.
- “Início de Matrícula” não altera cartório automaticamente.

### T15–T20 — Dados e constraints

- Comandos de auditoria são somente leitura.
- Migrações interrompem diante de conflito e não escolhem correções.
- A constraint final de Documento inclui `tipo`, `numero` e `cartorio`.
- A constraint final do documento principal inclui tipo, número e cartório.

### T21–T24 — Origens estruturadas

- O campo textual antigo permanece durante a transição.
- Cada origem preserva seu próprio tipo e cartório.
- Migração antiga oferece `--dry-run`, é idempotente e não converte ambiguidades.

### T25–T30 — Interface e entrega

- Opções mostram tipo, número, cartório, cidade/UF, CNS e imóvel.
- O backend valida o ID selecionado contra a identidade informada.
- A auditoria final distingue pesquisa textual de relacionamento de negócio.
- O roteiro de produção exige backup, homologação e critérios de rollback.

## Evidências por tarefa

Copie este bloco ao concluir uma tarefa:

```text
### TXX — título
- Estado: EM REVISÃO
- Data:
- Responsável/IA:
- Arquivos alterados:
- Testes adicionados:
- Comandos executados:
- Resultado:
- Riscos ou pendências:
- Commit/PR (se existir):
```

## Evidências registradas

### T01 — Auditar consultas de Documento por número

- Estado: CONCLUÍDA
- Data: 2026-07-11
- Responsável/IA: Codex
- Arquivos alterados: `AUDITORIA_CONSULTAS.md` e documentos de acompanhamento
- Testes adicionados: não aplicável; tarefa somente de leitura
- Comandos executados: buscas `rg` por consultas, `.first()`, chaves e conjuntos baseados em número
- Resultado: oito grupos críticos ativos, cinco parcialmente qualificados e três implementações com estruturas por número catalogados
- Riscos ou pendências: corrigir na ordem definida entre T06 e T14
- Commit/PR: não criado

### T02 — Testes-base da identidade completa

- Estado: EM REVISÃO
- Data: 2026-07-11
- Responsável/IA: Codex
- Arquivos alterados: `dominial/tests/test_identidade_documento.py`
- Testes adicionados: CT-01, CT-02, CT-03 e CT-04
- Comandos executados: `python manage.py test dominial.tests.test_identidade_documento --noinput` no contêiner web dev
- Resultado: 8 testes executados; 7 passaram e CT-02 ficou como falha esperada até T17
- Riscos ou pendências: CT-05 depende do resolvedor de T06; CT-02 depende da nova constraint de T17
- Commit/PR: não criado

### T03 — Testes do cadastro de imóvel

- Estado: CONCLUÍDA
- Data: 2026-07-11
- Responsável/IA: Codex
- Arquivos alterados: `dominial/tests/test_identidade_documento.py`, `dominial/forms/imovel_forms.py`
- Testes adicionados: CT-06, CT-08 e tipo diferente no mesmo cartório
- Comandos executados: suíte focada no contêiner web dev
- Resultado: formulário aceita homônimo de outro cartório, recusa a mesma identidade e aceita tipo diferente
- Riscos ou pendências: banco só aceitará tipo diferente após T18
- Commit/PR: não criado

### T04 — Função isolada de normalização

- Estado: CONCLUÍDA
- Data: 2026-07-11
- Responsável/IA: Codex
- Arquivos alterados: `dominial/utils/documento_identidade_utils.py`, `dominial/utils/__init__.py`, `dominial/tests/test_identidade_documento.py`
- Testes adicionados: CT-09 a CT-12 e cinco casos de borda
- Comandos executados: `python manage.py test dominial.tests.test_identidade_documento --noinput` no contêiner web dev
- Resultado: 17 testes executados; 16 passaram e a única falha esperada continua sendo CT-02/T17
- Riscos ou pendências: a função ainda não foi integrada aos fluxos; isso ocorrerá depois do objeto e resolvedor centrais
- Commit/PR: não criado

### T05 — Objeto imutável DocumentoIdentidade

- Estado: CONCLUÍDA
- Data: 2026-07-11
- Responsável/IA: Codex
- Arquivos alterados: `dominial/utils/documento_identidade_utils.py`, `dominial/utils/__init__.py`, `dominial/tests/test_identidade_documento.py`
- Testes adicionados: igualdade, diferença por tipo/cartório, identidade incompleta, imutabilidade e ID inválido
- Comandos executados: `python manage.py test dominial.tests.test_identidade_documento --noinput` no contêiner web dev
- Resultado: 24 testes executados; 23 passaram e a falha esperada continua restrita à constraint de T17
- Riscos ou pendências: o objeto ainda não consulta o ORM; essa integração pertence à T06
- Commit/PR: não criado

### T06 — DocumentoIdentidadeService

- Estado: CONCLUÍDA
- Data: 2026-07-11
- Responsável/IA: Codex
- Arquivos alterados: `dominial/services/documento_identidade_service.py`, `dominial/tests/test_identidade_documento.py`
- Testes adicionados: CT-13, CT-14, CT-15, distinção por tipo e rejeição de entrada incompleta
- Comandos executados: `python manage.py test dominial.tests.test_identidade_documento --noinput` no contêiner web dev
- Resultado: 30 testes executados; 29 passaram e a falha esperada continua restrita à constraint de T17
- Riscos ou pendências: enquanto dados legados mantiverem prefixos, a resolução filtra tipo+cartório no banco e normaliza os candidatos em memória
- Commit/PR: não criado

### T07 — Corrigir origens disponíveis na tabela

- Estado: EM REVISÃO
- Data: 2026-07-11
- Responsável/IA: Codex
- Arquivos alterados: `dominial/services/cadeia_dominial_tabela_service.py`, `dominial/tests/test_identidade_documento.py`
- Testes adicionados: CT-16 para extração e expansão; ausência de cartório, ambiguidade e tipo incompatível
- Comandos executados: suíte focada, `manage.py check`, auditoria `rg` e `git diff --check`
- Resultado: 35 testes executados; 34 passaram e a única falha esperada é T17; não restam consultas globais por número no serviço da tabela
- Riscos ou pendências: aguarda teste manual da tabela no navegador com documentos homônimos em cartórios diferentes
- Commit/PR: não criado

### T08 — Corrigir verificação inicial de duplicata

- Estado: CONCLUÍDA
- Data: 2026-07-12
- Responsável/IA: Codex
- Arquivos alterados: `dominial/services/duplicata_verificacao_service.py`, `dominial/tests/test_identidade_documento.py`
- Testes adicionados: CT-17, normalização do número e distinção por tipo
- Comandos executados: suíte focada de identidade, suíte legada de duplicatas, `manage.py check`, auditoria `rg` e `git diff --check`
- Resultado: 37 testes focados executados; 36 passaram e uma falha esperada permanece restrita à constraint de T17; `manage.py check` sem erros
- Riscos ou pendências: a suíte legada `test_duplicata_verificacao` possui 18 erros preexistentes no `setUp` por usar o campo removido `DocumentoTipo.descricao`; as buscas recursivas por número isolado permanecem para T09/T10
- Commit/PR: não criado

### T09 — Corrigir recursão de documentos importáveis

- Estado: CONCLUÍDA
- Data: 2026-07-12
- Responsável/IA: Codex
- Arquivos alterados: `dominial/services/duplicata_verificacao_service.py`, `dominial/tests/test_identidade_documento.py`
- Testes adicionados: CT-18 para a etapa de cálculo dos documentos importáveis
- Comandos executados: suíte focada de identidade, `manage.py check`, auditoria `rg` e `git diff --check`
- Resultado: 38 testes focados executados; 37 passaram e uma falha esperada permanece restrita à constraint de T17; `manage.py check` sem erros
- Riscos ou pendências: a montagem informativa da cadeia ainda possui uma consulta por número isolado, reservada à T10
- Commit/PR: não criado

### T10 — Corrigir obtenção da cadeia de origem

- Estado: CONCLUÍDA
- Data: 2026-07-12
- Responsável/IA: Codex
- Arquivos alterados: `dominial/services/duplicata_verificacao_service.py`, `dominial/tests/test_identidade_documento.py`
- Testes adicionados: CT-18 para a cadeia informativa completa da origem
- Comandos executados: suíte focada de identidade, `manage.py check`, auditoria `rg` e `git diff --check`
- Resultado: 39 testes focados executados; 38 passaram e uma falha esperada permanece restrita à constraint de T17; `manage.py check` sem erros
- Riscos ou pendências: CT-18 ainda terá cobertura nos serviços ativos de árvore durante T14; não restam consultas de `Documento` por número isolado neste serviço
- Commit/PR: não criado

### T11 — Corrigir criação automática de origem

- Estado: CONCLUÍDA
- Data: 2026-07-12
- Responsável/IA: Codex
- Arquivos alterados: `dominial/services/lancamento_origem_service.py`, `dominial/utils/hierarquia_utils.py`, `dominial/tests/test_identidade_documento.py`
- Testes adicionados: CT-19 para criação em B quando existe homônimo em A e reutilização quando B já existe
- Comandos executados: suíte focada de identidade, `manage.py check`, auditoria `rg` e `git diff --check`
- Resultado: 41 testes focados executados; 40 passaram e uma falha esperada permanece restrita à constraint de T17; `manage.py check` sem erros
- Riscos ou pendências: os métodos legados de alteração explícita de cartório permanecem definidos, embora não sejam mais chamados pelo fluxo de criação; sua remoção pertence à T12
- Commit/PR: não criado

### T12 — Proibir alteração automática de cartório

- Estado: CONCLUÍDA
- Data: 2026-07-12
- Responsável/IA: Codex
- Arquivos alterados: `dominial/services/lancamento_origem_service.py`, `dominial/tests/test_identidade_documento.py`
- Testes adicionados: CT-20 com documento homônimo sem lançamentos
- Comandos executados: suíte focada de identidade, `manage.py check`, auditoria `rg` e `git diff --check`
- Resultado: 42 testes focados executados; 41 passaram e uma falha esperada permanece restrita à constraint de T17; `manage.py check` sem erros
- Riscos ou pendências: não restam definições ou chamadas dos métodos de alteração automática de cartório
- Commit/PR: não criado

### T13 — Corrigir `HierarquiaOrigemService`

- Estado: CONCLUÍDA
- Data: 2026-07-12
- Responsável/IA: Codex
- Arquivos alterados: `dominial/services/hierarquia_origem_service.py`, `dominial/tests/test_identidade_documento.py`
- Testes adicionados: CT-16 para resolução no cartório do lançamento e CT-19 para criação em B sem alterar A
- Comandos executados: suíte focada de identidade, `manage.py check`, auditoria `rg` e `git diff --check`
- Resultado: 44 testes focados executados; 43 passaram e uma falha esperada permanece restrita à constraint de T17; `manage.py check` sem erros
- Riscos ou pendências: a integração dos serviços ativos de árvore e seus conjuntos de processados pertence à T14
- Commit/PR: não criado

### T14 — Corrigir identidade nos serviços ativos de árvore

- Estado: CONCLUÍDA
- Data: 2026-07-12
- Responsável/IA: Codex
- Arquivos alterados: `dominial/utils/hierarquia_utils.py`, `dominial/services/hierarquia_arvore_service.py`, `dominial/services/cadeia_completa_service.py`, `dominial/tests/test_identidade_documento.py`
- Testes adicionados: CT-18 para pais da árvore, cadeia completa, importados e tronco principal
- Comandos executados: suíte focada de identidade, `manage.py check`, auditoria `rg`, `git diff --check` e verificação somente leitura no imóvel 5 do banco dev
- Resultado: 48 testes focados executados; 47 passaram e uma falha esperada permanece restrita à constraint de T17; o caso real seguiu `M9442` de Amambai (ID 163), sem selecionar homônimos de Ponta Porã
- Riscos ou pendências: a lista visual inicial de botões da T07 ainda deve ser validada/corrigida separadamente antes da homologação; arquivos de backup/cópias antigas não foram alterados
- Commit/PR: não criado

### T15 — Comando somente leitura de auditoria de dados

- Estado: CONCLUÍDA
- Data: 2026-07-12
- Responsável/IA: Codex
- Arquivos alterados: `dominial/management/commands/auditar_identidade_documentos.py`, `dominial/tests/test_identidade_documento.py`
- Testes adicionados: conflito canônico, número inválido, interrupção segura e inspeção de ausência de SQL de escrita
- Comandos executados: suíte focada de identidade, comando no banco dev com `--json`, `manage.py check`, auditoria estática e `git diff --check`
- Resultado: 51 testes focados executados; 50 passaram e uma falha esperada permanece restrita à constraint de T17; banco dev com 1.220 documentos, zero conflitos, zero inválidos e zero documentos sem cartório
- Riscos ou pendências: a ausência de conflitos no banco dev não substitui a execução no espelho usado pela homologação antes das migrações
- Commit/PR: não criado

### T16 — Verificador de migrações e constraints por ambiente

- Estado: CONCLUÍDA
- Data: 2026-07-12
- Responsável/IA: Codex
- Arquivos alterados: `dominial/management/commands/verificar_estrutura_ambiente.py`, `dominial/tests/test_identidade_documento.py`
- Testes adicionados: relatório estrutural somente leitura e interrupção enquanto constraints finais estão ausentes
- Comandos executados: suíte focada de identidade, verificador no banco dev com `--json`, `manage.py check`, auditoria estática e `git diff --check`
- Resultado: 53 testes focados executados; 52 passaram e uma falha esperada permanece restrita à constraint de T17; banco dev sem migrações pendentes ou desconhecidas
- Riscos ou pendências: as constraints atuais ainda são `(numero, cartorio_id)` em Documento e `(matricula, cartorio_id)` em Imovel; `--expect-final` deve continuar falhando até T17/T18
- Commit/PR: não criado

### T17 — Constraint de Documento: tipo+número+cartório

- Estado: CONCLUÍDA
- Data: 2026-07-12
- Responsável/IA: Codex
- Arquivos alterados: `dominial/models/documento_models.py`, `dominial/migrations/0043_documento_identidade_constraint.py`, `dominial/tests/test_identidade_documento.py`, `dominial/tests/test_migracao_identidade_documento.py`
- Testes adicionados: avanço limpo, bloqueio por conflito canônico, constraint efetiva e reversão incompatível segura
- Comandos executados: suíte de identidade, testes de migração, execução conjunta, `makemigrations --check --dry-run`, `manage.py check` e `git diff --check`
- Resultado: 56 testes executados e aprovados; nenhuma falha esperada restante; modelo e migração sincronizados
- Riscos ou pendências: a migração 0043 não foi aplicada ao banco dev compartilhado; deve ser precedida por `auditar_identidade_documentos --fail-on-conflict` no ambiente alvo
- Commit/PR: não criado

### T18 — Constraint do documento principal do Imóvel

- Estado: CONCLUÍDA
- Data: 2026-07-12
- Responsável/IA: Codex
- Arquivos alterados: `dominial/models/imovel_models.py`, `dominial/migrations/0044_imovel_identidade_constraint.py`, `dominial/tests/test_identidade_documento.py`, `dominial/tests/test_migracao_identidade_imovel.py`
- Testes adicionados: avanço limpo, conflito canônico, constraint efetiva, reversão incompatível e aprovação de `--expect-final`
- Comandos executados: teste isolado de migração, execução conjunta T17/T18, `makemigrations --check --dry-run`, `manage.py check` e `git diff --check`
- Resultado: 59 testes executados e aprovados; modelo e migração sincronizados; constraints finais reconhecidas no schema de teste
- Riscos ou pendências: a migração 0044 não foi aplicada ao banco dev compartilhado; cartório ainda aceita `NULL` até T20
- Commit/PR: não criado

### T19 — Impedir novos registros sem cartório

- Estado: CONCLUÍDA
- Data: 2026-07-12
- Responsável/IA: Codex
- Arquivos alterados: `dominial/models/imovel_models.py`, `dominial/forms/imovel_forms.py`, `dominial/tests/test_identidade_documento.py`
- Testes adicionados: CT-07 no formulário e na criação direta pelo modelo
- Comandos executados: suíte focada, regressão conjunta T17/T18, `makemigrations --check --dry-run`, `manage.py check` e `git diff --check`
- Resultado: 61 testes executados e aprovados; cartório copiado corretamente pelo `ModelForm` e novas criações sem cartório bloqueadas pela aplicação
- Riscos ou pendências: `bulk_create` e SQL direto só passam a ser bloqueados pelo banco após a T20
- Commit/PR: não criado

### T20 — Tornar cartório `NOT NULL`

- Estado: CONCLUÍDA
- Data: 2026-07-12
- Responsável/IA: Codex
- Arquivos alterados: `dominial/models/imovel_models.py`, `dominial/migrations/0045_imovel_cartorio_not_null.py`, `dominial/tests/test_migracao_imovel_cartorio_not_null.py`
- Testes adicionados: avanço limpo, bloqueio de legado sem cartório e reversão para schema anulável
- Comandos executados: teste isolado da migração, regressão conjunta T17–T20, `makemigrations --check --dry-run`, `manage.py check` e `git diff --check`
- Resultado: 64 testes executados e aprovados; migração interrompe com IDs explícitos quando encontra `NULL` e o banco rejeita novas ausências após o avanço
- Riscos ou pendências: a migração 0045 não foi aplicada ao banco dev compartilhado; repetir auditoria no ambiente alvo antes de migrar
- Commit/PR: não criado

### T21 — Adicionar modelo `LancamentoOrigem`

- Estado: CONCLUÍDA
- Data: 2026-07-12
- Responsável/IA: Codex
- Arquivos alterados: `dominial/models/lancamento_models.py`, `dominial/models/__init__.py`, `dominial/migrations/0046_lancamento_origem.py`, `dominial/migrations/0047_alter_lancamentoorigem_id.py`, `dominial/tests/test_lancamento_origem_model.py`
- Testes adicionados: múltiplas origens no mesmo lançamento, cartórios distintos, normalização de número e bloqueio de duplicata estrutural
- Comandos executados: suíte focada de `test_lancamento_origem_model` + regressão `test_identidade_documento`, `manage.py check`, `makemigrations --check --dry-run` e `git diff --check`
- Resultado: 59 testes executados e aprovados; modelo estruturado criado; `makemigrations --check --dry-run` sem mudanças; `git diff --check` limpo
- Riscos ou pendências: a tabela nova ainda não foi aplicada ao banco dev compartilhado; a próxima tarefa grava as origens estruturadas
- Commit/PR: não criado
