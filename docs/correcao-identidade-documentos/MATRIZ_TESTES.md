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
| CT-08 | formulário/banco | Mesma identidade completa duas vezes | recusada | sim | PASSOU |
| CT-09 | unidade | `M123` como matrícula | normaliza para `123` | sim | PASSOU |
| CT-10 | unidade | `M 123` como matrícula | normaliza para `123` | sim | PASSOU |
| CT-11 | unidade | `00123` | zeros preservados | sim | PASSOU |
| CT-12 | unidade | prefixo incompatível com tipo | erro explícito | sim | PASSOU |
| CT-13 | serviço | Resolver matrícula 123 do cartório B | retorna somente B | sim | PASSOU |
| CT-14 | serviço | Identidade inexistente | `nao_encontrado` | sim | PASSOU |
| CT-15 | serviço/view | Dados ambíguos ou ID incompatível | não seleciona e informa erro | sim | PASSOU (serviço) |
| CT-16 | tabela/hierarquia | Origem M123 do cartório B | conecta somente B | sim | PASSOU (automático); manual pendente |
| CT-17 | duplicata | M123 existe apenas no cartório A; origem informa B | não acusa duplicata de A | sim | PASSOU (automático) |
| CT-18 | importação/árvore | Cadeias A e B reutilizam números | recursão não cruza cartórios | sim | PASSOU |
| CT-19 | criação | M123 existe em A e nova origem é de B | cria/reutiliza B sem tocar A | sim | PASSOU (automático) |
| CT-20 | início de matrícula | Documento homônimo de A não tem lançamentos; início ocorre em B | cartório de A permanece inalterado | sim | PASSOU (automático) |

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

## Cobertura manual de apresentação

| Item | Resultado esperado | Estado |
|---|---|---|
| Opção de documento mostra tipo e número | identidade legível | NÃO EXECUTADO |
| Mostra nome do cartório | cartório distinguível | NÃO EXECUTADO |
| Mostra cidade/UF | localidades distinguíveis | NÃO EXECUTADO |
| Mostra CNS | cartório identificado de forma estável | NÃO EXECUTADO |
| Mostra imóvel/cadeia | usuário entende o que será reutilizado | NÃO EXECUTADO |
| Prévia informa criar/reutilizar/importar | nenhuma ação implícita | NÃO EXECUTADO |
