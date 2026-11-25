# Arquitetura e plano — OCR assistido (pós-reunião de 23/11/2026)

> **Status:** plano aprovado pelo dono em 23/11/2026 (Q1=b, Q2 e Q3 abaixo).
> **Natureza:** documento de arquitetura e fila — **sem implementação, sem
> migration, sem deploy** nesta rodada.
> **Base verificada:** `origin/develop` `3f70c8e1` (CadeiaDominial) e
> `origin/main` `5382fc6` (ocr-service), ambos em 23/11/2026.
> **Escopo:** trilha OCR assistido (F3/FUNAPE + I-14). Não reordena R4–R10;
> entra como sub-trilha da F3 (ver `ROADMAP.md`, seção F3.1).

## 1. Decisões do dono (23/11/2026)

| # | Decisão | Consequência para o plano |
|---|---|---|
| D1 | Registrar **todos** os atos do documento, inclusive os não transmissivos | A extração não pode filtrar ato por "gera transmissão"; averbação de esclarecimento/encerramento é ato |
| D2 | **Nunca** inventar nem substituir dado documental por inferência | `normalized=null` + `requer_revisao=true` quando não houver lastro literal |
| D3 | `observacoes` **pode** receber ambiguidade, cálculo, divergência, ressalva e conclusão analítica | Q1 = opção **(b)**: marcador explícito de autoria + revisão humana |
| D4 | Observação documental ≠ observação do sistema | Marca obrigatória; nunca mistura silenciosa (§5) |
| D5 | O usuário revisa e decide o preenchimento final | A revisão continua sendo o portão; nada é gravado sem aceite |
| D6 | O banco do Umbelino é a **referência operacional inicial** | Vocabulário e exemplos saem dele; não é gabarito jurídico |
| D7 | Não auditar/corrigir todo o histórico nesta etapa | Medir, não sanear; erros históricos não bloqueiam |
| D8 | Aprender com a diferença entre sugestão e correção | Captura do diff (§6), reusando `CampoSugerido`/`ImportacaoIA` |
| D9 | Meta inicial: qualidade **comparável à do cadastro humano** | Métrica relativa ao humano, não "% de campos preenchidos" (§7) |
| D10 | Começar por dicionário, exemplos reais e recuperação contextual, **sem treinar modelo** | RAG primeiro; fine-tuning mantido como opção futura (§6.4) |
| D11 | Documento original é a fonte jurídica | Evidência (página + trecho/bbox) obrigatória por campo |
| D12 | **Q2:** `ocr-service` é dono do gerador e do artefato de vocabulário | O Umbelino define semântica e regras de preenchimento; consome cópia fixada por hash |
| D13 | **Q1:** opção (b) para observações analíticas | Marcador + autor + data + revisão humana; sem migration nesta etapa |
| D14 | **Q3:** implementação começa pela **#396** (parser de área) | A matriz documental da M237 (#395, Etapa 2) é atividade posterior |

## 2. Inventário verificado

### 2.1 Encanamento que já existe (não recriar)

| Ativo | Onde | O que já entrega |
|---|---|---|
| Contrato A3 | `ocr-service/contracts/extraction-schema-matricula-v1.2.json` | v1.2 = v1.1 + `livro/folha/data_transacao`; app pede v1.2 e aceita v1.1/v1.2 (`ia_ocr/extracao_schema.py`) |
| Destinos | `ia_ocr/destinos.py` (~38 ponteiros) | `descricao` e `observacoes` já têm destino (`:129-130`) |
| Prefill | `ia_ocr/formulario/prefill.py:26-48` | mapa chave→input; `:145` escreve `observacoes` |
| Revisão | `ia_ocr/revisao/*` | obrigatoriedade (`obrigatorio.py:196-235`), área em ha (`area_ha.py`), pendências, evidência |
| Sugestão persistida | `ia_ocr/models/extracao.py:60+` (`CampoSugerido`) | `raw`, `normalized`, `valor_final`, `escolha_explicita`, `status_revisao`, `revisado_por/em`, `confianca`, `motivos_revisao`, `evidencia_pagina/trecho/bbox` |
| Vínculo pós-importação | `ia_ocr/models/registro.py:29+` (`ImportacaoIA`) | um vínculo por objeto criado, FK opcional ao `CampoSugerido`, `documento_digital_id` sem FK (rastro sobrevive à exclusão) |
| Medição | `ocr-service/src/ocr_service/eval/gabarito.py` e `eval/score.py` | gabarito CSV→JSON (marca `ilegivel`) e classes `correto/ausente/errado_aceito/errado_revisao/extra`; **erro perigoso = divergente sem `requer_revisao`** (`score.py:1-19,124-133`) |
| Contexto do provedor | `ocr-service/src/ocr_service/extracao/provedor.py:54` | `propor_campos(paginas, schema, contexto)` — já aceita contexto externo |
| Regra anti-exemplo numérico | `workers_ai.py:50-52` | exemplo com dígitos no prompt vira resposta (medido no M237) |

### 2.2 O que **não** existe

- **Dicionário/vocabulário implementado**: nenhum em nenhum dos dois repos
  (busca por `dicionario|vocabulario|glossario` só acha o PR #70, aberto).
- **Base de exemplos semânticos**: inexistente.
- **Recuperação contextual** na extração: a interface aceita `contexto`, mas
  nada é injetado além de cartório/imóvel.
- **Promoção de correção a exemplo**: o diff existe em `CampoSugerido`, mas não
  é extraído nem realimentado.
- **Histórico de edições / motivo da correção**: só o último `valor_final`.
- **Distinção observação documental × analítica**: campo único
  (`dominial/models/lancamento_models.py:58`), sem marca, sem autor por trecho.

### 2.3 Banco de produção — retrato do preenchimento humano

Consulta somente leitura (usuário de inventário), agregados sem PII, snapshot
de 23/11/2026: **12.226 lançamentos** (averbação 5.404 · início de matrícula
3.442 · registro 3.380).

| Campo | Situação medida | Leitura |
|---|---|---|
| `forma` | vazio em 4.022 (33%) | maior lacuna de registro |
| `titulo` | vazio em 7.519 (61%) | idem |
| `descricao` | vazio em 6.868 de **12.226 lançamentos** (56%); preenchido em 5.358 (5.354 averbações + 4 registros; média 174, máx 4.226). Recorte de averbação: **50 vazios em 5.404 (0,9%)** | é campo de **averbação**, confirmado por uso; a taxa comparável ao scorer é a do recorte de averbação (§7) |
| `observacoes` | vazio em 7.762 (63%); 4.464 textos, média 239 chars; 220 com "atenção", 41 com "pendente" | já é usado para ressalva analítica, **sem marca** |
| `area` | 2.012 zeros, 2.141 valores < 1 ha, máximo 17.720.830 ha | não há invariante; magnitude já se perdeu no histórico |
| origens | 1.727 (transcrição 1.062 = 61% · matrícula 665); livro em 40%, folha em 12% | origem é predominantemente transcr. e raramente tem folha |

**Populações diferentes, números diferentes.** A tabela acima mede **todos os
12.226 lançamentos**. O scorer (§7) conta `ausente` apenas quando o **gabarito
tem valor**, por ato e por campo — para `descricao`, a população é a averbação.
O vazio humano comparável é **50 de 5.404 (0,9%)**, não os 56% do total, que
inclui início de matrícula e registro, onde o campo não é usado.

Vocabulário real (com variantes): `forma` — "Compra e Venda" 1.041 × "Compra e
venda" 432 × "Venda e compra" 280 × "Escritura Pública de Compra e Venda" 391 ×
"Escritura pública…" 183 × "…de venda e compra" 102; `titulo` — "Escritura
Pública" 543 × "Escritura pública de compra e venda" 442 × "Compra e Venda" 429.
**Consequência:** o cadastro humano não separa forma de título de modo
consistente — ele é referência operacional, não gabarito (D6/D7).

Adoção do OCR no app (mesmo snapshot): **1** `ImportacaoIA`, 150
`CampoSugerido` em `sugerido` + 14 `importado`. Ainda não há volume para
treinar nada; há volume para **vocabulário** e para **exemplos de texto**.

### 2.4 Os dois testes em pauta (não misturar)

| Teste | Documento | Origem do resultado | Volume | Artefato |
|---|---|---|---|---|
| **M6141** | 1 página, 2 atos | job `ab1e944554de4599b545fe4046084a0d`, executado direto no serviço | 2 atos | privado, preservado pelo OCR; não é recuperável pela API pública (`/v1/ocr/jobs/<id>` responde `JOB_NOT_FOUND` no commit `5382fc6` — estado do job é em memória) |
| **M237** | 2 páginas, 8 atos | `ExtracaoSugerida` 29 (job 25, documento digital 363), schema v1.2, provider `workers-ai`, status `revisado` | 8 atos | persistido no app (`payload_servico`) |

Comparações, relatórios e gabaritos devem nomear **qual** dos dois está sendo
medido. Os achados de uma rodada não se transferem para a outra.

## 3. Lacunas reais

| # | Lacuna | Evidência | Consequência |
|---|---|---|---|
| L1 | Sem vocabulário compartilhado | §2.2 | prefill não casa "Venda e compra" → "Compra e Venda"; sugestão parece erro ao usuário |
| L2 | Sem exemplos semânticos | §2.2 | o extrator não sabe como o cadastro escreve `descricao`/`observacoes`/`origem` |
| L3 | Forma × título confundidos nos dois lados | §2.3 + OCR #84 | 574 linhas de `forma` com texto de título; extração repete o padrão |
| L4 | Área sem parser único e sem semântica | #396, OCR #83 | `1.000` vira 1 ha; área destacada/remanescente/original se misturam |
| L5 | Observação sem marca de autoria | §2.3, `keyword_alerta_service.py` | texto de IA vira "observação do cartório" e entra no PDF jurídico (`cadeia_completa_pdf.html:238`) e no Excel (`exportacao_excel_service.py:439`) |
| L6 | Só o último valor revisado é guardado | `CampoSugerido.valor_final` | correção intermediária se perde; não há motivo da edição |
| L7 | Diff não vira exemplo | §2.2 | o sistema não aprende com o uso (D8) |
| L8 | Sem métrica de aceite por documento | eval existe, não é aplicado ao fluxo real | "8 atos extraídos" não diz quantos estão certos |
| L9 | Atos não transmissivos | OCR #87 | averbação explicativa/encerramento tratada como transação |
| L10 | `$id` do A3 v1.2 ainda diz v1.1 | `contracts/…v1.2.json` | drift cosmético que confunde consumidor e teste de versão |

## 4. Arquitetura proposta

### 4.1 Dois artefatos, dois regimes de publicação

```
                 (fechado, público)                    (aberto, privado)
  banco Umbelino ──► vocabulario_prod.json        banco Umbelino ──► exemplos_semanticos.json
                     ocr-service gera (#74)                           app gera (comando read-only)
                     commitado + hash                                 fora do git, no servidor
                     consumo: app (#372)                              consumo: ocr-service (contexto)
```

- **Vocabulário** = valores de domínio fechado — cartório/CNS, `tipo_lancamento`,
  formatos de `livro`/`folha` e formatos de área — **mais `forma` e `titulo`,
  que são texto livre no cadastro**. Campos fechados entram com contagem por
  valor (schema `vocabulario-prod/v1`, ver ocr-service #74). `forma` e `titulo`
  só entram depois de **allowlist revisada por humano**: valor não aprovado
  fica **fora** do JSON — não é mascarado nem "sanitizado". O teste automático
  de PII complementa a revisão, não a substitui.
- **Exemplos semânticos** = pares **(texto documental → valor preenchido)** por
  campo e tipo de ato, derivados de `descricao`, `observacoes`, `area`,
  `origem` e das colunas fechadas. O texto registral vai **mascarado** (pessoa →
  `transmitente 1`/`adquirente 1`; sem CPF/RG/endereço): é artefato **privado**
  (gerado por comando, gravado fora do git, com sha256 e contagens), nunca
  commitado, nunca logado e **sem PII** — mesma regra do plano do serviço (§3).
- Regra de ouro: **vocabulário ensina grafia; exemplo ensina forma de
  escrever**. Os dois nunca viram "resposta" no prompt (lição medida em
  `workers_ai.py:50-52`).

### 4.2 Fluxo e pontos de encaixe

```
PDF → OCR/texto → extração A3 → normalização determinística → revisão humana
    → importação transacional → captura do diff → promoção a exemplo
```

| Etapa | Componente | Encaixe desta proposta |
|---|---|---|
| Extração | `ocr-service/extracao/*` | `contexto` recebe `vocabulario` + `exemplos` (flag); provedor continua só **propondo** |
| Normalização | `ia_ocr/revisao/*`, `formulario/*` | casamento exato → sem acento/caixa → fuzzy, **nunca** inventando valor; divergência vira pendência |
| Revisão | `ia_ocr/views`, `templates/dominial/lancamento_form.html` | mostra `raw` ao lado do valor; analítico em bloco marcado (§5) |
| Importação | `ia_ocr/importacao/*` | inalterado; `ImportacaoIA` continua sendo o vínculo |
| Captura | `CampoSugerido` | já tem `raw` × `valor_final`; falta extrair, classificar e guardar candidato |
| Promoção | novo comando | candidato revisado por humano vira linha da base de exemplos (fora do git) |

### 4.3 Por que não serviço novo nem treino agora

- O volume revisado é **N≈1** (§2.3): treinar seria overfit de um documento.
- A interface `ExtractionProvider` e o `contexto` já existem: recuperação é
  mudança de conteúdo, não de arquitetura.
- Fine-tuning fica registrado como **opção futura** (D10), com pré-condições
  explícitas (§6.4) — não descartado, apenas não antecipado.

## 5. Observações: documental × analítica (Q1 = b)

Campo único (`Lancamento.observacoes`), dois tipos de conteúdo, **nunca
misturados sem marca**.

| Tipo | Regra | Exemplo de forma |
|---|---|---|
| **Documental** | texto literal com lastro; evidência (página + trecho) obrigatória; sem prefixo | "Área remanescente de 55 ha 69 a 85 ca" |
| **Analítica** | só por ação explícita do revisor (ou sugestão marcada e pendente de aceite); prefixo de autoria e data; entra na revisão como pendência, não como texto do cartório | `[ANÁLISE — <usuário> — 2026-11-23] Soma das áreas confere com o R.5; Av.7 encerra a matrícula.` |

Regras de implementação (sem migration nesta etapa):

1. O prefill escreve **só** texto documental em `observacoes`; análise nunca é
   preenchida automaticamente.
2. A tela de revisão e o formulário manual ganham ação explícita "registrar
   análise"; o texto sai com o marcador e o autor. O contrato de quebra de linha
   do campo é `\n`: o CRLF que o textarea do navegador devolve é normalizado na
   entrada (criação **e** edição), senão o bloco analítico volta colado ao
   documental e o badge do sistema nasce do texto do revisor (#400 v2).
3. Exibição (tela e formulário) mostra o marcador e o fechamento
   `[/ANÁLISE]` — não há como confundir. **PDF e Excel exportam só o texto
   documental**: a análise é pendência de revisão, não texto do cartório
   (#400 v4, achados P1 do Greptile no PR #409).
4. `buscar_keyword` (`keyword_alerta_service.py:11`) **ignora** blocos
   analíticos ao procurar "atenção"/"pendente" — alerta do sistema não pode ser
   criado por texto do sistema. Teste dedicado.
5. Migração para campo/tabela própria (autor, tipo, vínculo) fica como
   evolução futura, condicionada a aprovação do dono.
6. **Limite aceito do Q1=b:** colar à mão um bloco analítico — ou um texto que
   imite o marcador — no campo documental continua possível; o campo é texto
   livre e não há migration nesta etapa. A marca (autor + data) é o que separa
   os dois tipos; sem ela, o conteúdo é documental por definição. O que muda
   com o #400 v4: o marcador digitado no textarea documental é **descartado**
   na gravação (`observacoes_da_requisicao`) — o texto não vira análise nem
   autoria; só o servidor emite bloco marcado e fechado. A regra 5 é o caminho
   que fecha esse limite.

## 6. Aprendizado

### 6.1 Fase A — vocabulário (determinístico)

Casamento exato → normalizado (sem acento/caixa) → fuzzy, sempre marcando
confiança; valor fora do vocabulário **não** é corrigido em silêncio: vira
pendência com o valor lido preservado.

### 6.2 Fase B — exemplos recuperados (RAG)

- Recorte: por `tipo_lancamento` + campo, com top-k por similaridade léxica
  (sem embedding numa primeira rodada).
- Injeção: bloco no `contexto` rotulado como **referência de estilo**, com a
  regra explícita "não copie valores nem números".
- Avaliação: mesma fixture, com e sem contexto; ganho medido pelo scorer.

### 6.3 Fase C — correção vira exemplo

`CampoSugerido.raw`/`normalized` × `valor_final` (e `escolha_explicita`) já
guardam o diff. O comando de exportação classifica cada par como
`aceito` / `editado` / `descartado`, grava candidato **privado** e só promove a
exemplo após revisão humana. Nada de aprendizado automático não auditado.

### 6.4 Fine-tuning (opção futura, não descartada)

Pré-condições registradas: (a) ≥ 500 pares revisados por campo; (b) conjunto de
avaliação congelado e separado; (c) ganho de RAG medido e saturado; (d) decisão
explícita do dono sobre custo/privacidade dos dados registrais.

## 7. Métricas (não usar % de preenchimento)

Do scorer existente (`eval/score.py`):

| Métrica | Definição | Meta |
|---|---|---|
| **Erro perigoso** (`errado_aceito`) | divergente do gabarito **sem** `requer_revisao` | **0** em área, número, origem e cartório |
| `ausente` | gabarito tem valor, extração devolveu null — **população = campos com valor no gabarito**, por ato | ≤ vazio humano **na mesma população**; `descricao` em averbações: **0,9% (50/5.404)** — não os 56% de todos os lançamentos (§2.3) |
| `extra` | valor onde o gabarito diz ilegível/ausente | só com evidência; nunca sem |
| Taxa de edição | % de campos que o revisor alterou | tendência de queda por campo/tipo |
| Correção crítica | edição em área/número/origem | 0 sem pendência registrada |

Comparações **sempre** separadas por documento (M6141 × M237) e por ato.
Relatório reproduzível = comando + hash do PDF + `job_id` + data.

## 8. Fases

| Fase | Entrega | Depende | Aceite verificável | Esforço |
|---|---|---|---|---|
| **F0** | Este documento + ajuste do `PLANO_INTEGRACAO` + seção F3.1 no ROADMAP | — | docs revisados, sem código | ½ dia |
| **F1** | **#396** parser único de área pt-BR (formulário, revisão, edição) | — | teste RED→GREEN com `1.000`, `1.234,5678`, `1234,5678`, `150,5`, `150.5`; round-trip form→banco→exibição | 1 dia |
| **F2** | Observações documental × analítica (§5) | F1 | teste: prefill nunca escreve marcador; análise só com autor; `buscar_keyword` ignora análise; tela mostra a marca e PDF/Excel exportam só o documental | 1 dia |
| **F3** | Vocabulário compartilhado: fecha ocr-service #74/#70 e app #372 | F2 | Fase A (sintética): JSON schema v1 válido, teste de PII, hash fixado, prefill casa "Venda e compra". Fase B (produção): só após autorização do dono e com allowlist de `forma`/`titulo` aprovada | 1–2 dias |
| **F4** | Base de exemplos privada + export read-only | F3 (reusa vocabulário) | artefato fora do git com sha256/contagens; zero PII; comando parametrizado | 2 dias |
| **F5** | Recuperação contextual na extração | F4 | ganho medido no scorer com/sem contexto na mesma fixture; flag de rollback | 1–2 dias |
| **F6** | Correção → exemplo (contínuo) | F5 | pares classificados; promoção só após revisão; nada automático | 1–2 dias |
| **F7** | Correções O-M237 (ocr-service #83→#85→#87→#86→#84) + aceite #88 | F6 | matriz #395 verde por ato e campo | 4–6 dias |

> **Ordem sequencial (ROADMAP §F3.1, aprovada em 23/11/2026):** a coluna
> `Depende` reflete a ordem aprovada — cada fase começa depois da anterior
> terminar. Não há implementação em paralelo, nem entre fases nem entre os dois
> repositórios.

> **Regra operacional (23/11/2026):** até autorização explícita do dono, #74 e
> #372 trabalham **só com dados sintéticos**. A geração read-only em produção é
> uma fase separada e gated; a allowlist de `forma`/`titulo` é aprovada pelo
> dono antes de qualquer publicação.

## 9. Mapa de issues

### Existentes — atualizar (não duplicar)

| Issue | Ação |
|---|---|
| CadeiaDominial **#396** | é a **primeira** tarefa (Q3); registrar a regra de ambiguidade acordada e manter o escopo transversal |
| **#395** | corrigir a distinção M6141 × M237 (§2.4); Etapa 2 fica posterior (Q3) |
| **#372** | consome o artefato do ocr-service (#74); não varre produção |
| **#397** | ganha a coluna "valor no input × gravado × marcador de análise" |
| **#398** | incorpora L6/L7 confirmadas e a regra D8 |
| **#393** | vira teste do #388 (já mergeado) + matriz de cadeias compartilhadas |
| **#325** | recebe as distinções de referência registral do OCR #86 |
| ocr-service **#74** | dono único do artefato (Q2); inclui o recorte de #68 |
| ocr-service **#76** | atualizar o plano com as decisões de 23/11 |
| ocr-service **#83–#88** | ordem por risco: #83 → #85 → #87 → #86 → #84 → #88 |

### Novas (estritamente necessárias)

| Repo | Título | Por que não cabe numa existente |
|---|---|---|
| CadeiaDominial | `feat(ia_ocr): observações documentais × analíticas com marcador de autoria (U-M237-08)` | é regra de produto + tela + export, distinta da documentação de proveniência (#398) |
| CadeiaDominial | `feat(ia_ocr): base de exemplos semânticos por campo e tipo de ato (artefato privado)` | não é vocabulário (#372) nem dicionário do serviço (#74) |
| CadeiaDominial | `feat(ia_ocr): aprendizado contínuo — diff sugestão × valor final como candidato a exemplo` | captura e promoção são etapas próprias, com revisão humana |
| ocr-service | `feat(p3): exemplos semânticos como contexto de extração (contrato v1 do artefato privado)` | consumo no serviço; #74 é só vocabulário |

## 10. Documentação e skills

- **Novo:** este arquivo.
- **Atualizar:** `PLANO_INTEGRACAO_OCR_UMBELINO.md` §1 (comentário v1.1 stale) e
  §5 (estado dos PRs do serviço); `ROADMAP.md` (F3.1); ocr-service
  `docs/produto3/BACKEND-OCR.md` (ponteiro para o plano de vocabulário/exemplos).
- **Skill Hermes:** `ocr-umbelino-ciclo` — fila dos dois repos, como medir com o
  scorer, onde ficam a matriz e os artefatos, regra "vocabulário público ×
  exemplo privado". Reusar `cadeiadominial-test-service`, `codex-impl-cycle`,
  `harness-quota-discipline`, `contract-scope-audit`.

## 11. Riscos

| Risco | Mitigação |
|---|---|
| Exemplo privado vazar para repo público | comando grava fora do git; teste que falha se PII aparecer; revisão no PR |
| Vocabulário virar "resposta" no prompt | vocabulário só normaliza; exemplos só estilo; teste "prompt não traz exemplo numérico" |
| Erro histórico virar exemplo | promoção exige revisão humana; `ilegivel`/divergente não promove |
| Duas fontes de verdade de vocabulário | Q2: um dono (ocr-service), cópia fixada por hash |
| Reordenação indevida da fila | F3.1 é sub-trilha; R4–R10 intactos |
