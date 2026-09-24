# Roadmap — Produto 3

> **Fila reordenada 04/09/2026 por sequência lógica de desenvolvimento;
> nova reordenação aprovada pelo Hiure em 23/09/2026** (bugs de produção
> primeiro no R3, a começar pelo #218 — ver "Status geral").
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
3. **Bugs de produção antes de UX** — #218 (Livro↔Folha no banco, 22/09) e
   #144 (dados Maurício, aberto 13/08) vêm antes dos rapid wins de interface.
4. **Agrupar por área de código** — export / cartórios / navegação: menos
   troca de contexto por sprint, review 3 modelos mais barato.
5. **O que depende de decisão do cliente vai pro final, com gate explícito**
   — #150 e #151 estão `pendente-analise-cliente`; o gate é disparado no
   início do R4 para dar tempo de resposta até o R7.
6. **Features grandes por último** — #123 (certificação) e #132
   (multi-usuário) só depois do solo estabilizado.

## Status geral (snapshot 23/09/2026)

**✅ Entregue (mergeado em develop, PRs #177–#195):**
#108 CI · #159–#162 form bugs · #166 CRI · #145 PDF averbações · #172 troncos ·
#171 árvore no modal · #174 badge cadeia · #167 M anterior ·
**#13 área pt-BR · #179 XLS consolidado por TI (R2 completo) · #193 UF sugestões CRI**

**Releases:** v1.0.8 (01/09) · v1.0.9 (10/09, PR #190) ·
**v1.0.10 (12/09, PR #200 — #13/#179/#193, validada em produção)** ·
**v1.0.11 (20/09, PR #217 — #201 Fases 0+0b, #204, #210, #213 fase 1, #168;
GATE-LUANDRO autorizado pelo Hiure, deploy prod OK 18:45 UTC)**.

**🔥 Bug de produção (12/09):** #201/#202 — hotfix Fases 0+0b **em produção
na v1.0.11 (20/09)**; Fases 1–3 de saneamento (#202) **aguardando redefinição
via PRD** (tabela × exportações); #206 (origens homônimas) a revalidar. Veja **R3.5**.

**Fila Django (snapshot 23/09/2026, pós-housekeeping): 47 issues abertas no
GitHub — 34 Django** (excluídos #1 guarda-chuva e #61–#72 v2 fora de escopo).
- Cinco pendências de implementação que estavam fora dos blocos numerados
  foram incorporadas nesta reordenação: **#218, #219, #212** (R3), **#206**
  (R3.5), **#215** (R4).
- Mergeadas na v1.0.11: **#168, #201, #204, #210** — ✅ fechadas no GitHub
  em 23/09 (comentários apontam PR/release).

**Reordenação da fila aprovada pelo Hiure em 23/09/2026** (revisão Codex
gpt-6-sol xhigh: rodada 1 REJEITA, 6 MUST-FIX incorporados na v2 aprovada).

---

## R1 — Fechar o ciclo do Sprint 5 — 🟢 quase fechado (restam #187 + milestone + housekeeping 23/09)

> Gate de tudo: sem isso a fila cresce e se perde de novo.
> **R2 antecipado 10/09/2026 por demanda urgente do Hiure** (formatação do
> XLS = layout do PDF, #179, nunca desenvolvida). #187 e o milestone ficam
> pendentes e entram na sequência do #179.

1. **Validação no test server** dos PRs #177–#188 ✅ **FEITO 10/09/2026**
   (imóvel 265/Guyraroká usado no lugar do 499 — test server tem outra
   numeração; PDF 23 págs + XLS inspecionados, suites 18/18 e 42/42 OK)
   → **10 issues fechadas nesta validação: #145 #159 #160 #161 #162 #166
   #167 #171 #172 #174** (+ #152 já fechada antes — 11 no total).
2. **Release develop → main + tag v1.0.9** ✅ **FEITO 10/09/2026**
   (PR #190 mergeado + tag v1.0.9 — GATE-LUANDRO autorizado).
3. **#187** limpar `cartorio_hidden` stale quando operador edita nome do
   cartório (P2 do review do PR #186 — código quente, mesma área do #167).
4. GitHub: criar milestone "Produto 3" e mover a fila (decisão luandro/Hiure).
5. **Fechar no GitHub as issues já mergeadas na v1.0.11** ✅ **FEITO 23/09/2026**
   (comentário apontando PR + release PR #217/tag `v1.0.11`): **#168** (PR #216),
   **#201** (PRs #203/#205 — Fases 0+0b; Fases 1–3 seguem no #202),
   **#204** (PR #207), **#210** (PR #211).
6. **PRs zumbis — decidir destino** (reaproveitar ou fechar): **#103**
   (→#98, issue já fechada — candidato a fechar); **#136** (→#110, parado
   desde 21/08) — avaliar antes de iniciar #110 (R3 item 8); **#133**
   (→#132, parado desde 09/08) — avaliar antes do kickoff do #132 (R9).
7. **#215 — inventário SOMENTE LEITURA** dos registros `Pessoas`
   potencialmente corrompidos: iniciar em paralelo (**não bloqueia a
   fila**). O reparo em si fica no R4 (item 6), gateado na validação do
   cliente.
8. **PR deste roadmap** (branch `docs/roadmap-v1.0.11-release` → `develop`)
   só abre depois de incorporar a reordenação aprovada (✅ incorporada
   23/09) — ✅ **PR #220 aberto em 23/09** (`docs/roadmap-v1.0.11-release`
   → `develop`; docs-only, Greptile 4/5, Codex connector 2× P2 corrigidos
   neste commit).

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

## R3 — Integridade de documentos/cartórios I (~1,5–2 semanas)

> ⚠️ **REVALIDAR CONTRA O CÓDIGO ATUAL ANTES DE INICIAR** (pedido Hiure
> 11/09): export/cartórios mudaram muito no R2 (#166/#172/#179, renderer
> compartilhado, helper de origem) — conferir se cada bug ainda reproduz e
> se as causas raízes anotadas nas issues continuam válidas.
> Bug de produção + brechas de duplicidade. #144 é o mais antigo aberto
> com dados reais envolvidos (desde 13/08).
> **Reordenado 23/09 (aprovação do Hiure): bugs de produção primeiro** —
> #218 → #144 → #219 → #212, depois os itens já planejados. Estimativa
> revista de ~1–1,5 para ~1,5–2 semanas.

1. **#218** 🐛 P1 produção: Livro↔Folha invertidos **no banco** — não é só
   exibição (triagem 22/09: imóvel 488, doc 3879 T2540 gravado com
   livro=`154`/folha=`3H`; o padrão do cartório de Ponta Porã é
   livro=`3<letra>` + folha=número). Escopo: corrigir a gravação + reparar
   os dados invertidos já gravados (inventariar pelo padrão do cartório).
   Sem vínculo com #105 (causa comum descartada em revisão).
2. **#144** 🐛 produção: origem lançada (T585) não aparece na árvore —
   regressão v1.0.3→v1.0.5 ligada a cartórios (imóvel M955, Amambai; aberta
   desde 13/08). Revalidar contra o código atual (nota acima).
3. **#219** 🐛 validação: início de matrícula aceita a própria matrícula/
   transcrição como origem (auto-loop). Ponto de correção:
   `_sincronizar_origens_estruturadas` (identidade tipo + número normalizado
   + cartório vs documento do lançamento); inclui saneamento dos registros
   já gravados + testes. **Não** bloquear homônimos de cartório diferente
   (#206).
4. **#212** 🐛 P2: editar matrícula/tipo do imóvel não sincroniza
   `Documento.numero`/`tipo` — mesma classe do #210; o padrão de correção
   já existe no `ImovelDocumentoService`. P2: edição administrativa rara (o
   precedente #210 era cartório, edição comum).
5. **#114** 🐛 `criar_documento_matricula_automatico` permite cartório None.
6. **#141** 🐛 tratar IntegrityError (duplicidade canônica) em criar/editar.
7. **#149** ⚠️ avisar doc de mesmo tipo+número em cartório diferente.
8. **#110** levantar cartórios fantasmas + plano de merge (data quality —
   alimenta #113 do R5). **Antes de iniciar: checar o PR zumbi #136**
   (→#110, parado desde 21/08 — ver R1 item 6).
9. **#210** ✅ P1 produção: editar `Imovel.cartorio` deixava o documento
   principal no cartório antigo, e a matrícula sumia da cadeia (identidade
   resolvida por tipo+número+cartório). Corrigido com escopo reduzido:
   `ImovelDocumentoService` sincroniza SOMENTE o cartório (admin + views
   públicas), na mesma transação; cache do tronco principal desabilitado
   (LocMemCache multi-worker + invalidação transitiva insolúvel no hotfix).
   Sincronizar tipo/número do documento principal fica para **#212**
   (issue separada, ainda aberta — item 4 acima).
10. **#213 fase 1** ✅ **CONCLUÍDA 17/09** (PR #214, squash `e1274862`; Opus 5 ×2 +
   DeepSeek V4 Pro + Greptile 5/5 — Codex fora por cota): salvar lançamento
   **sobrescrevia o registro `Pessoas` compartilhado** quando o operador editava
   o nome sugerido pelo autocomplete (`pessoa.nome = texto; pessoa.save()`),
   corrompendo a ficha do imóvel. Corrigido: `lancamento_pessoa_service` **nunca**
   altera `Pessoas`; texto divergente do vínculo resolve o destino por
   `nome__iexact` (cria o registro de nome exato se não existir), o registro
   composto fica intacto e cada nome digitado ganha sua própria linha
   (`nome_digitado` guarda o texto). Duplicata mutante em `lancamento_service`
   virou delegação. 10 testes novos; o módulo dá 5F+1E contra o código antigo
   (regressão coberta de fato) e a suíte completa ficou com as mesmas falhas da
   baseline. **Achado novo durante a fase 1:** `unique_together
   (lancamento,pessoa,tipo)` + `get_or_create` colapsava N adquirentes com o
   mesmo `pessoa_id` em **1 linha** (sobrava só o último nome) — daí a resolução
   por nome exato, sem migração. Débitos: (a) o dado **já corrompido em produção
   não é reparado** (levantamento + script — issue **#215**), (b) lançamentos antigos ligados ao
   registro composto seguem exibindo o composto, (c) `lower()` não normaliza
   acento (`João` × `Joao` pode duplicar `Pessoas`). Fases 2–3 → R4.

## R3.5 — Fluxo de origens na cadeia (#201/#202/#206) — hotfix ✅ em produção (v1.0.11); restante depois do R3

> **Bug de produção ativo** reportado pelo Maurício (12/09): ao escolher a origem
> de uma **transcrição compartilhada** com origem dupla (caso real: imóvel 384,
> TI 201, T10786 → `T3280; T3281`), os documentos importados abaixo dela **somem
> da tabela** — "não tá dando pra visualizar nada do que é importado".
> Quebra a funcionalidade mais importante do produto: ver a cadeia na íntegra.
> **Antecipado na frente do R3** (bug de produção > débito planejado).
>
> Auditoria completa 12/09 com evidência coletada **no servidor de produção**
> (read-only). Plano: `docs/produto-3/PLANO_ORIGENS_ESCOLHAS.md`
> (**parcialmente superado** pela Fase 0b — o critério "17 docs com T3280/
> T3281 visíveis" descrevia o comportamento anterior; ver item 1b e a
> revisão Codex 24/09).
> Diagnóstico (12/09, histórico): backend correto na época (com escolha
> retornava 17 docs — comportamento pré-Fase 0b, ver item 1b; XLS já OK na
> v1.0.10) — quebra era **100% frontend** + default da página. 7 defeitos (D1–D7).
> **NÃO é regressão da v1.0.10** (exceto D3, formatação no re-render AJAX):
> o filtro `deveExibir` é hack de 09/2025 hardcoded para outro imóvel.
>
> **Reordenação 23/09 (aprovada pelo Hiure):** hotfix em produção → o
> restante do bloco executa **depois do R3** e antes do R4: #206 (revalidar
> escopo). O #202 fica **fora da sequência até existir o PRD** (não segura
> o R4).

1. **#201 Fase 0 — hotfix (v1.0.11)** ✅ **MERGEADA 13/09** (PR #203,
   squash `50ae2179` em develop). Pipeline Claude Opus 5 + Sonnet 5;
   reviews: Codex APPROVE (0 blocking) + Greptile 4/5. +521/−158 em 4
   arquivos: filtro client-side `deveExibir` removido; API devolve
   `area_formatada`/`origem_formatada` (mesmas funções Python dos filtros
   do template — paridade por construção); formatador duplicado em JS
   morto; 15 testes Django novos (508 linhas, fluxo tinha ZERO cobertura).
   Validado no test server com caso real (imóvel 4/TI 614, M6726 com 6
   origens): sem escolha 3 docs → com escolha M528 **12 docs, zero
   perdidos**. Deploy develop OK. ✅ **Release v1.0.11 em produção 20/09**
   (PR #217, tag `v1.0.11`, GATE-LUANDRO autorizado pelo Hiure, deploy CI success).
   ⚠️ Limitação conhecida: carga inicial ainda só mostra o tronco (D4) —
   Fase 1 do #202, aguardando redefinição (item 3).
1b. **#201 Fase 0b — ordenação canônica da cadeia** ✅ **MERGEADA 13/09**
   (PR #205, squash `65a73aa0` em develop; em produção na v1.0.11).
   - **Regra jurídica definida pelo Hiure (13/09):** (1) documento do imóvel
     sempre 1º; (2) **matrícula antes de transcrição — absoluta**, não
     desempate (M6861 vem antes de T21820); (3) número maior→menor,
     comparado como inteiro. **Data não participa** (no banco ela é quase
     toda fictícia/presumida — era a causa real da desordem).
     **⚠️ Escopo da regra (revisão Codex 24/09):** (2) e (3) valem **só
     entre origens irmãs** de um mesmo documento — decidem qual galho é
     seguido por default e a ordem dos botões. As **linhas da tabela nunca
     são reordenadas globalmente** por tipo ou número: elas seguem a
     caminhada hierárquica (quem é citado aparece depois de quem o citou —
     docstring de `dominial/services/cadeia_dominial_tabela_service.py`).
     Reordenação global separaria um documento da sua origem (bug que a
     Fase 0b corrigiu).
   - Corrige **4 ordenações divergentes** que conviviam (linhas por data,
     expansão sem ordem, opções por `int` desc, opções por **string** desc)
     e o bug em que o **botão destacado ≠ cadeia exibida** (caso real M6726:
     destacava M717 mas caminhava por M1612).
   - Chave única em `dominial/utils/ordenacao_cadeia.py`, consumida por
     linhas da tabela (2 trilhas), botões de origem e default da caminhada
     do tronco. 24 testes novos (39/39 OK com os 15 da Fase 0); suíte
     completa no baseline.
   - **DECISÃO DE ESCOPO (Hiure, 13/09): aplicar em TUDO.** A caminhada do
     tronco é compartilhada com exportação PDF/XLS (`CadeiaCompletaService`),
     página da árvore e modal de sequência — todos seguem a mesma regra, por
     consistência jurídica (o que a tela mostra = o que o documento exporta).
     A exportação continua **agrupada por troncos**; muda qual origem o
     tronco segue por default. Medido no test server: **14 de 406 imóveis**
     mudam a caminhada (só os com origens M e T misturadas); **conjunto de
     documentos exportados inalterado**.
   - Validado contra o caso real 384: sem escolha
     `M8272, M7775, M2623, M2072, T13367, T10786, T3281, T2391` (exatamente
     o esperado pelo Hiure); com escolha T3281 → só o tronco de T3281
     (o galho irmão T3280 fica de fora). **Evidência histórica (revisão
     Codex 24/09):** os "17 docs com T3280/T3281 visíveis" citados antes
     aqui eram o comportamento de expansão ANTERIOR à Fase 0b; o
     comportamento atual (garantido por `test_issue_201_origens_cadeia_tabela.py`)
     é: com escolha, somente o tronco da origem escolhida aparece. Qualquer
     nova expansão (ver os dois galhos juntos) continua dependente do PRD
     do #202 (item 3).
2. **#206** 🐛 origens homônimas — escopo **A REVALIDAR contra o código
   atual** antes de estimar. O diagnóstico original ("sessão grava só o
   número") está desatualizado: o fluxo principal já grava `documento:<id>`
   na sessão (API `escolher_origem_documento` em `api_views.py`; teste do
   segundo homônimo em `test_issue_201b_ordem_cadeia.py`). Restam caminhos
   residuais que comparam por código (ex.: expansão recursiva) — levantá-los
   primeiro. **Critério de saída do R3.5 (revisão Codex 24/09):** o bloco
   só fecha quando o #206 estiver (a) corrigido e validado no test server,
   OU (b) encerrado com evidência de que seus critérios já estão atendidos
   pelo código atual — diagnóstico sem desfecho não encerra o bloco (regra
   do AGENTS.md: "mark each release block done before starting the next
   one"). Se a revalidação confirmar trabalho, reestimar o início do R4
   antes de avançar.
3. **#202 Fases 1–3 — saneamento estrutural** — 🚦 **AGUARDANDO
   REDEFINIÇÃO**. Primeira tentativa abandonada em 14/09 (ordem por galho
   ambígua; PRs #208/#209 fechados sem merge; worktree mantido para
   reabrir). Retomada exige **PRD que distinga tabela × exportações**. As
   fases abaixo são direção, sujeitas ao PRD:
   - F1: "cadeia sempre expandida" (trilha única no service) **NÃO é
     requisito fechado** — decidir no PRD; corrigir cache (`sort()` in-place
     corrompe valor cacheado — conferir: o #210 desabilitou o cache do
     tronco principal), sessão com escopo por imóvel
   - F2: testes anti-regressão — service, contrato JSON das APIs, golden test
     do imóvel 384, infra de teste JS (vitest)
   - F3: modularizar o JS (1373 linhas), remover ~40 `console.log`, sanitizar
     `innerHTML` (casa com #196)

## R4 — UX Umbelino: rapid wins + CRI (~1 semana; #215 sem estimativa fechada)

> **No início desta sprint: disparar o gate de decisão do cliente**
> (perguntas #150 e #151) — ver "Gates" abaixo. **Previsão 23/09:** o
> acréscimo de trabalho em R3/R3.5 desloca o início efetivo do R4 (e o
> disparo) para ~29/09–03/10.

0. **#193** UF nas sugestões digitadas de CRI ✅ **FECHADA 12/09** (PR #195,
   commit `2677d9b7`; Codex 7/7 + Greptile 5/5; validada no test server —
   Guairá/PR×SP distinguíveis). Débito apontado na revisão (preexistente):
   XSS em innerHTML dos autocomplete — candidato a issue separada.
   **Incidente de deploy 12/09:** disco do test server 100% (221 imagens
   Docker, 52 GB) matou 2 deploys silenciosamente; resolvido com
   `docker image prune` + re-run. Débitos de infra candidatos a issue:
   (a) monitoramento/prune periódico de disco no test server,
   (b) `immutable` 30d em estáticos sem hash de versão (ManifestStaticFiles),
   (c) alerta quando deploy do CI falha.
1. **#168** TAB não parar no campo sigla ✅ **MERGEADO 17/09** (PR #216,
   squash `0de729ea`; em produção na v1.0.11)
2. **#169** corrigir janela de fim de cadeia que **não** fecha *(P)*
3. **#170** botão Adicionar Lançamento no topo *(P)*
4. **#164** quadro azul M/T em uma linha *(P)*
5. **#173** proprietário 255→500 + migração *(P)* — ver #213: se a dor real for
   "muitos proprietários" (campo único com vírgulas), aumentar para 500 só
   alonga o nome composto; resolver #213 (modelagem multi-proprietário) pode
   tornar #173 parcialmente desnecessária — decidir em conjunto
6. **#215** 🔨 reparo dos dados de `Pessoas` corrompidos em produção
   (débito (a) da #213 fase 1) — 🚦 **GATEADO na validação do cliente**;
   o inventário somente leitura do R1 (item 7) é a entrada. **Sem
   estimativa fechada:** parte dos casos pode ser irrecuperável
   automaticamente — `Pessoas` não tem timestamps nem histórico, e nos
   casos antigos `LancamentoPessoa.nome_digitado == Pessoas.nome` (a
   heurística óbvia não detecta). **Exceção aprovada 23/09:** não bloqueia
   o fechamento do R4 nem o R5 — se a validação do cliente não chegar,
   escorrega para depois (ver "Gates de decisão").
7. **#213 fases 2–3** 🐛 UX + estrutural: autocomplete de adquirente/
   transmitente sugere o bloco inteiro de nomes compostos (operador apaga os
   excedentes a cada linha); modelagem de proprietários múltiplos no imóvel
   (decisão de produto — `Imovel.proprietario` é FK única, `nome` é texto
   livre). **Fase 1 ✅ concluída no R3 (PR #214, squash `e1274862`)** — e ela
   deixou estes débitos para cá: (a) reparar o dado **já corrompido** em
   produção (nomes compostos sobrescritos por lançamentos; levantamento +
   script de correção — issue **#215**, item 6 acima), (b) lançamentos antigos ligados ao registro composto
   ainda exibem o nome composto no form/detalhe, (c) `lower()` não normaliza
   acento (`João` × `Joao` → `Pessoas` duplicado).
8. **#165** CRI obrigatório junto ao nº de M/T em todo o sistema *(M —
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

1. **#150** delimitar CRI vs cartório de transmissão no banco — *a issue é
   de **PLANEJAMENTO**: entrega "um plano de delimitação (documento de
   decisão + migrations), NÃO a implementação" (corpo da #150). Maior
   migração do plano, toca todas as FKs de cartório; design Opus 5 antes
   (spike 1–2 dias no início). A implementação da migração só é autorizada
   após o plano aprovado (luandro/Hiure) e entra como issues filhas —
   revisar o cronograma na ocasião (revisão Codex 24/09)*
2. **#151** avisar/exigir arquivamento quando origem referencia imóvel ativo

## R8 — Débitos técnicos + certificação fundiária (~1–1,5 semana)

1. **#105** `_processar_campos_inicio_matricula` indexa por posição
2. **#116** fixtures usam `Imovel.sncr` removido *(destrava suite de testes
   — fazer cedo se alguma sprint depender de testes)*
3. **#139** renomear 'transação' → 'transmissão' em todo o sistema
4. **#123** campos de certificação fundiária (SNCR, CCIR, CNIR, CIB, SIGEF,
   SNCI, CAR)
5. **#196** XSS: autocompletes montam innerHTML sem escape *(novo 12/09,
   apontado na revisão do #195; pré-existente)*
6. **#197** monitoramento de disco + prune Docker no test server *(novo
   12/09, incidente real — deploys falharam silenciosamente)*
7. **#198** ManifestStaticFilesStorage: cache immutable sem hash obriga
   hard refresh a cada deploy *(novo 12/09)*
8. **#199** notificação Telegram de deploy falhado *(novo 12/09; #197+#199
   juntos fecham o ciclo do incidente de 12/09 — candidatos a fast-track
   se o time quiser)*

## R9 — Segregação por usuário (a maior feature, ~2 semanas)

1. **#132** multi-tenancy leve: cada usuário vê só seus imóveis
   - A issue é de **levantamento e planejamento**: entrega o "plano de
     comportamento esperado", que deve ser **aprovado por luandro antes de
     abrir issues filhas de implementação** (corpo da #132, checklist).
   - Semana 1: design de schema + middleware/filtros (Opus 5 no design)
     → produzir o plano e submetê-lo a luandro.
   - Semana 2: implementação gradual + testes de isolamento — **só inicia
     com o plano aprovado**; sem aprovação, a implementação fica bloqueada
     e o cronograma é revisto (revisão Codex 24/09).
   - **Kickoff com luandro** — decisões de produto obrigatórias antes.
   - **Antes do kickoff: avaliar o PR zumbi #133** (→#132, parado desde
     09/08 — reaproveitar ou fechar; ver R1 item 6).

---

## Gates de decisão

- **GATE-CLIENTE (#150 + #151):** disparar pergunta no início do R4.
  Sem resposta até o fim do R6 → R8 entra antes do R7.
  **Previsão 23/09:** com o acréscimo de trabalho em R3/R3.5, o disparo
  desloca para o início efetivo do R4 (~29/09–03/10). Atraso de resposta
  **não** bloqueia R3–R6 — bloqueia só o R7 (R8 entra no lugar, regra acima).
- **GATE-LUANDRO (release):** tag de produção só com autorização explícita.
- **GATE-PRODUTO (#132):** kickoff com luandro no início do R9. O gate tem
  **dois eventos distintos** (revisão Codex 24/09): (1) kickoff = decisões
  de produto para redigir o plano; (2) **aprovação do plano** = evento que
  autoriza abrir as issues filhas e iniciar a implementação. Sem o evento
  (2), a Semana 2 do R9 não começa (mesma lógica do #150 no R7).
- **EXCEÇÃO #215 (aprovada pelo Hiure em 23/09/2026):** o reparo dos dados
  de `Pessoas` (#215, R4 item 6) é gateado na validação do cliente, mas
  **NÃO bloqueia o fechamento do R4 nem o avanço para o R5**. Se o gate não
  abrir a tempo, o #215 escorrega para depois da fila sem segurar os blocos
  seguintes (mesmo tratamento do #202, que não segura o R4). (Justificativa:
  dados já corrompidos em produção, sem timestamps/histórico — parte pode
  ser irrecuperável automaticamente; não faz sentido travar R5+ por uma
  validação externa.) **Operacionalização do gate (revisão Codex 24/09):**
  concluído o inventário somente leitura (R1 item 7), o responsável pelo
  contato com o cliente (Hiure/luandro — confirmar quem) envia a lista de
  reparos da issue #215 para validação e registra a data do pedido aqui;
  a pendência é revisitada no replanejamento de cada sprint até resposta.

## Dependências críticas

- R1 valida/fecha → libera a fila (evita acumular issues zumbis)
- #13 → #179 (mesma área, warmup)
- #110 (R3) → #113 (R5) → #135 (R5)
- #175 → #176 (dentro do R6)
- #165 (R4) desenhado junto a #150 (R7) para minimizar retrabalho
- #144 pode revelar dados que alimentam #110 — investigar cedo no R3 (logo
  após o #218)
- #219 (R3) × #206 (R3.5): a trava de auto-loop não pode bloquear
  homônimos de cartório diferente
- #215: inventário somente leitura (R1) → validação do cliente → reparo (R4)
- PR zumbi #136 → #110 (R3); PR zumbi #133 → #132 (R9)
- #202 F1–F3 (R3.5) ← PRD que distinga tabela × exportações

## Cronograma (sprints ~1 semana; replanejar ao fim de cada uma)

> **Atualizado 11/09: R1+R2 entregues na semana 07–11/09 (1 semana de
> ganho). Fila adiantada em ~1 semana.**
>
> **Atualizado 23/09 (reordenação aprovada):** a semana 14–18/09 foi para o
> hotfix #201 + release v1.0.11; R3 ampliado (#218 → #144 → #219 → #212 +
> existentes), R3.5 reduzido a #206 (revalidação) com #202 congelado até o
> PRD (fora do cronograma), R4 com #215 gateado. A partir do R4 a fila
> desloca ~1 semana (GATE-CLIENTE: 21–25/09 → ~29/09–03/10).

```
Sem 07/09–11/09  R1 fechar ciclo (parcial: validação+release ✅; #187 e
                 milestone seguem no housekeeping) + R2 #13/#179 XLS consolidado ✅
                 (+ #193 rapid win adiantado e fechado 12/09 ✅)
Sem 14/09–18/09  R3.5 hotfix #201 Fases 0+0b + #204 ✅ (12–13/09) · R3 #210 ✅
                 + #213 fase 1 ✅ · #168 ✅ → release v1.0.11 em produção 20/09 ✅
Sem 21/09–25/09  R1 housekeeping (#187, milestone, #168/#201/#204/#210 ✅
                 fechadas 23/09, PR zumbi #103; inventário #215 em paralelo)
                 → R3 #218 → #144
Sem 28/09–02/10  R3 (cont.) #219 → #212 → #114/#141/#149/#110 → R3.5 #206
                 (revalidar + estimar; saída do bloco só com correção
                 validada OU encerramento com evidência — ver R3.5 item 2)
                 → início do R4 ~29/09–03/10 (+ disparar GATE-CLIENTE)
Sem 05/10–09/10  R4 (cont.; #215 só com validação do cliente) / R5 #113 + #135
Sem 12/10–16/10  R5/R6 multi-cadeia/navegação
Sem 19/10–23/10  R6/R7 (se gate respondido) — senão R8
Sem 26/10–30/10  R7/R8 débitos + certificação
Sem 02/11–06/11  R8/R9 kickoff #132 (avaliar PR zumbi #133 antes)
Sem 09/11–13/11  R9 (reserva)
```

**Reserva de capacidade:** ~20% por sprint para novos relatos de
Maurício/Umbelino (padrão desde o plano geral).

**Premissas do cronograma (revisão Codex 24/09):** as estimativas de
R3–R9 somam ~7–8,5 semanas para um horizonte de ~8 semanas (21/09–13/11),
SEM contar o housekeeping restante do R1, o desfecho do #206 (R3.5), o R7
(gateado) e o eventual reparo #215. É um cronograma **apertado e
otimista**, não um compromisso de entrega — a reserva de ~20% acima já
está considerada no horizonte, não nas estimativas dos blocos. As datas
a partir do R4 ficam **condicionadas** às estimativas que saírem da
revalidação do #206, das fases 2–3 do #213 e do plano do R7; replanejar
ao fim de cada sprint (regra da seção).

**Fora do escopo:** backlog v2 #61–#72 (TypeScript/Cloudflare) — só depois
do Django estabilizar. #1 segue aberta como guarda-chuva.

---

*Última atualização: 24/09/2026 — **revisão Codex gpt-6-astra xhigh do
roadmap como norte de desenvolvimento** (rodada 1: 4 PASS / 4 MUST-FIX /
4 NICE — REJEITA; todos os MUST-FIX validados contra código/issues reais
e incorporados nesta revisão): M-1 escopo da regra M>T só entre origens
irmãs (linhas nunca reordenadas globalmente); M-2 "17 docs" marcado como
evidência histórica pré-Fase 0b (comportamento atual: só o tronco
escolhido; `PLANO_ORIGENS_ESCOLHAS.md` parcialmente superado); M-3
critério de saída do R3.5 (#206 corrigida+validada OU encerrada com
evidência); M-4 #150/#132 distinguidos como issues de planejamento —
implementação só após plano aprovado (GATE-PRODUTO com 2 eventos). NICEs:
premissas de capacidade do cronograma, operacionalização do gate #215,
título do #169 corrigido, contagem do R1 (10+1) ajustada.*

*24/09/2026 (mais cedo) — correções do review do PR #220 (Codex
connector 2× P2 + Greptile 1× P2 convergente): #168, #201, #204 e #210 ✅
fechadas no GitHub em 23/09 (R1 item 5; snapshot recontado: 47 abertas,
34 Django); PR #220 aberto em 23/09 (R1 item 8); bloco R3.5 movido para
depois do R3 sem alterar o conteúdo — a ordem no arquivo passa a ser a
ordem de execução (R3 → R3.5 #206 → R4).*

*23/09/2026 — **reordenação da fila aprovada pelo
Hiure** pós-revisão Codex gpt-6-sol (xhigh; rodada 1 REJEITA, 6 MUST-FIX
incorporados na v2): 5 issues incorporadas à fila — #218, #219, #212 (R3,
bugs de produção primeiro), #206 (R3.5, escopo a revalidar), #215 (R4,
gateado na validação do cliente; inventário somente leitura antecipado no
R1); 4 issues para fechamento administrativo no R1 (#168, #201, #204,
#210); #202 (Fases 1–3) congelado até PRD; GATE-CLIENTE previsto para o
início efetivo do R4 (~29/09–03/10). Exceção de gate aprovada: #215 não
bloqueia R4/R5 (escorrega se a validação do cliente atrasar).*

*20/09/2026 — **release v1.0.11 em produção** (PR #217,
tag `v1.0.11`, deploy CI success 18:45 UTC): #201 Fases 0+0b (PRs #203/#205),
#204 XLS A4 paisagem (PR #207), #210 sync cartório (PR #211), #213 fase 1
Pessoas (PR #214), #168 TAB sigla (PR #216). GATE-LUANDRO autorizado pelo
Hiure. #202 (Fases 1–3) e #215 (reparo de dados) seguem na fila.*

*16/09/2026 — #213 enfileirada (relato: autocomplete de
adquirente/transmitente preenche o bloco de nomes compostos e a edição
sobrescreve o registro `Pessoas` da ficha do imóvel) — fase 1 no R3 item 7,
fases 2–3 no R4 item 6, decidir junto com #173.*

*12/09/2026 — #193 fechada (PR #195 validado no test
server); incidente de disco no test server resolvido (prune 51 GB);
R3 exige revalidação contra o código atual; cronograma adiantado ~1 semana.*
