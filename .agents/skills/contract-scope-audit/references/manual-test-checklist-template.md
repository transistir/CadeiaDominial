# Manual test checklist template

After a contract-compliance fix PR is opened, the user runs manual tests in their real environment. This is a **template** for the prompt you send to Codex (xhigh, read-only) to generate the checklist, plus a **real example** from issue #85 / PR #89 in the CadeiaDominial repo.

## The prompt to send Codex

```
You are a senior QA engineer writing a MANUAL TEST CHECKLIST for PR #N on transistir/CadeiaDominial.
The PR title: "<exact title from PR>"

It implements M TDR-compliance fixes (Contrato Nº 019/2026/AJU-FADESP, item 1.1(a)) forbidding
legal/registry validation language in the <feature>.

## What changed (from the diff at /tmp/prN-diff.txt):

<enumerate the M fixes with the specific files/lines affected>

## Your task

Write a MANUAL TEST CHECKLIST that the developer can follow to verify all M fixes work
correctly in a real running instance.

The checklist should be:
- Concrete (specific URLs, click sequences, expected text)
- Testable (clear pass/fail criteria)
- Organized (group by area: formulário, organograma D3, PDFs)
- Bilingual (Portuguese interface is what the user sees)

Format:

# Checklist de Testes Manuais — PR #N / Issue #M

## Pré-condições
- Branch: feature/issue-N-<short>
- URL-base: http://localhost:8000
- [ ] Ambiente rodando: docker compose up
- [ ] Login feito como usuário com permissão
- [ ] Imóvel com documentos normais disponível
- [ ] Imóvel com <feature> cadastrada para testes 2-M
- [ ] Critério: cada item deve resultar em APROVADO / PASS

## 1. <First fix name>
- [ ] <test step>
  **Esperado / Expected:** <expected outcome>
...

## Sanity checks finais
- [ ] <grep the old forbidden term everywhere — expect 0 hits>
- [ ] <grep the disclaimer negative claim — expect only in disclaimer>
- [ ] The system loads without console errors
```

## Key elements Codex MUST include (validated 2026-07-29 in #89)

1. **DB-compatibility probe** — a `python manage.py shell` command that proves the internal
   enum string was preserved (e.g. `OrigemFimCadeia.objects.get(...).classificacao_fim_cadeia`
   returns `'origem_lidima'`, NOT the new label).
2. **Three explicit PDF checks** — download each PDF (default + completo), verify the
   yellow banner is at the top, the old label is gone, the layout is not broken.
3. **Color checks with hex codes** — for each color change, the user should see specific
   hex values (e.g. `#6c757d` for neutral gray, NOT green). The colors are the
   legal-compliance lever, so be precise.
4. **Tooltip fallback simulation** — for fix #4 (the "Sem Origem" → "Tipo não classificado"
   fix), provide a JS console snippet that monkey-patches the data and re-renders. **Flag
   to the user that the snippet depends on globals that may not exist in the build** —
   `window.tisId`, `window._zoomGroup`, etc. If they don't exist, the test is invalid.
5. **Model default shell check** — `FimCadeia(nome='QA').classificacao` should return `''`
   or `None`, NOT `'origem_lidima'`.

## Honest caveats Codex MUST include in the reply

- "Some JS snippets in the checklist depend on window globals that may not be exposed in
  the actual build. If a snippet doesn't work, the test is invalid; report back."
- "The DB-compatibility probe requires the user to be in a shell session, not the browser."
- "Some tests require creating new data — make a backup first or use a QA property."

## Real example (extracted from issue #85 / PR #89, 2026-07-29)

The full checklist generated for #89 has 5 fix sections + PDFs + sanity checks. It
includes:

- Section 1 (label): 7 form + 2 table + 1 DB-shell bullet
- Section 2 (disclaimer): 3 tooltip bullets
- Section 3 (colors): 6 color/glyph bullets (origem identificada, inconclusa, sem origem, badge emoji)
- Section 4 (fallback): 3 bullets including a JS monkey-patch snippet
- Section 5 (default removed): 3 bullets including a `manage.py shell` check
- PDFs: 5 bullets (download default, download completo, banner text, no "Lídima", layout)
- Sanity: 5 bullets

Total: ~32 bullets, ~140 lines. The user reported the checklist as skimmable and runnable
in ~20 min.

## Common Codex mistake in the checklist

Codex sometimes puts the "DB-compatibility probe" as a one-liner that requires the user to
construct the `OrigemFimCadeia.objects.get(...)` query with the right `lancamento_id`. This
fails if the user doesn't know the right ID. **Pre-include a generic query** that the user
can adapt:

```bash
docker compose exec web python manage.py shell -c "
from dominial.models import OrigemFimCadeia;
o = OrigemFimCadeia.objects.first();
print('classificacao_fim_cadeia:', repr(o.classificacao_fim_cadeia)) if o else print('no rows')
"
```

This works on the first fim-de-cadeia row in the DB. The user can adapt `first()` to
`filter(...)` for a specific test case.
