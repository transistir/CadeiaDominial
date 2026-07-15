# Matriz de testes obrigatórios

Estados: `NÃO EXECUTADO`, `PASSOU`, `FALHOU`, `BLOQUEADO`.

| ID | Nível | Cenário | Resultado obrigatório | Automatizar | Estado |
|---|---|---|---|---|---|
| CT-01 | unidade | Matrícula 123 nos cartórios A e B | identidades diferentes | sim | PASSOU |
| CT-02 | unidade | Matrícula e transcrição 123 no cartório A | identidades diferentes | sim | PASSOU |
| CT-03 | unidade | Mesmo tipo, número e cartório | identidades iguais | sim | PASSOU |
| CT-04 | unidade | Ordem diferente de criação | resolução não muda | sim | PASSOU |
| CT-05 | unidade | Consulta sem tipo ou cartório | erro/estado incompleto; nunca `.first()` | sim | PASSOU |
| CT-06 | formulário | Mesmo número em cartórios diferentes | cadastro aceito | sim | PASSOU |
| CT-07 | formulário | Cadastro sem cartório | recusado claramente | sim | PASSOU |
| CT-08 | formulário/banco | Mesma identidade completa duas vezes, inclusive variantes `M123`/`123` | recusada | sim | PASSOU |
| CT-09 | unidade | `M123` como matrícula | normaliza para `123` | sim | PASSOU |
| CT-10 | unidade | `M 123` como matrícula | normaliza para `123` | sim | PASSOU |
| CT-11 | unidade | `00123` | zeros preservados | sim | PASSOU |
| CT-12 | unidade | prefixo incompatível com tipo | erro explícito | sim | PASSOU |
| CT-13 | serviço | Resolver matrícula 123 do cartório B | retorna somente B | sim | PASSOU |
| CT-14 | serviço | Identidade inexistente | `nao_encontrado` | sim | PASSOU |
| CT-15 | serviço/view | Dados ambíguos ou ID incompatível | não seleciona e informa erro | sim | PASSOU (serviço) |
| CT-16 | tabela/hierarquia | Origem M123 do cartório B | conecta somente B | sim | PASSOU (automático); manual pendente |
| CT-17 | duplicata | M123 existe apenas no cartório A; origem informa B | não acusa duplicata de A | sim | PASSOU (automático) |
| CT-18 | importação/árvore | Cadeias A e B reutilizam números | recursão, arestas e níveis não cruzam cartórios | sim | PASSOU |
| CT-19 | criação | M123 existe em A e nova origem é de B | cria/reutiliza B sem tocar A | sim | PASSOU (automático) |
| CT-20 | início de matrícula | Documento homônimo de A não tem lançamentos; início ocorre em B | cartório de A permanece inalterado | sim | PASSOU (automático) |

## Casos corretivos da revisão de 2026-07-13

| ID | Nível | Cenário | Resultado obrigatório | Automatizar | Estado |
|---|---|---|---|---|---|
| CR-01 | modelo/banco | Documento matrícula `M123` e `123` no mesmo cartório | segunda identidade recusada | sim | PASSOU |
| CR-02 | formulário/banco | Imóvel matrícula `M 123` quando `123` já existe no mesmo cartório | formulário e banco recusam | sim | PASSOU |
| CR-03 | modelo/banco | `00123` e `123` | permanecem identidades diferentes | sim | PASSOU |
| CR-04 | migração | dados legados possuem variantes canônicas conflitantes | migração para sem escolher correção | sim | PASSOU |
| CR-05 | serviço | imóvel atual contém homônimo A e origem aponta homônimo B importado | tronco segue B | sim | PASSOU |
| CR-06 | árvore | dois nós com mesmo número e cartórios diferentes aparecem simultaneamente | IDs, arestas e níveis permanecem distintos | sim | PASSOU |
| CR-07 | criação | múltiplas origens têm livro/folha informados | documentos criados preservam metadados | sim | PASSOU |
| CR-08 | serviço | candidato legado inválido existe junto de candidato válido | resultado controlado, sem exceção não tratada | sim | PASSOU |
| CR-09 | modelo/banco | `LancamentoOrigem` é gravada diretamente pelo ORM, sem `full_clean()` | legado preservado, canônico gerado e duplicata equivalente recusada | sim | PASSOU |

## Execuções

Adicione uma linha por execução. Não sobrescreva históricos anteriores.

| Data/hora | Ambiente | Revisão/commit | Escopo | Comando ou procedimento | Resultado | Responsável | Evidência/observação |
|---|---|---|---|---|---|---|---|
| 2026-07-11 10:46 | Docker Compose dev/PostgreSQL | árvore local | CT-01 a CT-04, CT-06 e CT-08 | `manage.py test dominial.tests.test_identidade_documento` | 7 passaram; 1 falha esperada | Codex | CT-02 bloqueada pela constraint atual `(numero, cartorio)` |
| 2026-07-11 10:50 | Docker Compose dev/PostgreSQL | árvore local | CT-09 a CT-12 e regressão | `manage.py test dominial.tests.test_identidade_documento` | 16 passaram; 1 falha esperada | Codex | normalização isolada, sem mudança de tela |
| 2026-07-11 10:54 | Docker Compose dev/PostgreSQL | árvore local | T05 e regressão | `manage.py test dominial.tests.test_identidade_documento` | 23 passaram; 1 falha esperada | Codex | objeto imutável e CT-05 aprovados |
| 2026-07-11 10:59 | Docker Compose dev/PostgreSQL | árvore local | CT-13 a CT-15 e regressão | `manage.py test dominial.tests.test_identidade_documento` | 29 passaram; 1 falha esperada | Codex | resolvedor nunca escolhe candidato ambíguo |
| 2026-07-11 11:09 | Docker Compose dev/PostgreSQL | árvore local | CT-16 e regressão | `manage.py test dominial.tests.test_identidade_documento` | 34 passaram; 1 falha esperada | Codex | tabela resolveu e expandiu somente pelo cartório da origem |
| 2026-07-12 12:56 | Docker Compose dev/PostgreSQL | árvore local | CT-17 e regressão | `manage.py test dominial.tests.test_identidade_documento --noinput` | 36 passaram; 1 falha esperada | Codex | duplicata inicial usa tipo, número normalizado e cartório; suíte legada bloqueada no `setUp` preexistente |
| 2026-07-12 13:00 | Docker Compose dev/PostgreSQL | árvore local | CT-18/T09 e regressão | `manage.py test dominial.tests.test_identidade_documento --noinput` | 37 passaram; 1 falha esperada | Codex | cálculo recursivo de importáveis respeita o cartório de cada lançamento |
| 2026-07-12 13:02 | Docker Compose dev/PostgreSQL | árvore local | CT-18/T10 e regressão | `manage.py test dominial.tests.test_identidade_documento --noinput` | 38 passaram; 1 falha esperada | Codex | cadeia informativa completa respeita o cartório de cada lançamento |
| 2026-07-12 13:06 | Docker Compose dev/PostgreSQL | árvore local | CT-19/T11 e regressão | `manage.py test dominial.tests.test_identidade_documento --noinput` | 40 passaram; 1 falha esperada | Codex | criação/reutilização em B não altera o homônimo de A |
| 2026-07-12 13:20 | Docker Compose dev/PostgreSQL | árvore local | CT-20/T12 e regressão | `manage.py test dominial.tests.test_identidade_documento --noinput` | 41 passaram; 1 falha esperada | Codex | início em B preserva cartório e observações do homônimo sem lançamentos em A |
| 2026-07-12 13:22 | Docker Compose dev/PostgreSQL | árvore local | CT-16/CT-19/T13 e regressão | `manage.py test dominial.tests.test_identidade_documento --noinput` | 43 passaram; 1 falha esperada | Codex | hierarquia de origens usa tipo, número normalizado e cartório do lançamento |
| 2026-07-12 13:35 | Docker Compose dev/PostgreSQL | árvore local + banco dev somente leitura | CT-18/T14 e regressão | suíte focada, `check`, auditoria e imóvel 5 | 47 passaram; 1 falha esperada; tronco real terminou em M9442/Amambai | Codex | árvore, cadeia completa, importados e tronco usam identidade completa e IDs processados |
| 2026-07-12 13:41 | Docker Compose dev/PostgreSQL | árvore local + banco dev somente leitura | T15 e regressão | suíte focada e `auditar_identidade_documentos --json` | 50 passaram; 1 falha esperada; 1.220 documentos sem impedimentos | Codex | comando não executa SQL de escrita e pode falhar com segurança via `--fail-on-conflict` |
| 2026-07-12 14:30 | Docker Compose dev/PostgreSQL | árvore local + banco dev somente leitura | T16 e regressão | suíte focada e `verificar_estrutura_ambiente --json` | 52 passaram; 1 falha esperada; sem migrações pendentes/desconhecidas | Codex | constraints finais ausentes como esperado antes de T17/T18 |
| 2026-07-12 14:47 | Docker Compose dev/PostgreSQL | banco de teste temporário | T17, CT-02 e regressão | suíte de identidade + testes de migração | 56 passaram | Codex | avanço, conflito, constraint e reversão segura validados; 0043 não aplicada ao banco dev compartilhado |
| 2026-07-12 15:10 | Docker Compose dev/PostgreSQL | banco de teste temporário | T18 e regressão T17 | suíte de identidade + duas suítes de migração | 59 passaram | Codex | identidade do imóvel inclui tipo; `--expect-final` aprovado no schema completo; 0044 não aplicada ao banco dev |
| 2026-07-12 15:15 | Docker Compose dev/PostgreSQL | banco de teste temporário | T19/CT-07 e regressão | suíte de identidade + migrações T17/T18 | 61 passaram | Codex | formulário e modelo impedem nova criação sem cartório |
| 2026-07-12 16:33 | Docker Compose dev/PostgreSQL | banco de teste temporário | T20 e regressão T17–T20 | suíte de identidade + três suítes de migração | 64 passaram | Codex | NOT NULL auditado, aplicado e revertido em testes; 0043–0045 não aplicadas ao banco dev |
| 2026-07-13 | Docker Compose dev/PostgreSQL | `0ff36d3` | revisão do checkpoint | 59 testes focados; 9 de migração; `check`; `makemigrations`; suíte completa | focados/migrações passaram; completa com 47 erros e 1 falha legados | Codex | revisão estática reabriu CT-08 e CT-18; detalhes em `REVISAO_GERAL_2026-07-13.md` |
| 2026-07-13 | Docker Compose dev/PostgreSQL + SQLite 3.40.1 | árvore local após `0ff36d3` | R02, CR-01 a CR-04 e regressão de migrações | 77 testes integrados; schema limpo e 13 testes SQLite; `check`; `makemigrations`; `git diff --check` | PASSOU | Codex | campos gerados equivalem ao normalizador; conflitos bloqueiam a migração sem reescrita; banco dev compartilhado não foi migrado |
| 2026-07-13 | Docker Compose dev/PostgreSQL | árvore local após R02 | R03, CR-05 e regressão integrada | 80 testes de identidade, origem e migrações | PASSOU | Codex | tronco seguiu B com ordens de criação distintas e escolha textual contextual; arestas/níveis continuam para R04 |
| 2026-07-13 | Docker Compose dev/PostgreSQL + Node.js local | árvore local após R03 | R04, CR-06, regressão e sintaxe D3 | 81 testes integrados; `node --check`; compilação Python | PASSOU | Codex | IDs em arestas, deduplicação, visitados e níveis; números mantidos somente como rótulos |
| 2026-07-13 | Docker Compose dev/PostgreSQL | árvore local após R04 | R05, CR-07 e regressão integrada | 83 testes de identidade, origem e migrações | PASSOU | Codex | metadados individuais preservados e fallback geral aprovado; `0` reservado à ausência real |
| 2026-07-13 | Docker Compose dev/PostgreSQL + SQLite 3.40.1 | árvore local após R05 | R06, CR-08/CR-09, migração 0049 e regressão | 90 testes integrados PostgreSQL; 9 focados SQLite | PASSOU | Codex | inválidos relatados separadamente; valor legado preservado; constraint canônica cobre gravação direta |
| 2026-07-13 | Docker Compose dev/PostgreSQL + SQLite 3.40.1 + Node.js local | árvore local após R06 | R07, CR-01 a CR-09, CT-08/CT-18 e portões finais | 90 integrados PostgreSQL; 9 focados SQLite; suíte global com 144; `check`; `makemigrations`; sintaxe D3; diff | ESCOPO PASSOU; global manteve 47 erros e 1 falha legados | Codex | tarefas reabertas fechadas; falhas globais têm a mesma contagem do baseline e permanecem como débito explícito |
| 2026-07-13 | Docker Compose dev/PostgreSQL + SQLite 3.40.1 | árvore local após R07 | T22, escrita dupla e regressão | 92 integrados PostgreSQL; 11 focados SQLite; suíte global com 146; `check`; `makemigrations`; diff | ESCOPO PASSOU; global manteve 47 erros e 1 falha legados | Codex | signal real cria, atualiza, reordena e limpa origens estruturadas sem alterar o texto legado |
| 2026-07-13 | Docker Compose dev/PostgreSQL + SQLite 3.40.1 | árvore local após T22 | T23, migração histórica e regressão | 4 focados; 96 integrados PostgreSQL; 15 focados SQLite; suíte global com 150; checks | ESCOPO PASSOU; global manteve 47 erros e 1 falha legados | Codex | dry-run sem escrita, relatório por IDs, idempotência, ambiguidades preservadas e rollback integral aprovados |
| 2026-07-13 | Docker Compose dev/PostgreSQL + SQLite 3.40.1 | árvore local após T23 | T24, leitura estruturada/fallback e regressão | 69 focados; 98 integrados PostgreSQL; 17 focados SQLite; suíte global com 152; checks | ESCOPO PASSOU; global manteve 47 erros e 1 falha legados | Codex | estrutura B prevaleceu sobre texto A em todos os consumidores relacionais; fallback legado isolado também passou |

## Cobertura manual de apresentação

| Item | Resultado esperado | Estado |
|---|---|---|
| Opção de documento mostra tipo e número | identidade legível | NÃO EXECUTADO |
| Mostra nome do cartório | cartório distinguível | NÃO EXECUTADO |
| Mostra cidade/UF | localidades distinguíveis | NÃO EXECUTADO |
| Mostra CNS | cartório identificado de forma estável | NÃO EXECUTADO |
| Mostra imóvel/cadeia | usuário entende o que será reutilizado | NÃO EXECUTADO |
| Prévia informa criar/reutilizar/importar | nenhuma ação implícita | NÃO EXECUTADO |
