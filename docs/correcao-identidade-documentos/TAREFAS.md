# Backlog e acompanhamento

Atualize a coluna **Estado** e a seção **Evidências** ao terminar cada tarefa. Não execute tarefas com dependências incompletas.

## Resumo

| ID  | Entrega pequena                                                | Depende de         | Testes                     | Estado     |
| --- | -------------------------------------------------------------- | ------------------ | -------------------------- | ---------- |
| T01 | Auditar consultas de `Documento` por número                    | —                  | revisão estática           | CONCLUÍDA  |
| T02 | Testes-base da identidade completa                             | —                  | CT-01 a CT-05              | CONCLUÍDA  |
| T03 | Testes do cadastro de imóvel                                   | —                  | CT-06 a CT-08              | CONCLUÍDA  |
| T04 | Função isolada de normalização                                 | T02                | CT-09 a CT-12              | CONCLUÍDA  |
| T05 | Objeto imutável `DocumentoIdentidade`                          | T04                | CT-01 a CT-05              | CONCLUÍDA  |
| T06 | `DocumentoIdentidadeService`                                   | T05                | CT-13 a CT-15              | CONCLUÍDA  |
| T07 | Corrigir origens disponíveis na tabela                         | T06                | CT-16                      | EM REVISÃO |
| T08 | Corrigir verificação inicial de duplicata                      | T06                | CT-17                      | CONCLUÍDA  |
| T09 | Corrigir recursão de documentos importáveis                    | T08                | CT-18                      | CONCLUÍDA  |
| T10 | Corrigir obtenção da cadeia de origem                          | T09                | CT-18                      | CONCLUÍDA  |
| T11 | Corrigir criação automática de origem                          | T06                | CT-19                      | CONCLUÍDA  |
| T12 | Proibir alteração automática de cartório                       | T11                | CT-20                      | CONCLUÍDA  |
| T13 | Corrigir `HierarquiaOrigemService`                             | T06                | CT-16, CT-19               | CONCLUÍDA  |
| T14 | Corrigir identidade nos serviços ativos de árvore              | T13                | CT-18                      | CONCLUÍDA  |
| T15 | Comando somente leitura de auditoria de dados                  | T04                | testes do comando          | CONCLUÍDA  |
| T16 | Verificador de migrações e constraints por ambiente            | T15                | testes do comando          | CONCLUÍDA  |
| T17 | Constraint de Documento: tipo+número+cartório                  | T02, T04, T15      | testes de migração         | CONCLUÍDA  |
| T18 | Constraint do documento principal do Imóvel                    | T03, T15           | testes de migração         | CONCLUÍDA  |
| T19 | Impedir novos registros sem cartório                           | T15                | CT-07                      | CONCLUÍDA  |
| T20 | Tornar cartório `NOT NULL`                                     | T19                | teste de migração          | CONCLUÍDA  |
| T21 | Adicionar modelo `LancamentoOrigem`                            | T17                | testes do modelo           | CONCLUÍDA  |
| R01 | Definir persistência do número canônico                        | T04, T15           | decisão arquitetural       | CONCLUÍDA  |
| R02 | Garantir unicidade canônica de Documento e Imóvel              | R01, T04, T15, T16 | CR-01 a CR-04 + migrações  | CONCLUÍDA  |
| R03 | Resolver o tronco principal pela identidade contextual         | T06, T13           | CR-05                      | CONCLUÍDA  |
| R04 | Usar IDs nas conexões e níveis da árvore                       | T06, T13           | CR-06                      | CONCLUÍDA  |
| R05 | Restaurar livro/folha na criação com múltiplas origens         | T06, T12           | CR-07                      | CONCLUÍDA  |
| R06 | Endurecer resolvedor e modelo de origem estruturada            | R01, T06           | CR-08 e CR-09              | CONCLUÍDA  |
| R07 | Regressão e fechamento das tarefas reabertas                   | R02–R06            | suítes focadas + auditoria | CONCLUÍDA  |
| T22 | Gravar origens estruturadas                                    | R07                | testes de integração       | CONCLUÍDA  |
| T23 | Comando `--dry-run` para migrar origens antigas                | R07                | testes do comando          | CONCLUÍDA  |
| T24 | Consultar origens estruturadas com fallback                    | T22, T23           | CT-17, CT-18               | CONCLUÍDA  |
| T25 | Exibir identidade completa nas opções                          | T08                | teste de template/view     | CONCLUÍDA  |
| T26 | Exigir seleção inequívoca por ID e validar backend             | T25                | CT-15                      | CONCLUÍDA  |
| T27 | Regressão: confirmação de duplicata usa cartório ponta a ponta | T26                | teste de regressão         | CONCLUÍDA  |
| T28 | Auditoria final de buscas por número isolado                   | T07–T27            | revisão estática           | CONCLUÍDA  |
| T29 | Teste integrado de regressão                                   | T07–T27            | suíte CT completa          | CONCLUÍDA  |
| T30 | Roteiro de implantação e rollback                              | T15–T29            | validação documental       | CONCLUÍDA  |

## Ordem de retomada após a revisão de 2026-07-13

1. R01 — concluída; decisão registrada em `DECISAO_PERSISTENCIA_CANONICA.md`.
2. R02 — concluída; campos gerados, constraints, migração e testes registrados.
3. R03 — concluída; o tronco resolve origens no cartório do lançamento.
4. R04 — concluída; arestas, deduplicação, visitados e níveis usam IDs.
5. R05 — concluída; livro e folha individuais são preservados com fallback explícito.
6. R06 — concluída; resolvedor tolera inválidos e `LancamentoOrigem` tem proteção canônica no banco.
7. R07 — concluída; portões e auditoria repetidos, com T03, T11, T14, T17, T18 e T21 novamente concluídas.
8. T22 — concluída; o fluxo funcional mantém escrita textual e estruturada sincronizadas.
9. T23 — concluída; migração histórica conservadora, idempotente e auditável.
10. T24 — concluída; consumidores relacionais usam estrutura com fallback exclusivo para o legado.
11. T25 — concluída; identidade completa exibida e homologada manualmente pelo usuário.
12. T26 — concluída; seleção inequívoca por ID e validação backend homologadas manualmente pelo usuário.
13. T27 — concluída (redefinida como teste de regressão após tentativa de UI descartada; passou sem alteração de código de produção). Próxima tarefa: tratar as duas dívidas técnicas pré-T28, depois T28/T29/T30. T07 continua dependendo também da homologação manual já registrada, separadamente de T25/T26.

As tarefas R01–R07 corrigiram o checkpoint reconstruído e não substituem
T22–T30. Com T22–T27 concluídas, T28 está desbloqueada (após as dívidas técnicas).

## Detalhamento das correções R01–R07

### R01 — Definir persistência do número canônico

- Estado final: CONCLUÍDA.
- Decisão: preservar os valores legados e criar campos canônicos gerados/persistidos pelo banco.
- A mesma expressão cobrirá `Documento.numero`, `Imovel.matricula` e `LancamentoOrigem.numero`; prefixo é apresentação e zeros à esquerda são preservados.
- Constraints usarão os campos gerados, cobrindo também `bulk_create`, `update` e SQL direto.
- Evidência: `DECISAO_PERSISTENCIA_CANONICA.md` e entrada de 2026-07-13 no diário.
- Nenhum modelo, dado ou migração foi alterado nesta tarefa.

### R02 — Garantir unicidade canônica de Documento e Imóvel

- Estado final: CONCLUÍDA.
- Implementação: `Documento.numero_normalizado` e `Imovel.matricula_normalizada` são campos gerados persistidos; as constraints e consultas desses fluxos usam os valores canônicos.
- Migração: `0048_identidade_canonica_gerada` audita dados antes da mudança, interrompe conflitos/inválidos sem reescrever dados e suporta avanço/reversão testados.
- Aceite: CR-01 a CR-04 passaram em PostgreSQL; criação limpa e constraints também foram verificadas em SQLite. A equivalência entre a expressão gerada e a função Python foi testada.
- Escopo adiado conforme a fila: a proteção de `LancamentoOrigem` permanece em R06/CR-09, junto do caminho real de gravação.
- Fechamento associado: T03, T17 e T18 só podem voltar a `CONCLUÍDA` durante R07.

### R03 — Resolver o tronco principal pela identidade contextual

- Estado final: CONCLUÍDA.
- Implementação: o documento atual usa tipo, número canônico, cartório e imóvel; cada origem usa tipo, número normalizado e o `cartorio_origem` do lançamento.
- Escolhas textuais legadas só são aceitas quando correspondem exatamente a uma origem já resolvida contextualmente; sem lançamento, não provocam salto por número.
- Aceite: CR-05 passou com A e B criados em ordens diferentes; a regressão integrada passou com 80 testes.
- Fechamento associado: parte de T14.

### R04 — Usar IDs nas conexões e níveis da árvore

- Estado final: CONCLUÍDA.
- Implementação: `from`/`to`, deduplicação, mapas de níveis e visitados usam IDs; `from_numero`/`to_numero` e `numero` permanecem como rótulos.
- Consumidores atualizados: conversor/renderização D3, organizador hierárquico da view e comandos diagnósticos do serviço ativo.
- Aceite: CR-06 preservou simultaneamente duas origens `M123` de cartórios distintos, suas duas arestas e o nível 1 de ambos os nós; 81 testes integrados passaram e o JavaScript passou na checagem sintática.
- Fechamento associado: parte restante de T14.

### R05 — Restaurar livro/folha na criação com múltiplas origens

- Estado final: CONCLUÍDA.
- Implementação: o mapeamento de cada origem fornece cartório, livro e folha; os valores são normalizados e os campos gerais do lançamento atuam apenas como fallback.
- Regra compartilhada: primeiro lançamento do documento de origem, valor individual informado, valor geral do lançamento e, somente na ausência de todos, `0` na criação.
- Aceite: CR-07 preservou metadados distintos em duas origens/cartórios e um segundo teste aprovou o fallback geral; 83 testes integrados passaram.
- Fechamento associado: T11.

### R06 — Endurecer resolvedor e modelo de origem estruturada

- Estado final: CONCLUÍDA.
- Resolvedor: revalida o texto legado, separa `candidatos_invalidos` e continua retornando o candidato válido sem exceção ou seleção do inválido.
- Modelo/banco: `LancamentoOrigem.numero` é preservado, `numero_normalizado` é gerado/persistido e constraint/índice usam a representação canônica.
- Migração: `0049_lancamento_origem_identidade_canonica` audita inválidos/conflitos, não reescreve dados e possui avanço/reversão testados.
- Aceite: CR-08/CR-09 passaram na gravação ORM disponível antes da T22; 90 testes integrados no PostgreSQL e 9 focados no SQLite passaram.
- Fechamento associado: T21.

### R07 — Regressão e fechamento

- Estado final: CONCLUÍDA.
- Escopo: sem nova funcionalidade; executar portões, auditoria estática e atualizar documentação.
- Aceite: CR-01 a CR-09, CT-08 e CT-18 passaram; 90 testes integrados no PostgreSQL e 9 focados no SQLite passaram; `check`, `makemigrations --check --dry-run`, sintaxe D3 e `git diff --check` ficaram limpos.
- Auditoria: os fluxos ativos reabertos não mantêm resolução ou estruturas relacionais por número isolado; ocorrências restantes são pesquisa/diagnóstico, implementações alternativas inativas ou escopo já reservado a T22/T28.
- Resultado documental: T03, T11, T14, T17, T18 e T21 voltaram a `CONCLUÍDA`, preservando as evidências históricas.
- Ressalva conhecida: a suíte global executou 144 testes e manteve 47 erros e 1 falha legados já reproduzidos antes das correções; fixtures/API antigas e um teste autocontido precisam de saneamento próprio e não foram ocultados como aprovação da suíte completa.
- Pendência independente: T07 continua em revisão até a homologação manual da tabela.

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

### R01–R07 — Correções obrigatórias da revisão

- `M123`, `M 123` e `123`, quando o tipo estruturado é matrícula, não podem coexistir como identidades distintas no mesmo cartório.
- A estratégia escolhida deve valer igualmente para `Documento`, `Imovel` e `LancamentoOrigem` e deve preservar zeros à esquerda.
- A proteção não pode depender apenas de uma auditoria executada antes da migração; novas gravações também devem ser seguras.
- Arestas, deduplicação, visitados e níveis da árvore usam IDs ou identidade completa.
- O tronco resolve cada origem com o cartório do lançamento correspondente.
- Criação de múltiplas origens preserva livro e folha conforme a regra já existente para origem única.
- Um candidato legado inválido é relatado de forma controlada e não derruba a resolução de candidatos válidos.

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

As entradas abaixo preservam o estado declarado quando cada implementação foi
feita. Quando houver divergência, o resumo no início deste arquivo e a revisão
de 2026-07-13 são o estado vigente. Não reescreva evidência histórica; registre
o fechamento atual em R01–R07 e no diário.

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

### T22 — Gravar origens estruturadas

- Estado: CONCLUÍDA
- Data: 2026-07-13
- Responsável/IA: Codex
- Arquivos alterados: `dominial/services/lancamento_origem_service.py`, `dominial/signals.py`, `dominial/tests/test_lancamento_origem_model.py`
- Testes adicionados: dual-write pelo signal real, cartórios e metadados individuais, reprocessamento idempotente, reordenação com IDs preservados, remoção parcial e limpeza total
- Comandos executados: 92 testes integrados no PostgreSQL; 11 testes de modelo/migração no SQLite; suíte global; `manage.py check`; `makemigrations --check --dry-run`; `git diff --check`
- Resultado: escrita estruturada reconciliada em transação sem alterar `Lancamento.origem`; 92/92 e 11/11 passaram; a suíte global cresceu para 146 testes e manteve exatamente os 47 erros e 1 falha legados do baseline
- Riscos ou pendências: leituras ainda usam o texto legado até T24; dados históricos serão tratados somente pelo comando seguro da T23; nenhuma migração foi aplicada ao banco compartilhado
- Commit/PR: não criado

### T23 — Comando `--dry-run` para migrar origens antigas

- Estado: CONCLUÍDA
- Data: 2026-07-13
- Responsável/IA: Codex
- Arquivos alterados: `dominial/management/commands/migrar_origens_estruturadas.py`, `dominial/tests/test_migrar_origens_estruturadas_command.py`
- Testes adicionados: dry-run sem SQL de escrita, conversão inequívoca, preservação do legado/metadados, idempotência, classificação de ambiguidades/inválidos/fim de cadeia/ausência de cartório e rollback do lote
- Comandos executados: 4 testes focados; 96 integrados no PostgreSQL; 15 focados no SQLite; suíte global; `manage.py check`; `makemigrations --check --dry-run`; compilação; `git diff --check`
- Resultado: comando converte apenas uma origem direta com `cartorio_origem` explícito; JSON contém contagens e IDs; 96/96 e 15/15 passaram; suíte global com 150 testes manteve os 47 erros e 1 falha legados
- Riscos ou pendências: múltiplas origens e textos descritivos não são inferidos automaticamente; revisar o relatório de `--dry-run` no ambiente alvo antes da execução real; nenhuma escrita foi feita no banco compartilhado
- Commit/PR: não criado

### T24 — Consultar origens estruturadas com fallback

- Estado: CONCLUÍDA
- Data: 2026-07-13
- Responsável/IA: Codex
- Arquivos alterados: `dominial/services/lancamento_origem_leitura_service.py`, consumidores de duplicata, árvore, cadeia completa, tabela e hierarquia, `dominial/utils/hierarquia_utils.py`, `dominial/tests/test_lancamento_origem_leitura_service.py`
- Testes adicionados: fallback textual sem estrutura e cenário contraditório em que texto aponta A e estrutura aponta B, verificado em importação, cadeia informativa, tronco, árvore, cadeia completa, tabela e hierarquia de origens
- Comandos executados: 69 testes focados; 98 integrados no PostgreSQL; 17 focados no SQLite; suíte global; compilação; `manage.py check`; `makemigrations --check --dry-run`; `git diff --check`
- Resultado: contrato imutável preserva tipo, canônico, cartório, ordem, livro, folha e fonte; estrutura e texto nunca são combinados; 98/98 e 17/17 passaram; suíte global com 152 manteve 47 erros e 1 falha legados
- Riscos ou pendências: campos textuais continuam necessários para apresentação/edição durante a transição; componentes de interface serão tratados em T25–T27; nenhuma migração foi aplicada ao banco compartilhado
- Commit/PR: não criado

### T25 — Exibir identidade completa nas opções

- Estado: CONCLUÍDA
- Data: 2026-07-14
- Responsável/IA: Claude Code (plano revisado por Codex)
- Arquivos alterados: `dominial/services/lancamento_duplicata_service.py`, `templates/dominial/duplicata_importacao.html`, `templates/dominial/selecionar_documento_lancamento.html`, `dominial/tests/test_t25_identidade_opcoes.py`
- Testes adicionados: DTO de origem/cadeia/importáveis com identidade completa; distinção de homônimos `M123` em cartórios distintos; preservação dos campos existentes do contrato; view de seleção exibindo tipo correto da FK, CNS e localidade; view distinguindo homônimos na mesma tela
- Decisões: T25 cobre as duas telas de opções (duplicata/importação e seleção de documento); o DTO é aditivo e preserva IDs/URLs/campos existentes; o contrato de seleção permanece intocado (T26); nenhuma migração; corrigido `documento.get_tipo_display` → `documento.tipo.get_tipo_display`
- Comandos executados: `test_t25_identidade_opcoes` (7/7); `test_identidade_documento` (67/67); `test_fase2_duplicata_integracao` (12 erros preexistentes em `setUp` por `descricao` removido); `manage.py check` (OK); `makemigrations --check --dry-run` (sem mudanças); `git diff --check` (limpo); `dominial.tests` global (159 testes, 47 erros + 1 falha legados, baseline inalterado)
- Resultado: 7/7 novos passaram; canônica 67/67; baseline global mantido; nenhum teste removido ou afrouxado
- Revisão do usuário: roteiro manual de homologação (seleção de documento e tela de duplicata com homônimos M123 em cartórios A/B) executado localmente em 2026-07-14; usuário confirmou funcionamento correto. Fechamento formal desta entrada.
- Riscos ou pendências: dois caminhos ativos de criação automática por contexto incompleto foram registrados como dívida (ver seção abaixo) e devem ser tratados antes de T28/T29; nenhuma migração aplicada ao banco compartilhado; homologação manual da T07 (cross-cartorio no servidor de teste, com dados reais) continua pendente separadamente
- Commit/PR: não criado

### T26 — Exigir seleção inequívoca por ID e validar backend

- Estado: CONCLUÍDA
- Data: 2026-07-14
- Responsável/IA: Claude Code
- Arquivos alterados: `dominial/views/lancamento_views.py`, `templates/dominial/selecionar_documento_lancamento.html`, `dominial/services/lancamento_duplicata_service.py`, `dominial/tests/test_t26_selecao_inequivoca.py`
- Testes adicionados: `documento_id` de outro imóvel recusado (404) e do próprio imóvel aceito; importação de duplicata aceita quando `documento_origem_id`/`documentos_importaveis[]` conferem com a duplicata recalculada; documento fora da cadeia recusado mesmo existindo no banco; `documento_origem_id` incompatível com a origem/cartório informados recusado; importação sem origem/cartório preservados recusada
- Decisões: `novo_lancamento_documento` passou a usar `get_object_or_404(Documento, id=documento_id, imovel=imovel)`; o botão de "Novo Lançamento" na seleção de documento usa essa URL com `documento_id` explícito em vez de depender do primeiro documento do imóvel; a importação de duplicata reprocessa `origem_completa[]`/`cartorio_origem[]` (campos ocultos já preservados no template) pelo mesmo `DuplicataVerificacaoService.verificar_duplicata_origem` usado na detecção original e só aceita `documento_origem_id`/`documentos_importaveis[]` que batam exatamente com o resultado recalculado; nenhuma migração
- Comandos executados: `test_t26_selecao_inequivoca` (6/6); `test_t25_identidade_opcoes` (7/7); `test_identidade_documento` (67/67); `manage.py check` (OK); `makemigrations --check --dry-run` (sem mudanças); `git diff --check` (limpo); `dominial.tests` global (165 testes, 47 erros + 1 falha legados, baseline inalterado)
- Resultado: 6/6 novos testes passaram; baseline global mantido; nenhum teste removido ou afrouxado
- Revisão do usuário: mesma sessão de homologação manual local de T25 (botão de novo lançamento por `documento_id`, importação de duplicata) confirmada pelo usuário em 2026-07-14. Fechamento formal desta entrada.
- Riscos ou pendências: `test_fase2_duplicata_integracao` continua com 12 erros pré-existentes no `setUp` (campo `descricao` removido de `DocumentoTipo`), já registrados no baseline; não foi possível reutilizar esse arquivo para exercitar T26, coberto pelo novo módulo de teste; nenhuma migração aplicada ao banco compartilhado
- Commit/PR: não criado

### T27 — histórico: tentativa descartada, depois redefinida

**Tentativa descartada (2026-07-14, tarde).** Implementação original interpretou o título do backlog ("Prévia: criar, reutilizar ou importar") como uma funcionalidade nova de UI — bloco CRIAR/IMPORTAR/REUTILIZAR em `duplicata_importacao.html`, com classificação de "já importado" via `DocumentoImportado`. O usuário apontou, antes mesmo de testar, que isso partia de uma compreensão errada do escopo: o fluxo de detectar duplicata → avisar → confirmar → importar cadeia + gerar aresta + recalcular hierarquia **já existe no baseline** (`ImportacaoCadeiaService`, migração 0031, `duplicata_importacao.html`), é anterior a esta branch, e esta branch (`feature/identidade-documento-cartorio`) deve se limitar a corrigir a identidade por cartório nesse fluxo — não inventar uma prévia nova. Consulta ao Codex confirmou: (1) a entrada T27 do backlog não tinha critério funcional correspondente, foi especificada sem base verificável; (2) o comportamento que o usuário descreve já está coberto, inclusive quanto ao cartório, por `duplicata_verificacao_service.py` (T08), `lancamento_duplicata_service.py` (T26), `lancamento_origem_service.py` (T22) e `hierarquia_arvore_service.py` (R04/T14); (3) recomendação: descartar integralmente a implementação. Os arquivos alterados (`dominial/services/lancamento_duplicata_service.py`, `dominial/views/lancamento_views.py`, `templates/dominial/duplicata_importacao.html`) foram revertidos via `git checkout --` para o estado de T26, e `dominial/tests/test_t27_previa_duplicata.py` foi removido. Nenhum código dessa tentativa permanece.

**Redefinição (2026-07-14, tarde), seguindo a recomendação do Codex:** T27 passa a ser um teste de regressão do fluxo pós-confirmação já existente, não uma nova interface. Critério de aceite: criar dois documentos homônimos em cartórios diferentes; confirmar a duplicata do cartório escolhido; verificar que o lançamento e seu `LancamentoOrigem` guardam o cartório correto; reconstruir a árvore; afirmar que a aresta aponta, por ID, para o documento do cartório correto; afirmar os níveis recalculados; afirmar que o homônimo do outro cartório não aparece. Se esse teste passar sem exigir mudança de código (que é o esperado, já que R03/R04/T14/T26 já cobrem esse caminho), T27 é encerrada sem alteração funcional — apenas com o teste de regressão registrado.

**Fechamento (2026-07-14, tarde).** Teste `test_t27_regressao_cartorio_duplicata.py` implementado seguindo exatamente o critério acima: dois documentos M123 homônimos (cartório A e B); confirmação da duplicata do cartório A via `LancamentoDuplicataService.processar_importacao_duplicata`; criação do lançamento original via `LancamentoCriacaoService.criar_lancamento_completo` (`apos_importacao=true`, mesmo caminho de `duplicata_views.importar_duplicata`); reconstrução da árvore via `HierarquiaArvoreService.construir_arvore_cadeia_dominial`. **Passou na primeira execução, sem qualquer mudança em código de produção**, confirmando a previsão do Codex: `LancamentoOrigem` estruturado grava `cartorio_id` e `numero_normalizado` corretos; a aresta reconstruída liga o documento ativo ao documento do cartório A por ID; o homônimo do cartório B não aparece nem como aresta nem como nó; o nível do nó importado é 1.

- Estado: CONCLUÍDA
- Data: 2026-07-14
- Responsável/IA: Claude Code (redefinição por recomendação do Codex; execução confirma diagnóstico)
- Arquivos alterados: `dominial/tests/test_t27_regressao_cartorio_duplicata.py` (novo); nenhum arquivo de produção.
- Testes adicionados: 1 teste de regressão ponta a ponta (confirmação de duplicata → `LancamentoOrigem` → aresta/nível da árvore), cobrindo a distinção de homônimos por cartório em todo o caminho pós-confirmação.
- Comandos executados: `test_t27_regressao_cartorio_duplicata` isolado (1/1); combinado com `test_t26_selecao_inequivoca` + `test_t25_identidade_opcoes` + `test_identidade_documento` (81/81); `manage.py check` (OK); `makemigrations --check --dry-run` (sem mudanças); `git diff --check` (limpo); `dominial.tests` global (166 testes, 47 erros + 1 falha legados, baseline inalterado, +1 novo de T27)
- Resultado: teste passou de primeira, sem alteração de código de produção — confirma que R03/R04/T14/T22/T26 já cobrem a identidade de cartório ponta a ponta no fluxo de confirmação de duplicata legado
- Riscos ou pendências: nenhuma nova; as duas dívidas técnicas pré-T28 continuam pendentes
- Commit/PR: não criado

## Dívidas identificadas (pré-T28) — CORRIGIDAS em 2026-07-14

Encontradas na revisão de 2026-07-14 (Codex, verificadas no código). Contradiziam o objetivo “homônimos nunca confundidos”.

1. **Criação automática com cartório arbitrário na árvore — CORRIGIDO**
   - `dominial/services/hierarquia_arvore_service.py:237` — `_criar_documento_automatico()` criava documento com `Cartorios.objects.first()` quando uma origem não resolve.
   - `dominial/views/cadeia_dominial_views.py:64` — a view `cadeia_dominial_arvore` chama `construir_arvore_cadeia_dominial(imovel, criar_documentos_automaticos=True)`, acionando o caminho acima ao renderizar a árvore D3 (write-on-read).
   - Fix: `_criar_documento_automatico` passou a receber `cartorio` como parâmetro explícito (o `origem.cartorio` do chamador, o mesmo já usado por `_resolver_documento_por_codigo`); sem cartório, retorna `None` em vez de `Cartorios.objects.first()`. Achado curioso durante a correção: existe um arquivo `hierarquia_arvore_service_backup.py`, não importado por nada no projeto (código morto), que já tinha essa mesma correção aplicada uma vez — reforça que esse é o padrão correto já estabelecido em outras partes do código (`lancamento_origem_service.py`, `hierarquia_origem_service.py`).
   - Teste: `dominial/tests/test_divida_cartorio_arbitrario_arvore.py` (2/2) — usa `bulk_create` para contornar o sinal de criação automática já correto (T11/T12) e isolar o caminho de fallback sob teste; usa dois cartórios em ordem de criação tal que `Cartorios.objects.first()` devolveria o cartório errado se o bug persistisse.
2. **Criação automática via view com busca por número isolado — CORRIGIDO**
   - `dominial/views/documento_views.py:199` — `criar_documento_automatico` verificava existência por `imovel + numero` bruto, sem tipo/cartório canônicos, e tinha os mesmos dois fallbacks para `Cartorios.objects.first()`.
   - Fix: existência agora verificada por tipo + número normalizado (`normalizar_numero_documento`); os dois fallbacks para `Cartorios.objects.first()` foram removidos — sem cartório resolvível pelo contexto (matrícula do imóvel ou lançamento com `cartorio_origem`), a criação é recusada com mensagem de erro, nunca adivinha um cartório.
   - Achado: esta view não está referenciada em nenhum template/JS ativo (nem a URL nomeada `criar_documento_automatico`, nem o path `criar-documento/` aparecem em `templates/` ou `static/`) — é um endpoint morto do ponto de vista de uso real, só alcançável por URL direta. Corrigido mesmo assim porque a rota nomeada permanece registrada e pode ser usada manualmente ou por integrações futuras; não foi removida (decisão: corrigir a resolução, não remover o caminho automático).
   - Teste: `dominial/tests/test_divida_criar_documento_automatico_view.py` (3/3).
3. **Autorização de edição de lançamento por número isolado — encontrado na auditoria T28, CORRIGIDO**
   - `dominial/views/lancamento_views.py` (`editar_lancamento`) — a checagem "direta" de que um documento de outro imóvel é legitimamente referenciado como origem desta cadeia usava `origem__icontains=lancamento.documento.numero`: um match textual de número, sem checar cartório. Um homônimo (mesmo número, cartório diferente, não referenciado de fato) passava só por coincidência de texto, autorizando edição indevida de um lançamento que não pertence à cadeia do imóvel — achado durante a auditoria estática de T28, não estava no checkpoint original de dívidas.
   - Fix: a checagem agora usa `LancamentoOrigemLeituraService.obter_origens` (já usado em `hierarquia_arvore_service.py` e outros serviços) e compara tipo + número normalizado + cartório de cada origem do imóvel contra a identidade completa do documento do lançamento a editar.
   - Teste: `dominial/tests/test_divida_edicao_lancamento_homonimo.py` (2/2) — homônimo em cartório diferente não referenciado é recusado (antes seria aceito); documento realmente referenciado continua aceito.

Suíte combinada (T25+T26+T27+identidade canônica+as três correções): 88/88. Suíte global: 173 testes, 47 erros + 1 falha legados (baseline inalterado). `manage.py check`, `makemigrations --check --dry-run` e `git diff --check` limpos. Nenhuma migração envolvida em nenhuma das três correções.

## T28 — Auditoria final de buscas por número isolado

- Estado: CONCLUÍDA
- Data: 2026-07-14
- Responsável/IA: Claude Code
- Método: repetição do tipo de busca estática já feita em T01/R07 (`grep` por `.filter(numero=`, `.get(numero=`, `origem__icontains`, `Q(numero=`, `.filter(matricula=`) sobre `dominial/services/`, `dominial/views/`, `dominial/utils/`, `dominial/admin.py` e `dominial/management/commands/`, excluindo testes e migrações, classificando cada ocorrência.
- Achados classificados:
  1. **Corrigidos nesta sessão** (itens 1–3 acima): `hierarquia_arvore_service.py`, `documento_views.py`, `lancamento_views.py` (`editar_lancamento`).
  2. **Implementações alternativas inativas (código morto, não importado por nada):** `dominial/services/hierarquia_arvore_service_backup.py`, `hierarquia_arvore_service_corrigido.py`, `documento_service_consolidado.py`. Confirmado por busca: nenhum arquivo do projeto importa desses três.
  3. **Diagnóstico usado apenas por script isolado:** `dominial/services/hierarquia_arvore_service_melhorado.py`, importado só por `dominial/management/commands/testar_conexao_t1004_t2822.py` — comando de investigação hardcoded para documentos específicos (T1004/T2822), não faz parte do fluxo do usuário.
  4. **Comandos de management somente-diagnóstico** (nomes começam com `investigar_`/`verificar_`/`testar_`): `investigar_documentos_duplicados.py`, `verificar_documentos.py`, `investigar_conexoes_incorretas.py`, `verificar_matricula_constraint.py`, `verificar_cartorios_documentos.py` — leem e reportam, não alimentam resolução de relacionamento de negócio (árvore, duplicata, importação).
  5. **Pesquisa textual administrativa, não relacionamento de negócio:** `dominial/admin.py` — `NumeroDocumentoFilter` (filtro de lista) e a ação `investigar_duplicatas` reportam documentos com o mesmo número (inclusive entre cartórios diferentes, o que é esperado/legítimo neste domínio) para o staff investigar manualmente; não resolvem nem confundem identidades automaticamente.
  6. **Campo não relacionado à identidade documental:** `numero_lancamento` em `lancamento_service.py`/`lancamento_validacao_service.py` é a numeração interna do lançamento dentro do seu próprio documento (conceito diferente de tipo+número+cartório do `Documento`), fora do escopo desta auditoria.
  7. **Fallback já seguro, dentro do mesmo imóvel:** `hierarquia_arvore_service.py:75` (`_identificar_documento_principal`) usa `Documento.objects.filter(imovel=imovel).first()` só como último recurso, depois de tentar a identidade canônica completa, e já escopado a um único imóvel (não atravessa cartórios/imóveis) — comportamento testado desde antes desta branch (`test_identificar_documento_principal_fallback_to_oldest`), não é uma confusão de homônimos.
- Resultado: nenhum fluxo ativo de negócio (árvore, duplicata/importação, autorização de edição) resolve ou autoriza mais por número isolado. As ocorrências restantes são código morto, diagnóstico manual, pesquisa administrativa ou já devidamente escopadas.
- Riscos ou pendências: os arquivos de código morto (`_backup`, `_corrigido`, `_melhorado`, `documento_service_consolidado.py`) não foram removidos nesta tarefa — é uma decisão de limpeza separada, fora do escopo de correção de identidade; considerar removê-los em uma tarefa de housekeeping futura.
- Commit/PR: não criado

## T29 — Teste integrado de regressão

- Estado: CONCLUÍDA
- Data: 2026-07-14
- Responsável/IA: Claude Code
- Comandos executados:
  - Suíte global `dominial.tests` (todo o app, sem filtro): **173 testes, 47 erros + 1 falha** — exatamente o baseline legado já documentado desde antes de T22, sem nenhuma quebra nova introduzida por T25–T28.
  - Suíte focada combinada (identidade canônica + migrações de identidade + `LancamentoOrigem` + leitura de origem + comando de migração histórica + T25/T26/T27/dívidas pré-T28): **116/116 testes, todos passando** — `test_identidade_documento`, `test_t25_identidade_opcoes`, `test_t26_selecao_inequivoca`, `test_t27_regressao_cartorio_duplicata`, `test_divida_cartorio_arbitrario_arvore`, `test_divida_criar_documento_automatico_view`, `test_divida_edicao_lancamento_homonimo`, `test_migracao_identidade_documento`, `test_migracao_identidade_imovel`, `test_migracao_identidade_canonica`, `test_migracao_lancamento_origem_canonica`, `test_lancamento_origem_model`, `test_lancamento_origem_leitura_service`, `test_migrar_origens_estruturadas_command`.
  - `manage.py check`: OK. `makemigrations --check --dry-run`: sem mudanças. `git diff --check`: limpo.
- Resultado: o baseline legado de 47 erros + 1 falha é o mesmo desde antes de T22 (pré-existente, não causado por este trabalho); todo o código novo/alterado por T25–T28 está coberto e verde. Nenhuma migração pendente ou desconhecida.
- Riscos ou pendências: o baseline legado (47 erros + 1 falha) não foi saneado nesta tarefa — são fixtures/API antigas e um teste autocontido que precisam de manutenção própria, fora do escopo desta correção de identidade (já registrado em sessões anteriores, ex.: `test_fase2_duplicata_integracao` com 12 erros por `DocumentoTipo.descricao` removido).
- Commit/PR: não criado

## T30 — Roteiro de implantação e rollback

- Estado: CONCLUÍDA
- Data: 2026-07-14
- Responsável/IA: Claude Code
- Entregável: `docs/correcao-identidade-documentos/ROTEIRO_IMPLANTACAO.md` — cobre escopo do deploy (migrações 0043–0049 + T25–T29), estado conhecido do servidor de teste (branch atual, config local não commitada, containers), backup do banco, preservação de config local (`git stash`), troca de branch, subida controlada com acompanhamento de migração, verificação pós-deploy (estrutural via `verificar_estrutura_ambiente`/`auditar_identidade_documentos` + funcional + homologação de T25/T26/T07 com dados reais), e rollback de código/migração/dado.
- Decisões: roteiro cobre só o servidor de teste, não produção/merge para `main` — decisão explicitamente fora de escopo, registrada no próprio documento. A execução real do roteiro (deploy efetivo) permanece separada, pendente de autorização explícita do usuário a cada etapa arriscada (push da branch, backup/restore, restart do container).
- Riscos ou pendências: a auditoria automatizada só cobre `Documento` (comando `auditar_identidade_documentos`); `Imovel`/`LancamentoOrigem` contam apenas com a auditoria embutida nas próprias migrações 0048/0049 (que abortam sem reescrever dados em caso de conflito, mas não têm um relatório prévio dedicado como o de `Documento`).
- Commit/PR: não criado
