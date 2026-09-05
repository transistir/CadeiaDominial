# Disclaimer text by domain

Standard disclaimer / non-claim text for regulated systems, organized by domain. Copy the closest match and adapt to your contract.

## CadeiaDominial (Brazilian public registry / INCRA)

**For fim de cadeia dominial, origin indicators, chain visualization:**

```
⚠️ Atenção: Visualização organizada exclusivamente a partir dos dados
cadastrados. Não constitui parecer jurídico nem validação registral.
```

**Variants (for tighter spaces, tooltips):**
- Short: `Visualização organizada exclusivamente a partir dos dados cadastrados. Não constitui parecer jurídico nem validação registral.`
- Long: `Os dados apresentados refletem exclusivamente a organização das informações cadastradas neste sistema, sem análise jurídica, validação registral, nem atribuição de legitimidade às origens documentais.`

**Where it must appear (verified 2026-07-29):**
- D3 tooltip for fim-de-cadeia cards (append to existing tooltip)
- `templates/dominial/cadeia_dominial_pdf.html` (banner before header)
- `templates/dominial/cadeia_completa_pdf.html` (banner before header)
- Optional but recommended: tronco_principal.html (above the chain), documento_detalhado.html footer

**HTML styling for the banner (CadeiaDominial, amarela 9pt):**
```html
<div class="disclaimer" style="background: #fff3cd; border-left: 4px solid #856404; padding: 8px 12px; margin: 10px 0; font-size: 9pt; color: #856404;">
    <strong>⚠️ Atenção:</strong> Visualização organizada exclusivamente a partir dos dados cadastrados. Não constitui parecer jurídico nem validação registral.
</div>
```

## LGPD (Brazilian data protection)

**For systems that display or process personal data:**

```
Os dados pessoais exibidos são tratados conforme a Lei nº 13.709/2018
(LGPD). O acesso é restrito a usuários autorizados e registrado para
fins de auditoria.
```

**Variant for sharing/exporting:**
```
Este documento contém dados pessoais. O compartilhamento deve observar
a finalidade do tratamento e a necessidade de informação, conforme LGPD.
```

**Variant for public-facing pages (with no PII):**
```
Este sistema não exibe dados pessoais sensíveis. Em caso de dúvida
sobre o tratamento de dados, consulte o encarregado (DPO) da
organização.
```

## Financial / investment / tax

**For systems that show calculations, projections, or financial advice-adjacent data:**

```
As informações apresentadas são meramente indicativas e não
constituem recomendação de investimento, planejamento tributário,
ou aconselhamento financeiro. Consulte um profissional habilitado
antes de tomar decisões com base nestes dados.
```

**Variant for projections / forecasts:**
```
Projeções e estimativas são baseadas em premissas e dados históricos
disponíveis na data de geração. Resultados reais podem diferir
significativamente. Esta informação não constitui garantia de
performance futura.
```

## Medical / health (CFM, ANVISA)

**For systems that display health data, vital signs, or clinical information:**

```
As informações exibidas são de caráter informativo e auxiliam, mas
não substituem, o julgamento clínico do profissional de saúde
habilitado. Diagnósticos e condutas terapêuticas devem ser
determinados por profissional médico registrado no Conselho Federal
de Medicina.
```

## Engineering / construction (CREA, CAU)

**For systems that show technical specifications, project data, or measurements:**

```
Os dados técnicos apresentados são fornecidos pelos responsáveis
habilitados e registrados nos respectivos conselhos profissionais
(CREA/CAU). A utilização destas informações deve observar a
responsabilidade técnica do profissional emissor.
```

## Educational / academic (MEC, INEP)

**For systems that show academic records, grades, or institutional data:**

```
Os dados acadêmicos apresentados refletem os registros oficiais
da instituição. Certidões e históricos oficiais devem ser solicitados
diretamente à secretaria acadêmica, conforme regulamentação do MEC.
```

## Generic / multi-purpose

When the domain doesn't fit any of the above, or as a fallback:

```
As informações apresentadas são organizadas a partir dos dados
cadministrados neste sistema, sem análise ou interpretação adicional.
Para decisões com efeitos legais, consulte profissional habilitado
e fontes oficiais.
```

## Anti-patterns in disclaimer text

- **Hidden in CSS:** `display: none; font-size: 0; visibility: hidden` — legally invalid. The disclaimer must be RENDERED.
- **Different text per surface:** D3 tooltip says one thing, PDF says another. They must be IDENTICAL (or at least semantically equivalent — same meaning).
- **Optional / "as needed":** the disclaimer is MANDATORY, not optional. Show it on every render of the regulated data.
- **Below the data:** the disclaimer should be ABOVE the data, so the user sees it before the data, not after.
- **Vague:** "use with care" or "verify before use" — legally weak. The disclaimer must say EXACTLY what the system is NOT (não constitui parecer jurídico, não constitui validação registral, etc.).
- **Implementation-invented:** the disclaimer text must come from the contract/TDR or a lawyer, not from the implementer's intuition. If the contract doesn't specify the exact text, FLAG THIS to the user before generating one.

## The "where to put it" checklist

For any feature that has a disclaimer, verify the disclaimer appears in EVERY surface that shows the regulated data:

- [ ] D3 / chart tooltips
- [ ] Tree / organogram card tooltips
- [ ] PDF templates (each one)
- [ ] Excel export (header row or footer)
- [ ] Email notifications (subject or body)
- [ ] Print view
- [ ] API responses (in the `disclaimer` field)
- [ ] Admin / debug views (if accessible to non-admins)

For each surface, verify:
- The disclaimer is RENDERED (CSS-visible)
- The disclaimer is the SAME text across all surfaces
- The disclaimer comes BEFORE the regulated data
