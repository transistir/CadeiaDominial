# Especificação — matriz de referência da cadeia M6141 → M237

**Issue:** transistir/CadeiaDominial#395 (U-M237-01, P0) · **Série:** U-M237
**Status deste documento:** especificação de insumo (somente leitura). Não é a matriz.
**Base:** `origin/develop` @ `7ca71237` · **Data:** 24/11/2026
**Escopo:** definir campos, fontes read-only, formato do artefato, aceite, riscos e
dependências para construir `docs/produto-3/MATRIZ_REFERENCIA_M6141_M237.md`.

> Regra-mãe: a matriz mede o **ser** (documento × OCR × banco), não o **dever-ser**
> do contrato A3 (`docs/produto-3/PLANO_INTEGRACAO_OCR_UMBELINO.md` §2). Cada célula
> precisa nomear a camada de origem do valor e a evidência.

---

## 1. Campos que a matriz precisa cobrir

A unidade da matriz é **uma célula = (documento, ato, campo)**. Nenhuma célula existe
sem documento e ato identificados. A matriz cobre três documentos em cadeia
(M6141 → M237 → M1754), mas a Etapa 1 e o aceite do #395 fecham em M6141 + M237;
a M1754 entra como contexto da origem (`T10090`).

### 1.1 Colunas de identificação (por linha/ato)

| Coluna | Fonte canônica | Regra |
|---|---|---|
| Documento e elo | `dominial_documento.id` + `numero` | `M6141 (atual)` / `M237 (antecedente)` / `M1754 (contexto)` |
| Ato e ordem registral | `dominial_lancamento.numero_lancamento` | preservar a redação do documento (`R.4`, `Av.6`, `Abertura`), não renumerar |
| Tipo de ato | `dominial_lancamentotipo.tipo` | `registro` / `averbacao` / `inicio_matricula` |
| Data do ato | `dominial_lancamento.data` | data do ato, nunca a data do documento nem `data_cadastro` |
| `data_presumida` | `dominial_documento.data_presumida` | registrar; explica data de cadastro usada como data |
| Evidência | `evidencia_pagina`, `evidencia_trecho`, `evidencia_bbox` | página + trecho literal; bbox quando o job fornecer |

### 1.2 Campos por campo (o mesmo conjunto para todo ato)

| Campo da matriz | Coluna no banco | Coluna OCR (`CampoSugerido`) | Observação |
|---|---|---|---|
| Forma | `lancamento.forma` | `chave` do campo + `raw`/`normalized` | texto do ato, sem normalizar para o dicionário |
| Título | `lancamento.titulo` | idem | escritura/formal/transcrição com livro e folhas |
| Natureza / tipo | `lancamentotipo.tipo` | `tipo_valor='ato'` | distingue registro × averbação × abertura |
| Descrição | `lancamento.descricao` | idem | texto documental do ato (não interpretação) |
| Observação | `lancamento.observacoes` | idem | separar observação documental de analítica (#400) |
| Detalhes | `lancamento.detalhes` | idem | texto livre legado; marcar quando for cópia da descrição |
| Área (valor) | `lancamento.area` (`Decimal(12,4)`) | `raw`, `normalized`, `area_convertida` | guardar valor lido com unidade e o convertido em ha/4 casas |
| Unidade / semântica da área | — (derivado) | — | rotular **original**, **transmitida**, **destacada** ou **remanescente** (ver O-M237-01) |
| Valor da transação | `lancamento.valor_transacao` | `raw`/`normalized` | moeda e data do documento; não converter |
| Origem — tipo | `lancamentoorigem.tipo_documento` | — | `matricula` / `transcricao` |
| Origem — número | `lancamentoorigem.numero` + `numero_normalizado` | idem | preservar prefixos (`M`, `T`, `R.`) |
| Origem — cartório | `lancamentoorigem.cartorio_id` | — | id + nome/comarca quando `dominial_cartorios` estiver liberado |
| Origem — livro / folha | `lancamentoorigem.livro`, `.folha` | — | opcionais no contrato (#63) |
| Origem legada (texto) | `lancamento.origem` + `cartorio_origem_id` | — | registrar a redação literal; é o que a cadeia usa hoje |
| Vínculo ao documento de origem | `lancamento.documento_origem_id` | — | registrar `NULL` explicitamente (hoje é o caso em todos os 8 atos) |
| Referências a outras matrículas | `lancamentoorigem` + texto do ato | `raw` | número + cartório citados; número ambíguo fica **pendente** |
| Livro/folha da transação | `livro_transacao`, `folha_transacao`, `data_transacao` | — | separados dos campos de origem |
| Cartório da transação | `cartorio_transmissao_id` (novo) / `cartorio_transacao_id` (legado) | — | registrar qual coluna respondeu |
| `eh_inicio_matricula` | `lancamento.eh_inicio_matricula` | — | registrar o valor gravado; abertura de matrícula é o único ato com origem |
| Fim de cadeia | `documento.classificacao_fim_cadeia`; `origemfimcadeia.fim_cadeia`/`tipo_fim_cadeia`/`classificacao_fim_cadeia`; catálogo `fimcadeia` | — | encerramento da M237 (Av.7) é caso de teste; catálogo só rotula, não guarda o vínculo |
| Cabeçalho do documento | `numero`, `livro`, `folha`, `cartorio_id`, `cri_atual_id`, `cri_origem_id`, `data`, `data_cadastro` | — | ficha × folha é pendência semântica (P1) |
| OCR — confiança e revisão | — | `confianca`, `requer_revisao`, `motivos_revisao`, `status_revisao`, `valor_final`, `escolha_explicita` | registrar `job_id` e `extracao_id` no cabeçalho |
| OCR — evidência | — | `evidencia_pagina`, `evidencia_trecho`, `evidencia_bbox` | bbox só quando o serviço devolver |
| Classificação da célula | — | — | exatamente uma das 5 classes (§4.1) |

### 1.3 Campos proibidos no artefato

`transmitente_id` / `adquirente_id` e qualquer coluna de `dominial_pessoas`
(`nome`, documentos). Partes entram, se o dono pedir, como papel: `transmitente 1`,
`adquirente 1`. Nunca CPF/RG, nunca dump, nunca PDF anexado ao repositório.

### 1.4 Regras de medição

1. A célula registra **três camadas**: documento (D), OCR (O), banco (B). Ausência
   de camada é célula `n/d`, não célula vazia.
2. Ato existente no documento e ausente no banco é linha própria com classe
   `dado documental` e anotação "ato não cadastrado" (R.1/Av.2/Av.3 da M237;
   Av.1–Av.5 da M1754).
3. Ato existente no banco e ausente no documento é `erro confirmado` somente após
   conferência do PDF; até lá, `divergência pendente`.
4. Não transferir achados entre documentos (M6141 e M237 foram medidos por jobs
   diferentes).
5. Nenhuma célula "corrigida" na planilha: a matriz mostra, não conserta.

---

## 2. Fontes read-only necessárias

### 2.1 Tabelas (produção, somente `SELECT`)

Já legíveis pelo usuário de inventário (`inventario_ro`):
`dominial_documento`, `dominial_documentodigital`, `dominial_documentotipo`,
`dominial_imovel`, `dominial_lancamento`, `dominial_lancamentotipo`,
`dominial_origemfimcadeia`, `dominial_tis`, `dominial_tis_imovel`.

Faltam para fechar a matriz (grants de `SELECT` a conceder pelo dono, sem alterar
privilégios existentes):

| Tabela | Por quê |
|---|---|
| `dominial_cartorios` | identificar 393 (Itamaraju?), 1615 e 483 (Prado) e resolver P5/P6/P7 |
| `dominial_lancamentoorigem` | múltiplas origens por ato, `indice_origem`, livro/folha por origem |
| `dominial_fimcadeia` | catálogo de tipos de fim de cadeia (`nome`, `tipo`, `classificacao`, `sigla`); o estado por documento/ato fica em `documento.classificacao_fim_cadeia` e em `dominial_origemfimcadeia` (esta já legível) |

Não liberar: `dominial_pessoas`, `dominial_lancamentopessoa` (PII).

### 2.2 Regras de acesso

- Sessão/transação `READ ONLY` (`SET TRANSACTION READ ONLY` / `default_transaction_read_only = on`).
- Consultas **por ID** (TI 67, imóvel 283, documentos 1086/4980/4981, cartórios
  393/1615/483) e por número + cartório. Sem varredura ampla, sem `COPY` de tabela.
- Nenhuma migration, script de correção, `UPDATE`, `ALTER`, grant auto-aplicado.
- Execução mediada e autorizada pelo dono; credencial fora do repositório.
- Exportação minimizada (alternativa aceita pela issue): CSV/JSON por tabela,
  filtrado pelos IDs acima, com colunas de PII removidas na origem
  (`SELECT id, ...` explícito, nunca `SELECT *`).

### 2.3 PDFs e OCR

- PDFs: M6141 (1 pág.), M237 (2 págs.), M1754 (1 pág.), conferidos por SHA-256.
  São digitalizações **sem camada de texto** — a leitura é visual/OCR.
- Produção **não tem** tabelas `ia_ocr_*`: as colunas OCR da matriz só podem ser
  preenchidas no ambiente de testes, com job próprio e registro do `job_id`;
  ou por execução direta no serviço, como no job `ab1e944554de4599b545fe4046084a0d`
  (M6141), cujos artefatos são privados e não recuperáveis pela API pública
  (`/v1/ocr/jobs/<id>` → `JOB_NOT_FOUND` no commit `5382fc6`).
- Consequência: qualquer job novo precisa ter **payload bruto, texto por página,
  `raw`/`normalized` e bbox exportados no momento da execução** para armazenamento
  privado; o repositório guarda só o `job_id` e o hash.
- M237 já tem `ExtracaoSugerida` 29 (job 25, documento digital 363, schema v1.2,
  provider `workers-ai`) no ambiente de testes.

---

## 3. Formato do artefato e versionamento

### 3.1 Entregável principal (obrigatório pela issue)

`docs/produto-3/MATRIZ_REFERENCIA_M6141_M237.md`, versionado no repositório, com:

1. cabeçalho de proveniência: data da consulta, usuário read-only, `job_id` do OCR
   por documento, SHA-256 dos PDFs (prefixo), IDs de TI/imóvel/documentos/cartórios;
2. matriz por documento → ato → campo (D / O / B / evidência / classe);
3. seção **"Relação M6141 ↔ M237"** com a redação literal da referência, página,
   e a leitura que a evidência sustenta — ou `pendente`;
4. resumo: nº de atos por documento, células por classe, campos com mais erros
   confirmados, pendências abertas;
5. rodapé com o que **não** foi verificado (ex.: `dominial_cartorios` bloqueada).

### 3.2 Companheiro legível por máquina (recomendado, opcional)

Se houver volume, versionar ao lado um `MATRIZ_REFERENCIA_M6141_M237.json`:

```json
{
  "schema": "matriz-referencia/1",
  "gerado_em": "2026-11-24",
  "fonte_banco": {"modo": "read-only", "consulta": "2026-11-24"},
  "documentos": [
    {"elo": "atual", "numero": "M6141", "documento_id": 1086,
     "ocr_job": "ab1e944554de4599b545fe4046084a0d",
     "atos": [
       {"ordem": "Abertura", "tipo": "inicio_matricula", "data": "2015-06-18",
        "campos": [
          {"campo": "area", "documento": {"valor": "74,6755", "unidade": "ha", "semantica": "destacada"},
           "ocr": {"raw": null, "normalized": null, "confianca": null},
           "banco": {"coluna": "lancamento.area", "valor": "74.6755"},
           "evidencia": {"pagina": 1, "trecho": "...", "bbox": null},
           "classe": "dado_documental"}
        ]}
     ]}
  ],
  "relacao_m6141_m237": {"status": "confirmada", "evidencia": "..."},
  "pendencias": []
}
```

Enums fechados: `classe` ∈ {`dado_documental`, `interpretacao_humana`,
`calculo_derivado`, `erro_confirmado`, `divergencia_pendente`};
`elo` ∈ {`atual`, `antecedente`, `contexto`}.

### 3.3 Onde versionar e o que nunca versionar

- Versionar **somente** o `.md` (e o `.json` sanitizado) em `docs/produto-3/`,
  via branch própria a partir de `develop` e PR para `develop`.
- Fora do repositório (armazenamento privado do dono): PDFs, páginas renderizadas,
  recortes de bbox, payloads brutos de OCR, CSV de exportação, logs de consulta.
- No repositório: `job_id`, prefixo de SHA-256, contagens, trechos literais curtos
  sem nome de pessoa. Trocar nomes por papel.
- A matriz não é gabarito de dados nem base para correção automática; é evidência.

---

## 4. Critérios de aceite e riscos

### 4.1 Classes (fechadas, sem "outros")

`dado documental` · `interpretação humana` · `cálculo derivado` · `erro confirmado`
· `divergência pendente`.

### 4.2 Aceite

- [ ] TI 67 (Barra Velha/BA), imóvel 283 (Fazenda Condessa) e documento 1086
      (M6141) identificados por ID, com o comando/consulta registrado.
- [ ] M237 localizada por **número + cartório** (doc 4980, cartório 393) a partir
      da referência literal da M6141, não por busca só de número.
- [ ] Todos os lançamentos dos dois documentos listados, com contagem exata
      (M6141: 2; M237: 5 cadastrados + 3 documentais ausentes, se confirmado)
      e ordem registral.
- [ ] Toda célula traz camada (D/O/B) e evidência (página + trecho) quando existir;
      ausência de camada marcada como `n/d`.
- [ ] Toda divergência em exatamente uma das 5 classes.
- [ ] Seção "Relação M6141 ↔ M237" com redação literal, página e leitura — ou
      `pendente` explícito.
- [ ] Nenhuma conclusão de erro cadastral sem prova documental; nenhum número
      ambíguo "corrigido".
- [ ] Cabeçalho com data da consulta, `job_id` do OCR e SHA-256 dos PDFs.
- [ ] Zero PII, zero credencial, zero dump no artefato.
- [ ] Pendências de acesso listadas com a tabela bloqueada e a decisão pendente.

### 4.3 Riscos

| Risco | Mitigação |
|---|---|
| Vazamento de PII em trecho/descrição | mascarar na extração; revisão dedicada antes do commit; nunca anexar PDF |
| OCR de scan sem camada de texto gerar ruído e virar "erro confirmado" | classe `divergencia pendente` até conferência visual da página |
| Assumir que a matriz é gabarito e "corrigir" o banco | regra de não-escrita; correção é issue separada com autorização |
| Número de origem ambíguo (M237 × T237) | sempre número + cartório; ambíguo fica pendente |
| `documento_origem_id` nulo fazer a cadeia parecer inexistente | registrar o vínculo textual (`lancamento.origem` + `cartorio_origem_id`) como elo real |
| Tabelas bloqueadas (`cartorios`, `lancamentoorigem`, `fimcadeia`) | declarar pendência; não inferir nome de cartório |
| Dois artefatos OCR distintos (job direto × `ExtracaoSugerida`) | coluna de proveniência por documento com `job_id`/`extracao_id` |
| Drift entre PDF e banco após a consulta | registrar data/hora da consulta e SHA do export |
| Matriz confundida com o contrato A3 | separar explicitamente "ser" (matriz) de "dever-ser" (contrato) |

---

## 5. Dependências com a série O-M237 (ocr-service)

A matriz é **insumo** de todas; nenhuma delas pode ser fechada "por leitura de código".

| OCR issue | Tema | Células da matriz que alimenta | Direção |
|---|---|---|---|
| [#83](https://github.com/transistir/ocr-service/issues/83) O-M237-01 (P0) | área destacada × remanescente × original | `area`, `area_convertida`, semântica da área, Av.6 (74,6755 saem / 55,6985 ficam), R.4 (38,72 × 130,374), M1754 (169,0940) | matriz → issue |
| [#84](https://github.com/transistir/ocr-service/issues/84) O-M237-02 | forma × título × natureza do ato | `forma`, `titulo`, `lancamentotipo`, Av.6 "Compra e venda" sem título | matriz → issue |
| [#85](https://github.com/transistir/ocr-service/issues/85) O-M237-03 | descrição documental × observação interpretativa | `descricao`, `observacoes`, `detalhes`, marcador de autoria (#400) | matriz → issue |
| [#86](https://github.com/transistir/ocr-service/issues/86) O-M237-04 | referências registrais sem vínculo incorreto | `lancamentoorigem.*`, `lancamento.origem`, `cartorio_origem_id`, `documento_origem_id` | matriz → issue |
| [#87](https://github.com/transistir/ocr-service/issues/87) O-M237-05 | averbações de esclarecimento/desmembramento/encerramento | Av.6, Av.7, `classificacao_fim_cadeia`, `dominial_fimcadeia` | matriz → issue |
| [#72](https://github.com/transistir/ocr-service/issues/72) O-M237-06 | extração não emite início de matrícula | abertura dos três documentos, `eh_inicio_matricula`, contrato `act.origens[]` (#63) | matriz → issue |
| [#88](https://github.com/transistir/ocr-service/issues/88) O-M237-07 (P1) | avaliação integrada / aceitação da M237 | matriz inteira como linha de base de aceite | matriz → aceite |

Dependências do lado do app (série U-M237):

- **#395 (esta especificação)** — não depende de nada; destrava #397, #325, #393, #398.
- **#396 (U-M237-02)** — área perde magnitude. **Fechada e mergeada** em
  `7ca71237`; a matriz deve ser montada sobre o parser novo, e qualquer área antiga
  gravada com magnitude errada deve aparecer como célula medida, não como prova do bug.
- **#397 (U-M237-03)** — validação semântica dos campos da revisão: consome as
  células `forma`/`titulo`/`descricao`/`observacoes`/`area`.
- **#325 (I-11e)** — aceite do bloco no M237: consome a matriz como linha de base.
- **#393** — persistência parcial em `revisar_ato_duplicata_ocr`: usa as células de
  vínculo/origem para provar convivência com cadeias compartilhadas (M1754 em 4 imóveis).
- **#398 (U-M237-06)** — proveniência das sugestões: exige que a matriz registre
  `job_id`/`extracao_id`/`provider`/`schema_version` por documento.
- **#400 / #401 / #402** — observações com autoria, base de exemplos e aprendizado:
  consomem as células de classe `interpretação humana` como pares sugestão × final.

Ordem acordada (Q3, comentário de 23/11): **Etapa 1 (M6141)** → **#396** (já mergeada)
→ **Etapa 2 (M237)**. A matriz não pode ser publicada com achados de M237 antes da
Etapa 2, nem transferir achados de um documento para o outro.

---

## 6. O que esta especificação deliberadamente não faz

- Não acessa produção, não roda SQL, não lê PDF privado, não altera código ou banco.
- Não decide se atos não transmissivos (R.1/hipoteca, Av.2, Av.3, Av.1–Av.5 da M1754)
  devem ser importados — é decisão de produto, registrada como pendência.
- Não substitui a leitura documental já feita nos comentários da #395; consolida os
  requisitos que faltavam para transformá-la em matriz fechada e auditável.
