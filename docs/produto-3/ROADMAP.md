# Roadmap — Produto 3

> **Fase pós-entrega — estabilização em campo.** Nasceu do feedback de uso real:
> Umbelino (doc 01/09/2026) e Maurício (03–04/09/2026), sobre o sistema em
> produção (cadeiadominial.com.br).
>
> **Milestone GitHub: ainda não existe** — sugerido criar "Produto 3" e mover
> as issues da fila atual para ele (decisão luandro/Hiure).

## Status Geral

| Sprint | Escopo | Status |
|---|---|---|
| Sprint 5 — Exportações | #166 #145 #172 (+ #171 #174 #167 do plano geral) | ✅ Concluído 04/09 (PRs mergeados, issues ainda abertas) |
| Sprint 6 — XLS consolidado por TI | #179 + #13 | 🔴 Não iniciado |
| Sprints 2–4 do plano geral | Integridade/cartórios, UX Umbelino, multi-cadeia | 🔴 Não executados |

Base: `docs/PLANO_SPRINTS.md` (plano geral, 02/09) + fila de 04/09.

---

## Sprint 5 — Exportações: correções e diagramação — ✅ CONCLUÍDO (04/09/2026)

> Objetivo: estabilizar e compactar as exportações antes do relatório consolidado.

| # | Título | Tipo | Prioridade | Status |
|---|---|---|---|---|
| #166 | Trocar 'Cartório de Registro de Imóveis' por 'CRI' na planilha | 🎨 diagramação | **Alta** | ✅ PR #180 (04/09) |
| #145 | PDF completo omite textos das averbações | 🐛 bug | **Crítica** | ✅ PR #181 (04/09) |
| #172 | Suprimir 'tronco principal' na cadeia exportada | 🎨 diagramação | Média | ✅ PR #182 (04/09) |

Extras puxados do Sprint 5 do plano geral, entregues na mesma leva:

| # | Título | Status |
|---|---|---|
| #171 | Árvore D3 no modal 'Selecionar Sequência de Exportação' | ✅ PR #183 (04/09) |
| #174 | Badge de cadeia finalizada na relação de imóveis da TI | ✅ PR #184 (04/09) |
| #167 | M anterior vinculada no formulário de origem (quebra sucessória) | ✅ PRs #185 + #186 + #188 (04/09) |

Também no período (Sprint 1 do plano geral): **#108** CI ✅ (PR #177),
**#159–#162** form bugs ✅ (PR #178).

### Pendências pós-merge do Sprint 5

1. **Fechar issues no GitHub** — #145, #166, #167, #171, #172, #174 seguem
   OPEN; fechar após validação no test server/produção (padrão do repo).
2. **Release** — os PRs #177–#188 estão no `develop`; última tag é **v1.0.8**
   (01/09). Falta release `develop → main` + tag para subir pra produção.
3. **#166**: conferir na planilha real se "CRI" aparece em valores E rótulos de
   coluna (requisito do cliente).

---

## Sprint 6 — Relatório consolidado XLS por TI — 🔴 NÃO INICIADO (topo da fila)

> Demanda do cliente (03–04/09): exportar centenas de imóveis numa planilha só.
> **Status 04/09: #179 nunca foi iniciado — sem branch, sem worktree, sem PR.**

| # | Título | Tipo | Prioridade | Estimativa |
|---|---|---|---|---|
| #179 | Relatório consolidado XLS por TI — formato = layout do PDF | 🆕 feature | **Alta** | 3–5 dias |
| #13 | Área em ha perde formato brasileiro (0,0000) nas tabelas | 🐛 bug | Média | 0,5–1 dia |

- **Formato definido pelo cliente (04/09): "a formatação do PDF é ideal"** — a
  tabela da cadeia (tela/PDF) é a referência; uma seção por imóvel.
- Reaproveita o serviço de cadeia existente (mesma fonte do export por imóvel).
- Ponto de entrada: botão "Exportar XLS da TI" na listagem de imóveis da TI.
- Risco: volume/memória com centenas de imóveis — openpyxl `write_only` se pesar.
- **Dependência #166: ✅ resolvida** (PR #180 — CRI libera espaço de coluna).

---

## Backlog (Sprints 2–4 do plano geral — não executados)

Ver `docs/PLANO_SPRINTS.md` para detalhe. Resumo:

- **S2 — Integridade/cartórios I:** #144 #114 #141 #149 #110
- **S3 — UX Umbelino I:** #168 #169 #170 #164 #173 #165 #113
- **S4 — Multi-cadeia + decisões:** #155 #175 #176 #150 #151 #135
- Outras abertas: #1 #13 #105 #116 #123 #132 #139 #152 #160 #161 #162 #187

---

## Cronograma

```
Semana 07/09–11/09
├── Sprint 5 ✅ concluído antecipadamente (04/09)
└── Validação no test server → fechar issues → release develop→main (tag pós-v1.0.8)

Semana 14/09–18/09
└── Sprint 6: #179 (XLS consolidado por TI) + #13 (formato área) + revisão/testes
```

---

*Última atualização: 04/09/2026 (levantamento de fila pós-merge #180–#188).*
