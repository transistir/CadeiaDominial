# Revisão independente — commit docs 658ebe9c (roadmap reordenado v1.1.0)

Você é um revisor independente. Emita um veredito formal (APPROVE / REQUEST_CHANGES) sobre um commit **docs-only** que está pendente de push. Seja rigoroso mas justo: é documentação de roadmap, não código.

## O commit

Repo: /root/dev/cadeia-dominial/CadeiaDominial (Django, projeto Cadeia Dominial — registro de cadeias dominiais de imóveis em TIs).
Branch local: docs/roadmap-reordenacao-132-v110, commit único `658ebe9c`, cortada do develop atualizado (b1fcb785).
Alvo do PR: develop (branch model do repo: PRs nunca miram main diretamente; main só via release/tag).

Inspecione com: `git show 658ebe9c` (diff completo, 25+/14- em docs/produto-3/ROADMAP.md).
Contexto adicional (leia se quiser): docs/produto-3/ROADMAP.md inteiro no branch; AGENTS.md na raiz (regras de fila R1–R9, gates).

## O que o commit faz

1. Marca R9 (segregação multiusuário #132, PR #133) como ANTECIPADO — vira a meta da release v1.1.0.
2. Incorpora a avaliação de compatibilidade do PR #133 vs develop (revisão Opus 5.5): 15 conflitos de merge, 8 vazamentos de escopo S1–S8, estratégia merge-not-rebase, plano de commits C1–C9 em TDD, estimativa 35–50h.
3. Registra as decisões de produto D1–D6 respondidas pelo owner operacional (Hiure) em 30/09 no grupo Telegram.
4. Changelog datado citando a aprovação do Hiure para a reordenação (o AGENTS.md exige aprovação explícita do usuário registrada no próprio roadmap para reordenar a fila).

## Evidências de aprovação (regra do AGENTS.md: "Reordering the queue requires explicit user approval, recorded in the roadmap file itself")

- Hiure, 30/09, literal: "podemos reordenar o roadmap? o que acha de colocarmos como meta a issue 132.. pra v1.1.0?"
- Decisões D1–D6 (Hiure, literal): D1 acesso a um imóvel ⇒ acesso à TI inteira; D2 acesso ao documento ⇒ pode editar/excluir; D3 existe em outra TI ⇒ informar e pedir acesso ao admin; D4 só superuser edita cartório; D5 TI inteira; D6 atribuição fina por TI.
- Hiure, 01/10: delegou o push à aprovação do avaliador Jev ("sim quando o jev aprovar").
- Estado de execução consistente com o roadmap: C1 (merge 6306fcca) e C2 (b4163140) já commitados localmente no worktree de integração; contrato C3–C9 do Opus pronto; hotfixes C2a/C2b em execução.

## Critérios do veredito

1. O diff é consistente com o que as evidências de aprovação autorizam (reordenação + meta v1.1.0 + D1–D6)?
2. O roadmap continua internamente coerente (fila R1–R9, gates GATE-CLIENTE/GATE-LUANDRO/GATE-PRODUTO respeitados com o escopo definido no próprio arquivo)?
3. Sem informação falsa/sem segredo/sem dado pessoal no diff?
4. Branch model correto (cortada do develop, PR mira develop)?

## Formato da resposta

VEREDITO: APPROVE ou REQUEST_CHANGES
ACHADOS: lista numerada (se REQUEST_CHANGES, cada achado com arquivo+linha e correção necessária)
NOTAS: observações não-bloqueantes (opcional)
