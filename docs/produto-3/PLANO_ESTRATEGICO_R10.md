# Plano Estratégico — R10 + fila pós-v1.1.0

> **Status: PROPOSTA — aguardando aprovação do Hiure** (reordenação de fila
> exige aprovação explícita registrada no roadmap, regra do AGENTS.md).
> Criado em 02/10/2026 a pedido do Hiure ("vamos criar um plano estratégico
> para implementar isso de acordo com as prioridades").
> Este plano **não substitui** o `ROADMAP.md` (source of truth da fila);
> ele detalha a estratégia de execução do R10 e o interleaving com R3/R4–R8
> depois da release v1.1.0.

## Contexto

- **v1.1.0 (R9/#132) segue em testes** — escopo da tag congelado, nada deste
  plano entra nela. O Wave 0 abaixo é o que resta do R9.
- **R10** (criado 02/10, PR #255): #251 exportar fim de cadeia · #252 opção
  "Outra" nos Estados do destacamento · #253 cartório da transmissão sem CRI
  + histórico · #254 badge "Parcialmente sem Origem".
- **R3 pausado** pela EXCEÇÃO DE FILA do R9, com itens abertos que incluem
  bug de data-loss (#238) e 500 em produção (#223) — podem furar fila caso a
  caso com aprovação do Hiure.
- Capacidade medida (revisão Codex 24/09, PR #221): fila R3–R9 já era
  ~0,6–2,1 semanas maior que o horizonte; R10 soma ~1 sprint. O plano
  abaixo **não promete datas** — promete sequência e critérios.

## Princípios de priorização (os mesmos do roadmap + 2 novos)

1. **Bug de produção > débito planejado > feature nova** (princípio 3 do
   roadmap). Exceção: feature nova pedida pelo dono entra no bloco dele
   (R10) sem desalojar P1 de produção.
2. **Agrupar por área de código** (princípio 4): menos troca de contexto,
   review mais barato — os waves abaixo são desenhados por área.
3. **Dependência antes do dependente**: #252 antes de #251 (o export exibe o
   texto livre do "Outra"); #232 antes/junto de #253 (o falso-negativo de
   `q_nome_cri()` vira falso-positivo na exclusão de CRI).
4. **(novo) Cada wave fecha com release ou entra na release seguinte** —
   nada de código mergeado em develop sem tag por mais de ~1 sprint
   (lição do PR #133 zumbi).
5. **(novo) Pipeline por issue, não por wave**: 1 issue = 1 worktree/branch
   = 1 PR → develop, com TDD (RED→GREEN obrigatório) + reviews do pipeline
   (Opus plan/review + co-reviewer; harnesses conforme `harness-state.yaml`).

## Waves de execução (pós-v1.1.0)

```
Wave 0 (agora)      v1.1.0: validação test server + T9 + tag (GATE-LUANDRO)
       │
Wave 1 (~1 sprint)  P1s de produção do R3 + pré-requisito do R10
       │            #238 (data-loss observações) · #223 (500 novo_documento)
       │            #232 (filtro CRI — pré-req do #253)
       │            [candidatos junto: #237, #228 — mesma área livro/folha]
       │
Wave 2 (~1 sprint)  R10 quick wins — área fim de cadeia + badge
       │            #252 (opção "Outra") · #254 (badge parcial)
       │            [candidato junto: #169 do R4 — janela de fim de cadeia
       │             não fecha; MESMA área do drawer, evita retrabalho]
       │
Wave 3 (~1 sprint)  R10 export — área CadeiaCompletaService
       │            #251 (fim de cadeia nos exports PDF/XLS)
       │            #240 (cobertura do get_cadeia_completa — mesma área)
       │
Wave 4 (~1 sprint)  R10 transmissão — área autocomplete
       │            #253 (transmissão sem CRI + histórico)
       │            [candidato junto: #235 do R8 — listener órfão no mesmo
       │             lancamento_form.js]
       │
Depois              R4 restante (#170, #164, #173, #213 f2–3, #165) →
                    R5 → R6 → R7 (gateado) → R8 restante
```

### Wave 0 — fechar a v1.1.0 (bloqueia tudo)
- Validação do #132 no test server: deploy develop, migração T9
  (0056→0061 sobre dump de produção), casos D1–D6.
- PR develop → main + tag **v1.1.0** (GATE-LUANDRO). Issue #132 fecha na tag.

### Wave 1 — P1s de produção + pré-requisito (~1 sprint)
| Issue | Por quê agora | Tamanho |
|---|---|---|
| #238 | **data-loss silencioso** em uso normal (edição de documento apaga observações) — candidato a P1 de produção pela regra da EXCEÇÃO R9 | P |
| #223 | 500 em produção na tela de criar documento do fluxo de lançamento | P |
| #232 | ~169 CRIs legítimos fora do filtro — pré-requisito do #253 e corrige o #227 nos campos de origem | M |
- **#237 e #228** (livro/folha, mesma área do #228/#237 já mapeados no R3):
  candidatos a entrar no mesmo wave se a capacidade permitir — decisão no
  replanejamento.
- **Release sugerida: v1.1.1** (patch de bugs) ao fim do wave, se o Hiure
  autorizar a tag (GATE-LUANDRO).

### Wave 2 — R10 quick wins (~1 sprint)
| Issue | Escopo resumido | Tamanho |
|---|---|---|
| #252 | opção fixa "Outra" + texto livre no select de Estado do destacamento; campo `sigla_patrimonio_publico` já aceita texto livre — falta opção no select, validação ("Outra" sem texto = erro, padrão `OrigemFimCadeia.clean()`), reexibição em edição, drawer D3 | P |
| #254 | estender `StatusCadeiaService` (#174): caso misto sem_origem+origem_lidima → `parcialmente_sem_origem` → badge novo no `tis_detail`; demais combinações inalteradas; respeitar escopo `for_user` do #132 | P/M |
- **#169** (R4, janela de fim de cadeia não fecha): proposta de puxar para
  cá — mesmo domínio do drawer de fim de cadeia que o #252 toca; fazer
  separado geraria retrabalho de contexto. **Decisão D4 abaixo.**
- Ordem interna: #252 primeiro (pré-req do #251), #254 independente (pode
  paralelizar no mesmo sprint).

### Wave 3 — R10 export (~1 sprint)
| Issue | Escopo resumido | Tamanho |
|---|---|---|
| #251 | fim de cadeia como elemento nos 4 exports (PDF único, PDF completo, XLS único, XLS consolidado — renderer compartilhado, 1 mudança cobre os XLS); consumir nó sintético `is_fim_cadeia` ou `OrigemFimCadeia` direto; NÃO recriar Documento real (formato antigo já migrado); exibir texto livre do #252; manter ouro dos testes #179/#204 verdes | M |
| #240 | cobrir `CadeiaCompletaService.get_cadeia_completa` (teste C2 do #230 só verifica a árvore) — mesma área, entra como parte do TDD do #251 ou PR irmão | P |
- Release sugerida: acumular para **v1.2.0** com o Wave 4 (features novas =
  minor), ou tag intermediária se o Hiure preferir — **decisão D3**.

### Wave 4 — R10 transmissão (~1 sprint)
| Issue | Escopo resumido | Tamanho |
|---|---|---|
| #253 | `cartorio_autocomplete`: parâmetro novo de exclusão de CRI (`~q_nome_cri()`, simétrico ao `somente_cri` do #227) + histórico de `cartorio_transmissao` (considerar legado `cartorio_transacao` via compat); JS: histórico no focus/click do campo transmissão, padrão do campo de origem; não regressar #227 | M |
- **#235** (R8, listener órfão pós-clone + XSS imovel_form.js): candidato a
  entrar junto — mesmo `lancamento_form.js`. Fix de 1 linha + XSS casa com
  #196. **Decisão D4.**
- **Release sugerida: v1.2.0** (R10 completo) ao fim do wave.

## Riscos e mitigações

1. **Novos relatos de Maurício/Umbelino** furam a fila (reserva ~20%/sprint
   já prevista no cronograma do roadmap). P1 de produção segue a regra da
   EXCEÇÃO R9: entra com aprovação do Hiure registrada no roadmap.
2. **#253 sem #232 pronto** → sugestões de transmissão podem incluir CRIs
   não detectados pelo filtro ("Nº Ofício de X"). Mitigação: dependência
   dura Wave 1 → Wave 4; se o #232 atrasar, o #253 pode sair com a
   limitação documentada (decisão do Hiure na ocasião).
3. **#251 muda exports validados pelo cliente** (#179/#204 são ouro). 
   Mitigação: testes golden existentes verdes como gate de regressão +
   validação no test server antes da tag.
4. **#254 toca área recém-escopada pelo #132** (`StatusCadeiaService` com
   `for_user`). Mitigação: só iniciar após a v1.1.0 estabilizada; teste de
   negação cross-TI obrigatório.
5. **Capacidade**: 4 waves ≈ 4 sprints de execução + overhead de pipeline.
   Sem datas prometidas; replanejar ao fim de cada wave (regra do roadmap).

## Decisões pendentes (aprovação do Hiure)

- **D1 — Posição do R10 na fila:** propor executar R10 (Waves 2–4)
  **antes** do R4–R8 restantes (features pedidas pelo dono > rapid wins
  antigos), mantendo bugs de produção do R3 na frente (Wave 1). Alternativa:
  R4 primeiro (ordem original do cronograma). **Recomendação: R10 antes.**
- **D2 — #238 fura fila como P1?** (data-loss silencioso em uso normal).
  **Recomendação: sim**, junto do #223 no Wave 1.
- **D3 — Estratégia de releases:** (a) v1.1.1 (bugs Wave 1) + v1.2.0 (R10
  completo, Waves 2–4); ou (b) uma tag única ao fim do Wave 4.
  **Recomendação: (a)** — bugs de produção não esperam features.
- **D4 — Agrupamentos por área:** puxar #169 (R4) para o Wave 2 e #235 (R8)
  para o Wave 4? **Recomendação: sim para ambos** (mesmo domínio de código;
  o roadmap mantém o registro de origem de cada issue).

## Regras de execução (válidas para todos os waves)

- 1 issue = 1 branch/worktree a partir do `origin/develop` atualizado →
  PR mira `develop` (nunca `main` direto); `main` só via release/tag.
- TDD obrigatório: teste falhando antes da correção (RED→GREEN no relatório
  do implementador); suíte completa no baseline antes/depois.
- Pipeline de implementação/revisão: conforme `harness-state.yaml`
  (`projects.cadeia_dominial`) — implementador qwen (fallback zai-glm),
  senior Opus 5.5 (plan/review), co-reviewer Codex (ou kiro-cli/agy quando
  sem cota, registrado no PR). Merge só com autorização humana explícita.
- Tags: sempre GATE-LUANDRO.
- Cada wave fecha com: issues do wave comentadas/fechadas no GitHub com
  apontamento de PR/release + atualização do roadmap (status + snapshot).
