# Matriz de referência da cadeia M6141 → M237

**Issue:** transistir/CadeiaDominial#395 (U-M237-01, P0) · **Série:** U-M237
**Status:** matriz medida (etapa 1 M6141 + etapa 2 M237). Não corrige dados.
**Base do repositório:** `origin/develop` @ `7ca71237` · **Data da medição:** 24/11/2026
**Especificação:** `docs/produto-3/ESPEC_MATRIZ_REFERENCIA_M6141_M237.md` (PR #405)

> A matriz mede o **ser** (documento × OCR × banco), não o dever-ser do contrato A3.
> Toda célula nomeia a camada de origem (D = documento, O = OCR, B = banco) e a
> evidência. Nenhum valor foi corrigido nem inferido. Artefato sem PII: partes
> aparecem como papel (`transmitente 1`, `adquirente 1`).

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

### 1.1 OCR usado como camada O

| Documento | `job_id` (OCR) | `meta.job_id` | Schema | Págs | Atos |
|---|---|---|---|---|---|
| M6141 | `34c2479557d44ec69d55eedd681b9209` | `15f199fa-51d0-49ce-a64f-f0b90a4452e8` | `umbelino-extracao-matricula-v1.2` | 1 | 2 |
| M237 | `be21a14f24ed4c9baadc3655a48fa4ca` | `769641e2-9484-414c-81c1-2855a161d35c` | `umbelino-extracao-matricula-v1.2` | 2 | 8 |
| M1754 | `fa0ec8b4f3a14c07bb50cdbb0bfeef0d` | `4a7c1a0e-…` (contexto) | `umbelino-extracao-matricula-v1.2` | 1 | 6 |

O job da M237 foi reexecutado em 24/11/2026 sobre o PDF de produção, porque a
`ExtracaoSugerida` 29 (job 25) não existe mais no banco de testes. O job da M6141 é
o artefato de homologação pós-`48d1660`. **Lacuna conhecida:** em ambos os jobs a
data do cabeçalho/abertura sai com `raw` preenchido e `normalized = null`; a
correção está em `t_34a673b9`. A matriz registra o `raw` e **não infere** a data.

### 1.2 Classes (fechadas)

`dado_documental` · `interpretacao_humana` · `calculo_derivado` · `erro_confirmado`
· `divergencia_pendente`.

Critério de `erro_confirmado` nesta matriz: a camada B contradiz de forma direta e
não ambígua o literal do documento (camada D) reproduzido na evidência. O literal
vem do OCR A3 v1.2; a conferência visual da digitalização permanece como etapa de
revisão humana registrada no rodapé. `n/d` = camada ausente, nunca célula vazia.

---

## 2. M6141 (documento 1086) — cabeçalho

| Campo | D | O | B | Evidência | Classe |
|---|---|---|---|---|---|
| Número | `6.141` | `6141` | `M6141` | p.1 `MATRÍCULA 6.141` | dado_documental |
| Livro / folha | `2` / n/d | `2` / n/d | `2` / `0` | p.1 `LIVRO Nº 2` | interpretacao_humana (folha placeholder) |
| Data do documento | `18.06.2015` (raw) | raw `18.06.2015`, norm. nulo | `2024-01-01`, presumida `f` | p.1 `DATA 18.06.2015` | erro_confirmado |
| Cartório | Itamaraju/BA | `CARTÓRIO … ITAMARAJU – BAHIA` | 393 | p.1 | dado_documental |
| `classificacao_fim_cadeia` | n/d | n/d | vazio | — | n/d |

### 2.1 Ato 1 — Abertura (M-6141), banco 14803

| Campo | D | O | B | Evidência | Classe |
|---|---|---|---|---|---|
| Título / natureza | abertura de matrícula | `inicio_matricula` | `inicio_matricula` | p.1 `MATRÍCULA 6.141` | dado_documental |
| Data do ato | `18.06.2015` (raw) | raw `18.06.2015`, norm. nulo | `2015-06-18` | p.1 `DATA 18.06.2015` | dado_documental (lacuna de normalização) |
| Área | `74 ha. 67 a. 55 ca.` | raw idem, norm. nulo | `74.6755` | p.1 | dado_documental |
| Origem — número | `R. 5, da matrícula 237` | `237` (matrícula) | `M237`; `LancamentoOrigem` matrícula 237 | p.1 `REGISTRO ANTERIOR: R. 5, da matrícula 237, livro nº 2, fls. 237, de 06.05.2002, deste Cartório.` | dado_documental (R.5 omitido) |
| Origem — livro/folha | `2` / `237` | `2` / `237` | n/d | idem | **erro_confirmado** (omissão) |
| Origem — data | `06.05.2002` | `2002-05-06` | `data_origem = 2015-06-18` | idem | **erro_confirmado** |
| `documento_origem_id` | elo textual | n/d | `NULL` | — | dado_documental (vínculo só textual) |
| `eh_inicio_matricula` | abertura | `true` | `false` | p.1 `MATRÍCULA 6.141` | **erro_confirmado** |
| Observação | INCRA/CCIR/NIRF | presente | texto analítico "Suposto destaque…" | p.1 | interpretacao_humana |
| Descrição | texto do imóvel | presente | n/d | p.1 | dado_documental |

### 2.2 Ato 2 — R.1 M6141, banco 14804

| Campo | D | O | B | Evidência | Classe |
|---|---|---|---|---|---|
| Número / tipo | `R. 1` / registro | `R-1` / registro | `R1 M6141` / registro | p.1 `R. 1-6.141` | interpretacao_humana (renumerado) |
| Data do ato | `18 de junho de 2015` | `2015-06-18` | `2015-06-18` | p.1 | dado_documental |
| Forma | `Escritura pública de 10 de abril de 2015` | idem | `Compra e Venda` | p.1 | **erro_confirmado** (forma × título) |
| Título | `Venda e Compra` | idem | `Escritura pública` | p.1 | **erro_confirmado** (forma × título) |
| Descrição | `O imóvel objeto desta matrícula.` | idem | n/d | p.1 | erro_confirmado (omissão) |
| Detalhes / valor | preço `R$ 100.000,00`; valor `R$ 186.688,75` | `186688.75` | n/d | p.1 | erro_confirmado (omissão) |
| Livro / folha / data da transação | `02` / `116 a 117` / `10.04.2015` | `02` / `116 a 117` / `2015-04-10` | `02` / `116-117` / n/d | p.1 | dado_documental (data ausente) |
| Cartório da transmissão | Cachoeira do Mato | idem | 4857 | p.1 | dado_documental |

---

## 3. M237 (documento 4980) — cabeçalho

| Campo | D | O | B | Evidência | Classe |
|---|---|---|---|---|---|
| Número | `237` | `237` | `M237` | p.1 `MATRÍCULA Nº 237` | dado_documental |
| Livro / folha | `2` / `237` | `2` / `237` | `2` / `0` | p.1 `LIVRO 2 FLS 237` | interpretacao_humana (folha placeholder) |
| Data do documento | `09.06.1982` (raw) | raw idem, norm. nulo | `2026-11-12`, presumida `t` | p.1 `DATA 09.06.1982` | interpretacao_humana (data de cadastro) |
| Cartório | Itamaraju/BA (atos) | `OFÍCIO DO REGISTRO DE IMÓVEIS E HIPOTECAS` | 393 | p.1–2 | dado_documental (rótulo OCR genérico) |
| `classificacao_fim_cadeia` | `ENCERRADA` (Av.7) | n/d | vazio | p.2 | **erro_confirmado** |

### 3.1 Ato 1 — Abertura sintética (M-237), banco 14805

| Campo | D | O | B | Evidência | Classe |
|---|---|---|---|---|---|
| Natureza | cabeçalho da matrícula | `inicio_matricula` | `inicio_matricula` | p.1 | interpretacao_humana (não é ato registral) |
| Data | `09.06.1982` (raw) | raw idem, norm. nulo | `1982-06-09` | p.1 | dado_documental |
| Área | `169 hectares, 09 ares e 40 centiares` | raw idem, norm. nulo | `169.0940` | p.1 | dado_documental |
| Origem | não há "REGISTRO ANTERIOR" literal | só menção a Prado-BA | `M1754` em cartório **1615** | p.1; M1754 p.1 | **erro_confirmado** (cartório) |
| `eh_inicio_matricula` | abertura | `true` | `false` | p.1 | **erro_confirmado** |
| Observação | INCRA/FUNRURAL | presente | n/d | p.1 | dado_documental (omissão) |

### 3.2 Atos 2–4 — R.1, Av.2 e Av.3 (ausentes no banco)

| Ato | D (literal) | O | B | Classe |
|---|---|---|---|---|
| R.1 | `R: 1-237 – Itamaraju, 09 de junho de 1982`; `Cr$ 1.525.273,12`; livro 3, fls. 194 | presente | **n/d** | dado_documental (ato não cadastrado) |
| Av.2 | `Av: 2-237 – Itamaraju, 19 de dezembro de 1983`; Cédula Rural Hipotecária; `Cr$ 2.504.829,00` | presente | **n/d** | dado_documental (ato não cadastrado) |
| Av.3 | `Av: 3-237 – … 08 de outubro de 1986`; cancela o `R: 1-237` | presente | **n/d** | dado_documental (ato não cadastrado) |

### 3.3 Ato 5 — R.4 M237, banco 14843

| Campo | D | O | B | Evidência | Classe |
|---|---|---|---|---|---|
| Forma / título | escritura de 17.01.1995 / `Compra e venda` | idem | `Compra e Venda` / `Escritura pública` | p.1 | **erro_confirmado** (invertidos) |
| Área | `38 ha. e 72 a.` (transmitida) | idem | `130.3740` (remanescente) | p.1 `IMÓVEL: Área de 38 ha. e 72 a.` | calculo_derivado (semântica invertida) |
| Valor | `R$ 20.000,00 majorado para R$ 25.000,00` | raw idem, norm. nulo | n/d | p.2 | erro_confirmado (omissão) |
| Descrição | área de 38,72 ha do imóvel | idem | n/d | p.1 | erro_confirmado (omissão) |
| Observação | CND FUNRURAL/IAPAS | idem | texto analítico "Segundo o R4 M237…" | p.2 | interpretacao_humana (#400) |
| Detalhes | Receita Federal 1302524-4; "CONJUNTO SÃO JOSÉ" | idem | idem | p.2 | dado_documental |
| Livro / folha / cartório | `87` / `41/42` / Tabelionato de Itamaraju | idem | `87` / `41-42` / 4293 | p.1 | dado_documental |

### 3.4 Ato 6 — R.5 M237, banco 14844

| Campo | D | O | B | Evidência | Classe |
|---|---|---|---|---|---|
| Forma / título | escritura de 25.04.2002 / `Compra e venda` | idem | `Compra e Venda` / `Escritura pública` | p.2 | **erro_confirmado** (invertidos) |
| Área | `130 ha. 37 a. e 40 ca.` | idem | `130.3740` | p.2 | dado_documental |
| Valor | `R$ 47.100,00` | `47100.00` | `47100.00` | p.2 | dado_documental |
| Livro / folha / cartório | `14` / `80/81` / Tabelionato de Itamaraju | idem | `14` / `80-81` / 4293 | p.2 | dado_documental |
| Data da transação | escritura de 25.04.2002 | `2002-05-06` | `2002-05-06` | p.2 | divergencia_pendente (OCR não separa ato × escritura) |

### 3.5 Ato 7 — Av.6 M237, banco 14845

| Campo | D | O | B | Evidência | Classe |
|---|---|---|---|---|---|
| Forma | `Por escritura pública de 10 de abril de 2015` | raw `Escritura Pública`, norm. nulo | `Compra e venda` | p.2 | divergencia_pendente |
| Título | `Escritura Pública de 10 de abril de 2015` | raw idem, norm. nulo | n/d | p.2 | divergencia_pendente |
| Área | `74 ha. 67 a. 55 ca.` (destacada) | idem | `55.6985` (remanescente) | p.2 | calculo_derivado (semântica invertida) |
| Descrição / vínculo | "registrada … sob o nº 1, da matrícula 6.141 … em 18.06.2015" | campo só com partes | texto analítico com `6.141` | p.2 | interpretacao_humana (OCR perde o vínculo) |
| Valor | `R$ 45,08` | `45.08` | `45.08` | p.2 | dado_documental |
| Livro / folha / cartório | `02` / `116 a 117` / Cachoeira do Mato | idem | idem / 4857 | p.2 | dado_documental |

### 3.6 Ato 8 — Av.7 M237, banco 15072

| Campo | D | O | B | Evidência | Classe |
|---|---|---|---|---|---|
| Forma | `escritura pública de 07 de dezembro de 2016` | idem | `Compra e venda` | p.2 | **erro_confirmado** |
| Título | não há "TÍTULO" no ato | `PROTOCOLO nº 28.492` | `Compra e venda` | p.2 | divergencia_pendente |
| Área | `94 ha. 41 a. 85 ca.` = 38,7200 + 55,6985 | idem | n/d | p.2 | calculo_derivado (soma; campo vazio) |
| Descrição | venda da área total a adquirente 1 | só partes | resumo analítico | p.2 | interpretacao_humana |
| Observação / fim | `ficando ENCERRADA a presente escrituração` | n/d | texto analítico de encerramento | p.2 | dado_documental (D) / interpretacao_humana (B) |
| Fim de cadeia | encerrada | n/d | `classificacao_fim_cadeia` vazio; `origemfimcadeia` vazio | p.2 | **erro_confirmado** |
| Valor | `R$ 49,76` | `49.76` | `49.76` | p.2 | dado_documental |
| Livro / folha / cartório | `34` / `037/038` / Itagimirim | idem | idem | p.2 | dado_documental |

---

## 4. Relação M6141 ↔ M237

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

---

## 5. Divergências priorizadas

Prioridade = impacto na cadeia/aceite. Cada item tem **uma** classe.

### P0 — bloqueiam o aceite da M237

1. **Cartório da origem M237 → M1754 errado (1615 Prados/MG).** O documento M1754
   é do Registro de Imóveis de **Prado/BA**; o próprio lançamento de abertura da
   M1754 cita `T10090` no cartório **483**. `interpretacao` gravada como
   `erro_confirmado`.
2. **Cabeçalho do documento 4981 (M1754) aponta cartório 1615**, contradizendo o
   PDF (`REGISTRO DE IMÓVEIS HIPOTECAS PRADO - BAHIA`) e sua própria origem.
   `erro_confirmado`.
3. **M237 sem fim de cadeia:** Av.7 diz `ENCERRADA`; `documento.classificacao_fim_cadeia`
   e `dominial_origemfimcadeia` estão vazios. `erro_confirmado`.
4. **M6141 `data_origem` = 2015-06-18**, mas o registro anterior é de **06.05.2002**.
   `erro_confirmado`.
5. **Áreas com semântica invertida:** R.4 (B 130.3740 remanescente × D 38,72
   transmitida), Av.6 (B 55.6985 remanescente × D 74,6755 destacada) e Av.7 (B
   vazio × D 94,4185 = 38,7200 + 55,6985). `calculo_derivado`.
6. **R.1, Av.2 e Av.3 da M237 não cadastrados** (3 atos). `dado_documental`.
7. **`eh_inicio_matricula = false` nos três inícios** (M6141, M237, M1754), embora
   o OCR v1.2 emita `true` com evidência do cabeçalho. `erro_confirmado`.
8. **Origem da M6141 sem livro/folha e sem o ato R.5** no banco. `erro_confirmado`.

### P1 — qualidade e contrato A3

9. **Forma e título invertidos** em R.1 M6141, R.4 e R.5 M237. `erro_confirmado`.
10. **Valores de transação ausentes** em R.1 M6141 e R.4 M237. `erro_confirmado`.
11. **Datas de documento:** M6141 grava 2024-01-01 com `data_presumida=false`;
    M237/M1754 gravam 2026-11-12 (cadastro) com presumida `t`. `erro_confirmado`
    (M6141) e `interpretacao_humana` (M237/M1754).
12. **OCR M237:** forma/título de Av.6 e Av.7 com `normalized = null`; descrição da
    Av.6 perde a referência à matrícula 6.141; Av.7 não emite a observação
    `ENCERRADA`. `divergencia_pendente`.
13. **OCR M6141:** data do cabeçalho e da abertura com `normalized = null`
    (lacuna conhecida, `t_34a673b9`). `dado_documental` (raw registrado).
14. **Abertura sintética da M237** não corresponde a ato registral do documento;
    é interpretação do cadastro a partir do cabeçalho. `interpretacao_humana`.
15. **Observações analíticas na coluna documental** (R.4, Av.6, Av.7): texto de
    analista sem marcador de autoria (#400). `interpretacao_humana`.

### P2 — contexto e higiene

16. **Folha `0`** nos três documentos é placeholder, não valor documental.
    `interpretacao_humana`.
17. **Cartório do cabeçalho da M237** no OCR sai genérico
    (`OFÍCIO DO REGISTRO DE IMÓVEIS E HIPOTECAS`), sem município; os atos e o banco
    apontam Itamaraju. `divergencia_pendente` (rótulo OCR).
18. **M1754 (contexto):** 5 atos documentais ausentes no banco (R.1, R.2, R.3,
    Av.4, Av.5). Fora do aceite do #395. `dado_documental`.

---

## 6. Resumo por documento

| Documento | Atos no documento | Atos no banco | Ausentes | Células `erro_confirmado` | Células `divergencia_pendente` |
|---|---|---|---|---|---|
| M6141 | 2 (abertura + R.1) | 2 | 0 | 8 | 0 |
| M237 | 8 (abertura + 7 atos) | 5 (abertura sintética + 4 atos) | 3 (R.1, Av.2, Av.3) | 9 | 4 |
| M1754 | 6 | 1 (abertura sintética) | 5 | 3 | 0 |

Campos com mais erros confirmados: `origem` (cartório/data/livro), `area`
(semântica), `forma`/`titulo`, `eh_inicio_matricula`, `classificacao_fim_cadeia`.

---

## 7. OCR destravadas por esta matriz

| Issue | Situação | Células entregues |
|---|---|---|
| [#72](https://github.com/transistir/ocr-service/issues/72) O-M237-06 | **destravada para fechamento no serviço**: os três inícios são emitidos com `eh_inicio_matricula=true` e evidência; a falha remanescente é de persistência no app (`false`) | abertura M6141/M237/M1754 |
| [#83](https://github.com/transistir/ocr-service/issues/83) O-M237-01 | **destravada** | R.4 38,72 × 130,374; Av.6 74,6755 × 55,6985; Av.7 94,4185 = 38,7200 + 55,6985; abertura 169,0940 |
| [#84](https://github.com/transistir/ocr-service/issues/84) O-M237-02 | **destravada** | pares D/O/B de `forma`, `titulo` e natureza em R.1, R.4, R.5, Av.6, Av.7 |
| [#85](https://github.com/transistir/ocr-service/issues/85) O-M237-03 | **destravada** | observações analíticas no banco × literais do documento em R.4, Av.6, Av.7 |
| [#86](https://github.com/transistir/ocr-service/issues/86) O-M237-04 | **destravada** | M6141 → R.5 M237 (livro 2, fls. 237, 06.05.2002); Av.6 → 6.141; cartório 1615 comprovadamente errado |
| [#87](https://github.com/transistir/ocr-service/issues/87) O-M237-05 | **destravada** | Av.6 (destaque de 74,6755) e Av.7 (`ENCERRADA`); ausência de classificação no banco |
| [#88](https://github.com/transistir/ocr-service/issues/88) O-M237-07 | **linha de base entregue; aceite bloqueado** | 8 atos medidos; P0 1–8 precisam de decisão antes do aceite |

---

## 8. O que não foi verificado

- **Conferência visual humana** página a página das digitalizações: as camadas D
  vêm do OCR A3 v1.2 (job registrado). Células marcadas `erro_confirmado` valem
  contra o literal OCR; a revisão humana do scan ainda é etapa separada.
- **`dominial_cartorios`**: liberada e consultada (393/483/1615/4293/4857), mas o
  nome do cartório da M237 no OCR não traz município; não foi inferido.
- **M1754** entrou apenas como contexto; não foi medida como documento de aceite.
- Nenhuma escrita, migration, correção de dados ou deploy foi executada.
- O JSON completo (com PII e payloads) fica **fora do repositório** em
  `/root/.private/acervo-ocr/relatorios/`; o repositório guarda só este `.md`.
