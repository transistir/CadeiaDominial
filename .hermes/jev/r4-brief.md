# Brief RE-REVIEW rodada 4 (FINAL) — PR #133 (v1.1.0 segregação #132)

Você é revisor sênior de segurança Django. Histórico: r1 → 3 P1 (A/B/C)
corrigidos; r2 → P1-D/P1-E corrigidos + P2 higiene; r3 → você (ou seus pares)
apontou P1-F e P1-G, agora corrigidos no commit 20e89ea9. Verdict:
**APPROVE / APPROVE-WITH-NITS / REQUEST-CHANGES**.

## Delta desta rodada (ÚNICO foco — 198 linhas)

Arquivo: `.hermes/jev/r4-delta.diff` (git diff 15a48bd1..20e89ea9, só dominial/).

**P1-F — bypass `imovel_id=0`** (`dominial/views/imovel_views.py`):
guard usava `is None` mas lookup/criação usavam truthiness; com
`/tis/<TI_alheia>/imovel/0/editar/`, POST válido criava imóvel na TI alheia.
Fix: `if imovel_id is not None:` no lookup (id=0 → get_object_or_404 → 404
natural) e `if imovel_id is None:` nos 2 pontos de criação. Testes: GET/POST
id=0 em TI alheia → 404 + count inalterado (test_get_imovel_id_zero_em_ti_alheia_404,
test_post_imovel_id_zero_em_ti_alheia_nao_cria).

**P1-G — admin cria com TI só-legado** (`dominial/admin.py` ImovelAdmin):
- `formfield_for_foreignkey`: na adição (`resolver_match.url_name.endswith('_add')`)
  e não `usuario_ve_todo`, queryset = `TIs.objects.filter(pk__in=tis_atribuidas_ids(user))`;
  edição mantém `tis_for_user` (preserva P1-D legado).
- `save_model`: `if not change and not usuario_tem_ti_inteira(request.user,
  obj.terra_indigena_id_id): raise PermissionDenied(MENSAGEM_TI_SEM_ACESSO)`
  (barreira real contra POST manipulado; formfield é só UX).
- Testes: AdminCriacaoImovelEscopoTest — staff só UserImovel legado não cria
  (count inalterado), staff UserTI cria, superuser cria em qualquer TI.

## Perguntas de fechamento

1. P1-F: restou algum uso de truthiness de `imovel_id` em `imovel_form` ou
   noutra view com parâmetro opcional parecido (grep `imovel_id` em
   dominial/views/)? O `get_object_or_404` com pk=0 dá 404 mesmo (não existe
   pk 0)? O guard do topo (`imovel_id is None and not usuario_tem_ti_inteira`)
   continua correto para a rota de criação?
2. P1-G: a detecção `_add` por `resolver_match.url_name` é confiável no admin
   Django (confira os url_names reais: `dominial_imovel_add` vs
   `dominial_imovel_change`)? O `save_model` cobre mudança de TI na EDIÇÃO
   (`change=True`) — um staff pode MOVER um imóvel para TI alheia editando?
   (decida se isso é P1 novo ou aceitável: na edição o formfield ainda lista
   `tis_for_user`...). `PermissionDenied` no `save_model` vira 403 no admin?
   `AtribuicaoAuditoriaMixin.save_model` (super) continua funcionando?
3. Alguma regressão nos diffs (imports, indentação, ordem de guard vs
   transaction.atomic)?
4. Com este delta fechado, você daria APPROVE ao PR inteiro (produção
   `.hermes/jev/prod-full.diff` já revisada nas rodadas 1-3)?

## Material

- Repo: `/root/dev/cadeia-dominial/CadeiaDominial/worktrees/issue-132-integracao`
- Delta r4: `.hermes/jev/r4-delta.diff`
- Produção completa vs develop: `.hermes/jev/prod-full.diff`
- Verdicts anteriores: `.hermes/jev/r3-opus.md` (APPROVE-WITH-NITS),
  `.hermes/jev/r3-kirosol.md` (REQUEST-CHANGES: P1-F/P1-G), `.hermes/jev/r3-agy.md`
- Estado develop de arquivo: `git show b1fcb785:dominial/…`

## Evidência (verificada pelo orquestrador)

segregacao 255/255 · combinado pós-fix 344 OK · s8 6/6 · p1e 4/4 ·
escopo_global 30/30 · 144_fase2+157 OK · check 0 issues. Suíte completa pré-r3:
1076 testes, 0 falhas novas vs develop.

Responda em português. Findings P0/P1/P2 com arquivo:linha. Se APPROVE, diga
explicitamente: sem P0/P1, P1-F/P1-G resolvidos, PR apto para merge ( pendente
só autorização humana).
