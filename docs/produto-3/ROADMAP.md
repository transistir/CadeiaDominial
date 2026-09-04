# Roadmap — Produto 3

> **Fila reordenada 04/09/2026 por sequência lógica de desenvolvimento.**
> Este arquivo é o **source of truth da fila**. O `docs/PLANO_SPRINTS.md`
> (plano geral de 02/09) passa a ser **histórico** — não planejar por ele.
>
> Origem: feedback de uso real de Umbelino (doc 01/09) e Maurício (03–04/09)
> sobre o sistema em produção (cadeiadominial.com.br).

## Princípios da sequência (por que esta ordem)

1. **Fechar o ciclo antes de abrir new front** — validar no test server,
   fechar issues e fazer release do que JÁ foi mergeado (Sprint 5), senão o
   fio se perde de novo (foi o que aconteceu com #179).
2. **Demanda nº1 do cliente primeiro** — #179 (XLS consolidado por TI) foi
   pedido em 03–04/09 e é a pendência mais quente; dependência #166 ✅.
3. **Bugs de produção antes de UX** — #144 (dados Maurício, aberto 13/08)
   vem antes dos rapid wins de interface.
4. **Agrupar por área de código** — export / cartórios / navegação: menos
   troca de contexto por sprint, review 3 modelos mais barato.
5. **O que depende de decisão do cliente vai pro final, com gate explícito**
   — #150 e #151 estão `pendente-analise-cliente`; o gate é disparado no
   início do R4 para dar tempo de resposta até o R7.
6. **Features grandes por último** — #123 (certificação) e #132
   (multi-usuário) só depois do solo estabilizado.

## Status geral (snapshot 04/09/2026)

**✅ Entregue (mergeado em develop, PRs #177–#188):**
#108 CI · #159–#162 form bugs · #166 CRI · #145 PDF averbações · #172 troncos ·
#171 árvore no modal · #174 badge cadeia · #167 M anterior

**Issues abertas só aguardando validação p/ fechar:**
#145 #152 #159–#162 #166 #167 #171 #172 #174

**Última release:** v1.0.8 (01/09) — PRs #177–#188 ainda sem tag.

---

## R1 — Fechar o ciclo do Sprint 5 — 🟡 TOPO DA FILA (0,5–1 dia)

> Gate de tudo: sem isso a fila cresce e se perde de novo.

1. **Validação no test server** dos PRs #177–#188 (imóvel 499 p/ #145,
   doc 3168/imóvel 491 p/ #152, planilha p/ #166) → **fechar as 11 issues**
   da lista acima.
2. **Release develop → main + tag v1.0.9** — *exige autorização explícita
   do luandro*.
3. **#187** limpar `cartorio_hidden` stale quando operador edita nome do
   cartório (P2 do review do PR #186 — código quente, mesma área do #167).
4. GitHub: criar milestone "Produto 3" e mover a fila (decisão luandro/Hiure).

## R2 — Exportação consolidada (semana seguinte a R1, ~1 semana)

> Demanda nº1 do cliente (03–04/09): "centenas de imóveis numa planilha só,
> a formatação do PDF é ideal".

1. **#13** área em ha perde formato 0,0000 nas tabelas (0,5–1 dia) —
   *fazer antes como warmup da área de export*.
2. **#179** relatório consolidado XLS por TI, formato = layout do PDF
   (3–5 dias) — botão "Exportar XLS da TI" na listagem; reaproveita o
   serviço de cadeia; risco: volume → openpyxl `write_only` se pesar.

## R3 — Integridade de documentos/cartórios I (semana 3, ~1–1,5 semana)

> Bug de produção + brechas de duplicidade. #144 é o mais antigo aberto
> com dados reais envolvidos (desde 13/08).

1. **#144** 🐛 produção: origem lançada (T585) não aparece na árvore —
   regressão v1.0.3→v1.0.5 ligada a cartórios (imóvel M955, Amambai).
2. **#114** 🐛 `criar_documento_matricula_automatico` permite cartório None.
3. **#141** 🐛 tratar IntegrityError (duplicidade canônica) em criar/editar.
4. **#149** ⚠️ avisar doc de mesmo tipo+número em cartório diferente.
5. **#110** levantar cartórios fantasmas + plano de merge (data quality —
   alimenta #113 do R5).

## R4 — UX Umbelino: rapid wins + CRI (semana 4, ~1 semana)

> **No início desta sprint: disparar o gate de decisão do cliente**
> (perguntas #150 e #151) — ver "Gates" abaixo.

1. **#168** TAB não parar no campo sigla *(P)*
2. **#169** janela de fim de cadeia fecha *(P)*
3. **#170** botão Adicionar Lançamento no topo *(P)*
4. **#164** quadro azul M/T em uma linha *(P)*
5. **#173** proprietário 255→500 + migração *(P)*
6. **#165** CRI obrigatório junto ao nº de M/T em todo o sistema *(M —
   maior do bloco; desenhar considerando #150 para minimizar retrabalho)*

## R5 — Constraint de identidade + fantasmas fase final (~0,5–1 semana)

1. **#113** constraint de identidade de documento + relatório de cartórios
   suspeitos *(usa saída do #110/R3)*
2. **#135** cartório 3574 (Tabelionato de Prado) fase 2 *(depende #113)*

## R6 — Multi-cadeia + navegação (~1 semana)

1. **#155** detectar doc compartilhado via `lancamento.documento_origem`
2. **#175** retornar à cadeia de trabalho ao voltar da árvore
3. **#176** botão retornar à relação de imóveis da TI *(depende #175)*

## R7 — Decisões de negócio cartórios (🚦 GATEADO pelo cliente)

> Só entra em execução se o gate disparado no R4 foi respondido.
> Enquanto isso, avançar R8 no lugar.

1. **#150** delimitar CRI vs cartório de transmissão no banco — *maior
   migração do plano, toca todas as FKs de cartório; design Opus 5 antes
   (spike 1–2 dias no início)*
2. **#151** avisar/exigir arquivamento quando origem referencia imóvel ativo

## R8 — Débitos técnicos + certificação fundiária (~1–1,5 semana)

1. **#105** `_processar_campos_inicio_matricula` indexa por posição
2. **#116** fixtures usam `Imovel.sncr` removido *(destrava suite de testes
   — fazer cedo se alguma sprint depender de testes)*
3. **#139** renomear 'transação' → 'transmissão' em todo o sistema
4. **#123** campos de certificação fundiária (SNCR, CCIR, CNIR, CIB, SIGEF,
   SNCI, CAR)

## R9 — Segregação por usuário (a maior feature, ~2 semanas)

1. **#132** multi-tenancy leve: cada usuário vê só seus imóveis
   - Semana 1: design de schema + middleware/filtros (Opus 5 no design)
   - Semana 2: implementação gradual + testes de isolamento
   - **Kickoff com luandro** — decisões de produto obrigatórias antes.

---

## Gates de decisão

- **GATE-CLIENTE (#150 + #151):** disparar pergunta no início do R4.
  Sem resposta até o fim do R6 → R8 entra antes do R7.
- **GATE-LUANDRO (release):** tag de produção só com autorização explícita.
- **GATE-PRODUTO (#132):** kickoff com luandro no início do R9.

## Dependências críticas

- R1 valida/fecha → libera a fila (evita acumular issues zumbis)
- #13 → #179 (mesma área, warmup)
- #110 (R3) → #113 (R5) → #135 (R5)
- #175 → #176 (dentro do R6)
- #165 (R4) desenhado junto a #150 (R7) para minimizar retrabalho
- #144 pode revelar dados que alimentam #110 — investigar primeiro no R3

## Cronograma (sprints ~1 semana; replanejar ao fim de cada uma)

```
Sem 07/09–11/09  R1 fechar ciclo (+ iniciar #13)
Sem 14/09–18/09  R2 #179 XLS consolidado
Sem 21/09–25/09  R3 integridade/cartórios (#144 primeiro)
Sem 28/09–02/10  R4 UX Umbelino (+ disparar GATE-CLIENTE)
Sem 05/10–09/10  R5 #113 + #135
Sem 12/10–16/10  R6 multi-cadeia/navegação
Sem 19/10–23/10  R7 (se gate respondido) — senão R8
Sem 26/10–30/10  R8 débitos + certificação
Sem 02/11–06/11  R9 kickoff #132
```

**Reserva de capacidade:** ~20% por sprint para novos relatos de
Maurício/Umbelino (padrão desde o plano geral).

**Fora do escopo:** backlog v2 #61–#72 (TypeScript/Cloudflare) — só depois
do Django estabilizar. #1 segue aberta como guarda-chuva.

---

*Última atualização: 04/09/2026 — fila R1–R9 criada por sequência lógica
(substitui a numeração de sprints do plano geral).*
