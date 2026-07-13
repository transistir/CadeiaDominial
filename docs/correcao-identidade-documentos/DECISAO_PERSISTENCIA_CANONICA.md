# R01 — Decisão de persistência do número canônico

Data: 2026-07-13. Estado: IMPLEMENTADA EM DOCUMENTO/IMÓVEL NA R02 E LANCAMENTOORIGEM NA R06.

Premissa verificada no contêiner dev: Django 5.2.3 expõe `GeneratedField` e o
SQLite disponível é 3.40.1. O ambiente Docker principal usa PostgreSQL 15. A
expressão concreta e as migrações foram provadas nos dois backends na R02 para
`Documento`/`Imovel` e na R06 para `LancamentoOrigem`.

## Decisão

Preservar os campos legados digitados e adicionar uma representação canônica
gerada pelo banco:

| Modelo | Valor legado preservado | Campo canônico planejado |
|---|---|---|
| `Documento` | `numero` | `numero_normalizado` |
| `Imovel` | `matricula` | `matricula_normalizada` |
| `LancamentoOrigem` | `numero` | `numero_normalizado` |

Os campos canônicos serão colunas geradas/persistidas (`GeneratedField` com
`db_persist=True`) a partir apenas do campo textual da própria linha. As
constraints de identidade passarão a usar o campo canônico:

```text
Documento: tipo + numero_normalizado + cartorio
Imovel: tipo_documento_principal + matricula_normalizada + cartorio
LancamentoOrigem: lancamento + tipo_documento + numero_normalizado + cartorio
```

## Regra da expressão canônica

1. Remover espaços externos.
2. Se o primeiro caractere for `M` ou `T`, sem diferenciar maiúscula/minúscula, removê-lo como prefixo de apresentação.
3. Remover os espaços externos que ficaram após o prefixo.
4. Preservar zeros à esquerda, pontuação e espaços internos restantes.

Exemplos:

| Entrada legada | Canônico |
|---|---|
| `M123` | `123` |
| `M 123` | `123` |
| `123` | `123` |
| `00123` | `00123` |
| ` T 00123 ` | `00123` |

A compatibilidade entre prefixo e tipo estruturado continua sendo validada
pela aplicação e pela auditoria. A coluna gerada não consulta outra tabela e
não tenta inferir o tipo.

## Motivos

- `save()` e `clean()` não são executados por `bulk_create`, `update`, SQL direto ou todas as rotas legadas.
- Uma constraint sobre o texto bruto permite `M123` e `123` simultaneamente.
- Uma coluna gerada mantém a proteção no banco para qualquer caminho de escrita.
- Preservar o campo original evita uma migração destrutiva e mantém rastreabilidade do dado legado.
- O campo canônico torna consultas indexáveis e elimina a varredura/normalização de candidatos em Python.
- A expressão pode ser composta com funções básicas (`Trim`, `Substr`, `Upper`, `Case`) compatíveis com PostgreSQL e SQLite suportado pelo projeto.

## Estratégias rejeitadas

### Normalizar apenas em formulário ou `save()`

Rejeitada porque não cobre operações em massa, comandos legados nem SQL direto.

### Sobrescrever os campos legados durante a migração

Rejeitada nesta fase porque altera dados históricos e perde a forma originalmente
armazenada. Mesmo sendo determinística, exigiria política específica de
implantação e rollback.

### Manter a constraint sobre o texto bruto

Rejeitada porque não representa a identidade definida pelo projeto.

### Escolher/mesclar conflitos durante a migração

Proibida. A migração deve listar os IDs conflitantes e interromper.

## Requisitos de implementação nas R02/R06

- Implementar a mesma expressão canônica nos três modelos sem duplicar regras divergentes.
- Preferir nova migração após 0047, preservando o histórico já reconstruído.
- Reauditar conflitos imediatamente antes de trocar cada constraint.
- Não atualizar `numero` ou `matricula` durante a migração.
- Trocar as constraints para os campos gerados e verificar os nomes pelo comando estrutural.
- Atualizar formulário e resolvedor para consultar a coluna canônica.
- Manter `normalizar_numero_documento()` como regra pura da aplicação e provar em testes que seu resultado coincide com o campo gerado.
- Verificar PostgreSQL no Docker e SQLite nas checagens compatíveis do projeto.
- Se `GeneratedField` ou a expressão não forem suportados em um dos bancos, interromper R02 e registrar a decisão; não cair silenciosamente para proteção apenas em `save()`.

## Casos de aceite vinculados

- CR-01: Documento `M123`/`123` no mesmo tipo e cartório.
- CR-02: Imóvel `M 123`/`123` no mesmo tipo e cartório.
- CR-03: `00123` permanece diferente de `123`.
- CR-04: migração bloqueia conflitos preexistentes sem corrigi-los.
- CR-09: `LancamentoOrigem` persiste e restringe a identidade canônica no caminho real.
