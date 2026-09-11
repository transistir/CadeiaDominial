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

## Status geral (snapshot 11/09/2026)

**✅ Entregue (mergeado em develop, PRs #177–#194):**
#108 CI · #159–#162 form bugs · #166 CRI · #145 PDF averbações · #172 troncos ·
#171 árvore no modal · #174 badge cadeia · #167 M anterior ·
**#13 área pt-BR · #179 XLS consolidado por TI (R2 completo)**

**Releases:** v1.0.8 (01/09) · **v1.0.9 (10/09, PR #190 — PRs #177–#188)** ·
PRs #191/#192/#194 (R2) em develop **ainda sem tag** → próxima release v1.0.10.

**Fila Django: 25 issues abertas** (#1 guarda-chuva + #61–#72 v2 fora de escopo).

---

## R1 — Fechar o ciclo do Sprint 5 — 🟢 quase fechado (restam #187 + milestone)

> Gate de tudo: sem isso a fila cresce e se perde de novo.
> **R2 antecipado 10/09/2026 por demanda urgente do Hiure** (formatação do
> XLS = layout do PDF, #179, nunca desenvolvida). #187 e o milestone ficam
> pendentes e entram na sequência do #179.

1. **Validação no test server** dos PRs #177–#188 ✅ **FEITO 10/09/2026**
   (imóvel 265/Guyraroká usado no lugar do 499 — test server tem outra
   numeração; PDF 23 págs + XLS inspecionados, suites 18/18 e 42/42 OK)
   → **11 issues fechadas: #145 #159 #160 #161 #162 #166 #167 #171 #172 #174**
   (+ #152 já fechada antes).
2. **Release develop → main + tag v1.0.9** ✅ **FEITO 10/09/2026**
   (PR #190 mergeado + tag v1.0.9 — GATE-LUANDRO autorizado).
3. **#187** limpar `cartorio_hidden` stale quando operador edita nome do
   cartório (P2 do review do PR #186 — código quente, mesma área do #167).
4. GitHub: criar milestone "Produto 3" e mover a fila (decisão luandro/Hiure).

## R2 — Exportação consolidada — ✅ FECHADO 11/09/2026 (PRs #191/#192/#194)

> Demanda nº1 do cliente (03–04/09): "centenas de imóveis numa planilha só,
> a formatação do PDF é ideal".
> **Antecipado em 10/09/2026 (autorização do Hiure na sessão).**
> Ciclo de revisão: Opus 5 ×3 rounds + Codex GPT-5.6 gate ×2 + Greptile 5/5.
> P1 Security corrigido: injeção de fórmula + XSS neutralizados.

1. **#13** área em ha perde formato 0,0000 nas tabelas ✅ **FECHADA 11/09**
2. **#179** relatório consolidado XLS por TI, formato = layout do PDF ✅
   **FECHADA 11/09** (sem emojis, aba por imóvel + Resumo, origem tratada,
   cabeçalho sem duplicatas — validado no test server pelo Hiure)
3. **Follow-ups do review (não bloqueantes):** bound de trabalho do
   consolidado p/ TIs gigantes; aviso em relatório parcial; performance do
   `CadeiaCompletaService` recursivo (medir com base real do Maurício);
   bug vizinho `documentos_compartilhados` (chave morta em
   `exportar_cadeia_dominial_excel`) — candidatos a issue.
4. **NA FILA (pedido Hiure 11/09):** export XLS de cadeia única (botão na
   tela "Cadeia Dominial Geral") deve usar o MESMO padrão novo do
   consolidado (cabeçalho sem duplicatas, tipografia/cores do PDF, área
   pt-BR, origem tratada, sem emojis). Deve ser simples: trocar a view por
   imóvel para chamar `renderizar_planilha_imovel` (renderer já
   compartilhado) com os mesmos estilos — conferir se algo do layout antigo
   ainda diverge.
5. **Correções pós-teste do cliente (11/09):** cabeçalho duplicado
   Área/Origem/Observações no XLS (bug visual reportado com screenshot) —
   ✅ corrigido e mergeado (PR #194, commit `cfa25fb`): merge vertical
   `N:N+1/O:O+1/P:P+1` = rowspan do PDF; cobre os DOIS exports (consolidado
   + cadeia única, renderer compartilhado) → item 4 acima já atendido
   automaticamente. **Validado no test server (11/09): #13 e #179 FECHADAS.**

## R3 — Integridade de documentos/cartórios I (~1–1,5 semana)

> ⚠️ **REVALIDAR CONTRA O CÓDIGO ATUAL ANTES DE INICIAR** (pedido Hiure
> 11/09): export/cartórios mudaram muito no R2 (#166/#172/#179, renderer
> compartilhado, helper de origem) — conferir se cada bug ainda reproduz e
> se as causas raízes anotadas nas issues continuam válidas.
> Bug de produção + brechas de duplicidade. #144 é o mais antigo aberto
> com dados reais envolvidos (desde 13/08).

1. **#144** 🐛 produção: origem lançada (T585) não aparece na árvore —
   regressão v1.0.3→v1.0.5 ligada a cartórios (imóvel M955, Amambai).
2. **#114** 🐛 `criar_documento_matricula_automatico` permite cartório None.
3. **#141** 🐛 tratar IntegrityError (duplicidade canônica) em criar/editar.
4. **#149** ⚠️ avisar doc de mesmo tipo+número em cartório diferente.
5. **#110** levantar cartórios fantasmas + plano de merge (data quality —
   alimenta #113 do R5).

## R4 — UX Umbelino: rapid wins + CRI (~1 semana)

> **No início desta sprint: disparar o gate de decisão do cliente**
> (perguntas #150 e #151) — ver "Gates" abaixo.

0. **#193** UF nas sugestões digitadas de CRI *(P — decidido Hiure 11/09:
   entra no R4, mesma área de formulário; bug de homônimos Guairá/PR×SP.
   Diagnóstico pronto: backend já retorna `estado`; corrigir render no
   `lancamento_form.js` `carregarCartorios` para o mesmo padrão
   `nome (cidade/UF)` do `cri_search.js`)*
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

> **Atualizado 11/09: R1+R2 entregues na semana 07–11/09 (1 semana de
> ganho). Fila adiantada em ~1 semana.**

```
Sem 07/09–11/09  R1 fechar ciclo ✅ + R2 #13/#179 XLS consolidado ✅
Sem 14/09–18/09  #193 (rapid win) + R3 integridade/cartórios (⚠️ revalidar
                 contra o código atual; #144 primeiro) + release v1.0.10
Sem 21/09–25/09  R3 (cont.) ou R4 UX Umbelino (+ disparar GATE-CLIENTE)
Sem 28/09–02/10  R4 (cont.) / R5 #113 + #135
Sem 05/10–09/10  R5/R6 multi-cadeia/navegação
Sem 12/10–16/10  R6/R7 (se gate respondido) — senão R8
Sem 19/10–23/10  R7/R8 débitos + certificação
Sem 26/10–30/10  R8/R9 kickoff #132
Sem 02/11–06/11  R9 (reserva)
```

**Reserva de capacidade:** ~20% por sprint para novos relatos de
Maurício/Umbelino (padrão desde o plano geral).

**Fora do escopo:** backlog v2 #61–#72 (TypeScript/Cloudflare) — só depois
do Django estabilizar. #1 segue aberta como guarda-chuva.

---

*Última atualização: 11/09/2026 — R1+R2 fechados (#13/#179 validadas,
v1.0.9 no ar); #193 enfileirada no R4; R3 exige revalidação contra o
código atual; cronograma adiantado ~1 semana.*
