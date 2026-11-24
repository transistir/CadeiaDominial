# Plano de integração OCR ↔ Umbelino (Produto 3, contrato A3)

> **Atualização 23/11/2026:** as decisões da reunião com o cliente e a
> arquitetura de vocabulário/exemplos estão em
> **`docs/produto-3/ARQUITETURA_OCR_ASSISTIDO.md`** (fila e mapa de issues).
> Este documento continua sendo a matriz A3 → formulário → modelo; onde os dois
> divergirem sobre **fila**, vale o novo.


> Estado em `origin/develop` `dc6fbca4` (22/11/2026). Documento de plano e
> matriz — **sem migração, sem deploy**. Decisões do dono (22/11) aplicadas:
> nenhum campo novo de formulário, nenhuma coluna nova, nenhum papel novo em
> `LancamentoPessoa` nesta etapa.

## 1. Estado real da integração

Fluxo existente: `DocumentoDigital` (anexo de um `Documento` já cadastrado) →
`OcrJob` → worker → OCR → `POST /v1/extract` → `ExtracaoSugerida` +
`CampoSugerido` (desnormalizados) → revisão por ato (reusa
`templates/dominial/lancamento_form.html`) → `LancamentoService.criar_lancamento_completo`.

- **Contrato:** o app **pede v1.2** (`extracao_schema.SCHEMA_VERSION =
  umbelino-extracao-matricula-v1.2`) e **aceita v1.1 e v1.2**, escolhendo o
  contrato pelo `schema_version` do payload. A cópia em `ia_ocr/schemas/` é
  byte a byte igual a `ocr-service/contracts/` (sha256
  `8be9b56f…0bc5`). O comentário "Contrato A3 v1.1" em
  `ia_ocr/extracao_client.py` está **desatualizado** — é a origem da
  divergência apontada pelo Codex.
- **Fonte de verdade:** o schema oficial é o do `ocr-service`
  (`contracts/`). O app mantém cópia vendorizada, pinada por sha256 nos testes
  (`test_extracao_schema`). Não existe terceiro repositório.
- **Destinos:** `ia_ocr/destinos.py` mapeia ~38 ponteiros; os 67 campos-folha
  do A3 se resolvem em 33 destinos, 2 linhas ignoradas por decisão (#328) e o
  resto é conferência.
- **O que falta é conteúdo do A3, não encanamento:** abertura não é emitida
  (ocr-service #72, PR #75), `partes` volta `[]` (#50), `origem` volta vazia
  (#63), `document.cartorio` volta `null` (#37).
- **Bugs reais no app:** `data_origem` recebe a data do ato
  (`lancamento_criacao_service.py:677`); `eh_inicio_matricula` chega no A3,
  tem destino mapeado e **nunca é gravado**; `document.area` e
  `document.imovel_descricao` são `SEM_DESTINO` e não aparecem na tela.

## 2. Matriz única — campo da API → formulário → modelo → validação

Legenda: **F** = input do formulário manual; **C** = conferência (sem
destino, exibida na revisão, nunca importada); **I** = ignorado por decisão
(#328); **R** = resolvido na revisão (papel/cartório por escolha).

### Documento (cabeçalho da matrícula/transcrição)

| Campo A3 | Formulário | Persistência | Regra |
|---|---|---|---|
| `document.tipo` | tipo do documento (já existe antes do OCR) | `Documento.tipo` (FK) | obrigatório na revisão; nunca sobrescreve o cadastro |
| `document.numero` | — | `Documento.numero` | conferência; `numero_normalizado` é gerado |
| `document.data` | — | `Documento.data` | obrigatório na revisão; `data_presumida` é decisão humana |
| `document.cartorio` | seletor da revisão | `Documento.cartorio` (FK) | obrigatório; escolha fica em `CampoSugerido`, não reescreve o `Documento` |
| `document.cri_atual` | — | `Documento.cri_atual` | conferência |
| `document.livro` | `livro_documento` | `Documento.livro` | grava **só se vazio** (regra pétrea #138/#218) |
| `document.folha` | `folha_documento` | `Documento.folha` | idem, **exceto matrícula**: FLS é irrelevante em M (decisão do cliente, #138) |
| `document.imovel_descricao` | — | **C** | sem coluna nova (decisão 22/11); texto e evidência preservados na revisão |
| `document.area` | — | **C** no documento | a área da abertura vai para o **ato** `inicio_matricula` (§3) |
| `document.area.unidade` | — | — | só metadado de conferência; unidade original preservada |

### Ato (R / Av / abertura)

| Campo A3 | Formulário | Persistência | Regra |
|---|---|---|---|
| `acts[].ordem` | ordem das abas | — | única; ordena a revisão (decrescente) e o último ato |
| `acts[].rotulo` | `numero_lancamento_simples` | — (deriva número) | `M` não é lançamento; `R`/`Av` definem o tipo |
| `acts[].tipo_sugerido` | `tipo_lancamento` | `Lancamento.tipo` (FK) | precedência: escolha explícita → rótulo R/Av → sugestão |
| `acts[].numero_lancamento` | `numero_lancamento_simples` | `Lancamento.numero_lancamento` | composto por tipo + sigla; nunca herda número de matrícula |
| `acts[].data` | `data` | `Lancamento.data` | obrigatório; ISO, sem inferência |
| `acts[].area` | `area` | `Lancamento.area` | hectares, 4 casas, `ROUND_HALF_UP`; unidade não reconhecida = pendência |
| `acts[].titulo` | `titulo_transacao` | `Lancamento.titulo` | exigido pelo tipo `registro` |
| `acts[].forma` | `forma_transacao` / `forma_averbacao` | `Lancamento.forma` | exigido pelo tipo |
| `acts[].descricao` | `descricao` | `Lancamento.descricao` | exigido pelo tipo `averbacao` |
| `acts[].observacoes` | `observacoes` | `Lancamento.observacoes` | livre |
| `acts[].valor_transacao` | **I** | `Lancamento.valor_transacao` existe, form não tem | fora do formulário (#328); **não** descartar em silêncio: expor em conferência |
| `acts[].detalhes` | **I** | `Lancamento.detalhes` existe, form não tem | idem |
| `acts[].eh_inicio_matricula` | — | `Lancamento.eh_inicio_matricula` | **derivado** de `tipo == inicio_matricula` na gravação; nunca decisão independente |
| `acts[].confianca` / `requer_revisao` | evidência na tela | `CampoSugerido.confianca` | não vira campo de negócio |
| `acts[].evidencia` | trecho clicável | `CampoSugerido.evidencia` | página + trecho obrigatórios |

### Partes

| Campo A3 | Formulário | Persistência | Regra |
|---|---|---|---|
| `partes[].papel` | lista `transmitente[]` / `adquirente[]` | `LancamentoPessoa.tipo` | só esses dois têm destino; `conjuge`/`representante` são contexto (não gravam, não bloqueiam) |
| `partes[].nome` | `*_nome[]` | `Pessoas.nome` + `LancamentoPessoa.nome_digitado` | nome do cadastro quando escolhido; senão texto lido |
| `partes[].match_pessoa_id` | autocomplete | FK `LancamentoPessoa.pessoa` | só vínculo determinístico; nunca cria pessoa por palpite |
| `partes[].documento_identificacao` | — | **C** (CPF 11 dígitos → `Pessoas.cpf`; RG → `Pessoas.rg`) | fora do formulário (I-11f); não completa dígito mascarado |

**Proprietários na abertura:** o formulário atual já os representa como
**adquirente** no `inicio_matricula` (não há transmissão na abertura). Não há
lacuna que justifique `papel = proprietario`; criar o papel exigiria auditar
~68 pontos de exibição/exportação e não altera o dado gravado. Fica como
proposta separada, se o dono quiser distinguir "proprietário original" de
"adquirente" na UI.

### Origem registral

| Campo A3 | Formulário | Persistência | Regra |
|---|---|---|---|
| `origem.tipo_documento` | `tipo_origem[]` | `LancamentoOrigem.tipo_documento` | M/T; não inferir de "início de matrícula" (64% reais são T) |
| `origem.numero` | `numero_origem[]` | `LancamentoOrigem.numero` (+ `Documento` de origem quando identidade fecha) | prefixo de apresentação preservado |
| `origem.cartorio` | `cartorio_origem_nome[]` | `LancamentoOrigem.cartorio` (FK) | escolha ou "criar novo" explícito |
| `origem.livro` | `livro_origem[]` | `Lancamento.livro_origem` + `LancamentoOrigem.livro` | separado do livro do documento atual e do livro da transação |
| `origem.folha` | `folha_origem[]` | `Lancamento.folha_origem` + `LancamentoOrigem.folha` | idem; opcional (89% das origens reais não têm) |
| `origem.data` | **sem input** | `Lancamento.data_origem` | **só** quando presente na referência ou digitada; hoje recebe a data do ato (bug) |

**Três livros/folhas que nunca se misturam:** (a) `Documento.livro/folha` =
documento atual; (b) `Lancamento.livro_origem/folha_origem` (e
`LancamentoOrigem.livro/folha`) = documento de origem; (c)
`Lancamento.livro_transacao/folha_transacao` = livro/folha onde a transmissão
foi registrada. O código já respeita (a)≠(b) desde o #118.

### Fechamento e metadados

| Campo A3 | Formulário | Persistência | Regra |
|---|---|---|---|
| `closure.*` | — | **C** | `OrigemFimCadeia`/`FimCadeia` só por decisão humana |
| `meta.*` | — | `OcrJob`/`ExtracaoSugerida` | auditoria, sem PII |

## 3. Área e descrição (decisões 22/11)

- **Área do documento** não vira coluna. Quando o PDF associa a área à
  abertura (primeiro/segundo parágrafo, com evidência), ela preenche o campo
  `area` **do ato `inicio_matricula`**; o normalizador existente converte para
  hectares/4 casas e a unidade lida fica preservada na revisão. Sem
  evidência ou unidade inequívoca → não preenche, fica pendência.
- **Alqueires** continuam sem conversão até haver fator regional validado.
- **`imovel_descricao`** permanece conferência (sem coluna), com texto e
  evidência visíveis na revisão — sem descarte silencioso.

## 4. Dependências do OCR (estado em 22/11)

| Issue | Tema | Estado | Bloqueia |
|---|---|---|---|
| ocr-service **#72 / PR #75** | abertura como ato `inicio_matricula` | PR aberto, mergeable | aceite ponta a ponta |
| ocr-service **#50** | `partes[]` sempre vazio | aberto | registro/averbação com pessoas |
| ocr-service **#63** | `act.origens[]` (N origens) | aberto (proposta v1.3) | cadeia com 2–27 origens |
| ocr-service **#71** | `eh_inicio_matricula` / ordem / tipo | aberto | alinhamento do campo morto |
| ocr-service **#73** | área normalizada no A3 | aberto | evita conversão dupla |
| ocr-service **#37** | `document.cartorio` null | aberto | revisão de cartório |
| ocr-service **#74/#68** | dicionário de vocabulário | aberto | #372 (um dono só) |

`v1.3` **não** é adotado sem coordenação: o app continua pedindo v1.2 e
aceitando v1.1/v1.2. Quando o `ocr-service` publicar v1.3, o app adiciona o
arquivo vendorizado + sha256 e passa a pedi-la — PR nos dois lados.

## 5. Issues locais (#371, #372, #373, #378, #379, #382, #383)

| Issue | Estado real | Ação |
|---|---|---|
| #371 abertura | aberta; causa no serviço (#72) | fixture M237 no app; fechar quando #75 + app estiverem verdes |
| #372 dicionário | aberta | bloqueada por #74: consumir artefato do `ocr-service`, não varrer prod |
| #373 área | **implementada** pelo #379 (mergeado 22/11) | fechar na validação; falta só o E2E |
| #378 sidebar | mergeada | — |
| #379 área (PR) | mergeado | — |
| #382 A3 sem unidade | aberta | depende de medir `area.raw` real; sem prod nesta etapa |
| #383 área nits | aberta com **PR #383 aberto** | review; sem relação com a matriz |

## 6. Sequência mínima de PRs

1. **PR 0 (este):** plano + matriz. Docs only.
2. **PR 1:** `data_origem` não copia a data do ato; `eh_inicio_matricula`
   derivado do tipo na gravação; comentário v1.1 → v1.2. Teste de regressão
   (RED antes).
3. **PR 2 (quando o #75 mergear):** fixture M237 → abertura vira
   `inicio_matricula`, área do cabeçalho vai para o ato, sem ato fantasma;
   regressão de contagem/ordem dos R/Av.
4. **PR 3:** conferência explícita de `valor_transacao`/`detalhes`/
   `imovel_descricao` (sem campo novo; nada de descarte silencioso).
5. **PR 4:** N origens quando o A3 v1.3 chegar (array + compatibilidade com
   `origem` singular).
6. **PR 5:** I-8 (#265) — E2E com PDF real + smoke com stubs.

## 7. Critérios de aceite (E2E com PDF real)

- Abertura sugerida como `inicio_matricula`, com livro/folha/data e área
  quando o texto confirmar.
- R e Av separados, ordem do documento preservada, números nunca trocados
  (`M-237` ≠ `R-1-237`).
- Livro/folha do documento atual, da origem e da transação em campos
  distintos.
- Pessoas e área nos campos corretos; toda sugestão editável antes de salvar.
- Documento sem abertura **não** ganha ato fantasma.
- Preenchimento manual continua idêntico (regressão).
- `data_origem` ausente quando a origem não traz data.

## 8. Riscos e esforço

- **Caminho crítico é o serviço** (#72/#75, #50): sem isso, o E2E só prova
  com stub.
- PR 1: pequeno (½ dia, 2 arquivos + teste).
- PR 2: médio (1 dia) e depende do #75.
- PR 4: grande (2–3 dias) e depende de v1.3 acordada.
- Total do lado Django nesta etapa: **~4–6 dias de agente**, sem migração.
