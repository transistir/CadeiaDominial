# Re-review — commit 79aa757a (correções dos seus 5 achados)

Você revisou a branch docs/roadmap-reordenacao-132-v110 (commits 944d4875 + 658ebe9c) e deu REQUEST_CHANGES com 5 achados + 5 notas. Seu relatório: .hermes/jev/docs-review-opus.md neste worktree (leia-o).

O orquestrador aplicou as correções no commit 79aa757a. Verifique no repo /root/dev/cadeia-dominial/CadeiaDominial/worktrees/docs-roadmap-reord-132:

`git show 79aa757a` — diff completo das correções.

Decisões de texto aplicadas (contexto factual que você não tinha antes):
- Achado 1: EXCEÇÃO DE FILA R3/R3.5 registrada no cabeçalho + bloco R9 (R3/R3.5 PAUSADOS até v1.1.0; #230/#223 podem furar fila caso a caso com aprovação do Hiure registrada no arquivo).
- Achado 2: GATE-PRODUTO evento (2) CONCLUÍDO em 01/10 — evidência real: após receber status detalhado com a fila C1–C9, o Hiure respondeu "Ok seguir" no grupo Transistir_CadDomDev (01/10/2026). Mapeamento C↔Fases registrado.
- Achado 3: D2 operacionalizado — "acesso ao documento" = documentos_for_user(user) (imóvel dono em TI atribuída), senão 404; S6 mantém TDD de negação cross-TI.
- Achado 4: conteúdo derivado rotulado "(Implementação derivada — recomendação Opus, não decisão literal do owner)" em D1 (origem restrita), D4 (form/admin), D5 (404).
- Achado 5: cronograma reescrito — semanas até 25/09 mantidas como histórico, 28/09–02/10 marcada SUPERADO, R9/v1.1.0 em execução, R4–R8 replanejados pós-release.
- Nota 1: aspas corrigidas para a fala LITERAL do Hiure em 30/09 (a frase real de abertura da tarefa) + "Ok seguir" 01/10; "aprovo a reordenação" (não literal) removido — a proposta de reordenar partiu do próprio Hiure ("podemos reordenar o roadmap? o que acha de colocarmos como meta a issue 132.. pra v1.1.0?").
- Nota 2: referência a /tmp trocada — registrado que o relatório original se perdeu na limpeza do /tmp e os achados vivem no contrato .hermes/plans/c3-c9-contrato.md (versionado no worktree de integração) e serão resumidos no PR #133.
- Nota 3: seção Gates registra prática corrente: Hiure decide o GATE-PRODUTO na ausência do luandro (eventos 1 e 2 concluídos).
- Nota 4: snapshot 23/09 recebeu linha apontando para a reordenação 30/09.
- Nota 5: evento (2) registrado como aprovação do PLANO (não confunde com liberação do merge — tag segue GATE-LUANDRO).

Responda APENAS:
VEREDITO: APPROVE ou REQUEST_CHANGES
ACHADOS: (se REQUEST_CHANGES, numerados com arquivo+linha)
NOTAS: (opcional, não-bloqueantes)
