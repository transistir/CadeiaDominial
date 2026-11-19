# Plano de refatoração — limite de 400 linhas por arquivo

> Pedido do Hiure em 19/11/2026: "nenhum código com mais de 400 linhas" e a
> regra não pode voltar a desaparecer. Este plano começa pelos arquivos da
> fase OCR (`ia_ocr`), que é onde o trabalho corrente acontece.
> Diagnóstico levantado em `origin/develop` (`37ade097`, 19/11/2026).

## 1. Diagnóstico (números reais)

- **84 arquivos** acima de 400 linhas em 397 arquivos de código
  (`.py`, `.js`, `.html`, `.css`), excluindo `migrations/`, `node_modules`,
  venv e `old/`.
- Distribuição: `ia_ocr/tests` 24 · `dominial/tests` 20 · `dominial` 15 ·
  `static` 13 · `ia_ocr` 9 · templates 3.
- A regra **não existe em lugar nenhum do repositório**: `grep -r "400 linhas"`
  em `AGENTS.md`, `CLAUDE.md` e `docs/` não retorna nada. Não há hook, teste
  ou check de CI que a imponha. Por isso ela "sumiu" sem ninguém removê-la.

Maiores ofensores hoje:

| Linhas | Arquivo |
|---:|---|
| 5202 | `dominial/tests/test_segregacao_usuario.py` |
| 3437 | `ia_ocr/tests/test_importacao.py` |
| 2793 | `ia_ocr/tests/test_revisao_tela.py` |
| 2661 | `ia_ocr/tests/test_revisao.py` |
| 2446 | `ia_ocr/revisao.py` |
| 2157 | `dominial/admin.py` |
| 1557 | `ia_ocr/importacao.py` |
| 1475 | `dominial/services/lancamento_origem_service.py` |
| 1429 | `ia_ocr/views.py` |
| 1248 | `ia_ocr/services.py` |
| 1213 | `dominial/views/lancamento_views.py` |

## 2. Por que isso trava a entrega do que foi especificado

Cada issue do fluxo OCR cai hoje em módulos de 1.200–2.400 linhas. O agente
precisa reconstruir o contexto inteiro do arquivo para mudar 30 linhas, escolhe
o caminho errado com frequência e o revisor não consegue provar que nada fora do
escopo mudou. O sintoma que o Hiure descreveu ("o que eu especifiquei não é
realizado") é consequência mecânica disso, não falta de especificação.

Regra derivada para os próximos briefs: **uma issue deve caber em um módulo de
até 400 linhas**. Se não couber, a etapa de refatoração daquele módulo vem
antes da feature.

## 3. A regra (a partir da etapa 0, sem exceção)

1. Arquivo de código acima de **400 linhas** não entra em `develop`.
2. Arquivo legado acima do limite **não pode crescer**: o check compara com o
   baseline e falha em qualquer aumento.
3. A cada etapa concluída, o baseline encolhe. Baseline vazio é o critério de
   conclusão do plano.
4. Testes seguem a mesma regra, divididos por cenário — não por "arquivo do
   módulo testado".
5. Arquivos gerados (`migrations/`, `node_modules`, build) ficam fora.

## 4. Etapas

Cada etapa = uma branch a partir de `develop` + um PR. Nenhuma muda
comportamento; a suíte é a prova (ver §6).

### Etapa 0 — travar a regra (0,5 dia, 1 PR)

- `scripts/check_file_size.py`: percorre `.py/.js/.html/.css`, ignora
  `migrations/`, `node_modules`, `old/`, `staticfiles/`, lê o limite (400) e o
  baseline (`scripts/file_size_baseline.json`).
  Falha se: arquivo novo > 400; arquivo no baseline crescer; arquivo do
  baseline desaparecer sem atualização do baseline.
- `scripts/file_size_baseline.json` gerado com os 84 arquivos atuais.
- Hook de pre-commit (`.githooks/pre-commit` ou `pre-commit`) chamando o script.
- Workflow `.github/workflows/file-size.yml` rodando em PR para `develop`.
- `AGENTS.md`: seção "Tamanho de arquivo — 400 linhas, imposto por CI", com o
  comando para atualizar o baseline só ao reduzir.

**Aceite:** PR com um arquivo de 401 linhas falha; PR que reduz o baseline passa.

### Etapa 1 — núcleo de revisão do OCR (2–3 dias, 1 PR)

`ia_ocr/revisao.py` (2.446) → pacote `ia_ocr/revisao/`:

| Módulo novo | Conteúdo | Origem aproximada |
|---|---|---|
| `estruturas.py` | `ParteRevisada`, `AtoRevisado`, `DocumentoRevisado`, `DadosRevisados`, exceções | l. 114–205 |
| `dados.py` | `dados_revisados`, `_montar_dados` | l. 205–377 |
| `linhas.py` | `versao_linha`, `aplicar_linha`, `_valor_*`, `identidade_parte` | l. 377–636 |
| `tipos.py` | `tipo_da_origem`, `_resolver_tipo_do_ato`, `_tipos_efetivos`, `resolucoes_de_tipo`, `tipos_efetivos`, caminhos | l. 694–860 |
| `obrigatorios.py` | `campo_obrigatorio`, `_local_*`, `descrever_pendencia` | l. 861–1035 |
| `pendencias.py` | `pendencias*`, `_pendencias_de_linhas` | l. 1036–1200 |
| `avisos.py` | `descrever_aviso`, `_origem_nao_consta`, `_origens_homonimas`, `avisos` | l. 1200–1439 |
| `rotulos.py` | `rotulo_efetivo`, `rotulo_de_campo`, ordem no formulário | l. 551–610, 1439–fim |

`ia_ocr/revisao.py` continua existindo como fachada que reexporta os nomes
públicos — nenhum import externo muda nesta etapa.

**Aceite:** `revisao.py` ≤ 60 linhas (fachada); cada módulo ≤ 400; suíte
`ia_ocr` sem novas falhas; `grep` de imports externos inalterado.

### Etapa 2 — importação assistida (2–3 dias, 1 PR)

`ia_ocr/importacao.py` (1.557) → pacote `ia_ocr/importacao/`:

`orquestracao.py` (`importar`, `resumo`) · `ato.py` (`_importar_ato`,
`_resolver_tipo_e_numero`) · `pessoas.py` (`_resolver_pessoa`, CPF/RG,
unicidade) · `cartorios.py` (`_resolver_cartorio`, fallback, homônimos) ·
`travas.py` (locks de nome/CPF/cartório) · `avisos.py` (gravação/leitura de
avisos). Fachada em `importacao/__init__.py`.

**Aceite:** nenhum módulo > 400; testes de importação passam sem alteração de
asserções.

### Etapa 3 — views do OCR (2 dias, 1 PR)

`ia_ocr/views.py` (1.429) → pacote `ia_ocr/views/`:
`texto.py` (texto/confirmar/editar páginas) · `extracao.py` (extrair,
reprocessar) · `campos.py` (`campos_job_ocr`, mascaramento, opções) ·
`salvar.py` (`salvar_bloco_ocr`, decisões, validação) · `importar.py`
(importar/finalizar) · `revisao.py` (`revisar_job_ocr`, `revisar_ato_ocr`,
navegação) · `helpers.py` (CSRF JSON, URLs, contexto). URLs continuam
apontando para os mesmos nomes de view via `ia_ocr/urls.py` — só o caminho de
import muda.

**Aceite:** `reverse()` de todas as rotas inalterado; testes de view passam;
`urls.py` sem mudança de nome de rota.

### Etapa 4 — serviços do OCR (2 dias, 1 PR)

`ia_ocr/services.py` (1.248) → `ia_ocr/services/`: `erros.py` (exceções) ·
`jobs.py` (criar/reprocessar/claim/reap) · `texto.py` (páginas, versão,
confirmação) · `extracao.py` (solicitar extração, validação de payload) ·
`revisao.py` (salvar bloco, finalizar revisão, limites) · `worker.py`
(`finalizar`, logs). Fachada em `services/__init__.py`.

**Aceite:** worker e `manage.py` inalterados; testes de fila/serviço passam.

### Etapa 5 — testes do OCR (3–4 dias, 1 PR por grupo)

24 arquivos acima de 400, sendo os três maiores `test_importacao.py` (3.437),
`test_revisao_tela.py` (2.793) e `test_revisao.py` (2.661). Divisão por
cenário, usando as factories que já existem (`tests/factories.py`,
`tests/payloads_extracao.py`):

1. `test_importacao` → `test_importacao_pessoas.py`, `_cartorios.py`,
   `_duplicidade.py`, `_avisos.py`, `_atos.py`.
2. `test_revisao_tela` → `_navegacao.py`, `_salvar.py`, `_pendencias.py`,
   `_prefill.py`.
3. `test_revisao` → acompanha a Etapa 1: um arquivo por módulo novo.
4. Demais (`test_extracao_views` 1.416, `test_backend_ocr_servico` 1.332,
   `test_revisao_formulario_view` 1.307, `test_ocr_client` 1.204,
   `test_fila` 1.009, etc.) na mesma lógica.

**Aceite:** mesma contagem de testes (nada apagado); nomes de teste preservados
para rastrear regressão; nenhum arquivo > 400.

### Etapa 6 — front-end do OCR (1–2 dias, 1 PR)

`static/dominial/js/ocr_revisao.js` (694) → `ocr_revisao/` (`form.js`,
`atos.js`, `pendencias.js`, `evidencia.js`, `api.js`); `ocr_card.js` (413) →
card + polling; `ia_ocr/tests/js/ocr_card.test.js` (1.275) e
`ocr_revisao.test.js` (975) → um arquivo por comportamento.

**Aceite:** testes JS verdes; nenhum bundle novo (mesmo `<script>` com
`defer`, ordem preservada).

### Etapa 7 — código `dominial` tocado pelo fluxo OCR (2–3 dias)

`services/lancamento_origem_service.py` (1.475) → `origem/` (`resolucao.py`,
`homonimos.py`, `criacao.py`); `views/lancamento_views.py` (1.213) →
`lancamento/` (`criar.py`, `editar.py`, `origem.py`); `admin.py` (2.157) →
`admin/` por modelo.

### Etapa 8 — resto (dominial/tests 20 arquivos, static 13, templates 3)

Última etapa, depois de F3 e antes do R4. `test_segregacao_usuario.py`
(5.202) é o maior item isolado do repositório.

## 5. Ordem e esforço

| Etapa | Escopo | Dias de agente | Quando |
|---|---|---:|---|
| 0 | travar a regra + CI | 0,5 | imediato |
| 1 | `revisao.py` | 2–3 | agora, antes de I-14 fase 3 |
| 2 | `importacao.py` | 2–3 | depois da 1 |
| 3 | `views.py` | 2 | depois da 2 |
| 4 | `services.py` | 2 | depois da 3 |
| 5 | testes OCR | 3–4 | junto das 1–4 |
| 6 | front OCR | 1–2 | depois da 5 |
| 7 | `dominial` do fluxo | 2–3 | depois de F3 |
| 8 | resto do repo | 3–4 | antes do R4 |

Total: ~18–24 dias de agente. Nada disso bloqueia o aceite do F3 se a Etapa 0
entrar primeiro: ela impede o código de piorar enquanto as features seguem.

## 6. Como cada PR prova que não quebrou nada

1. Baseline da suíte antes da mudança, com os ids das falhas salvo em arquivo.
2. Suíte depois, mesmos ids comparados por `diff`.
3. As falhas de ambiente conhecidas hoje são 11 (`test_leitor_pdf` /
   `test_ocr_client`, provider AES do `cryptography` no venv local) — mesmas em
   `develop`, não entram no critério.
4. PR só com movimentação de código: revisor confere que não há linha de lógica
   nova (diff de funções movidas, não alteradas).
5. `python scripts/check_file_size.py` verde com baseline atualizado para baixo.

## 7. Efeito esperado no fluxo de issues

- Brief de implementação passa a citar **um arquivo-alvo ≤ 400 linhas**, não um
  módulo inteiro.
- Revisão (Codex/Opus) consegue ler 100% do diff relevante.
- O formulário continua sendo a fonte de verdade da extração (regra #328): o
  split é por responsabilidade, nunca por "sobra de linhas".
