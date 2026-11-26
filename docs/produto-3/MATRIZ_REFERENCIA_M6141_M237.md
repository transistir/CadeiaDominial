# Matriz de referência da cadeia M6141 → M237

**Issue:** transistir/CadeiaDominial#395 (U-M237-01, P0) · **Série:** U-M237
**Status:** matriz medida (etapa 1 M6141 + etapa 2 M237). Não corrige dados.
**Revisão:** 25/11/2026 — 1ª revisão Opus (7 must-fix) e 2ª revisão Opus (3 must-fix)
do PR #407 endereçados (§10).
**Base do repositório:** `origin/develop` @ `7ca71237` · **Data da medição:** 24/11/2026
**Especificação:** `docs/produto-3/ESPEC_MATRIZ_REFERENCIA_M6141_M237.md` (PR #405)

> A matriz mede o **ser** (documento × OCR × banco), não o dever-ser do contrato A3.
> Toda célula nomeia a camada de origem (D = documento, O = OCR, B = banco) e a
> evidência. Nenhum valor foi corrigido nem inferido; o cabeçalho da M237 foi
> conferido visualmente em 25/11 (§3.1, §9). Artefato sem PII: partes aparecem
> como papel (`transmitente 1`, `adquirente 1`).
>
> **Camada D = transcrição do OCR A3 v1.2, sem conferência visual humana** (§1.1),
> exceto o cabeçalho da M237, conferido em 25/11 (§9).
> "Literal" nesta matriz significa literal do OCR, não do scan; as células
> `erro_confirmado` valem contra esse literal.

---

## 1. Proveniência da medição

| Item | Valor |
|---|---|
| Banco | produção `cadeia_dominial`, usuário `inventario_ro` |
| Sessão | `BEGIN READ ONLY; … COMMIT;` em toda consulta (`prod_ro_query.sh`) |
| Consulta | 2026-11-24 18:08 UTC (cabeçalho e lançamentos), 18:12–18:14 UTC (origens/catálogo) |
| Filtro | por ID: TI 67, imóvel 283, documentos 1086/4980/4981, cartórios 393/1615/483/4293/4857 |
| TI 67 | Barra Velha — Pataxó — 8.627,46 ha — BA |
| Imóvel 283 | Fazenda Condessa — matrícula 6141 — cartório 393 — TI 67 |
| Documento 1086 | M6141 — cartório 393 (Itamaraju/BA) — livro 2 — folha 0 |
| Documento 4980 | M237 — cartório 393 (Itamaraju/BA) — livro 2 — folha 0 — `data_presumida=t` |
| Documento 4981 | M1754 (contexto) — cartório **1615** (Prados/MG) — livro 2 — folha 0 — `data_presumida=t` |
| Cartório 393 | Registro de Imóveis de Itamaraju — CNS 140160 — ITAMARAJU/BA |
| Cartório 483 | Registro de Imóveis de Prado — CNS 007559 — PRADO/BA |
| Cartório 1615 | Registro de Imóveis de Prados — CNS 054015 — PRADOS/MG |
| PDF M6141 | SHA-256 `1caaa1a155a8` — 1 página — 287.537 bytes |
| PDF M237 | SHA-256 `3c915803c4c0` — 2 páginas — 507.991 bytes |
| PDF M1754 | SHA-256 `a845eb9b1467` — 1 página — 334.512 bytes |

### 1.1 OCR usado como camada O — e o que é a camada D

| Documento | `job_id` (OCR) | `meta.job_id` | Schema | Págs | Atos |
|---|---|---|---|---|---|
| M6141 | `34c2479557d44ec69d55eedd681b9209` | `15f199fa-51d0-49ce-a64f-f0b90a4452e8` | `umbelino-extracao-matricula-v1.2` | 1 | 2 |
| M237 | `be21a14f24ed4c9baadc3655a48fa4ca` | `769641e2-9484-414c-81c1-2855a161d35c` | `umbelino-extracao-matricula-v1.2` | 2 | 8 |
| M1754 | `fa0ec8b4f3a14c07bb50cdbb0bfeef0d` | `4a7c1a0e-…` (contexto) | `umbelino-extracao-matricula-v1.2` | 1 | 6 |

O job da M237 foi reexecutado em 24/11/2026 sobre o PDF de produção, porque a
`ExtracaoSugerida` 29 (job 25) não existe mais no banco de testes. O job da M6141 é
o artefato de homologação pós-`48d1660`. **Lacuna conhecida:** nos três jobs a
data do cabeçalho/abertura sai com `raw` preenchido e `normalized = null`; a
correção está no PR transistir/ocr-service#94. Esta medição usa o A3 v1.2
**anterior** ao fix. A matriz registra o `raw` e **não infere** a data.

**Camada D.** A coluna D é a **transcrição do OCR A3 v1.2** (`paginas_texto` do
job registrado acima), **sem conferência visual humana** da digitalização. Ela é,
portanto, dependente da camada O: não é uma leitura independente do scan.
Convenções: valor entre crases = citação literal do OCR (citação truncada leva
`…`); prefixo `derivado:` = paráfrase, normalização ou conta feita a partir de
literais; `n/d` = camada ausente. Fora o cabeçalho da M237 conferido em 25/11
(§3.1), nenhum valor foi conferido contra a imagem — a conferência visual página a
página é etapa humana separada (§9).

O A3 v1.2 **tem** `origem` por ato (`$defs/act.properties`: `tipo_documento`
— `matricula`/`transcricao` —, `numero`, `cartorio`, `livro`, `folha`, `data`).
Na abertura da M6141 o campo vem completo (`matricula` 237, livro 2, folha 237,
06.05.2002); na abertura da M237, onde o literal traz `TÍTULO AQUISITIVO:
Transcrição de nº 1-1.754…`, o job devolveu `origem = null`. É falha de extração,
não lacuna de contrato (item 20).

### 1.2 Classes (fechadas)

`dado_documental` · `interpretacao_humana` · `calculo_derivado` · `erro_confirmado`
· `divergencia_pendente`.

Critérios usados nesta matriz:

- `erro_confirmado` — a camada B **contradiz** de forma direta e não ambígua o
  literal do documento (D), **ou omite** conteúdo documental que o ato registral
  contém (campo ausente ou ato inteiro não cadastrado). A mesma situação recebe a
  mesma classe em todas as seções.
- `divergencia_pendente` — a evidência não permite decidir: ambiguidade de campo
  (ex.: `forma` × natureza), falha/lacuna do OCR (campo existe no contrato A3 e o
  job não entregou — a ausência é da camada O, não do cadastro), campo sem
  representação no cadastro ou vínculo sem lastro literal completo.
- `dado_documental` — campo documental consistente entre as camadas, ou registro
  do que o documento traz sem juízo.
- `interpretacao_humana` — leitura/rotulagem humana sem base literal direta.
- `calculo_derivado` — conta a partir de literais (áreas, somas).

O `erro_confirmado` vale contra o **literal do OCR**; a conferência visual da
digitalização permanece como etapa de revisão humana registrada no rodapé.
`n/d` = camada ausente, nunca célula vazia.

**Por que `forma`/`título` não recebe a mesma classe em todo ato.** Nos atos de
registro (R.1 da M6141, R.4 e R.5 da M237) o documento traz rótulo explícito
`TÍTULO:` com o negócio jurídico e a escritura em `FORMA DO TÍTULO:`; o banco
grava a escritura no título e o negócio na forma — contradição direta,
`erro_confirmado`. Nas averbações (Av.6 e Av.7) não existe rótulo `TÍTULO`: a
escritura aparece no corpo do ato, sem campo documental de natureza a comparar —
daí `divergencia_pendente` (item 12), não erro.

### 1.3 Datas dos atos e estado de revisão (A3 v1.2)

| Documento · ato | D (literal) | O `data.normalized` | B `data` | `confianca` (O) | `requer_revisao` (O) | `motivos_revisao` |
|---|---|---|---|---|---|---|
| M6141 · cabeçalho | `18.06.2015` | n/d (`raw` only) | — | 0.0 | true | n/d |
| M6141 · abertura | `18.06.2015` | n/d (`raw` only) | 2015-06-18 | 0.0 | true | n/d |
| M6141 · R.1 | `18 de junho de 2015` | 2015-06-18 | 2015-06-18 | 1.0 | true | n/d |
| M237 · cabeçalho | `09.06.1982` | n/d (`raw` only) | — | 0.0 | true | n/d |
| M237 · abertura | `09.06.1982` | n/d (`raw` only) | 1982-06-09 | 0.0 | true | n/d |
| M237 · R.1 | `09 de junho de 1982` | 1982-06-09 | n/d (ato ausente — §3.2) | 1.0 | false | — |
| M237 · Av.2 | `19 de dezembro de 1983` | 1983-12-19 | n/d (ato ausente — §3.2) | 1.0 | true | n/d |
| M237 · Av.3 | `08 de outubro de 1986` | 1986-10-08 | n/d (ato ausente — §3.2) | 1.0 | false | — |
| M237 · R.4 | `14 de março de 1995` | 1995-03-14 | 1995-03-14 | 1.0 | true | n/d |
| M237 · R.5 | `06 de maio de 2002` | 2002-05-06 | 2002-05-06 | 1.0 | true | n/d |
| M237 · Av.6 | `18 de junho de 2015` | 2015-06-18 | 2015-06-18 | 1.0 | true | n/d |
| M237 · Av.7 | `22 de fevereiro de 2017` | 2017-02-22 | 2017-02-22 | 1.0 | true | n/d |
| M1754 · cabeçalho | `31/maio/1977` | n/d (`raw` only) | — | 0.0 | true | n/d |
| M1754 · abertura | `31/maio/1977` | n/d (`raw` only) | 1977-05-31 | 0.0 | true | n/d |

`motivos_revisao` não é preenchido pelo A3 v1.2 em nenhum ato desta medição — daí
`n/d`. `requer_revisao = true` marca o ato para conferência humana; não é, por si
só, erro confirmado (a classe de cada divergência está nas seções 2–4).

`B data = n/d` nas linhas da M237 sem lançamento marca ato **não cadastrado**
(§3.2); não é célula vazia nem inferência a partir do OCR.

---

## 2. M6141 (documento 1086) — cabeçalho

| Campo | D | O | B | Evidência | Classe |
|---|---|---|---|---|---|
| Número | `6.141` | `6141` | `M6141` | p.1 `MATRÍCULA 6.141` | dado_documental |
| Livro / folha | `2` / n/d | `2` / n/d | `2` / `0` | p.1 `LIVRO Nº 2` | interpretacao_humana (folha placeholder) |
| Data do documento | `18.06.2015` (raw) | raw `18.06.2015`, norm. nulo | `2024-01-01`, presumida `f` | p.1 `DATA 18.06.2015` | erro_confirmado |
| Cartório | `derivado: Itamaraju/BA` (`CARTÓRIO DE REGISTRO DE IMÓVEIS COMARCA DE ITAMARAJU – BAHIA`) | idem | 393 | p.1 | dado_documental |
| `classificacao_fim_cadeia` | n/d | n/d | vazio | — | n/d (campo classifica a ponta de origem; a M6141 tem origem) |

### 2.1 Ato 1 — Abertura (M-6141), banco 14803

| Campo | D | O | B | Evidência | Classe |
|---|---|---|---|---|---|
| Título / natureza | `derivado: abertura de matrícula` | `inicio_matricula` | `inicio_matricula` | p.1 `MATRÍCULA 6.141` | dado_documental |
| Data do ato | `18.06.2015` (raw) | raw `18.06.2015`, norm. nulo | `2015-06-18` | p.1 `DATA 18.06.2015` | dado_documental (lacuna de normalização) |
| Área | `74 ha. 67 a. 55 ca.` | raw idem, norm. nulo | `74.6755` | p.1 | dado_documental |
| Origem — número | `R. 5, da matrícula 237` | `237` (matrícula) | `M237`; `LancamentoOrigem` matrícula 237 | p.1 `REGISTRO ANTERIOR: R. 5, da matrícula 237, livro nº 2, fls. 237, de 06.05.2002, deste Cartório.` | **erro_confirmado** (omissão do `R. 5`) |
| Origem — livro/folha | `2` / `237` | `2` / `237` | `"None"` / `"None"` (texto, não nulo) | idem | **erro_confirmado** (omissão) |
| Origem — data | `06.05.2002` | `2002-05-06` | `data_origem = 2015-06-18` | idem | **erro_confirmado** |
| `documento_origem_id` | elo textual | n/d | `NULL` | — | dado_documental (vínculo só textual) |
| `eh_inicio_matricula` | `derivado: abertura` | `true` | `false` | p.1 `MATRÍCULA 6.141` | **erro_confirmado** |
| Observação | `derivado: INCRA/CCIR/NIRF` | presente | texto analítico "Suposto destaque…" | p.1 | interpretacao_humana |
| Descrição | `derivado: descrição do imóvel` | presente | n/d | p.1 | **erro_confirmado** (omissão) |

### 2.2 Ato 2 — R.1 M6141, banco 14804

| Campo | D | O | B | Evidência | Classe |
|---|---|---|---|---|---|
| Número / tipo | `R. 1` / registro | `R-1` / registro | `R1 M6141` / registro | p.1 `R. 1-6.141` | interpretacao_humana (renumerado) |
| Data do ato | `18 de junho de 2015` | `2015-06-18` | `2015-06-18` | p.1 | dado_documental |
| Forma | `Escritura pública de 10 de abril de 2015` | idem | `Compra e Venda` | p.1 `FORMA DO TÍTULO: Escritura pública de 10 de abril de 2015, lavrada no Tabelionato de Notas de Cachoeira do Mato, livro nº 02, fls. 116 a 117` | **erro_confirmado** (forma × título) |
| Título | `Venda e Compra` | idem | `Escritura pública` | p.1 | **erro_confirmado** (forma × título) |
| Descrição | `O imóvel objeto desta matrícula.` | idem | n/d | p.1 | erro_confirmado (omissão) |
| Detalhes / valor | `VALOR: R$ 90.647,60, majorados para R$ 186.688,75`; `O preço convencionado da venda e compra foi de R$ 100.000,00` | `valor_transacao = 186688.75`; `detalhes` com o preço de R$ 100.000,00 | n/d | p.1 | erro_confirmado (omissão) |
| Livro / folha / data da transação | `02` / `116 a 117` / `10.04.2015` | `02` / `116 a 117` / `2015-04-10` | `02` / `116-117` / n/d | p.1 | **erro_confirmado** (data da transação omitida) |
| Cartório da transmissão | `Tabelionato de Notas de Cachoeira do Mato` | idem | 4857 | p.1 | dado_documental |

---

## 3. M237 (documento 4980) — cabeçalho

| Campo | D | O | B | Evidência | Classe |
|---|---|---|---|---|---|
| Número | `237` | `237` | `M237` | p.1 `MATRÍCULA Nº 237` | dado_documental |
| Livro / folha | `2` / `237` | `2` / `237` | `2` / `0` | p.1 `LIVRO 2 FLS 237` | **erro_confirmado** (contradição: `FLS 237` × `0`), item 21 |
| Data do documento | `09.06.1982` (raw) | raw idem, norm. nulo | `2026-11-12`, presumida `t` | p.1 `DATA 09.06.1982` | interpretacao_humana (data de cadastro) |
| Cartório | `derivado: Itamaraju/BA (atos)`; cabeçalho literal sem município | `OFÍCIO DO REGISTRO DE IMÓVEIS E HIPOTECAS`; `municipio = REGISTRO DE IMÓVEIS COMARCA DE` | 393 | p.1–2 | divergencia_pendente (rótulo OCR) |
| `classificacao_fim_cadeia` | n/d | n/d | vazio | — | n/d (campo classifica a ponta de origem; a M237 tem título aquisitivo — §3.1) |

### 3.1 Ato 1 — Abertura sintética (M-237), banco 14805

| Campo | D | O | B | Evidência | Classe |
|---|---|---|---|---|---|
| Natureza | `derivado: cabeçalho da matrícula` | `inicio_matricula` | `inicio_matricula` | p.1 | interpretacao_humana (não é ato registral) |
| Data | `09.06.1982` (raw) | raw idem, norm. nulo | `1982-06-09` | p.1 | dado_documental |
| Área | `169 hectares, 09 ares e 40 centiares` | raw idem, norm. nulo | `169.0940` | p.1 | dado_documental |
| Origem — título aquisitivo | `TÍTULO AQUISITIVO: Transcrição de nº 1-1.754, do Cartório de Imóveis da Comarca de Prado-Ba` | `origem = null` (campo existe no A3 v1.2; extração não preencheu) | `M1754` em cartório **1615** (Prados/MG) | p.1, após `PROPRIETÁRIOS`; M1754 p.1 | **erro_confirmado** (cartório do vínculo) |
| `eh_inicio_matricula` | `derivado: abertura` | `true` | `false` | p.1 | **erro_confirmado** |
| Observação | `derivado: INCRA/FUNRURAL` | presente | n/d | p.1 | **erro_confirmado** (omissão) |

A camada O desta linha é `origem = null`, não `n/d` por falta de campo: o A3 v1.2
tem `origem` por ato e o preenche na abertura da M6141 (§2.1) — a falha é da
extração (item 20). Critério verificável do #86 para este ato:
`origem.tipo_documento.normalized = transcricao` (literal), `origem.numero.raw =
1-1.754`, `origem.cartorio` = Comarca de Prado-BA.

### 3.2 Atos 2–4 — R.1, Av.2 e Av.3 (ausentes no banco)

| Ato | D (literal) | O | B | Classe |
|---|---|---|---|---|
| R.1 | `R: 1-237 – Itamaraju, 09 de junho de 1982`; `hipoteca cedular de 2º grau`, `Cr$ 1.525.273,12`, livro 3, fls. 194 | presente | **n/d** | **erro_confirmado** (ato não cadastrado — ônus) |
| Av.2 | `Av: 2-237 – Itamaraju, 19 de dezembro de 1983`; `Por Cédula Rural Hipotecária`; `Cr$ 2.504.829,00` | presente | **n/d** | **erro_confirmado** (ato não cadastrado — ônus) |
| Av.3 | `Av: 3-237 – … 08 de outubro de 1986`; cancela o `R: 1-237` | presente | **n/d** | **erro_confirmado** (ato não cadastrado — baixa de ônus) |

### 3.3 Ato 5 — R.4 M237, banco 14843

| Campo | D | O | B | Evidência | Classe |
|---|---|---|---|---|---|
| Forma / título | `Escritura pública de 17 de janeiro de 1995, lavrada no Tabelionato de Itamaraju, livro 87, fls. 41/42` / `Compra e venda` | idem | `Compra e Venda` / `Escritura pública` | p.1 | **erro_confirmado** (invertidos) |
| Data do ato | `14.03.1995` | `1995-03-14` | `1995-03-14` | p.1 `R: 4-237` | dado_documental |
| Área | `38 ha. e 72 a.` — `derivado (semântica): fração transmitida` | idem | `130.3740` (remanescente) | p.1 `IMÓVEL: Área de 38 ha. e 72 a.` | calculo_derivado (semântica invertida) |
| Valor | `R$ 20.000,00 majorado para R$ 25.000,00` | raw idem, norm. nulo | n/d | p.2 | erro_confirmado (omissão) |
| Descrição | `IMÓVEL: Área de 38 ha. e 72 a. (trinta e oito hectares e setenta e dois ares) do imóvel objeto desta matrícula.` | idem | n/d | p.1 | erro_confirmado (omissão) |
| Observação | `derivado: CND FUNRURAL/IAPAS` | idem | texto analítico "Segundo o R4 M237…" | p.2 | interpretacao_humana (#400) |
| Detalhes | `Número do imóvel na Receita Federal 1302524-4` (NIRF); `"CONJUNTO SÃO JOSÉ"` | idem | idem | p.2 | dado_documental |
| Livro / folha / cartório | `87` / `41/42` / `Tabelionato de Itamaraju` | idem | `87` / `41-42` / 4293 | p.1 | dado_documental |

### 3.4 Ato 6 — R.5 M237, banco 14844

| Campo | D | O | B | Evidência | Classe |
|---|---|---|---|---|---|
| Forma / título | `derivado: escritura de 25.04.2002` / `Compra e venda` | idem | `Compra e Venda` / `Escritura pública` | p.2 | **erro_confirmado** (invertidos) |
| Área | `130 ha. 37 a. e 40 ca.` | idem | `130.3740` | p.2 | dado_documental |
| Valor | `R$ 47.100,00` | `47100.00` | `47100.00` | p.2 | dado_documental |
| Livro / folha / cartório | `14` / `80/81` / `Tabelionato de Itamaraju` | idem | `14` / `80-81` / 4293 | p.2 | dado_documental |
| Data da transação | `derivado: escritura de 25.04.2002` | `2002-05-06` | `2002-05-06` | p.2 | divergencia_pendente (OCR não separa ato × escritura) |

### 3.5 Ato 7 — Av.6 M237, banco 14845

| Campo | D | O | B | Evidência | Classe |
|---|---|---|---|---|---|
| Forma | `derivado: escritura pública de 10 de abril de 2015` (`nos termos da escritura pública lavrada … no dia 10 de abril de 2015`) | raw `Escritura Pública`, norm. nulo | `Compra e venda` | p.2 | divergencia_pendente |
| Data do ato | `18.06.2015` | `2015-06-18` | `2015-06-18` | p.2 `Av: 6-237` | dado_documental |
| Título | `Escritura Pública de 10 de abril de 2015` | raw idem, norm. nulo | n/d | p.2 | divergencia_pendente |
| Área | `74 ha. 67 a. 55 ca.` — `derivado (semântica): fração destacada` | idem | `55.6985` (remanescente) | p.2 | calculo_derivado (semântica invertida) |
| Descrição / vínculo | `registrada … sob o nº 1, da matrícula 6.141 … em 18.06.2015` (citação truncada) | campo só com partes | texto analítico com `6.141` | p.2 | interpretacao_humana (OCR perde o vínculo) |
| Valor | `R$ 45,08` | `45.08` | `45.08` | p.2 | dado_documental |
| Livro / folha / cartório | `02` / `116 a 117` / `Tabelionato de Notas de Cachoeira do Mato` | idem | idem / 4857 | p.2 | dado_documental |

### 3.6 Ato 8 — Av.7 M237, banco 15072

| Campo | D | O | B | Evidência | Classe |
|---|---|---|---|---|---|
| Forma | `escritura pública de 07 de dezembro de 2016` | raw idem, norm. idem | `Compra e venda` | p.2 | divergencia_pendente (forma × natureza) |
| Data do ato | `22.02.2017` | `2017-02-22` | `2017-02-22` | p.2 `Av: 7-237` | dado_documental |
| Título | não há `TÍTULO` no ato | `PROTOCOLO nº 28.492` | `Compra e venda` | p.2 | divergencia_pendente |
| Área | `94 ha. 41 a. 85 ca.` | raw idem, norm. nulo | n/d | p.2 | calculo_derivado (campo vazio) |
| Área — conta | — | `derivado (conta): 94,4185 = 38,7200 + 55,6985` | — | p.2 `sendo 38 ha. 72 a. 00 ca., do R. 4. … e a área remanescente de 55 ha. 69 a. 85 ca. do R. 5` | calculo_derivado |
| Descrição | `derivado: venda da área total a adquirente 1` | só partes | resumo analítico | p.2 | interpretacao_humana |
| Encerramento | `ficando ENCERRADA a presente escrituração`; rodapé p.2 `MATRÍCULA ENCERRADA` | n/d | sem marcação: `classificacao_fim_cadeia` e `origemfimcadeia` vazios **e** sem campo de encerramento da matrícula | p.2 | divergencia_pendente (lacuna de cadastro) |
| Valor | `R$ 49,76` | `49.76` | `49.76` | p.2 | dado_documental |
| Livro / folha / cartório | `34` / `037/038` / `Tabelionato de Notas de Itagimirim` | idem | idem | p.2 | dado_documental |

---

## 4. M1754 (documento 4981) — recorte de contexto

A M1754 entra como contexto, mas sustenta três itens de P0/P1: cartório do
cabeçalho (#2), `eh_inicio_matricula` (#7) e data do documento (#11). Recorte
D/O/B dos campos que sustentam esses itens — nada além disso foi medido.

| Campo | D | O | B | Evidência | Classe |
|---|---|---|---|---|---|
| Cartório do cabeçalho | `REGISTRO DE IMÓVEIS HIPOTECAS PRADO - BAHIA` | raw idem, norm. idem; `municipio = REGISTRO DE IMÓVEIS COMARCA DE` | documento 4981: **1615** (Prados/MG); lançamento 15073 origem 483 (Prado/BA) | p.1 | **erro_confirmado** |
| `eh_inicio_matricula` | `derivado: abertura` (`MATRÍCULA N.º 1.754`) | `true` em `eh_inicio_matricula` (conf. 1.0 no campo; a `confianca` do ato é 0.0) | `false` (lançamento 15073) | p.1 | **erro_confirmado** |
| Data do documento | `31/maio/1977` | raw idem, norm. nulo; `requer_revisao = true` | `2026-11-12` (presumida `t`) | p.1 | interpretacao_humana (data de cadastro) |
| Área | `169ba.09a.40ca.` (literal do OCR) | raw idem, norm. nulo | `169.0940` | p.1 | dado_documental |
| Atos R.1–Av.5 | 5 atos: R.1 1977, R.2 1977, R.3 1978, Av.4 1986, Av.5 2001 | presente | **n/d** | p.1 | **erro_confirmado** (atos não cadastrados — item 18) |

---

## 5. Relação M6141 ↔ M237

**Status: confirmada.** As duas pontas foram medidas em jobs distintos e não foram
transferidas entre si.

- M6141, abertura, p.1 (literal): `REGISTRO ANTERIOR: R. 5, da matrícula 237,
  livro nº 2, fls. 237, de 06.05.2002, deste Cartório.`
  Leitura sustentada: a M6141 nasceu do **R.5 da M237** (não da abertura genérica
  da M237), livro 2, fls. 237, referência de 06.05.2002.
- M237, Av.6, p.2 (literal): a fração destacada de `74 ha. 67 a. 55 ca.` foi
  `registrada neste Cartório sob o nº 1, da matrícula 6.141, livro 2, ficha 01,
  em 18.06.2015`. Leitura sustentada: o destino do destaque é a M6141.
- Banco: `LancamentoOrigem` 2817 (matrícula 237, sem livro/folha) e
  `Lancamento.origem = 'M237'`; `documento_origem_id = NULL` nos dois sentidos.
  O elo existe apenas como texto — a cadeia parece inexistente para quem só lê FK.

O elo **M237 → M1754** é outro vínculo e está tratado à parte: a §3.1 mostra o
literal `TÍTULO AQUISITIVO: Transcrição de nº 1-1.754, do Cartório de Imóveis da
Comarca de Prado-Ba`; o OCR devolveu `origem = null` nesse ato — falha de extração,
porque o campo existe no contrato A3 v1.2 (item 20) — e o cadastro aponta cartório
divergente. O elo existe como M1754 **só no banco**.

---

## 6. Divergências priorizadas

Prioridade = impacto na cadeia/aceite. Cada item tem **uma** classe. São 22 itens:
os 18 da medição original, dois abertos na 1ª revisão (19 e 20) e dois na 2ª
revisão (21 e 22).

### P0 — bloqueiam o aceite da M237

1. **Cartório da origem M237 → M1754 errado (1615 Prados/MG).** O literal da
   M1754 é `REGISTRO DE IMÓVEIS HIPOTECAS PRADO - BAHIA`; o próprio lançamento de
   abertura da M1754 cita `T10090` no cartório **483** (Prado/BA). O banco grava
   `LancamentoOrigem` 2818 = 1615. `erro_confirmado`.
2. **Cabeçalho do documento 4981 (M1754) aponta cartório 1615**, contradizendo o
   literal (`REGISTRO DE IMÓVEIS HIPOTECAS PRADO - BAHIA`, §4) e sua própria
   origem (`T10090`, cartório 483). `erro_confirmado`.
3. **Av.7 declara a matrícula ENCERRADA e o cadastro não registra o
   encerramento.** Literal: `ficando ENCERRADA a presente escrituração` (Av.7,
   p.2) e rodapé `MATRÍCULA ENCERRADA`. O cadastro não tem campo de encerramento:
   `documento.classificacao_fim_cadeia` e `OrigemFimCadeia.classificacao_fim_cadeia`
   classificam a **ponta de origem** (`origem_lidima` / `sem_origem` / `inconclusa`),
   não "matrícula encerrada"; `origemfimcadeia` está vazio. Como a M237 tem título
   aquisitivo (§3.1), não é ponta de origem e a ausência de classificação não é erro:
   é lacuna de cadastro/contrato. `divergencia_pendente`.
4. **M6141 `data_origem` = 2015-06-18**, mas o registro anterior é de **06.05.2002**.
   `erro_confirmado`.
5. **Áreas com semântica invertida:** R.4 (B 130.3740 remanescente × D 38,72
   transmitida), Av.6 (B 55.6985 remanescente × D 74,6755 destacada) e Av.7 (B
   vazio × D 94,4185 = 38,7200 + 55,6985). `calculo_derivado`.
6. **R.1, Av.2 e Av.3 da M237 não cadastrados** (3 atos). O R.1 traz
   `hipoteca cedular de 2º grau` (derivado: rótulo do corpo do ato; ônus real), a
   Av.2 é outra Cédula Rural Hipotecária e a Av.3 dá baixa no R.1: sem os três o
   app perde o histórico de ônus do imóvel, não só a sequência de transmissões —
   daí o P0. `erro_confirmado` (omissão).
7. **`eh_inicio_matricula = false` nos três inícios** (M6141, M237, M1754), embora
   o OCR v1.2 emita `eh_inicio_matricula.normalized = true`, com evidência do
   cabeçalho e `confianca = 1.0` **nesse campo** (§4); a `confianca` do ato é 0.0
   porque a data sai sem `normalized` (§1.3). `erro_confirmado`.
8. **Origem da M6141 sem o `R. 5` no número e sem livro/folha** no banco; o
   número vira só `237` (matrícula), livro/folha são gravados como a string
   `"None"` e a `data_origem` recebe a data da própria abertura (item 4).
   `erro_confirmado`.

### P1 — qualidade e contrato A3

9. **Forma e título invertidos** em R.1 M6141, R.4 e R.5 M237. `erro_confirmado`.
10. **Valores de transação ausentes** em R.1 M6141 e R.4 M237. No R.1 M6141 o A3
    emite `valor_transacao = R$ 186.688,75` — o campo `VALOR: R$ 90.647,60,
    majorados para R$ 186.688,75` — e mantém o preço convencionado de
    `R$ 100.000,00` em `detalhes`; o banco grava `valor_transacao = null` nos dois
    lançamentos, perdendo os dois valores. `erro_confirmado`.
11. **Datas de documento:** M6141 grava 2024-01-01 com `data_presumida=false`;
    M237/M1754 gravam 2026-11-12 (cadastro) com presumida `t`. `erro_confirmado`
    (M6141) e `interpretacao_humana` (M237/M1754).
12. **OCR M237:** Av.6 com `forma` e `título` `normalized = null`; Av.7 com
    `título` normalizado como `PROTOCOLO nº 28.492` (não é título) e `forma`
    normalizada sem separar ato × escritura; a descrição da Av.6 perde a referência
    à matrícula 6.141; a Av.7 não emite a observação `ENCERRADA`. `divergencia_pendente`.
13. **OCR M6141/M237/M1754:** data do cabeçalho e da abertura com `normalized =
    null` (lacuna do A3 v1.2; correção em transistir/ocr-service#94). Falha de OCR
    não é dado documental. `divergencia_pendente`.
14. **Abertura sintética da M237** não corresponde a ato registral do documento;
    é interpretação do cadastro a partir do cabeçalho. `interpretacao_humana`.
15. **Observações analíticas na coluna documental** (R.4, Av.6, Av.7): texto de
    analista sem marcador de autoria (#400). `interpretacao_humana`.
19. **Descrição e data da transação não gravadas no banco:** a abertura da M6141,
    o R.1 M6141 (`O imóvel objeto desta matrícula.`) e o R.4 M237 (`IMÓVEL: Área
    de 38 ha. e 72 a. … do imóvel objeto desta matrícula.`) têm descrição no
    documento e `descricao = null` no banco; no R.1 M6141 a `data_transacao` da
    escritura (`10.04.2015`) também não é gravada. `erro_confirmado` (omissão).
20. **OCR M237 devolve `origem = null` na abertura — falha de extração.** O
    literal traz `TÍTULO AQUISITIVO: Transcrição de nº 1-1.754, do Cartório de
    Imóveis da Comarca de Prado-Ba`, mas o A3 v1.2 — que **tem** `origem` por ato
    (`tipo_documento`, `numero`, `cartorio`, `livro`, `folha`, `data`) e o preenche
    na abertura da M6141 (§2.1) — devolveu `origem = null` neste ato. Critério
    verificável do #86: `origem.tipo_documento.normalized = transcricao` (literal),
    `origem.numero.raw = 1-1.754`, `origem.cartorio` = Comarca de Prado-BA. O elo
    M237→M1754 existe como M1754 **só no banco**. `divergencia_pendente` (falha de
    extração no serviço, não lacuna de contrato). Divergência de tipo registrada
    junto: o documento rotula `Transcrição` e o banco modela `matrícula` M1754;
    `1-1.754` pode ser o R.1 da matrícula 1.754, no mesmo formato de
    `R. 1-6.141` — `divergencia_pendente`.

21. **Folha do cabeçalho da M237 gravada como `0`** contra `FLS 237` no literal
    (`MATRÍCULA Nº 237 LIVRO 2 FLS 237 DATA 09.06.1982`). Aqui não é placeholder:
    o documento traz a folha e o banco contradiz. `erro_confirmado`.
22. **Observação documental INCRA/FUNRURAL da abertura da M237 não gravada.** O
    documento traz a observação (`derivado: INCRA/FUNRURAL`) e o banco fica
    `n/d`. `erro_confirmado` (omissão).

### P2 — contexto e higiene

16. **Folha `0`** é placeholder só onde o literal não traz folha (M6141, cuja D é
    `n/d`), não valor documental. `interpretacao_humana`. Na M237 o mesmo `0`
    contradiz `FLS 237` — item 21, `erro_confirmado`.
17. **Cartório do cabeçalho da M237** no OCR sai genérico
    (`OFÍCIO DO REGISTRO DE IMÓVEIS E HIPOTECAS`) e com `municipio` mal parseado
    (`REGISTRO DE IMÓVEIS COMARCA DE`); os atos e o banco apontam Itamaraju.
    `divergencia_pendente`.
18. **M1754 (contexto):** 5 atos documentais ausentes no banco (R.1, R.2, R.3,
    Av.4, Av.5 — §4). Fora do aceite do #395. `erro_confirmado` (omissão).

---

## 7. Resumo por documento

| Documento | Atos no documento | Atos no banco | Ausentes | Células `erro_confirmado` | Células `divergencia_pendente` |
|---|---|---|---|---|---|
| M6141 | 2 (abertura + R.1) | 2 | 0 | 11 | 0 |
| M237 | 8 (abertura + 7 atos) | 5 (abertura sintética + 4 atos) | 3 (R.1, Av.2, Av.3) | 11 | 7 |
| M1754 | 6 | 1 (abertura sintética) | 5 | 3 | 0 |
| **Total** | **16** | **8** | **8** | **25** | **7** |

Contagem por célula das tabelas das seções 2, 3 e 4 (uma classe por célula;
`n/d` não conta). Campos com mais erros confirmados: `origem`
(cartório/data/livro/número), `area` (semântica), `forma`/`titulo`,
`eh_inicio_matricula`, descrição e data da transação, folha e observação omitidas
e atos ausentes. A ausência de `classificacao_fim_cadeia` **não** é erro (item 3).

---

## 8. OCR destravadas por esta matriz

Nenhuma issue é destravada apenas pela camada D: a transcrição do A3 v1.2 não
passou por conferência visual humana, exceto o cabeçalho da M237 (§9). As issues
abaixo usam células D e ficam condicionadas a essa conferência.

| Issue | Situação | Células entregues |
|---|---|---|
| [#72](https://github.com/transistir/ocr-service/issues/72) O-M237-06 | **destravada para fechamento no serviço**: os três inícios são emitidos com `eh_inicio_matricula=true` e evidência; a falha remanescente é de persistência no app (`false`) | não usa células D (camada O + banco) |
| [#83](https://github.com/transistir/ocr-service/issues/83) O-M237-01 | **destravada após conferência humana das células D usadas pela issue** | R.4 38,72 × 130,374; Av.6 74,6755 × 55,6985; Av.7 `94 ha. 41 a. 85 ca.` = 38,7200 + 55,6985 (conta); abertura 169,0940 |
| [#84](https://github.com/transistir/ocr-service/issues/84) O-M237-02 | **destravada após conferência humana das células D usadas pela issue** | pares D/O/B de `forma`, `titulo` e natureza em R.1, R.4, R.5, Av.6, Av.7 |
| [#85](https://github.com/transistir/ocr-service/issues/85) O-M237-03 | **destravada após conferência humana das células D usadas pela issue** | observações analíticas no banco × literais do documento em R.4, Av.6, Av.7 |
| [#86](https://github.com/transistir/ocr-service/issues/86) O-M237-04 | **destravada após conferência humana das células D usadas pela issue** | M6141 → R.5 M237 (livro 2, fls. 237, 06.05.2002); Av.6 → 6.141; título aquisitivo da M237 (`Transcrição de nº 1-1.754`, Comarca de Prado-BA) — o A3 v1.2 tem `origem` por ato e devolveu `null` neste ato (item 20: falha de extração; critério `tipo_documento = transcricao`, `numero.raw = 1-1.754`, `cartorio` = Prado-BA); cartório 1615 comprovadamente errado |
| [#87](https://github.com/transistir/ocr-service/issues/87) O-M237-05 | **destravada após conferência humana das células D usadas pela issue** | Av.6 (destaque de 74,6755) e Av.7 (`ENCERRADA`); requisito de OCR: emitir Av.7 como averbação com a observação `ENCERRADA` (item 12); a ausência de marcação de encerramento no banco é lacuna de cadastro (item 3), não de OCR |
| [#88](https://github.com/transistir/ocr-service/issues/88) O-M237-07 | **linha de base entregue; aceite bloqueado** | 8 atos medidos; P0 1–8 precisam de decisão antes do aceite; conferência humana das células D pendente |

---

## 9. O que não foi verificado

- **Conferência visual humana** página a página das digitalizações: as camadas D
  vêm do OCR A3 v1.2 (job registrado). **Exceção:** o cabeçalho da M237 (p.1) foi
  conferido visualmente em 25/11/2026 por Hiure — `MATRÍCULA Nº 237`, `LIVRO 2`,
  `FLS 237`, `DATA 09.06.1982`, e **sem** `14.905` na página. O restante segue sem
  conferência humana; células `erro_confirmado` valem contra o literal OCR.
- **`dominial_cartorios`**: liberada e consultada (393/483/1615/4293/4857), mas o
  nome do cartório da M237 no OCR não traz município; não foi inferido.
- **M1754** entrou apenas como contexto (§4); não foi medida como documento de
  aceite.
- Nenhuma escrita, migration, correção de dados ou deploy foi executada.
- O JSON completo (com PII e payloads) fica **fora do repositório** em
  `/root/.private/acervo-ocr/relatorios/`; o repositório guarda só este `.md`.

---

## 10. Correções das revisões de 25/11 (PR #407)

### 1ª revisão (v2): 7 must-fix

Revisão Opus de 25/11: REJECT com 7 must-fix. Todos foram endereçados no commit
`315dbe1d`. Em um deles (item 3) a evidência contradisse a premissa da revisão —
registrado abaixo com o literal que sustenta a correção.

| Must-fix | O que mudou |
|---|---|
| 1. P0 #3 não é fim de cadeia | P0 #3 reescrito como divergência de **cadastro** (`Av.7 ENCERRADA` sem marcação de encerramento); expressão "sem fim de cadeia" removida; célula D de `classificacao_fim_cadeia` da M237 virou `n/d`; §3.6 renomeada para "Encerramento"; item 12 e a linha #87 ajustados |
| 2. Camada D não é independente | Cabeçalho e §1.1 rotulam D como **transcrição do OCR A3 v1.2, sem conferência visual humana**; #83–#87 passam a "destravada após conferência humana das células D usadas pela issue" |
| 3. Elo M237→M1754 sem lastro | Aberto o item 20 (`divergencia_pendente`); a redação da v2 atribuía a lacuna ao contrato e foi **corrigida na 2ª revisão/v3** (abaixo): o A3 v1.2 tem `origem` por ato e o job devolveu `null`. **Premissa corrigida:** o número não aparece só no banco — o cabeçalho da M237 traz `TÍTULO AQUISITIVO: Transcrição de nº 1-1.754, do Cartório de Imóveis da Comarca de Prado-Ba`; o lastro é literal mas **parcial** (número + comarca, sem o rótulo M1754) e foi incorporado à §3.1. #86 deixou de exigir `M1754` e passa a exigir o título aquisitivo |
| 4. M1754 sem tabela própria | Incluída a §4 com D/O/B de cartório do cabeçalho, `eh_inicio_matricula`, data e atos ausentes, que sustentam P0 #2/#7/#11. O payload tem os dados: **nada foi rebaixado para P1 nem zerado** |
| 5. Paráfrase como literal | Coluna D: `escritura de 17.01.1995`, `área de 38,72 ha do imóvel`, `venda da área total` e `94,4185 = 38,7200 + 55,6985` viraram citação literal ou `derivado:`; convenção registrada em §1.1 |
| 6. Classes desuniformizadas | Forma Av.6 × Av.7: ambas `divergencia_pendente` (item 12); omissões de campo × atos omitidos: todas `erro_confirmado` (critério em §1.2); item 17 × célula do cartório da M237: ambas `divergencia_pendente`. A célula O da forma da Av.7 foi corrigida para o valor real do A3 (`raw = normalized = escritura pública de 07 de dezembro de 2016`) e o item 12 foi corrigido: quem tem `normalized = null` é a Av.6; a Av.7 normaliza o título como `PROTOCOLO nº 28.492` |
| 7. `erro_confirmado` sem item na §5 | Item 19 cobre as descrições omitidas (R.1 M6141 e R.4 M237); a forma da Av.7 deixou de ser `erro_confirmado` (item 6) e cai no item 12. Nenhuma célula `erro_confirmado` ficou sem item; contagens da §7 refeitas |

### Células por classe — 1ª revisão (v1 → v2)

| Documento | `erro_confirmado` antes | depois | `divergencia_pendente` antes | depois |
|---|---|---|---|---|
| M6141 | 8 | 8 | 0 | 0 |
| M237 | 9 | 9 | 4 | 7 |
| M1754 | 3 | 3 | 0 | 0 |
| **Total** | **20** | **20** | **4** | **7** |

Mudanças de célula na M237: +3 atos não cadastrados (§3.2, agora
`erro_confirmado`), −1 `classificacao_fim_cadeia` (virou `n/d`), −1 forma da Av.7
e −1 fim de cadeia (ambas viraram `divergencia_pendente`), +1 cartório do cabeçalho
(`dado_documental` → `divergencia_pendente`).

### 2ª revisão (v3): 3 must-fix

| Must-fix | O que mudou |
|---|---|
| 1. Item 20 errado sobre o contrato | Item 20 virou **falha de extração**: o A3 v1.2 tem `origem` por ato e devolveu `null` na abertura da M237; critério do #86 registrado; conflito de tipo (`Transcrição` × `matrícula` M1754) e a hipótese `1-1.754` = R.1 da matrícula 1.754 ficam como `divergencia_pendente`; frases "o A3 não emite origem no cabeçalho" removidas (§1.1, §3.1, §5, item 20) |
| 2. Regra da §1.2 violada | As 5 células apontadas passaram a `erro_confirmado`: origem—número `R. 5` (§2.1), descrição da abertura da M6141 (§2.1), data da transação do R.1 M6141 (§2.2), observação INCRA/FUNRURAL da M237 (§3.1) e folha `FLS 237` × `0` da M237 (§3). Itens 8 e 19 absorveram as omissões; itens 21 (folha) e 22 (observação) foram abertos; contagens da §7 refeitas |
| 3. Datas de atos inexistentes | §1.3: `B data` de R.1, Av.2 e Av.3 da M237 passou a `n/d` (ato não cadastrado, §3.2) |

Não bloqueantes aplicados: conferência visual do cabeçalho da M237 (25/11, p.1) em
§3.1/§9; item 3 e item 20 falam em título aquisitivo e "só no banco";
`hipoteca cedular de 2º grau` em crases; §1.2 explica registro × averbação; item 7
diz de qual campo é a confiança 1.0.

#### Células por classe — 2ª revisão (v2 → v3)

| Documento | `erro_confirmado` v2 | v3 | `divergencia_pendente` v2 | v3 |
|---|---|---|---|---|
| M6141 | 8 | 11 | 0 | 0 |
| M237 | 9 | 11 | 7 | 7 |
| M1754 | 3 | 3 | 0 | 0 |
| **Total** | **20** | **25** | **7** | **7** |

Mudanças de célula: +3 na M6141 (`origem`—número, descrição da abertura, data da
transação) e +2 na M237 (folha e observação), todas de `dado_documental`/
`interpretacao_humana` para `erro_confirmado`. Toda célula `erro_confirmado` tem
item: origem—número→item 8; descrição/data da transação→item 19; folha→item 21;
observação→item 22; as demais já tinham item na §6.
