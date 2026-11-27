# Avaliação da M6141 — tabela versionada + medição do fluxo completo (homolog)

**Card:** `t_563a8c60` (App — fluxo completo de demonstração com tempo e intervenções)
**Base medida:** `origin/develop` @ `239d56b6`, implantada em homologação
(TestServer: containers `cadeia_dominial_web`, `cadeia_dominial_db`,
`cadeia_dominial_ocr_worker`; OCR `OCR_GIT_COMMIT=109710b`), 27/11/2026.
**Escopo:** MEDIÇÃO. Nenhum código alterado, nenhum dado de produção tocado.
**Fonte da tabela de 26 campos:** comentário de fechamento do card `t_7698885f`
(medição M6141 com extração 40, job 31) — aqui versionada como documento.

> **NOTA DE VERSÃO (importante para ler a tabela).** A tabela do §1 é a
> medição da **extração 40**. Com o OCR implantado hoje (`109710b`), a linha 27
> ("Origem / cartório") **não** volta mais com o rótulo do cabeçalho
> (`"REGISTRO DE IMÓVEIS E HIPOTECAS"`): o campo vem **vazio** e marcado
> `requer_revisao` (medido em 27/11 nas extrações 41 e 42). A
> intervenção humana continua necessária, mas **por ausência**, não por valor
> errado. O restante da tabela (contagens, ruído de revisão) segue válido como
> fotografia da extração 40; as linhas 8, 25 e 27 continuam sendo os pontos de
> intervenção.

---

## 1. Tabela de avaliação da M6141 (26 campos, conferência × intervenção)

**Critério declarado (reconstruído, não persistido antes):** os 26 inputs com
valor pré-preenchido que o revisor vê na revisão da M6141 — 2 do documento +
10 da abertura + 14 do R.1 (2 transmitentes + 1 adquirente). Medido com a mesma
função que a tela usa (`formulario.prefill_do_ato`).

| # | Campo (input da revisão) | Referência no documento | Baseline (extração 32) | Medição (extração 40) | Classe | requer_revisao | Ação p/ demo |
|---|---|---|---|---|---|---|---|
| 1 | Documento / livro | 2 | 2 | 2 | correto | sim | conferência |
| 2 | Documento / sigla | M6141 | M6141 | M6141 | correto | sim | conferência |
| 3 | Abertura / tipo | início de matrícula | 3 | 3 | correto | não | conferência |
| 4 | Abertura / número | M6141 | M6141 | M6141 | correto | não | conferência |
| 5 | Abertura / data | 18.06.2015 | 2015-06-18 | 2015-06-18 | correto | não | conferência |
| 6 | Abertura / área | 74,6755 ha | 74.6755 | 74.6755 | correto | sim | conferência |
| 7 | Abertura / descrição | texto do imóvel | preenchida | preenchida | correto | sim | conferência |
| 8 | Abertura / observações | INCRA/CCIR/NIRF | preenchida | **vazia** | vazio não bloqueante (texto segue na descrição) | não | conferência |
| 9 | Origem / tipo | matrícula | M | M | correto | sim | conferência |
| 10 | Origem / número | 237 (R.5 matr. 237) | 237 | 237 | correto | sim | conferência |
| 11 | Origem / livro | 2 | 2 | 2 | correto | não | conferência |
| 12 | Origem / folha | 237 | 237 | 237 | correto | não | conferência |
| 13 | R.1 / tipo | registro | 1 | 1 | correto | não | conferência |
| 14 | R.1 / número simples | 1 | 1 | 1 | correto | não | conferência |
| 15 | R.1 / número composto | R1 M6141 | R1 M6141 | R1 M6141 | correto | não | conferência |
| 16 | R.1 / data do ato | 18.06.2015 | 2015-06-18 | 2015-06-18 | correto | não | conferência |
| 17 | R.1 / forma (natureza) | Compra e Venda | Compra e Venda | Compra e Venda | correto (aviso de reinterpretação) | sim | conferência |
| 18 | R.1 / título (instrumento) | Escritura pública de 10.04.2015 | idem | idem | correto (aviso de reinterpretação) | sim | conferência |
| 19 | R.1 / livro da transação | 02 | 02 | 02 | correto | sim | conferência |
| 20 | R.1 / folha da transação | 116 a 117 | 116 a 117 | 116 a 117 | correto | sim | conferência |
| 21 | R.1 / data da transação | 10.04.2015 | 2015-04-10 | 2015-04-10 | correto | sim | conferência |
| 22 | R.1 / descrição | O imóvel objeto desta matrícula. | idem | idem | correto | sim | conferência |
| 23 | R.1 / observações | Não constam. | idem | idem | correto | sim | conferência |
| 24 | R.1 / transmitente 1 | Pedro Apóstolo Pereira Neto | preenchido | preenchido | correto | não | conferência |
| 25 | R.1 / transmitente 2 | Dilza Fernandes Apóstolo | preenchido | **vazio** | vazio (virou "cônjuge", não renderizada) | n/a | **INTERVENÇÃO — digitar** |
| 26 | R.1 / adquirente 1 | Olívio de Oliveira Dias | preenchido | preenchido | correto | não | conferência |
| 27 | Origem / cartório (fora dos 26) | Itamaraju ("deste Cartório") | vazio | **vazio** (era "REGISTRO DE IMÓVEIS E HIPOTECAS" na extração 40) | vazio + `requer_revisao` | sim (com motivo, hoje) | **INTERVENÇÃO — digitar** |
| 28 | R.1 / cartório da transmissão (fora dos 26) | Cachoeira do Mato | vazio | vazio | vazio | sim (trecho ausente) | **INTERVENÇÃO — digitar** |

### 1.1 Contagens

| Conjunto | Baseline 32 | Medição 40 |
|---|---|---|
| 26 campos — corretos | 26 | 24 |
| 26 campos — errados silenciosos | 0 | 0 |
| 26 campos — vazios | 0 | 2 (linhas 8 e 25) |
| 26 campos — vazios bloqueantes | 0 | 0 |
| 26 campos — conferência / intervenção | 26 / 0 | 25 / 1 |
| 28 campos visíveis — conferência / intervenção | 26 / 2 (92,9% / 7,1%) | 25 / 3 (89,3% / 10,7%) |

### 1.2 Ruído de revisão (`requer_revisao`)

| Métrica | Baseline 32 | Medição 40 |
|---|---|---|
| Campos marcados | 25 | 23 |
| Folhas marcadas com valor já correto (inúteis) | 18 | 15 |
| Marcadas em bloco oculto/fora de contexto | 3 | 3 |
| Marcadas fora do formulário | 1 | 1 |
| Marcadas úteis (ação real) | 1 | 2 |
| Dos 26 campos, marcados sem necessidade | 15 (58%) | 13 (50%) |

---

## 2. Fluxo completo executado em homologação (27/11/2026)

**Método declarado de medição (o que foi cronometrado e como).** O fluxo foi
executado no app implantado em homologação, pelas views e templates reais, com
o PDF real (`M6141_Itamaraju.pdf`, 287.537 bytes), dentro do container
`cadeia_dominial_web` com o código implantado (`manage.py shell`), usando
`django.test.Client` com sessão autenticada (`force_login` de `admin`). O
acesso ao servidor foi pela ponte SSH somente-leitura já existente
(`cadeia-ponte-teste` → TestServer); não há browser nem credencial de UI
disponível na máquina do agente.

- **Cronometrado com `time.monotonic()`**, por requisição HTTP completa
  (ida, view, render, resposta): upload multipart, criação do job, cada poll de
  status, POST de extração, GETs da revisão, POSTs de salvamento e GETs das
  telas da cadeia. Tempo de parede, não tempo de CPU.
- **Tempo de OCR** = laço de poll a cada 2 s até `concluido`; por isso tem até
  ~2 s de folga de amostragem (o horário de criação/atualização do job é
  registrado junto como conferência).
- **Não medido**: tempo de leitura/raciocínio humano (não havia revisor
  humano na sessão) e tempo de cliques/scroll/JS de um navegador real. Os
  tempos de trabalho humano do §3 são **modelados** com constantes declaradas.

**Cenários descartáveis (fora do cronômetro, nada de produção).**

| Cenário | TI | Imóvel | Documento | Arquivo digital | Job / extração | Lançamentos |
|---|---|---|---|---|---|---|
| A (12:36 UTC) | 67 | 710 "DEMO FLUXO 27-11" (`6141F27`) | 4443 M6141 (`matricula`, cartório 393) | 372 | 35 / 41 | 13112, 13113 |
| B (12:48 UTC) | 67 | 711 "DEMO FLUXO 27-11b" (`6141F27B`) | 4444 M6141 (`matricula`, cartório 393) | 373 | 36 / 42 | 13114, 13115 |

### 2.1 Etapas medidas

Rodada **B** é a execução completa (todos os passos cronometrados). Rodada
**A** foi a primeira, onde o coletor perdeu o tempo dos POSTs de gravação.

| Etapa | Ação | B (completa) | A |
|---|---|---|---|
| 1 | Upload do PDF (POST multipart + redirect) | **0,106 s** | 0,129 s |
| 2a | Criar job de OCR (POST JSON) | **0,028 s** (job 36) | 0,025 s (job 35) |
| 2b | Processamento no serviço OCR até `concluido` (1 página) | **30,306 s** (16 polls; job criado 12:48:40,3 → concluído 12:49:09,7 = **29,4 s** no serviço) | 10,119 s |
| 3 | Extrair campos (POST ao serviço) | **10,020 s** → extração 42, 48 campos, 2 atos | 12,628 s → extração 41, 50 campos, 2 atos |
| 4 | Abrir a revisão: GET entrada + GET ato 0 + GET ato 1 | **0,119 + 0,106 + 0,089 s** | 0,102 + 0,059 s |
| **Subtotal automático (1→4)** | upload → revisão aberta | **≈ 40,6 s** | ≈ 23,1 s |
| 5 | Salvar o ato 0 (Abertura) **sem digitar nada** (POST) | **0,280 s** → 302, lançamento 13114 | POST executado, 13112 gravado (tempo perdido) |
| 6 | Salvar o ato 1 (R.1) **sem digitar nada** (POST) | **0,213 s** → 302, lançamento 13115 | POST executado, 13113 gravado (tempo perdido) |
| 7 | Abrir a tela da cadeia (GET autenticado) | **tabela 0,148 s · tronco 0,102 s · D3 0,026 s** | ver §2.3 |

**Variação do serviço:** o mesmo PDF de 1 página levou **10,1 s** na rodada A e
**29,4 s** na rodada B (3× de diferença, mesmo commit `109710b`), e o número de
campos devolvidos mudou de **50 para 48** entre as extrações 41 e 42. A
extração do MESMO PDF **não é determinística** nos campos de transação (ver
§4.3).

### 2.2 O que o formulário de revisão entregou pronto

- **Ato 0 (Abertura):** tipo 3, número M6141, data 2015-06-18, área 74.6755,
  descrição completa (788 caracteres), origem M237 / livro 2 / folha 237,
  tipo de origem M. Vazios: forma (não se aplica à abertura), observações,
  cartório da origem (resolvido na gravação por herança → cartório 393).
  Avisos informativos do banner: "Data da origem: lido, sem campo no
  lançamento", "Campo recomendado não preenchido: Ato 1 — forma",
  "… Ato 1 — observacoes". **Nenhum bloqueio** → salvou sem digitação.
- **Ato 1 (R.1):** tipo 1, número R1 M6141, data 2015-06-18, forma
  "Compra e Venda", título "Escritura pública de 10 de abril de 2015",
  data da transação 2015-04-10, descrição "O imóvel objeto desta matrícula.",
  observações "Não constam.", adquirente Olívio de Oliveira Dias,
  transmitente 1 Pedro Apóstolo Pereira Neto (pessoa 6576 / 1266; o formulário
  reapresenta o mesmo par de partes em 3 blocos, todos com o mesmo valor).
  Avisos: reinterpretação forma/título e divergência entre data da transmissão
  do A3 e data do instrumento (valeu o instrumento).
  **Faltas medidas no pré-preenchimento:** transmitente 2 (Dilza) não
  renderizada; cartório da transmissão vazio; **livro/folha da transação
  vieram preenchidos na rodada B (02 / 116 a 117) e vazios na rodada A**
  (extração 41).

### 2.3 Resultado da gravação e da cadeia (conferido no banco e nas telas)

**Gravação — rodada B (imóvel 711 / documento 4444):**

| Lançamento | Tipo | Nº | Data | Campos persistidos | Origem persistida |
|---|---|---|---|---|---|
| 13114 | `inicio_matricula` | M6141 | 2015-06-18 | área/descrição completas; `eh_inicio_matricula = t`; livro/folha de origem 2 / 237 | `LancamentoOrigem` índice 0: `matricula` M237, livro 2, folha 237, **cartório 393** → antecedente explícito persistido com cartão (fix do fim de cadeia funcionando) |
| 13115 | `registro` | R1 M6141 | 2015-06-18 | forma "Compra e Venda", título "Escritura pública de 10 de abril de 2015", `data_transacao` 2015-04-10, livro/folha da transação 02 / "116 a 117", observações "Não constam.", transmitente 6576, adquirente 1266 | nenhuma (registro não cria origem) |

**Gravação — rodada A (imóvel 710 / documento 4443):** 13112 (`inicio_matricula`
M6141, `eh_inicio = t`, livro/folha de origem 2/237, cartório de origem NULL
resolvido por herança) + `LancamentoOrigem` M237/2/237/**393**; 13113
(`registro` R1 M6141, forma/título/data da transação corretos, **sem**
livro/folha da transação — coerente com a extração 41 que não os preencheu,
transmitente 6576, adquirente 1266).

**Tela da cadeia (GET autenticado, HTTP 200 nas três telas da rodada B):**

| Tela | URL | Tempo | O que aparece |
|---|---|---|---|
| `cadeia_dominial_tabela` / `tronco_principal` | `/tis/67/imovel/711/cadeia-tabela/` e `/ver-cadeia-dominial/` | 0,148 s / 0,102 s (41.241 bytes, idênticas) | "Matrícula: M6141 — Análise iniciada em: 18/06/2015 — Registro de Imóveis de Itamaraju"; linha do R.1 com PEDRO / Olívio / Compra e Venda / Escritura pública de 10 de abril de 2015 / 02 / 116 a 117 / 10/04/2015 / "Não constam."; linha da abertura com área 74,6755 e **origem "M237 (Registro de Imóveis de Itamaraju)"** |
| `cadeia_dominial` (D3) | `/tis/67/imovel/711/cadeia-dominial/` | 0,026 s | o GET traz só o esqueleto + mensagens ("Ato R1 salvo como lançamento", "Revisão concluída: todos os atos desta extração foram resolvidos"); a árvore é montada por JS, então a conferência de conteúdo foi feita nas telas server-side acima |

Ou seja: o fluxo fecha — PDF → extração → revisão → gravação dos 2 atos →
cadeia com o antecedente M237 e o cartório no cartão.

---

## 3. Comparação com preenchimento convencional (critérios iguais)

**Critérios (os mesmos para os dois modos):** (a) tempo de processamento
automático; (b) tempo de trabalho humano; (c) tempo total; (d) campos digitados
pelo humano; (e) qualidade final (corretos / errados silenciosos / revisados).

**Constantes declaradas** (assunção, não medição; calibrar com um revisor
humano real): conferir um campo pré-preenchido = **3 s**; digitar um campo
vazio/simples = **10 s**; digitar parte (nome de pessoa) = **15 s**; localizar
o ato no livro e conferir no PDF = **60 s** por documento; clicar/salvar =
**1 s** por POST.

| Critério | Convencional (estimativa declarada) | Assistido (medido + modelado) |
|---|---|---|
| (a) Processamento automático | 0 s (não existe) | **40,6 s medidos** na rodada B (upload 0,11 + job 0,03 + OCR 30,3 + extração 10,0 + revisão 0,31); **23,1 s** na rodada A (OCR 10,1 + extração 12,6) |
| (b) Trabalho humano | 28 campos digitados: 8,5 min (510 s) + 60 s de localização = **570 s** | 28 campos conferidos × 3 s = 84 s + **2 intervenções** na rodada B (parte Dilza 15 s + cartório da transmissão 10 s = 25 s) + 2 cliques de salvar (2 s) = **111 s modelados** (rodada A tinha 1 intervenção extra: livro/folha da transação, +20 s) |
| (c) Tempo total | **≈ 9,5 min** | **≈ 2,5 min** (40,6 s + 111 s) |
| (d) Campos digitados pelo humano | 28 | **2** na rodada B (Dilza; cartório da transmissão) / **3** na rodada A (+ livro/folha) — nos 26 do baseline: **1** |
| (e) Qualidade final | 0 erros por definição, mas sujeito a erro de digitação/transcrição não auditado | 24/26 corretos + 2 vazios (1 não bloqueante: observações da abertura; 1 bloqueante para a parte: Dilza) + **0 errados silenciosos**; 13 dos 26 campos corretos ainda vêm marcados `requer_revisao` (50%); livro/folha da transação oscilam entre extrações |

**Leitura:** a automação gasta ~23–41 s conforme a latência do serviço; o ganho
está em (d) — 2 digitações em vez de 28 — e em (c) — ~4× mais rápido sob as
constantes declaradas. A qualidade assistida tem **0 erro silencioso** nos 26
campos, mas **1 perda de parte** (Dilza) que só aparece se o revisor comparar
com o PDF.

---

## 4. Achados e defeitos registrados (sem correção de código)

1. **Transmitente 2 (Dilza) desaparece** — o serviço devolve a pessoa como
   `conjuge` e o formulário só renderiza transmitente/adquirente (#320/#332 já
   tratam pendência, mas não a ausência da parte). Intervenção obrigatória.
2. **Cartório da transmissão não resolvido** — "Tabelionato de Notas de
   Cachoeira do Mato" não vira cartório; campo fica vazio.
3. **Livro/folha da transação não são estáveis entre extrações do mesmo PDF:**
   extração 41 devolveu vazio (lançamento 13113 gravado sem eles) e a extração
   42 (mesmo PDF, mesmo commit do serviço) devolveu `02` e `116 a 117`
   (lançamento 13115). Ou seja: ora exigem digitação, ora não, sem que o
   revisor saiba. Ligado ao §4.7.
4. **Campo exibido e descartado na gravação:** a revisão do R.1 renderiza um
   `textarea name="descricao"` pré-preenchido com "O imóvel objeto desta
   matrícula.", mas `LancamentoFormService` só persiste `descricao` para
   `averbacao` e `inicio_matricula` (`dominial/services/lancamento_form_service.py`
   linhas 96–109). Para `registro` o texto mostrado ao revisor **não** é
   gravado (13113 e 13115 têm `descricao` NULL). Pode ser intencional; a tela
   não avisa.
5. **Ruído de revisão** — 13 dos 26 campos corretos ainda vêm marcados
   `requer_revisao` (50%), e 3 flags apontam para blocos que não estão visíveis
   no ato.
6. **`tipo_documento` enviado à extração é `documento.tipo.tipo`**
   (`ia_ocr/services/extracao.py:151`). Para documento cujo tipo é
   `transcricao`, o app envia `transcricao`; para o M6141 real (tipo
   `matricula`, embora o texto seja transcrição de livro antigo) envia
   `matricula` — e nesse caso o serviço devolveu **2 atos** nas três extrações
   medidas (40, 41 e 42), **sem perda silenciosa**. O caso de perda (1 ato
   vazio) descrito no corpus **não se reproduziu** com este documento; fica
   pendente de reprodução com uma transcrição antiga real (documento cujo
   `tipo.tipo == 'transcricao'`).
7. **Latência e volume do serviço variam 3×** para o mesmo PDF de 1 página
   (10,1 s vs 29,4 s) e o nº de campos devolvidos mudou (50 → 48). O app não
   tem timeout/limite visível afetado, mas o tempo "automático" da demo não é
   previsível.
8. **Duplicata não detectada** com origem M237 sem cartório no POST
   ("Origem 0 normal sem cartório, pulando verificação") — o cartório é
   resolvido depois, na gravação, por herança. Comportamento a confirmar.

## 5. Limitações

- Tabela de 26 campos reconstruída (o baseline original não estava persistido);
  critério declarado no §1.
- Tempo de trabalho humano **modelado**, não cronometrado: não havia revisor
  humano na sessão. Próximo passo recomendado: 30 min com um registrador real
  para calibrar as constantes do §3.
- O fluxo foi dirigido pelo `django.test.Client` dentro do container, não por
  cliques em navegador; medidas de rede/navegador (render, JS, upload real de
  arquivo) ficam de fora. A tela D3 não é conferível por HTML puro.
- Escritas em homolog (todas descartáveis): imóveis 710 e 711, documentos 4443
  e 4444, arquivos digitais 373 (e 372 na rodada A; 371 foi tentativa
  descartada), jobs 35 e 36, extrações 41 e 42, lançamentos 13112/13113
  (imóvel 710) e 13114/13115 (imóvel 711). Nada em produção.
