# Roadmap — Produto 2 (ENCERRADO)

> **Etapa 2 do contrato (Fase 2) — desenvolvimento funcional**
> Milestone: [Produto 2](https://github.com/transistir/CadeiaDominial/milestone/1)
>
> **Status: ✅ ENCERRADO em 04/09/2026.** Milestone 5/5 fechado. A fila
> pós-entrega (feedback Umbelino 01/09 + Maurício 03–04/09) movida para
> **`docs/produto-3/ROADMAP.md`**.

## Escopo do Produto 2 (TDR)

Conforme o Termo de Referência:
- **(a)** Análise de fim de cadeia dominial funcional e documentada
- **(b)** Ajustes de visualização gráfica da cadeia dominial (tela cheia + painel lateral)
- **(c)** Importação básica de documentos digitais vinculados a registros dominiais
- **(d)** Armazenamento organizado e protegido dos dados e documentos

## Status Final

| Fase | Status | Issues |
|---|---|---|
| Fim de cadeia | ✅ Entregue | #92, #93 (31/07) |
| Visualização D3 | ✅ Entregue | #54 (06/08) |
| Importação de documentos | ✅ Entregue | #86 (31/07) |
| Gestão de cartórios | ✅ Entregue | #90 (31/07) |

Milestone Produto 2: **5/5 issues fechadas**. Produção ativa em cadeiadominial.com.br.

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

Sprints 1–4 (concluídos): correções de fim de cadeia (#92, #93), gestão de
cartórios no admin (#90), importação de documentos digitais (#86), visualização
tela cheia + painel lateral (#54).

---

## Critérios de Aceite do Produto 2

- [x] Fim de cadeia classificado corretamente na árvore (#92, #93)
- [x] Cartórios localizáveis e gerenciáveis no admin (#90)
- [x] Upload de documentos funcionais com persistência (#86)
- [x] Visualização da cadeia em tela cheia com painel lateral (#54)
- [x] Issues #54, #86, #90, #92, #93 fechadas (milestone 5/5)
- [x] Deploy em produção com dados reais (cadeiadominial.com.br)

---

*Encerrado: 04/09/2026. Fila ativa em `docs/produto-3/ROADMAP.md`.*
