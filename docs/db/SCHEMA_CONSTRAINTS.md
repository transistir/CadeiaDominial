# Schema Constraints (v2)

Este documento lista as constraints **do banco** e as regras **condicionais** que devem ser garantidas pela aplicacao/trigger.

---

## 1) Constraints no banco (DDL)

### documento
- `tipo` NOT NULL CHECK (`tipo IN ('matricula','transcricao')`)
- `numero` NOT NULL CHECK (`numero GLOB '[0-9]*' AND numero <> ''`)
- `numero_raw` (opcional; sem NOT NULL)
- `cri_id` NOT NULL
- `imovel_id` NOT NULL
- `is_documento_atual` NOT NULL CHECK (`is_documento_atual IN (0,1)`)
- UNIQUE (`cri_id`, `tipo`, `numero`)
- UNIQUE parcial: `UNIQUE (imovel_id) WHERE is_documento_atual = 1`

### lancamento_tipo
- `tipo` NOT NULL CHECK (`tipo IN ('inicio_matricula','registro','averbacao')`)
- `nome` NOT NULL

### lancamento
- `tipo_id` NOT NULL
- `documento_id` NOT NULL
- `numero_lancamento` NOT NULL CHECK (`numero_lancamento > 0`)
- UNIQUE (`documento_id`, `numero_lancamento`)
- Nota: durante migracao, permitir NULL temporariamente e aplicar NOT NULL apos backfill.

### lancamento_pessoa
- `tipo` NOT NULL CHECK (`tipo IN ('transmitente','adquirente')`)

### imovel
- `cri_id` NOT NULL
- `proprietario_id` NOT NULL
- `arquivado` NOT NULL CHECK (`arquivado IN (0,1)`)

### origem
- `lancamento_id` NOT NULL
- `indice` NOT NULL CHECK (`indice >= 0`)
- `tipo` NOT NULL CHECK (`tipo IN ('matricula','transcricao','fim_cadeia')`)
- `documento_id` (opcional; sem NOT NULL)
- `cri_id` (opcional; sem NOT NULL)
- `numero` (opcional; CHECK (`numero IS NULL OR (numero GLOB '[0-9]*' AND numero <> '')`))
- UNIQUE (`lancamento_id`, `indice`)

### origem_fim_cadeia
- `origem_id` NOT NULL
- UNIQUE (`origem_id`)

### tis_imovel
- `tis_id` NOT NULL
- `imovel_id` NOT NULL
- UNIQUE (`tis_id`, `imovel_id`)

---

## 2) Regras condicionais (aplicacao/trigger)

- Se `lancamento_tipo.tipo = 'inicio_matricula'`, entao `origem.cri_id` e **obrigatorio** para as origens do lancamento.
- Se `documento.is_documento_atual = 1`, entao `documento.cri_id` deve **coincidir** com `imovel.cri_id`.
- Se `origem.tipo = 'fim_cadeia'`, entao deve existir uma linha em `origem_fim_cadeia` e `origem.documento_id` deve ser NULL.
- Se `origem.tipo IN ('matricula','transcricao')`, entao `origem_fim_cadeia` **nao** deve existir.
- Se `tipo_fim_cadeia = 'outra'`, entao `especificacao_fim_cadeia` e obrigatorio.
- Se `tipo_fim_cadeia = 'destacamento_publico'`, entao `sigla_patrimonio_publico` e obrigatorio.
- Se `tipo_fim_cadeia` estiver preenchido, entao `classificacao_fim_cadeia` e obrigatoria.
- `origem.indice` deve ser contiguo por `lancamento` (0,1,2...).
- Evitar deletar o **ultimo** documento atual de um `imovel`.

---

## 3) Notas

- `BOOLEAN` no SQLite e armazenado como `INTEGER` (0/1).
- Regras de consistencia entre `origem.documento_id` e os campos (`numero`, `livro`, `folha`, `data`) devem ser garantidas pela aplicacao quando houver duplicidade de dados.
