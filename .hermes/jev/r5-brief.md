# Brief RE-REVIEW rodada 5 (FINAL) — PR #133 (v1.1.0 segregação #132)

Você é revisor sênior de segurança Django. Histórico: r1→P1-A/B/C, r2→P1-D/E,
r3→P1-F/G, r4→P1-H — todos corrigidos. Na r4 você (Opus e kiro-cli) apontou o
P1-H: staff movia imóvel para TI visível só por UserImovel legado (save_model
não revalidava na edição + alterar_ti_view resolvia destino via tis_for_user).
O agy deu APPROVE na r4. Verdict desta rodada: **APPROVE / APPROVE-WITH-NITS /
REQUEST-CHANGES**.

## Delta desta rodada (ÚNICO foco — 248 linhas)

Arquivo: `.hermes/jev/r5-delta.diff` (git diff 20e89ea9..8603f00f, commit único).

**P1-H em `dominial/admin.py`:**
1. `ImovelAdmin.save_model`: guard agora é
   `eh_mudanca_de_ti = change and 'terra_indigena_id' in getattr(form, 'changed_data', [])`;
   `if (not change or eh_mudanca_de_ti) and not usuario_tem_ti_inteira(request.user,
   obj.terra_indigena_id_id): raise PermissionDenied(MENSAGEM_TI_SEM_ACESSO)`.
   Edição legítima SEM mover TI não dispara (P1-D preservado).
2. `alterar_ti_view`: após resolver `nova_ti`,
   `if not usuario_tem_ti_inteira(request.user, nova_ti.id): raise PermissionDenied(...)`.
   Dropdown `todas_tis`: superuser → tis_for_user; demais →
   `TIs.objects.filter(pk__in=tis_atribuidas_ids(user).values_list('pk', flat=True) + [ti_atual.id])`.

**P2 (testes vacuous do P1-G, apontado por vocês na r4):**
- `AdminCriacaoImovelEscopoTest`: UserTI/superuser exigem 302 + count+1 sem
  condicional; legado aceita só (200,403), nunca 302; teste novo direto do
  `save_model` com `assertRaises(PermissionDenied)`.
- Classe nova `AdminEdicaoImovelEscopoTest`: changeform e alterar_ti NÃO movem
  para TI só-legada (banco inalterado / 403); mover para TI com UserTI funciona
  (302 + banco atualizado).

## Perguntas de fechamento

1. O guard do save_model cobre o vetor? Algum caminho do admin que salva
   Imovel SEM passar por save_model (bulk actions, save_related, formsets)?
   `changed_data` contém 'terra_indigena_id' quando o POST muda o FK? (nome do
   campo no form é terra_indigena_id mesmo?)
2. `alterar_ti_view`: a barreira cobre o destino; e a ORIGEM — staff só-legado
   pode mover um imóvel QUE ELE VÊ (legado) para uma TI inteira dele? (decida
   se é aceitável: ele tem TI inteira no destino; o imóvel sai da TI onde só
   tem legado — o efeito cross-tenant é na origem, que ele já podia editar.)
3. Dropdown: `ti_atual.id` incluso garante que o form de edição/mover não
   perca a TI atual; algum efeito colateral (ex.: ex-TI inteira que virou
   legada aparece no dropdown mas o save_model barra — UX confusa, P2 no máximo)?
4. Testes: suficientes? algum vacuous remanescente?
5. Com este delta, o PR inteiro está apto para merge (pendente autorização
   humana)? As rodadas 1-4 já revisaram o resto do prod-full.diff.

## Material

- Repo: `/root/dev/cadeia-dominial/CadeiaDominial/worktrees/issue-132-integracao`
- Delta r5: `.hermes/jev/r5-delta.diff`
- Produção completa vs develop: `.hermes/jev/prod-full.diff`
- Verdicts anteriores: `.hermes/jev/r4-opus.md`, `.hermes/jev/r4-kirosol.md`, `.hermes/jev/r4-agy.md`
- Estado develop de arquivo: `git show b1fcb785:dominial/…`

## Evidência (verificada pelo orquestrador)

segregacao 259/259 · combinado pós-fix 319 OK (segregacao+escopo+s8+p1e+210) ·
check 0 issues · suíte completa pré-r4: 1076 testes, 0 falhas novas vs develop.

Responda em português. Findings P0/P1/P2 com arquivo:linha. Se APPROVE, diga
explicitamente: sem P0/P1, P1-H resolvido, PR apto para merge (pendente só
autorização humana).
