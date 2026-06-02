# Legenda - Diagrama de Entidades (ERD)

Este diagrama mostra **tabelas** (caixas) e **relacionamentos** (linhas) entre elas. A ideia e que qualquer pessoa consiga entender o que cada linha significa.

## 1) O que e cada caixa (tabela)
- Cada caixa representa uma **tabela** do banco de dados.
- Dentro da caixa estao os **campos** (colunas) com seu tipo (ex: `string`, `int`, `date`).
- `PK` = **Primary Key** (identificador unico da linha).
- `FK` = **Foreign Key** (campo que aponta para outra tabela).

## 2) Como ler os relacionamentos
O formato e do tipo: `A ||--o{ B : rotulo`
- **A** e a tabela de origem
- **B** e a tabela relacionada
- **rotulo** explica o sentido da relacao em linguagem humana

### Cardinalidade (quantidade de registros)
- `||` = exatamente 1
- `o|` = 0 ou 1 (opcional)
- `o{` = 0 ou muitos
- `|{` = 1 ou muitos

### Exemplos simples
- `cri ||--o{ documento : emite`
  - Um **CRI** pode emitir **varios documentos**.
  - Um documento pertence a **um** CRI.

- `lancamento ||--o{ origem : possui`
  - Um **lancamento** pode ter **varias origens**.
  - Cada origem pertence a **um** lancamento.

- `origem ||--o| origem_fim_cadeia : fim_cadeia`
  - Uma **origem** pode ter **zero ou um** fim de cadeia.

## 3) Significado dos rotulos (texto nas linhas)
- **emite**: CRI registra um documento.
- **registra**: CRI esta associado a um imovel.
- **possui**: entidade tem varias ligacoes (ex: imovel -> documento).
- **proprietario**: pessoa relacionada ao imovel como proprietario.
- **gera**: documento que gera lancamentos.
- **classifica**: tipo que define regras do lancamento.
- **envolve / participa**: ligacao entre lancamento e pessoa.
- **referencia**: origem aponta para um CRI (opcional).
- **origem_doc**: origem aponta para um documento (opcional).
- **transmissao**: cartorio_transmissao usado na transmissao do lancamento.
- **vincula (TI)**: imovel associado a uma TI.
- **referencia (TI)**: TI aponta para a tabela de referencia oficial.

## 4) Campos importantes explicados em linguagem simples
- **documento.is_documento_atual**: marca o documento vigente do imovel (apenas 1 por imovel).
- **cartorio_transmissao_id**: cartorio manual usado na transmissao.
- **origem.tipo**: `matricula`, `transcricao` ou `fim_cadeia`.
- **origem.documento_id**: documento de origem (opcional, quando tipo != `fim_cadeia`).
- **origem.indice**: ordem das origens dentro de um lancamento (0, 1, 2...).
- **origem_fim_cadeia.sigla_patrimonio_publico**: sigla do orgao (ex: INCRA, SPU) quando aplicavel.
- **lancamento.numero_lancamento**: numero informado pelo usuario (nao e derivado); usado para compor a sigla exibida (ex: `AV5 M123`).

## 5) Observacoes sobre obrigatoriedade
- Um campo marcado como `FK` pode ser **obrigatorio ou opcional** dependendo da regra de negocio.
- A obrigatoriedade especifica esta definida no documento `docs/db/SCHEMA_CONSOLIDATED.md`.
- No SQLite, `bool` representa `INTEGER` (0/1).
