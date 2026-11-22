# Auditoria do formulário de início de matrícula e origens (OCR ↔ Umbelino)

> Base: `origin/develop` `6a121d84` (22/11/2026). Complementa
> `PLANO_INTEGRACAO_OCR_UMBELINO.md` (PR #385) com o **fluxo funcional real**
> do formulário — não apenas models. Nenhuma alteração de código, migration ou
> deploy nesta auditoria.

## 1. Formulário real (o que o usuário vê e o POST recebe)

**Template:** `templates/dominial/lancamento_form.html` (bloco `inicio_matricula`
inline, linhas 91–105) + `components/_area_origem_form.html`.
**Órfãos (não incluídos em lugar nenhum):** `components/_lancamento_inicio_matricula_form.html`
e `components/_cartorio_form.html`. O segundo posta `data_origem_<prefix>`; como
não é incluído, esse nome **nunca chega ao POST**.

| Campo exibido | Nome no POST | Destino | Obrigatório real | Ausente |
|---|---|---|---|---|
| Tipo de lançamento | `tipo_lancamento` | `Lancamento.tipo` | front `required` (`_lancamento_basico_form.html:75`); back `lancamento_criacao_service.py:69` | erro claro |
| Livro do documento | `livro_documento` | `Documento.livro` | front se vazio e não edição; back só preenche se vazio (`lancamento_criacao_service.py:644`) | fica vazio |
| Folha do documento | `folha_documento` | `Documento.folha` | front exceto matrícula (`:54`); back **ignora em matrícula** (`:648`, #138) | fica vazia |
| Número | `numero_lancamento_simples` + `numero_lancamento` | `Lancamento.numero_lancamento` | back só registro/averbação (`:82`); início gera da sigla | erro claro |
| Data do ato | `data` | `Lancamento.data` | front `required`; back sem validação amigável (inválida → `None` → INSERT) | 500 |
| Transmitentes/Adquirentes | `transmitente[]`/`transmitente_nome[]` (idem adquirente) | `LancamentoPessoa` + `Pessoas` | não | ato sem pessoas |
| Área | `area_inicio_matricula` / `area` | `Lancamento.area` | não | vazio |
| Tipo da origem | `tipo_origem_N` | `LancamentoOrigem.tipo_documento` | front obrigatório no início (`origem_simples.js:741-756`); back não | origem não vincula |
| Número da origem | `numero_origem_N` | `LancamentoOrigem.numero` | idem | origem não vincula |
| Texto da origem | `origem_completa[]` (hidden) | `Lancamento.origem` (texto `; `) | âncora de alinhamento | — |
| CRI da origem | `cartorio_origem_nome[]` + `cartorio_origem[]` | `LancamentoOrigem.cartorio` | front só classe CSS (`:906`); back cria pelo nome (`lancamento_campos_service.py:345-352`) | cadastro novo com CNS aleatório |
| Livro da origem | `livro_origem[]` | `LancamentoOrigem.livro` + `Lancamento.livro_origem` | não | vazio (89% dos reais) |
| Folha da origem | `folha_origem[]` | `LancamentoOrigem.folha` + `Lancamento.folha_origem` | não | vazio |
| Fim de cadeia | `fim_cadeia[]` (value=índice) | `OrigemFimCadeia.indice_origem` | não | sem fim de cadeia |
| Tipo/classificação | `tipo_fim_cadeia[]`, `classificacao_fim_cadeia[]` | `OrigemFimCadeia` | “*” visual; back não valida | nulo |
| Estado/destacamento | `sigla_patrimonio_publico[]` + `info_adicional_fim_cadeia[]` | **sigla não é coluna**; só no texto `origem_completa[]` | não | — |
| Especificação “Outra” | `especificacao_fim_cadeia[]` | `OrigemFimCadeia.especificacao_fim_cadeia` | não | — |
| Observações | `observacoes` | `Lancamento.observacoes` | não | vazio |

**Validação backend real:** `Lancamento.clean()` **não é chamado** no fluxo web
(só `LancamentoOrigem.full_clean`, `lancamento_origem_service.py:465`). Logo
`requer_cartorio_origem`, `requer_titulo`, `requer_descricao` e
`requer_data_origem` **não são exigidos**; valem tipo e número.

## 2. Múltiplas origens

- Arrays **posicionais e densos**, ancorados em `origem_completa[]`
  (`lancamento_views.py:213-256`; `lancamento_campos_service.py:327-361`).
- `fim_cadeia[]` carrega só as linhas marcadas; os demais arrays de fim de
  cadeia são densos e alinhados por posição.
- JS renumera ids/checkboxes ao remover (`origem_simples.js:625-680`).
- O form já aceita N origens; o contrato A3 v1.2 tem **um** objeto `origem`
  (limitação de contrato, não do app — ver issue #63 do `ocr-service`).

## 3. `data_origem` — legado

- Campo: `dominial/models/lancamento_models.py:79`.
- **Nenhum formulário envia.** O único partial que posta `data_origem_<prefix>`
  (`_cartorio_form.html:87`) é órfão e nenhum código lê o nome prefixado.
- Leitura: `lancamento_campos_service.py:449-455` (só se vier no POST).
- Escrita por inferência: `lancamento_criacao_service.py:677` — **corrigido no
  PR #386** (mergeado).
- Herança: `lancamento_heranca_service.py:34` comentado; `:86` nunca recebe.
- Exibição: `lancamento_detail.html:207/232/244/276`,
  `documento_lancamentos.html:196`, admin `admin.py:1917`.
- Exportação/PDF/D3/cadeia: **nenhuma referência**.
- `requer_data_origem=True` para `registro` (`criar_tipos_lancamento.py:30`),
  mas nunca validado.
- **Conclusão:** legado sem UI. Não é usado no início; não criar data por
  origem no MVP. Se um dia for necessária, pertence ao `Documento` de origem
  (que tem `data`), não ao formulário do lançamento.

## 4. Fim de cadeia

- **Tipo:** `destacamento_publico` | `outra` | `sem_origem`
  (`_area_origem_form.html:82-87`).
- **Classificação:** `origem_lidima` | `sem_origem` | `inconclusa` (`:92-97`).
- **Condicionais:** destacamento → `sigla_patrimonio_publico[]` (select de
  `FimCadeia` cadastrados, `_fim_cadeia_destacamento_fields.html:26-33`) +
  `info_adicional_fim_cadeia[]`; outra → `especificacao_fim_cadeia[]`.
- **Persistência:** `OrigemFimCadeia` por `indice_origem`
  (`lancamento_campos_service.py:488-496`) + texto em `Lancamento.origem`
  (`Destacamento Público:SIGLA:CLASSIFICAÇÃO`, `origem_simples.js:397-450`).
- `Documento.classificacao_fim_cadeia` **não é escrito** neste fluxo.
- OCR: `closure/*` é `SEM_DESTINO` (`ia_ocr/destinos.py:160-162`) e o prefill
  força `fim_cadeia=False` (`ia_ocr/formulario/origens.py:100-105`). Correto:
  classificação jurídica é humana.

## 5. Sigla do patrimônio público — perda de persistência estruturada

`lancamento_campos_service.py:314` lê `sigla_patrimonio_publico[]`, mas
`:488-496` **não usa** o valor ao criar `OrigemFimCadeia` (o model não tem esse
campo). `_processar_fim_cadeia` (`lancamento_origem_service.py:651`), que leria
a sigla, **não tem chamador**. A sigla sobrevive apenas no texto
`Lancamento.origem`; `Documento.sigla_patrimonio_publico` não é criado neste
fluxo. Issue separada registrada — **sem coluna nova no MVP** (decisão do dono).

## 6. Risco: cartório de origem com CNS aleatório

`lancamento_campos_service.py:345-352`: se o nome digitado não existe no
cadastro, o service **cria** `Cartorios` com `cns = CNS<10 dígitos aleatórios>`.

- **No fluxo OCR**, a revisão bloqueia antes: linha de cartório sem
  `cartorio_escolhido_id`/`criar_novo` gera `escolha_pendente`
  (`ia_ocr/revisao/pendencias.py:83-94`) e `salvar_ato` recusa o POST
  (`bloqueios_do_post`). "Criar novo" sem nome também bloqueia
  (`MOTIVO_CRIAR_NOVO_SEM_NOME`, `:105-117`). Portanto **uma sugestão não
  confirmada não deve chegar ao auto-create**.
- **No formulário manual**, o comportamento continua: texto livre cria cadastro.
  Não será alterado nesta etapa (decisão do dono).
- **Risco residual:** qualquer caminho futuro que chame o service sem a revisão
  (script, importação em lote) volta a criar CNS aleatório. Proposta: guarda
  explícita no service (`origem_confirmada=True` ou proibir criação quando o
  cartório veio de texto e não de escolha), em issue separada.

## 7. Pendente de verificação

- **Origens repetidas:** `LancamentoOrigem` tem
  `unique_together (lancamento, indice_origem)` e constraint
  `(lancamento, tipo_documento, numero_normalizado, cartorio)`
  (`lancamento_models.py:184-195`). `_sincronizar_origens_estruturadas` usa
  `identidades_vistas` (`lancamento_origem_service.py:315`), mas **não foi
  verificado** o comportamento para duas origens idênticas no mesmo POST
  (dedupe, erro ou segunda linha descartada). Verificação read-only pendente.
- **E2E com serviço real:** bloqueado por credenciais do serviço de OCR no
  ambiente local (ver relatório da sessão).
