# Roadmap — Produto 2

> **Etapa 2 do contrato (Fase 2) — desenvolvimento funcional**
> Milestone: [Produto 2](https://github.com/transistir/CadeiaDominial/milestone/1)

## Escopo do Produto 2 (TDR)

Conforme o Termo de Referência:
- **(a)** Análise de fim de cadeia dominial funcional e documentada
- **(b)** Ajustes de visualização gráfica da cadeia dominial (tela cheia + painel lateral)
- **(c)** Importação básica de documentos digitais vinculados a registros dominiais
- **(d)** Armazenamento organizado e protegido dos dados e documentos

## Status Geral

| Fase | Status | Issues |
|---|---|---|
| Fim de cadeia | 🟢 Parcialmente entregue | #92 (bug), #93 (perf) |
| Visualização D3 | 🟢 Melhorias entregues | #54 (tela cheia) |
| Importação de documentos | 🔴 Não iniciado | #86 |
| Gestão de cartórios | 🟡 Em investigação | #90 |

---

## Entregues (Produto 1 → Produto 2)

PRs mergeados que compõem a base do Produto 2:

| PR | Título | Data |
|---|---|---|
| #89 | fix(#85): restaurar injeção de nós fim de cadeia + rótulo 'Lídima' + cores | 2026-07-31 |
| #88 | feat(d3): badge de keyword nos cards do organograma (#87) | 2026-07-29 |
| #84 | fix(tabela): badge keyword na serialização AJAX | 2026-07-28 |
| #83 | feat(tabela): badge de keyword na cadeia dominial | 2026-07-28 |
| #82 | fix(keyword): remove 'URGENTE' do keyword_alerta | 2026-07-28 |
| #81 | fix(redirect): usa TI do imóvel de origem ao redirecionar doc importado | 2026-07-28 |
| #73 | feat: seed orchestrator + writer (S-1 + S-2) | 2026-07-30 |
| #91 | refactor(d3): modulariza cadeia_dominial_d3.js em 12 arquivos | 2026-07-31 |

Issues fechadas associadas:
- **#85** — Validar análise fim de cadeia → resolvida pelo PR #89
- **#87** — Destacar cards com keyword → resolvida pelo PR #88

---

## Fila Atual (5 issues abertas)

### Sprint 1 — Correções de fim de cadeia

> **Objetivo:** estabilizar a análise de fim de cadeia antes de novas features.

| # | Título | Tipo | Prioridade | Estimativa |
|---|---|---|---|---|
| #92 | bug(hierarquia): parsing FIM_CADEIA falha com múltiplas origens e formato legado | 🐛 bug | **Crítica** | 1 dia |
| #93 | perf(hierarquia): query N+1 no processamento de fim de cadeia | ⚡ perf | Média | 1–2 dias |

**#92 — detalhe:**
- `_criar_no_fim_cadeia` não trata múltiplas origens separadas por `;`
- Formato legado de 5 partes (`FIM_CADEIA::tipo:classificacao:sigla`) não é aceito
- Nó rotulado 'Sem Origem' mesmo sendo destacamento público legítimo
- Correção sugerida na issue: split por `;` + fallback para `len(parts) == 5`
- Testes existentes só cobrem o caso de 6 partes com origem única

**#93 — detalhe:**
- Loop BFS faz 2 queries extras por documento na cadeia
- Cadeias com 50+ docs → 100+ queries desnecessárias
- Solução: `prefetch_related` com `Prefetch('lancamentos', queryset=...)`
- Nice-to-have, pode ser feito junto com #92

**Dependências:** nenhuma. Pode começar imediatamente.

---

### Sprint 2 — Gestão de cartórios

> **Objetivo:** permitir que admins localizem, corrijam e excluam cartórios incorretos.

| # | Título | Tipo | Prioridade | Estimativa |
|---|---|---|---|---|
| #90 | Investigar localização/exclusão de cartórios no admin | 🔧 admin | **Alta** | 2–3 dias |

**Escopo:**
- `CartoriosAdmin` dedicado com `search_fields` (nome, CNS, cidade, estado)
- `list_display` com id, nome, CNS, cidade, estado, tipo
- Filtros por estado, cidade, tipo — incluindo estado vazio/nulo
- Revisar pontos que criam cartórios automáticos sem cidade/UF confiáveis
- Eliminar fallback `Cartorios.objects.first().cidade`
- Caso concreto: Cartório de Ponta Porã duplicado com cidade "ASSIS BRASIL"

**Dados do problema:**
- 3.840 cartórios no banco
- 375 com `cidade = ASSIS BRASIL` e `estado` vazio
- Autocomplete limita a 10 resultados por `nome__icontains`

**Dependências:** nenhuma. Paralelo ao Sprint 1.

---

### Sprint 3 — Importação de documentos digitais

> **Objetivo:** upload e associação de arquivos a registros dominiais (sem OCR/processamento automático).

| # | Título | Tipo | Prioridade | Estimativa |
|---|---|---|---|---|
| #86 | Implementar importação básica de documentos digitais | 🆕 feature | **Alta** | 2–4 dias |

**Referência TDR:**
- Item 1.1(c): importação básica, sem processamento automático
- Item 8.1(e): armazenamento organizado e protegido
- Item 8.2(c): módulo de importação como entregável mínimo

**Tarefas:**
- [ ] Definir ponto de associação: documento, lançamento ou ambos
- [ ] Criar model de anexo ou campo de arquivo
- [ ] Migration
- [ ] Formulário/view de upload
- [ ] Exibir anexos na tela de detalhe do registro
- [ ] Validar tipo/tamanho (PDF + imagens)
- [ ] Respeitar autenticação/permissões (sem URL pública)
- [ ] Configurar armazenamento local/media
- [ ] Testar upload, visualização/download, remoção

**Dependências:** idealmente após Sprint 2 (cartórios limpos = dados mais confiáveis para associação).

---

### Sprint 4 — Visualização tela cheia + painel lateral

> **Objetivo:** redesign da tela da cadeia dominial — fullscreen + detalhe lateral no clique.

| # | Título | Tipo | Prioridade | Estimativa |
|---|---|---|---|---|
| #54 | Visualização em tela cheia com painel lateral de detalhes | 🆕 feature | **Alta** | 3–5 dias |

**Decisão de arquitetura (da issue):**
- Implementar no Django em produção (não no v2/React Flow)
- Avaliar reaproveitamento do componente React Flow do v2 trocando a camada de dados
- Se adaptação for maior que reimplementação → usar D3 atual + replicar padrão
- Requisito é comportamento (fullscreen + detalhe), não biblioteca específica

**Critérios de aceite:**
- [ ] Tela ocupa área útil inteira
- [ ] Clique em documento → painel lateral com informações
- [ ] Painel fecha/troca ao clicar em outro documento
- [ ] Funciona com cadeia real de tamanho médio/grande
- [ ] Não regride bugfixes recentes (duplicação de cards, cruzamento de linhas)

**Dependências:** idealmente após Sprint 1 (#92 corrigido = nós fim de cadeia com classificação correta no grafo).

---

## Cronograma Sugerido

```
Semana 1 (ago/04 – ago/08)
├── Sprint 1: #92 + #93 (correções fim de cadeia)
└── Sprint 2: #90 (cartórios admin) — paralelo

Semana 2 (ago/11 – ago/15)
├── Sprint 3: #86 (importação de documentos)
└── Revisão/testes Sprint 1–2

Semana 3 (ago/18 – ago/22)
├── Sprint 4: #54 (tela cheia + painel lateral)
└── Revisão/testes Sprint 3

Semana 4 (ago/25 – ago/29)
├── Integração e testes de aceitação
├── Documentação final do Produto 2
└── Deploy em produção e validação
```

---

## Critérios de Aceite do Produto 2

- [ ] Fim de cadeia classificado corretamente na árvore (sem 'Sem Origem' falso)
- [ ] Cartórios localizáveis e gerenciáveis no admin
- [ ] Upload de documentos funcionais (PDF + imagem) com persistência
- [ ] Visualização da cadeia em tela cheia com painel lateral de detalhes
- [ ] Todos os critérios individuais das issues #54, #86, #90, #92, #93 atendidos
- [ ] Deploy em produção estável com dados reais

---

*Última atualização: 2026-07-31*
