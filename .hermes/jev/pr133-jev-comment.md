## Fase 5 concluída — v1.1.0 integração #132 (head 5d8ad152)

**Re-reviews independentes (5 rodadas)**: Opus 5.5 + kiro-cli gpt-5.6-sol (assento Codex) + agy (fresh eyes). 8 P1 caçados e fechados em cadeia (A–H), todos em TDD RED→GREEN. **Rodada 5: consenso 3/3 APPROVE, zero P0/P1** — verdicts em `.hermes/jev/r{3,4,5}-*.md` nesta branch.

**Jev (checkpoint de decisão, item B)** — resposta id `gen-dec-1790890781-J5BSySCGe4yqp1SFK8Bv` (task `tae5772c-d57f-4c6a-b67f-41b1c95db00d`):

- quality_score **3.74** ≥ 3.5 ✅ (P(score=4) = 0.80, confidence 0.78)
- ready_for_human_decision **0.80** ≥ 0.6 ✅
- v1_governance_conflict **0.13** ≤ 0.3 ✅

→ push + atualização do PR feitos pela delegação Jev (regra do dono, 01/10). Payload/resposta retidos em `.hermes/jev/jev-payload-c.json` / `.hermes/jev/jev-resp-c.json`.

**Evidência de testes** (re-rodada pós-merge do develop `4dd37752`, zero conflitos):

- `test_segregacao_usuario`: 261/261 OK
- combinado (segregacao + escopo_global + s8_sem_str_e + p1e_duplicata_ordem): 301 OK
- `manage.py check`: 0 issues
- suíte completa pré-Fase 5: 1076 testes, 0 falhas novas vs develop (diff de ids; 53 pré-existentes do develop inalteradas)

**Resumo dos 8 P1 fechados na Fase 5:**

| P1 | Vetor | Fix |
|---|---|---|
| A | origem só de outra TI travava criação em tela de duplicata vazia | segue caminho D1 (salva sem vincular + aviso) |
| B | `imovel_form` sem guard de TI inteira | `usuario_tem_ti_inteira` → 404 |
| C | `str(e)` vazando em 4 pontos de services | mensagens fixas + `logger.exception` |
| D | guard do B bloqueava edição legítima via `UserImovel` legado | guard só na criação (`imovel_id is None`) |
| E | duplicata acessível preterida por inacessível conforme a ordem do POST | acessível tem prioridade nas 2 ordens |
| F | `/imovel/0/editar/` furava o guard (truthiness) e criava em TI alheia | `is None` / `is not None` nos 3 pontos |
| G | admin criava imóvel em TI visível só por legado | queryset de TI inteira na adição + `usuario_tem_ti_inteira` no `save_model` |
| H | admin **movia** imóvel para TI só-legada (changeform + `alterar_ti_view`) | revalidação em `changed_data` + `PermissionDenied` no destino |

**P2 follow-up (v1.2, registrados nos verdicts r5):** exigir TI inteira também na **origem** ao mover imóvel; select de edição do admin ainda lista TIs só-legadas (403 no `save_model` em vez de erro de form); nit `nova_ti=abc` → 500 no `alterar_ti_view`.

⚠️ **Merge segue exigindo autorização humana** (AGENTS.md + GATE-LUANDRO para a tag v1.1.0).
