# Plano — Fluxo de Escolha de Origens na Cadeia Dominial (tabela)

> Origem: bug de produção reportado pelo Maurício (12/09, imóvel 384/TI 201):
> "essas origens (onde temos que escolher entre as duas) não são exibidas";
> "não tá dando pra visualizar nada do que é importado".
> Auditoria Hermes 12/09 com evidência em produção (Django shell read-only).

## Evidência coletada (produção, imóvel 384)

- Banco íntegro: T3280/T3281 (docs 1943/1944, imóvel 358) existem e resolvem
- Backend OK: com escolha, `get_cadeia_dominial_tabela` retorna 17 docs
  (T3280, T3281, T2391, T9001, T4558 — importados todos presentes)
- Sem escolha: `obter_cadeia_tabela` retorna só 8 docs (tronco principal)
- XLS individual e consolidado (v1.0.10): completos ✅ (T3280/T3281/T4591 presentes)
- **Frontend quebra**: após clicar numa origem, o JS esconde os importados

## Defeitos encontrados (7)

**D1 (P0, causa do report) — filtro client-side `deveExibir`**
`cadeia_dominial_tabela.js` L204-244 (`atualizarTabelaCadeia`): após o
re-render AJAX, esconde TODO documento compartilhado cujo número ≠ origem
escolhida. Some com a cadeia importada abaixo da escolha (T2391, T9001,
T4558...). Hack de 18/09/2025 com casos hardcoded nos comentários
(M8487/M583/M4897) — feito para UM imóvel, quebrado para todos os outros.

**D2 (P0) — escolha "global" em vez de por documento**
`origemEscolhidaGlobal = cadeia.find(...)` pega a escolha do PRIMEIRO doc
com múltiplas origens e aplica a TODOS os compartilhados. Com 2+ docs
ambíguos na mesma cadeia, a escolha do doc A esconde a subcadeia do doc B.
= a "grande bagunça" reportada.

**D3 (P1, regressão v1.0.10) — formatação divergente no re-render AJAX**
O template server-side agora usa `{{ lancamento.area|area_ha }}` (#13), mas
a API devolve `area` bruta e o JS renderiza `${lancamento.area || '-'}`
(L458/L521). Após qualquer clique de origem, a coluna Área volta ao formato
antigo. Mesma divergência em `formatarOrigemCompleta` (L1297-1373):
reimplementação JS do filtro Django — já dessincronizada da versão Python
refatorada no #179 (que agora vive em `formatacao_utils`).

**D4 (P1) — duas trilhas de servidor para a mesma página**
View `tronco_principal`: sem escolhas → `obter_cadeia_tabela` (8 docs,
só tronco); com escolhas → `get_cadeia_dominial_tabela` (17 docs, expandida).
A página muda de comportamento radicalmente após o primeiro clique. O default
"esconde" T3280 mesmo SEM o hack JS (server-render inicial já vem sem ela).

**D5 (P2) — mutação do cache**
`obter_cadeia_tabela` faz `todos_documentos.sort(key=...)` IN-PLACE na lista
retornada pelo `CacheService` (cache de tronco principal) → corrompe a ordem
cacheada para as próximas requests.

**D6 (P2) — sessão sem escopo + limpar global**
Chaves `origem_documento_{doc_id}` sem escopo de imóvel/TI;
`limpar_escolhas_origem` apaga TODAS as chaves da sessão (todos os imóveis).
Escolhas vazam entre imóveis abertos em abas diferentes.

**D7 (P2) — zero testes do fluxo**
`cadeia_dominial_tabela_service.py` (619 linhas): 0 testes.
APIs `escolher-origem-documento`/`cadeia-dominial-atualizada`: 0 testes.
`cadeia_dominial_tabela.js` (1373 linhas): 0 testes (repo não tem infra JS).
Serialização do JSON da API sem contrato documentado/testado.

## Plano de correção (4 fases)

### Fase 0 — Hotfix P0 (mesmo dia, v1.0.11)
1. Remover o filtro `deveExibir` (D1+D2): JS renderiza EXATAMENTE o que o
   servidor manda (o backend já resolve escolhas corretamente — evidência B/C)
2. Manter badge "Compartilhado" e highlight da escolha ativa
3. API passa a devolver `area_formatada` (via `formatar_area_ha`) e
   `origem_formatada` (via `formatar_origem_completa`) — JS usa o campo
   pronto (D3, parte urgente)
4. Testes Django de regressão: `get_cadeia_dominial_tabela` com escolha
   inclui importados + serialização da API tem `area_formatada`

### Fase 1 — Consolidação server-side (2-3 dias)
5. Unificar D4: UMA trilha no service — cadeia sempre expandida
   (`_expandir_tronco_com_importados`), escolha default = maior número
   (comportamento atual), sem/mais-escolhas = mesmos docs, só destaque muda
6. Corrigir D5: `sorted()` em vez de `.sort()` in-place
7. D6: escopo de sessão por imóvel (`origem_documento_{imovel_id}_{doc_id}`)
   + `limpar_escolhas` com escopo do imóvel atual
8. Remover do JS os formatadores duplicados (`formatarOrigemCompleta`,
   `formatarClassificacaoFimCadeia`) — servidor é fonte única (D3 completo)

### Fase 2 — Testes contra regressão (junto com Fase 1)
9. Service: testes de `obter_cadeia_tabela`/`get_cadeia_dominial_tabela`
   (fixture reproduzindo o caso 384: doc com origem dupla T→T compartilhada)
10. API: teste de contrato do JSON de `cadeia-dominial-atualizada`
    (campos, tipos, campos formatados)
11. View: teste com sessão (escolher → re-GET → cadeia expandida persiste)
12. **Golden test**: para fixture padrão, conjunto de docs da cadeia ANTES e
    DEPOIS de cada escolha — snapshot aprovado vira baseline
13. Infra JS (decisão): vitest para funções puras extraídas do JS
    (sem DOM) — mínimo viável; OU manter só testes Django de contrato +
    checklist manual. Recomendação: vitest (barato, node já existe no repo)

### Fase 3 — Refatoração do JS (1 semana, pode virar R4.5)
14. Dividir `cadeia_dominial_tabela.js` (1373L) em módulos:
    `tabela_render.js` / `origem_escolhas.js` / `modal_sequencia.js` /
    `notificacoes.js`
15. Remover console.log de debug (~40 ocorrências)
16. Sanitizar innerHTML (relacionado ao #196) no re-render
17. Sem mudança de comportamento — coberta pelos testes da Fase 2

## Critérios de aceite gerais
- Imóvel 384 prod: clicar T3280 OU T3281 → tabela mostra os 17 docs
  (todos os importados visíveis), área em pt-BR, origem formatada igual
  ao server-render inicial
- Nenhum documento "some" após qualquer combinação de escolhas/limpar
- Suite Django verde + novos testes do fluxo
- XLS/PDF seguem completos (não regressar #179)

## Riscos
- Fase 1 item 5 muda o default da página (8→17 docs sem clique) — validar
  com Hiure/Maurício se é o desejado ("cadeia na íntegra" sugere que sim)
- Escopo de sessão (D6) muda chaves existentes — escolhas antigas dos
  usuários se perdem uma vez (aceitável)
- Refatoração JS sem cobertura prévia — por isso Fase 2 ANTES da Fase 3
