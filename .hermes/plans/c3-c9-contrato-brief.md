# Contrato de resolução — C3–C9 (pós-C1/C2, branch feat/issue-132-integracao-v110)

Você é o revisor sênior. Já produziu antes o relatório de compatibilidade do PR #133 e o contrato hunk-a-hunk da Fase 2 (C1) + arquitetura de escopo (C2) — ESSES ARTEFATOS SE PERDERAM (estavam em /tmp). Mas o estado EXECUTADO está no worktree:

- **C1 já commitado**: merge `6306fcca` (PR #133 head 9c95b117 + develop b1fcb785), 15 conflitos resolvidos conforme seu contrato anterior. S5/S6 (críticos) fechados no C1.
- **C2 já commitado**: `b4163140` — sentinela `ESCOPO_GLOBAL` + `documentos_no_escopo()`/`escopo_documentos()` em `dominial/managers.py`; 8 módulos endurecidos (None→global = TypeError); `dominial/tests/test_escopo_global.py` (T11, 29 testes, allowlist fechada de produção); 83 chamadas de teste adaptadas.
- Evidência atual: test_escopo_global 29/29; test_segregacao_usuario 194/195 (única falha = ManagerOptInRegressaoTest = canário S1 — XLS por TI sem escopo, agendado para C8).

Sua tarefa AGORA: escrever o **CONTRATO EXECUTÁVEL dos commits C3–C9** que um júnior (outra máquina/modelo) vai seguir em TDD. Você NÃO escreve o código; especifica cada decisão. Leia o código real do worktree (pós-C2) — não confie em memória do contrato anterior.

## Decisões de produto TOMADAS pelo Hiure (30/09–01/10) — incorpore em tudo

- **D1 — Granularidade = TI inteira.** Acesso a um imóvel ⇒ acesso a todos os imóveis da MESMA TI. O `for_user` já faz isso. Caso residual: cadeia cuja origem aponta para documento de OUTRA TI (não atribuída). Na visualização: mostrar "origem restrita/sem acesso" SEM expor dados do imóvel da outra TI. Na criação/escrita: não vincular e dar mensagem explícita (não IntegrityError anônimo). Texto neutro assumido pelo orquestrador (Hiure não vetou): "Origem em outra TI — sem acesso / solicite ao admin".
- **D2 — acesso ao DOCUMENTO ⇒ pode editar/excluir** o lançamento vinculado (vale documento compartilhado). Teste de autorização = "usuário tem acesso ao documento" (documentos_for_user), não "é dono do imóvel". `_resolver_lancamento_no_contexto_do_imovel` (#152) já escopa por user desde o C1 — verifique se a semântica D2 está completa.
- **D3 — `buscar_m_anterior` (S2):** se o documento existe em outra TI, responder "documento existe em outra TI — solicite acesso ao administrador", SEM doc_id, SEM matrícula, SEM nome do imóvel, SEM nome da outra TI. Só o fato de existir.
- **D4 — só superuser edita cartório** (S7/#210): sincronização de cartório do `ImovelDocumentoService` e campo de cartório em form/admin de imóvel gateados em `user.is_superuser`.
- **D5 — XLS por TI (S1/#179): exige a TI inteira atribuída.** `exportar_cadeia_dominial_excel_tis` só roda se a TI está nas TIs do usuário; senão 404. `CadeiaCompletaService` da rota recebe escopo do usuário. (Este é o canário que o ManagerOptInRegressaoTest já detecta.)
- **D6 — go-live com atribuição fina por TI** (runbook, não código).

## Commits a especificar (C3–C9)

- **C3 — D1 na LEITURA**: origem que aponta para documento fora do escopo → status "restrito" (sem dados: sem número, sem cartório, sem imóvel). Onde: `obter_origens_resolvidas`/pendências ambíguas em hierarquia_utils + tabela/arvore services + templates que renderizam origem. Especifique o formato do marcador "restrito" (dict/objeto), quem produz, quem consome, e o teste de segregação T-D1-leitura.
- **C4 — D1 na ESCRITA**: criação/edição de lançamento cuja origem resolve para documento de outra TI → não vincular + mensagem explícita (nunca IntegrityError/vincular cross-TI). Onde: lancamento_origem_service/lancamento_criacao_service/api_views (escolher_origem_documento). Especifique o fluxo e o teste T-D1-escrita.
- **C5 — D2 (#152)**: auditar se `_resolver_lancamento_no_contexto_do_imovel` e os call sites (editar/excluir lançamento) já cumprem D2 pós-C1; se sim, escreva o teste de regressão que PROVA (documento compartilhado: usuário com acesso ao documento edita/exclui; sem acesso → 404). Se houver lacuna, especifique o fix.
- **C6 — D3 (S2, buscar_m_anterior)**: resposta "existe em outra TI" sem metadados. Especifique assinatura, corpo e o teste T-D3 (inclui: não vaza doc_id/matrícula/nome).
- **C7 — D4 (S7/#210)**: cartório só superuser. Especifique onde gatear (ImovelDocumentoService.sincronizar..., form de imóvel, admin) e o teste T-D4.
- **C8 — D5/S1 (XLS por TI)**: `exportar_cadeia_dominial_excel_tis` exige TI inteira do usuário (404 senão) + CadeiaCompletaService com escopo do usuário. DEVE fazer o ManagerOptInRegressaoTest (canário) voltar a verde. Especifique o teste adicional se necessário.
- **C9 — S8 + badge**: (a) respostas de API não podem vazar `str(e)` com detalhes internos — especificar padrão de mensagem por endpoint tocado; (b) badge #174 em tis_detail (status_cadeia_map) — verificar o que o C1 deixou e o que falta.

Para CADA commit: assinaturas finais, pseudo-código Python preciso (o júnior não decide nada sozinho), arquivos+linhas (cite do código atual), testes novos (nome do teste + o que afirma + onde colocar: qual arquivo de teste existente ou novo), dependências entre commits, e critérios de verde (quais suites devem passar: mínimo test_segregacao_usuario 195/195 após C8, test_escopo_global 29/29 sempre, módulos específicos de cada issue).

## Seções finais obrigatórias

- **Ordem de execução** (dependências; quais commits podem ser paralelizados).
- **Riscos/ambiguidades**: onde você NÃO tem evidência → escreva "NÃO VERIFICADO — parar e perguntar" (o júnior deve parar, não chutar).
- **Fase 4 (fixtures)**: os ~169 testes do develop que falham por usuário-sem-TI (canário) — especifique a estratégia de adaptação das fixtures (helper compartilhado? UserTI no setUp de cada módulo?), sem afrouxar guards. Liste os módulos afetados (rode a suite se quiser evidência: /tmp/c2-suite-full2.log tem o log merged+C2; baseline develop puro em /tmp/baseline-develop-full.log).

## Material

- Worktree: `/root/dev/cadeia-dominial/CadeiaDominial/worktrees/issue-132-integracao` (HEAD b4163140, limpo).
- Python: `/root/dev/cadeia-dominial/CadeiaDominial/venv/bin/python`; rode testes com `manage.py test <módulo>`.
- Refs: origin/develop (b1fcb785), PR head 9c95b117, merge-base 0d95b54f.
- NÃO commite, NÃO altere código. Só leitura + testes (read-only de propósito).

Markdown, português, direto, cite arquivo+função+linha. SALVE O CONTRATO EM: `/root/dev/cadeia-dominial/CadeiaDominial/worktrees/issue-132-integracao/.hermes/plans/c3-c9-contrato.md` (NUNCA em /tmp — /tmp é limpo).
