# Plano Estratégico — fila pós-v1.1.0 (R4–R8 → R10; R3/R3.5 na geladeira)

> **Status: APROVADO na direção geral pelo Hiure em 02/10/2026** (grupo
> Transistir_CadDomDev): "pode ser primeiro do R4 ao R8" · "vamos deixar o
> R3 na 'geladeira' por agora pois não é um problema urgente" · "talvez
> valha fazer um novo backup do servidor de prod e colocar no servidor de
> testes". Detalhes de sequência/empacotamento abaixo ainda abertos a ajuste.
> Este plano **não substitui** o `ROADMAP.md` (source of truth da fila);
> detalha a estratégia de execução depois da release v1.1.0.
> (Renomeado de `PLANO_ESTRATEGICO_R10.md` — o escopo virou a fila toda.)

## Decisões registradas (Hiure, 02/10/2026)

- **D1 — Ordem pós-v1.1.0: R4 → R5 → R6 → R7 (se o gate abrir) → R8 → R10.**
  As features novas do R10 (#251–#254) ficam DEPOIS dos blocos já planejados
  (ordem original do cronograma 23/09 preservada).
- **D2 — R3 na GELADEIRA** (não apenas pausado pela EXCEÇÃO R9): muita
  correção de cartórios foi feita **manualmente direto em produção**
  (reconhecido como erro de processo) sem entrar em commits nem no servidor
  de testes. Os itens do R3 (integridade documentos/cartórios) precisam ser
  **revalidados contra os dados reais de produção** antes de voltar à fila —
  diagnósticos antigos podem não reproduzir mais. R3 não é urgente (Hiure,
  literal: "vamos deixar o R3 na 'geladeira' por agora").
  - **R3.5 junto na geladeira — CONFIRMADO pelo Hiure em 02/10 ("sim"):**
    #206 (homônimas) e #202 (fases 1–3) também dependem de dados reais para
    revalidação — o critério de saída do R3.5 (revisão Codex 24/09) exige
    validação no test server. Entram na mesma revisão do destravar.
  - ⚠️ **Ressalva registrada (não bloqueia a decisão):** #238 é data-loss
    silencioso em uso normal (editar documento apaga observações) e #223 é
    500 na tela de criar documento. Se algum usuário topar com eles, podem
    ser puxados caso a caso com aprovação do Hiure (regra da EXCEÇÃO R9).
- **D3 — Dump de produção → servidor de testes** (reaproximar os dados de
  teste da realidade): recomendado ANTES da validação da v1.1.0 (o T9 já
  pede migração 0056→0061 sobre dump de produção — um dump fresco serve aos
  dois propósitos) e é pré-requisito do "destravar geladeira" do R3.
  Execução: read-only em produção (pg_dump), restaura no teste. Regra Hiure
  26/09 intacta: **nunca alterar dados de produção** — o fluxo é só prod →
  teste. Skills de referência: `database-data-transfer`,
  `sync-cadeiadominial-test-to-prod` (direção inversa — adaptar).

## Princípios de priorização

1. **Bug de produção > débito planejado > feature nova** — com a exceção
   registrada: R3 foi para a geladeira por decisão do dono (D2).
2. **Agrupar por área de código** (princípio 4 do roadmap): menos troca de
   contexto por sprint.
3. **Dependência antes do dependente**: #232 antes/junto de #253 (filtro
   CRI); #252 antes de #251 (texto livre "Outra" no export); #113 → #135.
4. **Cada bloco fecha com release ou entra na seguinte** — nada de código
   mergeado em develop sem tag por mais de ~1 sprint (lição do PR #133).
5. **1 issue = 1 worktree/branch = 1 PR → develop**, TDD (RED→GREEN) +
   pipeline de reviews do `harness-state.yaml`; merge e tag só com
   autorização humana.

## Sequência de execução

```
Wave 0 (agora)        v1.1.0: dump prod→teste (D3) + validação test server
                      + T9 + casos D1–D6 → PR develop→main + tag (GATE-LUANDRO)
      │
Wave 1 (~1 sprint)    R4 rapid wins: #170 · #164 · #169 · #173 (decidir c/ #213)
      │
Wave 2 (~1–2 sprints) R4 pesado: #213 fases 2–3 · #165 (desenhar c/ #150)
      │               (#215 gateado no cliente — não segura o bloco, EXCEÇÃO 23/09)
      │
Wave 3 (~0,5–1)       R5: #113 → #135   ·   R6: #155 · #175 → #176
      │
Wave 4 (~0,5–1)       R8 parte 1 — segurança/infra: #234 · #196+#235 (XSS,
      │               mesma área) · #197 · #198 · #199
      │
Wave 5                R7 (🚦 só se GATE-CLIENTE responder): #150 plano →
      │               #151. Sem resposta → pular (regra do roadmap) e
      │               antecipar R8 parte 2.
      │
Wave 6 (~1)           R8 parte 2: #105 · #116 · #139 · #123 · #243+#249
      │               (mesma área duplicata)
      │
Wave 7 (~1 sprint)    R10 bloco A: #252 ("Outra") · #254 (badge parcial)
      │
Wave 8 (~1 sprint)    R10 bloco B: #251 (export fim de cadeia) + #240
      │               (mesma área CadeiaCompletaService; ver ressalva #232)
      │
Wave 9 (~1 sprint)    R10 bloco C: #253 (transmissão sem CRI + histórico)
      │
GELADEIRA (D2)        R3 + R3.5 (confirmado 02/10): destrava após (a) dump D3
                      rodado + (b) revisão item a item contra produção real.
                      Sem data.
```

### Wave 0 — v1.1.0 (bloqueia tudo)
1. **Dump prod → teste (D3)** — read-only na prod; restaurar no teste.
2. Validação do #132 no test server: deploy develop, **T9** (migrar
   0056→0061 sobre o dump fresco), casos **D1–D6**.
3. PR develop → main + tag **v1.1.0** (GATE-LUANDRO); #132 fecha na tag.

### Waves 1–2 — R4 (UX Umbelino + CRI)
- Rapid wins primeiro (P): #170 botão Adicionar Lançamento · #164 quadro
  azul 1 linha · #169 janela fim de cadeia não fecha · #173 proprietário
  255→500 (decidir junto com #213 — pode virar desnecessário).
- Depois os pesados: #213 fases 2–3 (autocomplete nomes compostos +
  modelagem multi-proprietário) · #165 CRI obrigatório com M/T (desenhar
  considerando #150 para minimizar retrabalho — nota original do roadmap).
- #215 (reparo Pessoas): gateado no cliente, não segura o bloco (EXCEÇÃO
  23/09). GATE-CLIENTE (#150/#151) deve ser disparado no início do R4 —
  Wave 1 é o momento.

### Wave 3 — R5 + R6
- R5: #113 constraint de identidade + relatório de suspeitos (usa saída do
  #110 — que está na geladeira; reavaliar se #113 consegue andar sem ele ou
  se o levantamento do #110 precisa ser refeito pós-dump) → #135.
- R6: #155 · #175 → #176.
- ⚠️ **Conflito a resolver no replanejamento:** a dependência #110 → #113
  cruza com a geladeira do R3. Opções: (a) mover só o levantamento read-only
  do #110 para junto do dump D3 (não é "correção", é inventário); (b) deixar
  #113 esperar o destravar do R3.

### Waves 4–6 — R8 (partido em 2) + R7 (gateado)
- R8 parte 1 (segurança/infra — itens com risco real em produção):
  **#234** (importar-cartorios sem auth) · **#196+#235** (XSS autocompletes,
  mesma área) · **#197** (disco) · **#198** (cache estáticos) · **#199**
  (alerta deploy).
- R7: só se o GATE-CLIENTE responder (#150 é PLANEJAMENTO — plano aprovado
  antes de qualquer implementação; #151 depende do plano).
- R8 parte 2 (débitos): #105 · #116 · #139 · #123 · **#243+#249** (duplicata,
  mesma área — fazer juntos).

### Waves 7–9 — R10 (features 02/10)
- **Bloco A** (~1 sprint): #252 opção "Outra" (texto livre) + #254 badge
  "Parcialmente sem Origem" — independentes entre si, paralelizáveis.
- **Bloco B** (~1 sprint): #251 export do fim de cadeia (PDF único/completo,
  XLS único/consolidado — renderer compartilhado) + #240 (cobertura do
  `get_cadeia_completa`, mesma área). Gate de regressão: testes golden
  #179/#204 verdes + validação no test server antes da tag.
- **Bloco C** (~1 sprint): #253 transmissão sem CRI + histórico.
  **Ressalva #232 (geladeira):** a exclusão de CRI usa `q_nome_cri()`, que
  tem ~169 falso-negativos (#232). Opções na ocasião: (a) embutir a correção
  mínima do filtro no próprio #253; (b) lançar com a limitação documentada.
  Decidir no replanejamento do Wave 9 — o #232 continua registrado no R3.
- #169 e #235 (agrupamentos propostos na versão anterior do plano):
  **perderam o objeto** — R4 e R8 executam ANTES do R10, cada issue corre no
  seu bloco de origem.

## Releases sugeridas (todas com GATE-LUANDRO)

- **v1.1.0** — Wave 0 (R9/#132).
- **v1.2.0** — ao fim de R4 (Waves 1–2): UX Umbelino + CRI obrigatório.
- **v1.3.0** — ao fim de R5+R6 (Wave 3) ou acumulado com R8 parte 1, a
  decidir no replanejamento.
- **v1.4.0** — R8 completo + R7 (se executado).
- **v1.5.0** — R10 completo (Waves 7–9).
- Regra: nenhum bloco fica >1 sprint sem entrar numa tag; patch (v1.x.y)
  para hotfix de produção fora de banda.

## Destravar a geladeira do R3 (critérios de saída)

1. Dump D3 restaurado no test server (dados ≈ produção real, incluindo as
   correções manuais de cartórios).
2. Revisão item a item do R3/R3.5 contra os dados reais: o que ainda
   reproduz, o que as correções manuais já resolveram, o que precisa de
   novo diagnóstico (#219, #212, #141, #149, #110, #223, #228, #232, #237,
   #238, #240, #248, #206, #202).
3. Hiure reordena o bloco revisado no roadmap (novo snapshot).
- **Nota de processo (registrar para não repetir):** correções de dados
  direto em produção sem commit/sem refletir no teste criam deriva
  banco↔código — a regra vigente (Hiure 26/09) é correção manual pelo
  usuário, mas o plano de reparo deve prever como o teste fica sabendo
  (dump periódico ou registro das correções aplicadas).

## Riscos e mitigações

1. **Novos relatos de Maurício/Umbelino** furam a fila (reserva ~20%/sprint
   do roadmap). P1 de produção entra com aprovação do Hiure caso a caso.
2. **Deriva produção↔teste por correções manuais** (causa da geladeira):
   mitigar com dumps periódicos pós-release (candidato a tarefa de infra no
   R8 parte 1, junto do #197).
3. **#110 na geladeira × #113 no Wave 3**: resolver no replanejamento
   (opções na seção Wave 3).
4. **#253 sem #232**: opções na seção Wave 9.
5. **Capacidade**: R4–R8+R10 ≈ 9 waves — horizonte longo SEM datas
   prometidas; replanejar ao fim de cada wave (regra do roadmap).

## Regras de execução (todos os waves)

- Branch/worktree a partir do `origin/develop` atualizado → PR mira
  `develop`; `main` só via release/tag.
- TDD obrigatório (RED→GREEN no relatório do implementador); suíte completa
  no baseline antes/depois.
- Pipeline conforme `harness-state.yaml` (`projects.cadeia_dominial`):
  implementador qwen (fallback zai-glm), senior Opus 5.5, co-reviewer Codex
  (kiro-cli/agy quando sem cota, registrado no PR). Merge/tag só com
  autorização humana explícita.
- Cada wave fecha com: issues comentadas/fechadas no GitHub apontando
  PR/release + atualização do roadmap (status + snapshot).
