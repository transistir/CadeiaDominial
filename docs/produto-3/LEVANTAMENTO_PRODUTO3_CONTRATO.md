# Levantamento — Produto 3 (contrato FADESP nº 019/2026) vs. código Django/D3

> **Escopo deste levantamento (definido pelo Hiure em 14/10/2026):** apenas o
> **código Django/D3 do Produto 3** deste contrato. Ficam de fora:
> **FUNAPE Fase 3** (outro contrato), **React Flow / v2** (outro contrato — o
> cliente aceitou o D3) e o **Produto 4** (manutenção/suporte).
> **A fila aprovada não muda com este documento:** a ordem vigente é
> **R4 → R5 → R6 → R7 → R8 → R10** (`PLANO_ESTRATEGICO_POS_V110.md`, decisão D1
> do Hiure em 02/10) e os blocos abaixo são os mesmos do `ROADMAP.md`.
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

**Nota sobre o React Flow (Etapa 2):** o cliente aceitou a entrega com **D3**
(decisão comunicada pelo Hiure em 14/10/2026); a implementação em React Flow sai
deste contrato. Fecha-se aqui como **atendido com D3**.

⚠️ **Pendência de conferência:** a data de assinatura está em branco no PDF
("Belém/PA, de ___ de 2026") — sem ela não é possível dizer em que mês do
cronograma o produto está.

## 2. Feito — 31 issues fechadas de 01/09 a 13/10 (6 releases)

| Área | Issues |
|---|---|
| Cadeia / árvore | #145 · #167 · #171 · #172 · #174 · #201 (Fases 0+0b) · #218 · #229 · #230 · #144 (fases 1–2) |
| Lançamento / formulário | #114 · #152 · #157 · #159 · #160 · #161 · #162 · #168 · #187 · #210 · #213-f1 · #227 · #241 · #244 · #245 · #246 |
| Export PDF / XLS | #13 · #166 · #179 · #193 · #204 |
| Multi-usuário | #132 / PR #133 — segregação de dados por usuário (C1–C9, 154 arquivos, +24.339/−911, suíte 1109 testes) |

- **Releases:** v1.0.8 (01/09) · v1.0.9 (10/09) · v1.0.10 (12/09) · v1.0.11 (20/09) · v1.0.12 (30/09) · **v1.1.0 (13/10, deploy de produção success; #132 fechada)**.
- Produto 2 encerrado em 04/09 (milestone 5/5) — base sobre a qual o Produto 3 trabalha.

## 3. Falta — 40 issues de código Django/D3, pelos blocos do ROADMAP

### R3 (14 dos 40) + R3.5 (2 adicionais) — 🧊 geladeira (condicionados ao destrave)
> Estes itens **não têm data**: só entram na execução pelos critérios de
> destravar do R3 (dump fresco de produção → test server **sanitizado**,
> revalidação item a item contra os dados reais e reordenação aprovada pelo
> Hiure). **Única exceção já registrada** (regra da EXCEÇÃO R9): **#238** e
> **#223** podem furar a fila caso a caso, com aprovação do Hiure.

- Bugs de produção: **#238** (edição apaga Observações — perda de dado) · **#223** (`novo_documento` 500) · **#219** (início de matrícula aceita a própria matrícula) · **#144** (fases 1–2 entregues; revalidar/fechar).
- Integridade / identidade de documento: #141 · #149 · #212 · #228 · #232 · #237 · #240 · #248.
- Enfileiradas em 14/10 (autorização do Hiure): #266 · #267.
- **R3.5 (congelado junto):** #206 · #202 — exigem a mesma revalidação.
- **Fora da fila, aguardando posição:** **#269** (origem removida no form de edição não apaga `lancamento.origem`) — é bug de produção da mesma área do #270, mas **não foi enfileirado**.

### R4 — 8 itens (primeiro bloco executável)
#271 autocomplete Forma/Título · #169 janela de fim de cadeia não fecha ·
#170 botão Adicionar Lançamento · #164 quadro M/T em 1 linha ·
#173 proprietário 255→500 · #165 CRI obrigatório com M/T ·
#213 fases 2–3 (nomes compostos + multi-proprietário) ·
#270 ocultar campos de origem em registro/averbação *(enfileirada 14/10)*.

### R5 + R6 — 4 itens
R5: #113 constraint de identidade. R6: #155 documento compartilhado · #175 ·
#176 navegação.

### R8 — 9 itens (débitos e segurança em Django/JS)
#105 · #116 · #123 · #139 · #196 (XSS autocompletes) · #234
(importar-cartorios sem auth) · #235 · #243 · #249.

### R10 — 4 itens (último bloco da ordem aprovada)
#252 "Outra" (texto livre) → #251 export inclui fim de cadeia → #253 cartório
da transmissão sem CRI · #254 badge "Parcialmente sem Origem".

> **Dependência:** o **#232** corrige os falso-negativos do filtro CRI e tem de
> estar pronto **antes ou junto do #253**. Atenção ao gate: o **#232 é item do
> R3 (geladeira)** — sob a ordem aprovada (R4 → R5 → R6 → R7 → R8 → R10) o R8
> vem antes do R10, mas isso **não libera** o #232: ele continua atrás do
> destrave do R3 (dump + revalidação + reordenação aprovada) ou de uma exceção
> registrada. O **#253 (R10) não deve começar** antes disso.

## 4. Fora do Produto 3 (não entram neste levantamento)

- **Fase 3 — FUNAPE** (outro contrato): #258–#265 (IA/OCR).
- **React Flow / v2** (outro contrato): #61–#72 — cliente aceitou o D3.
- **Produto 4 — manutenção/infra:** #197 (disco/prune) · #198 (cache de estáticos) · #199 (alerta de deploy) · #257 (nginx do test server).
- **Dados em produção (não é código):** #110 (levantamento de cartórios) · #135 · #215 (reparo de `Pessoas` — correção manual do usuário).
- **Gate do cliente:** #150 e #151 (`pendente-analise-cliente`) — gate do R7.

## 5. Contagem (snapshot 14/10/2026)

72 issues abertas no GitHub:

| Grupo | Qtd |
|---|---|
| **Código Django/D3 (Produto 3)** | **40** |
| Infra/manutenção (Produto 4) | 4 |
| Dados em produção | 3 |
| Gate do cliente | 2 |
| Congeladas (R3.5: #202, #206) | 2 |
| Guarda-chuva (#1) | 1 |
| Fase 3 — FUNAPE (outro contrato) | 8 |
| v2 (outro contrato) | 12 |

## 6. Caminho para finalizar o Produto 3 (ordem aprovada, sem reordenar a fila)

1. **R4 (8)** — 1–1,5 sprint (rapid wins primeiro: #271, #169, #170, #164) → **v1.2.0**.
2. **R5 + R6 (4)** — ~0,5–1 sprint → **v1.3.0**.
3. **R7** — só se o GATE-CLIENTE (#150/#151) abrir; sem resposta, **R8 entra no lugar**.
4. **R8 (9)** — 1–1,5 sprint (agrupar #196+#235 e #243+#249) → **v1.4.0**.
5. **R10 (4)** — 1 sprint, por último (o plano estratégico reserva o **v1.5.0**); antes do #253 confirmar o estado do **#232 (R3 — geladeira)**, que é pré-requisito do filtro CRI.

- **R3 (14)** — sem data: dependem do destrave da geladeira (dump sanitizado +
  revalidação item a item + reordenação aprovada pelo Hiure). Inclui as duas
  recém-enfileiradas (#266, #267). Exceção: #238 e #223.
- **R3.5 (#202, #206) — 2 itens adicionais, fora dos 40:** congelados junto do
  R3 e contados à parte no snapshot (seção 5).
- **#269** — fora da fila; precisa de posição aprovada antes de entrar.
- **Resumo (fecha em 40):** **25** com sprint na ordem aprovada (~**4 sprints /
  4–6 semanas**) + **14** sob o gate do R3 + **1** fora da fila = **40 issues
  de código Django/D3**. Os 2 do R3.5 são adicionais e não entram nesta conta.

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
