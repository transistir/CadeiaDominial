VEREDITO: APPROVE

ACHADOS: nenhum. O commit 79aa757a corrige os 5 achados e as 5 notas da revisão anterior:
- **Achado 1:** a exceção de fila R3/R3.5 está registrada no cabeçalho (`:8-9`) e no bloco R9 (`:447-453`). Inclui a regra caso a caso para #230/#223 e segue o modelo da EXCEÇÃO #215.
- **Achado 2:** o evento (2) está CONCLUÍDO (`:518-534`), com data, aprovador, evidência ("Ok seguir", 01/10) e mapeamento C↔Fases. Merge e tag continuam humanos, com GATE-LUANDRO.
- **Achado 3:** o D2 agora tem definição operacional, via `documentos_for_user` → 404, e mantém o TDD de negação cross-TI no S6.
- **Achado 4:** D1, D4 e D5 têm o rótulo de implementação derivada.
- **Achado 5:** o cronograma marca SUPERADO a partir de 28/09, e as datas de R4–R8 serão replanejadas depois da release.

NOTAS (não bloqueantes):
1. **Colunas quebradas no cronograma** (`ROADMAP.md:612-614`): na linha "Sem 05/10 em di- … ante (estimativa 35–50h)", o texto de duas colunas se misturou. Sugestão: `Sem 05/10→     R9/v1.1.0 (cont., ~35–50h): C3–C9 + fixtures + reviews` e, na linha seguinte, `+ release (GATE-LUANDRO) → resto R3/R3.5 → R4–R8 replanejados`.
2. **Aprovação da exceção R3/R3.5 é inferida** (`:447`): ela vem da reordenação, não de uma fala literal sobre pausar o R3. A justificativa ("a proposta partiu dele") é suficiente. Para manter o mesmo rigor da Nota 1, dá para trocar "aprovada" por "decorrente da reordenação aprovada" ou pedir um "ok" explícito ao Hiure quando surgir o primeiro caso de #230/#223.
3. **Fase 5 troca o trio de review do AGENTS.md** (`:527-528`): ficaria Opus + kiro-cli gpt-5.6-sol no lugar de Codex + agy, e o AGENTS.md exige APPROVE dos 3 modelos de fronteira. Vale confirmar que o Hiure aprovou essa troca (ou registrar que foi ele), para não parecer mudança de regra feita só no roadmap.
4. **Política de push automático** (`:528-531`): o Jev passa a fazer push e abrir PR automaticamente quando quality ≥ 3.5, readiness ≥ 0.6 e gov-conflict ≤ 0.3. Isso é governança nova dentro de um doc de fila. Merge e tag continuam humanos, então não conflita com o AGENTS.md, mas talvez caiba citar essa regra lá também.
5. **Resíduo do Achado 4:** a pergunta original do D1 ("origem que resolve para documento sem acesso") continua reescrita como "Granularidade" (`:490`). É cosmético, porque o rótulo de implementação derivada já cobre o ponto.
