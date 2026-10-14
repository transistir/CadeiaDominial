# Levantamento — Produto 3 (contrato FADESP nº 019/2026) vs. código Django/D3

> **Escopo deste levantamento (definido pelo Hiure em 14/10/2026):** apenas o
> **código Django/D3 do Produto 3** deste contrato. Ficam de fora:
> **FUNAPE Fase 3** (outro contrato), **React Flow / v2** (outro contrato — o
> cliente aceitou o D3) e o **Produto 4** (manutenção/suporte).
> Fonte da fila: `docs/produto-3/ROADMAP.md`. Contrato e proposta conferidos em
> `contrato/fase2/` (fora do repo).

## 1. O que o contrato pede (Proposta + Contrato nº 019/2026/AJU-FADESP)

- **Valor:** R$ 70.000,00 (R$ 50.000 desenvolvimento em 3 parcelas + R$ 20.000 manutenção em 5 parcelas mensais).
- **Vigência:** 12 meses a partir da assinatura.
- **Etapa 1 (m1–2):** ajustes de interface e usabilidade.
- **Etapa 2 (m3–4):** funcionalidades — Fim de Cadeia, Documentos, React Flow.
- **Etapa 3 (m5):** testes funcionais, correções e **entrega técnica**.
- **Etapa 4 (m6–10):** manutenção corretiva + suporte remoto (até 30h/mês).
- **Obrigações (cl. 4.2):** corrigir falhas/vulnerabilidades sem ônus; código
  organizado e apto à manutenção por terceiros (cl. 8.4); LGPD (cl. 9).

⚠️ **Pendência de conferência:** a data de assinatura está em branco no PDF
("Belém/PA, de ___ de 2026") — sem ela não é possível dizer em que mês do
cronograma o produto está.

## 2. Feito — 31 issues fechadas de 01/09 a 13/10 (6 releases)

| Área | Issues |
|---|---|
| Cadeia / árvore | #145 · #167 · #171 · #172 · #174 · #201 (Fases 0+0b) · #218 · #229 · #230 · #144 (fases 1–2) |
| Lançamento / formulário | #114 · #152 · #157 · #159 · #160 · #161 · #162 · #168 · #187 · #210 · #213-f1 · #227 · #241 · #244 · #245 · #246 |
| Export PDF / XLS | #13 · #166 · #179 · #193 · #204 |
| Multi-usuário | #132 / PR #133 — segregação por dados por usuário (C1–C9, 154 arquivos, +24.339/−911, suíte 1109 testes) |

- **Releases:** v1.0.8 (01/09) · v1.0.9 (10/09) · v1.0.10 (12/09) · v1.0.11 (20/09) · v1.0.12 (30/09) · **v1.1.0 (13/10, deploy de produção success; #132 fechada)**.
- Produto 2 encerrado em 04/09 (milestone 5/5) — base sobre a qual o Produto 3 trabalha.

## 3. Falta — 40 issues de código Django/D3

### A. Bugs de produção abertos (5) — hoje na geladeira do R3
- **#238** edição de documento abre Observações vazio e o save **apaga o valor** (perda de dado).
- **#223** `novo_documento` estoura **500** (assinatura incompatível).
- **#269** origem removida no form de edição não apaga `lancamento.origem` — origem fantasma quebra a cadeia.
- **#219** início de matrícula aceita a própria matrícula/transcrição como origem (auto-loop).
- **#144** fases 1–2 já entregues — issue segue aberta para revalidar/fechar.

### B. R4 — UX Umbelino + CRI (7)
#271 autocomplete Forma/Título · #169 janela de fim de cadeia não fecha ·
#170 botão Adicionar Lançamento · #164 quadro M/T em 1 linha ·
#173 proprietário 255→500 · #165 CRI obrigatório com M/T ·
#213 fases 2–3 (nomes compostos + multi-proprietário).

### C. R5 / R6 (6)
#113 constraint de identidade · #139 transação→transmissão · #123 campos de
certificação fundiária · #155 documento compartilhado · #175 · #176 navegação.

### D. R8 — débitos e segurança em Django/JS (15)
#105 · #116 · #141 · #149 · #196 (XSS autocompletes) · #212 · #228 · #232 ·
#234 (importar-cartorios sem auth) · #235 · #237 · #240 · #243 · #248 (admin) ·
#249.

### E. R10 — features de fim de cadeia (4)
#252 "Outra" (texto livre) → #251 export inclui fim de cadeia → #253 cartório da
transmissão sem CRI · #254 badge "Parcialmente sem Origem".

### F. Fora da fila — criadas em 08/10/2026 (3) — enfileiradas em 14/10
#270 ocultar campos de origem em registro/averbação (→ R4 item 10) ·
#267 avisar homônimo cross-type (→ R3 item 16) ·
#266 ação de reparo para origens não resolvidas na árvore (→ R3 item 17).

## 4. Fora do Produto 3 (não entram neste levantamento)

- **Fase 3 — FUNAPE** (outro contrato): #258–#265 (IA/OCR).
- **React Flow / v2** (outro contrato): #61–#72 — cliente aceitou o D3.
- **Produto 4 — manutenção/infra:** #197 (disco/prune) · #198 (cache de estáticos) · #199 (alerta de deploy) · #257 (nginx do test server).
- **Dados em produção (não é código):** #110 (levantamento de cartórios) · #135 · #215 (reparo de `Pessoas` — correção manual do usuário).
- **Gate do cliente:** #150 e #151 (`pendente-analise-cliente`).
- **Congeladas:** #202 (exige PRD) · #206 (exige revalidação).
- **Fora da fila, aguardando posição:** #257 e — atenção — **#269**, que é bug de
  produção da mesma área do #270 mas não foi enfileirado.

## 5. Contagem (snapshot 14/10/2026)

72 issues abertas no GitHub:

| Grupo | Qtd |
|---|---|
| **Código Django/D3 (Produto 3)** | **40** |
| Infra/manutenção (Produto 4) | 4 |
| Dados em produção | 3 |
| Gate do cliente | 2 |
| Congeladas (geladeira R3/R3.5) | 2 |
| Guarda-chuva (#1) | 1 |
| Fase 3 — FUNAPE (outro contrato) | 8 |
| v2 (outro contrato) | 12 |

## 6. Caminho para finalizar o Produto 3

1. **A (5)** — puxar da geladeira caso a caso (a fila já prevê a exceção); ~1 semana.
2. **B (7)** — 1 sprint, rapid wins primeiro (#271, #169, #170, #164).
3. **E (4)** — 1 sprint (#252 → #251 → #253; #254 paralelo).
4. **D (15)** — 1–1,5 sprint (agrupar #196+#235 e #243+#249).
5. **C (6)** — 1 sprint.
- **Releases sugeridas:** v1.2.0 (A+B+E) e v1.3.0 (C+D).
- **Estimativa:** ~5 sprints / 5–7 semanas com o pipeline atual (1 issue = 1
  branch = 1 PR → develop, TDD + review de 3 modelos, tag só com autorização).

### Pendência para fechar o produto
O contrato exige **entrega técnica** na Etapa 3 (cl. 8.4: código organizado e
documentado, apto à manutenção por terceiros). Não existe artefato de entrega
(termo + guia de manutenção/deploy). Item de 1 página — confirmar se entra no
Produto 3.

## 7. Evidências

- Fila e status dos blocos: `docs/produto-3/ROADMAP.md` + `PLANO_ESTRATEGICO_POS_V110.md`.
- Issues: API do GitHub (`transistir/CadeiaDominial`) — 72 abertas, 60 fechadas.
- Releases/tags: `git tag` (v1.0.8 → v1.1.0) + runs do CI "Deploy produção (por tag)".
- Contrato/proposta: `contrato/fase2/` (PDF assinado + proposta Transistir).
