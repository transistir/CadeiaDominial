# FILA DE DESENVOLVIMENTO — Correção PDF/Excel

> Atualizado: 17/08/2026. Este arquivo é auto-contido: se você perdeu o contexto
> da sessão, leia só ele para saber **o que falta antes de desenvolver**, **a ordem**
> e **como desenvolver**. Detalhes técnicos estão nos planos linkados.

## Estado atual

| # | Item | Issue | Plano | Status |
|---|---|---|---|---|
| 1 | Capturar corpo do erro 500 do Excel | #146 | `PLAN_ISSUE_146_EXPORT_EXCEL.md` | ✅ Concluído 17/08 — causa raiz identificada (NÃO é IllegalCharacterError) |
| 2 | Inspecionar HTML intermediário do PDF | #145 | `PLAN_ISSUE_145_PDF_AVERBACOES.md` | ✅ Concluído 17/08 — service crasha ANTES do template (mesma causa raiz do #146) |
| 3 | Desenvolver fix do Excel (#146) | #146 | `PLAN_ISSUE_146_EXPORT_EXCEL.md` | ✅ **Em produção** 17/08 — PR #147 → develop → PR #148 → main (`6f88a9f2`) → tag `v1.0.6` |
| 4 | Desenvolver fix do PDF (#145) | #145 | `PLAN_ISSUE_145_PDF_AVERBACOES.md` | ⏳ Revalidar se as 7 averbações aparecem AGORA (crash removido pela v1.0.6) |

## Resultados da Fase 1 (17/08/2026)

**Fix #146 commitado** (`217b7913`, branch `fix/146-export-excel`, não-pushado):
- `_obter_tronco_principal_completo` pula nós com `is_fim_cadeia` antes do
  `Documento.objects.get()` (7 linhas, flag-based, ordem/dedup preservados).
- `logger.exception` nas duas views de exportação (loga só tis_id/imovel_id).
- 5 testes novos em `test_exportacao_cadeia.py` (fixture com `OrigemFimCadeia` real):
  12/12 passam; reproduzem o `ValueError` sem o fix (prova de não-vacuidade).
- Suíte completa do app: mesmos 53 vermelhos do baseline de `main` intocada
  (zero novos, zero corrigidos) — quebra pré-existente, sem relação:
  cluster duplicata (30), documento_importado (8), documento_lancamento (8),
  issue_118 (3), identidade (2), + `pytest` ausente p/ `test_api_cnj`/`test_onr_post`.
  **Candidato a issue própria.**
- Nota de runbook: usar `manage.py test dominial.tests` (dotted label);
  `manage.py test dominial` quebra por resolução de pacote.

## Resultados da Fase 0 (17/08/2026)

**Item 1 — Excel (#146):** corpo do 500 capturado por diagnóstico read-only dentro do
container de produção:

```
Erro ao gerar Excel: Field 'id' expected a number but got 'fim_cadeia_3261_8937_512'.
```

- **Hipótese principal REFUTADA:** 0 campos com caracteres de controle XML em todo o
  imóvel 499 → não é `IllegalCharacterError` do openpyxl.
- **Causa raiz:** `HierarquiaArvoreService.construir_arvore_cadeia_dominial()` injeta nós
  sintéticos de fim de cadeia (issue #85) com **id string** `fim_cadeia_{doc}_{lanc}_{origem}`
  e flag `is_fim_cadeia: True`. `CadeiaCompletaService._obter_tronco_principal_completo()`
  (`cadeia_completa_service.py:83-85`) faz `Documento.objects.get(id=doc_node['id'])` para
  TODOS os nós da árvore sem pular os sintéticos → `ValueError`.
- **Fix primário:** pular nós `is_fim_cadeia` nesse loop. Sanitizador + `logger.exception()`
  + `BytesIO` do plano original permanecem como defesa em profundidade.

**Item 2 — PDF (#145):** o diagnóstico que renderizaria o template crashou na chamada a
`get_cadeia_completa()` com o MESMO erro. A view `exportar_cadeia_completa_pdf`
(`cadeia_dominial_views.py:408`) usa o mesmo serviço — ou seja, **hoje o botão "Exportar PDF"
padrão também retorna página de erro, não PDF**.

- O relato do #145 (PDF gerado sem as 7 averbações) ou é **anterior** à criação da origem
  fim-de-cadeia 512, ou veio do caminho de **sequência personalizada** (modal →
  `get_cadeia_completa_com_sequencia_personalizada`, que não usa a árvore).
- **Pendência opcional:** timeline de criação da origem_fc 512 vs. averbações
  (query pronta em `/tmp/fase0/timeline.sql` na máquina de teste; execução em produção
  travou no gate de aprovação — precisa de OK explícito).
- A condição do template `cadeia_completa_pdf.html:187`
  (`averbacao and != transcricao`) **continua suspeita** para o sumiço das descrições,
  mas só é validável DEPOIS do fix do crash.

## Fase 0 — Pendências de produção (desbloqueiam tudo)

Ambas **read-only**, via ponte SSH (teste `root@188.245.225.127` → prod `root@46.62.152.252`,
app em `/root/CadeiaDominial`). Caso real: **imóvel 499** (TI 67 Barra Velha, matrícula 29718).

1. **Excel (#146):** abrir `https://cadeiadominial.com.br/dominial/tis/67/imovel/499/ver-cadeia-dominial/`,
   DevTools → Network, clicar em **Exportar Excel** e copiar status + corpo da resposta 500.
   A view já retorna `Erro ao gerar Excel: {e}` em texto puro — o corpo revela a exceção.
   (Alternativa sem navegador: `docker-compose logs app | grep -i excel`.)
   **Hipótese principal:** caractere de controle XML inválido em texto → `IllegalCharacterError` do openpyxl.

2. **PDF (#145):** dentro do container app, rodar shell Django que monte o contexto do
   `CadeiaCompletaService.get_cadeia_completa()` do imóvel 499, renderize
   `cadeia_completa_pdf.html` via `render_to_string` e busque os textos das 7 averbações
   (lançamentos 8747, 8749, 8751, 8800, 8936, 8939, 9015) **antes** do WeasyPrint.
   - Se o texto ESTÁ no HTML → bug de paginação CSS (`page-break-inside: avoid` aninhado,
     `cadeia_completa_pdf.css:69-90, 246-261`).
   - Se o texto NÃO está no HTML → problema no contexto/template (ver condição
     `cadeia_completa_pdf.html:187`).
   - Logar só presença/comprimento/hash, nunca o conteúdo (dados sensíveis).

## Fase 1 — Desenvolvimento (ordem e racional)

### 1º: Issue #146 — Excel (estimativa 8–12h)
- **Por que primeiro:** a causa é fato (mensagem do erro capturada); fix tem escopo
  fechado e **também desbloqueia o PDF padrão** (mesmo serviço).
- **Escopo revisado pós-Fase 0:**
  1. **Fix primário:** em `CadeiaCompletaService._obter_tronco_principal_completo()`
     (`cadeia_completa_service.py:83-85`), pular nós com `doc_node.get('is_fim_cadeia')`
     antes do `Documento.objects.get(id=...)`. Teste de regressão com nó sintético.
  2. **Defesa em profundidade (plano original):** `logger.exception()` nas views de
     exportação (hoje perdem traceback); sanitizador central
     `dominial/utils/excel_utils.py` (remove controles XML proibidos, preserva `\n\t\r`,
     limita 32.767 chars); salvar em `BytesIO` antes do `HttpResponse`; testes com dados
     sujos (`\x0b`, >32k chars, emoji, `=`).
- **Branch sugerida:** `fix/146-export-excel`

### 2º: Issue #145 — PDF averbações
- **Pós-Fase 0:** o crash do fim-de-cadeia (fix do item 3) provavelmente já muda o
  comportamento do PDF. Antes de mexer no template: revalidar se as 7 averbações
  (8747, 8749, 8751, 8800, 8936, 8939, 9015) aparecem no HTML renderizado com o fix
  aplicado (reaproveitar `/tmp/fase0/diag_145_pdf.py`).
- **Escopo do plano (se necessário após revalidação):** teste de regressão do template
  real; alinhar condição de averbação com a tela (remover cláusula `!= 'transcricao'` de
  `cadeia_completa_pdf.html:187`, salvo confirmação funcional em contrário); corrigir
  paginação CSS **só se** o HTML contiver o texto e o PDF não.
- **Descartado:** pin pydyf **já está em produção** (ancestral da v1.0.5) — não é a causa.
- **Branch sugerida:** `fix/145-pdf-averbacoes`

## Como desenvolver (convenções do repo — ver AGENTS.md)

- Implementação: **Sonnet 5** (`claude --model sonnet`); arquitetura/revisão final: **Opus 5**;
  gate de PR: **Codex GPT-5.6-sol xhigh**.
- Loop: fix → Codex review → commit → Codex PR review até os 3 modelos APPROVAREM.
- **Nunca mergear sem autorização explícita do dono do projeto** (APPROVE triplo é necessário, não suficiente).
- Testes colocados com o código (`dominial/tests/test_exportacao_cadeia.py` já existe —
  hoje tem fixture sem lançamentos; ambos os planos mandam ampliá-la).
- Ao concluir cada item: atualizar a tabela de status deste arquivo.

## Fora desta fila (relatos relacionados já mapeados)

- Edição bloqueada (Mauricio, 16/08): comportamento do #140/#138 (folha readonly p/ matrícula) — não é bug novo.
- Duplicata matrícula 29718 (imóveis 499 e 508, cartórios 483/481): tema da **#113** — constraint permite por design (#14); decisão de produto pendente.
- Documento-lixo "M0": tema da **#144**.
