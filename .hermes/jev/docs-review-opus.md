**VEREDITO: REQUEST_CHANGES**

O escopo é maior que um commit só. A branch `docs/roadmap-reordenacao-132-v110` tem **dois** commits sobre `b1fcb785`, e nenhum dos dois está em outro branch:
- `944d4875`: a reordenação, R9 antecipado, avaliação do PR #133 e changelog (+69/−10).
- `658ebe9c`: as decisões D1–D6 (+25/−14).

Os dois vão juntos no PR, então revisei os dois. Os itens 1, 2 e 4 do briefing estão no `944d4875`, não no `658ebe9c`.

O que está OK:
- **Branch model:** a branch foi cortada do develop (`b1fcb785` é ancestral) e o PR mira develop.
- **Sem segredo nem dado pessoal novo.** Os nomes citados (Hiure, luandro, grupo Transistir_CadDomDev) já aparecem no arquivo.
- **A reordenação e a meta v1.1.0** batem com a proposta do Hiure ("colocarmos como meta a issue 132.. pra v1.1.0").
- **GATE-LUANDRO** continua exigido para a tag.

Os problemas estão na coerência interna do roadmap.

**ACHADOS**

1. **R3 e R3.5 ficam sem destino, e falta a exceção de gate.** `docs/produto-3/ROADMAP.md:6-8` e `:437-439` dizem que "R4–R8 deslizam" e que o R9 é o próximo bloco. Mas o R3 ainda tem itens abertos (#230/2b, #219, #212, #114, #141, #149, #110, #223), assim como o #206 do R3.5 e o housekeeping do R1 (`:61`). O AGENTS.md só permite começar um bloco antes de fechar o anterior com exceção explícita no roadmap. E a execução já começou: C1 e C2 estão commitados.
   **Correção:** registrar no cabeçalho e na seção R9 uma exceção explícita aprovada pelo Hiure em 30/09. Ela precisa dizer se o restante do R3/R3.5 (a) é pausado até a v1.1.0, (b) roda em paralelo, ou (c) só os P1 de produção (#230, #223) furam a fila. O texto deve seguir o modelo da "EXCEÇÃO #215" em `:516`.

2. **O GATE-PRODUTO evento (2) não está registrado, mas a implementação já começou.** `:494-496` diz que o evento (2), a aprovação do plano, autoriza a Fase 1. A seção de gates (`:511-515`) diz que sem esse evento a implementação não começa. O briefing, porém, informa que C1 (`6306fcca`) e C2 (`b4163140`) já estão commitados e que o plano efetivo é C1–C9. O diff não menciona C1–C9; fala em Fases 1–6 e "worktree novo a partir de 9c95b117".
   **Correção:** registrar o evento (2) com data e aprovador, e o plano aprovado (C1–C9, ou o mapeamento C↔Fases). Se não houve aprovação do plano, marcar C1/C2 como trabalho preparatório não mergeável até o evento (2).

3. **O D2 é ambíguo justamente no vazamento CRÍTICO S6.** Em `:481-482`, o texto "Acesso ao documento ⇒ pode editar/excluir (inclusive documento compartilhado, #152/S6)" pode ser lido como autorização da escrita cross-tenant que a própria avaliação classificou como CRÍTICA.
   **Correção:** definir "acesso ao documento" de forma operacional. Por exemplo: o imóvel dono do documento está numa TI atribuída ao usuário, via `documentos_for_user`; caso contrário, 403/404. Também registrar que o S6 continua exigindo teste TDD de negação cross-TI.

4. **Há conteúdo derivado atribuído ao Hiure.**
   - Em `:479-480`, o "caso residual … tratado como origem restrita" é a recomendação do Opus, não a decisão do Hiure (que foi "TI inteira"). O mesmo vale para o "404" do D5 e o "no form e no admin" do D4.
   - A pergunta original do D1 era "origem que resolve para documento sem acesso" e foi reescrita como "granularidade".
   **Correção:** separar com um rótulo como "(implementação derivada — recomendação Opus, não decisão do owner)" ou equivalente.

5. **O cronograma ficou desatualizado.** Em `:565-573`, o R9 ainda aparece em 02–13/11 e há o texto "R8/R9 kickoff #132 (avaliar PR zumbi #133 antes)". Isso contradiz a reordenação.
   **Correção:** reescrever o bloco a partir de 30/09: R9/v1.1.0 em ~35–50h, depois o que restar de R3/R3.5 conforme o achado 1, e então R4–R8 deslocados. Ou, no mínimo, uma nota "cronograma abaixo superado pela reordenação 30/09 — replanejar".

**NOTAS (não bloqueantes)**

1. Em `:442`, as citações "aprovo a reordenação" e "vamos trabalhar em uma nova versão… resolvendo o PR #133" não aparecem nas evidências que recebi. Lá, a fala do Hiure é a proposta "podemos reordenar o roadmap?…". Como a proposta partiu do próprio owner, considero a aprovação suficiente. Mesmo assim, confirmem que as aspas são literais ou citem a frase da evidência.
2. Em `:449`, o caminho `/tmp/pr133-opus-review.md` é efêmero. Prefiram o link do comentário no PR #133, ou versionar o relatório em `docs/produto-3/`.
3. Em `:511`, a GATE-PRODUTO ainda diz "kickoff com luandro". Vale registrar que o Hiure decidiu no lugar dele, como já é a prática do GATE-LUANDRO, para que o gate não pareça pendente.
4. Em `:32`, o "Status geral (snapshot 23/09)" está velho; pode receber uma linha apontando para a reordenação de 30/09.
5. O título do `658ebe9c` diz "GATE-PRODUTO evento 1 concluído", o que está correto. Só cuidado para o PR não ser lido como liberação do evento (2) (ver achado 2).

Com os achados 1–3 corrigidos e os 4–5 ajustados, eu aprovo. São só ajustes de texto: não muda a decisão de reordenar nem a meta v1.1.0.
