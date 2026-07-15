# Diário de desenvolvimento

Use entradas curtas e cronológicas. Decisões não podem existir apenas em conversa, comentário de código ou memória da IA.

## Decisões já estabelecidas

### 2026-07-11 — Identidade canônica

- Documento é identificado por tipo, número normalizado e cartório.
- Número sozinho serve apenas para pesquisa textual.
- CNS é o identificador estável preferido para apresentar o cartório ao usuário.
- Zeros à esquerda serão preservados.
- “Início de Matrícula” não pode alterar automaticamente o cartório de outro documento.
- Correção de dados será precedida por auditoria e não fará consolidação automática de ambiguidades.

## Modelo de nova entrada

```text
### AAAA-MM-DD HH:MM — TXX — título
- Estado inicial:
- Responsável/IA:
- Hipótese ou objetivo:
- Arquivos pretendidos:
- Decisões tomadas:
- Comandos executados:
- Resultado dos testes:
- Bloqueios/riscos:
- Próximo passo pequeno:
```

## Histórico

### 2026-07-14 (T30) — roteiro de implantação/rollback formalizado; T01–T30 completas

- Estado final: CONCLUÍDA. T01–T30 completas nesta branch.
- Responsável/IA: Claude Code.
- Entregável: `docs/correcao-identidade-documentos/ROTEIRO_IMPLANTACAO.md`, incorporando o que foi levantado nesta sessão sobre o servidor de teste real (SSH funcional em 188.245.225.127, branch atual `hotfix/arvore-duplicacao-cards`, duas alterações locais não commitadas em `settings_prod.py`/`docker-compose.yml`, dezenas de arquivos não rastreados, `scripts/init.sh` rodando migrate em todo restart) e o resultado da auditoria já executada (`auditar_identidade_documentos`, 2524 documentos, zero conflitos).
- Conteúdo: backup via `pg_dump`, preservação de config local via `git stash`, troca de branch, subida controlada com acompanhamento do log de migração, verificação pós-deploy (`verificar_estrutura_ambiente` + `auditar_identidade_documentos` + smoke test funcional + homologação de T25/T26/T07 com dados reais), e rollback de código/migração/dado.
- Decisão: o roteiro cobre só o servidor de teste, não produção; a execução real (push da branch, backup, restart do container) fica para uma sessão separada, com autorização explícita a cada etapa arriscada — este documento é o "o quê fazer", não uma autorização para fazer agora.
- Bloqueios/riscos: nenhum novo. Segue valendo que a auditoria automatizada só cobre `Documento`; `Imovel`/`LancamentoOrigem` contam com a auditoria embutida nas migrações 0048/0049.
- Próximo passo pequeno: revisão do usuário sobre o roteiro; depois commit, PR, e execução do deploy real no servidor de teste.

### 2026-07-14 (T29) — regressão integrada final

- Estado final: CONCLUÍDA. Próxima: T30.
- Responsável/IA: Claude Code.
- Comandos executados: suíte global `dominial.tests` (173 testes, 47 erros + 1 falha — baseline idêntico ao registrado desde antes de T22); suíte focada combinada de 14 módulos (identidade canônica, migrações de identidade/canônica/`LancamentoOrigem`, leitura de origem, comando de migração histórica, T25, T26, T27, e as três dívidas pré-T28 corrigidas): 116/116 passaram. `manage.py check` OK; `makemigrations --check --dry-run` sem mudanças; `git diff --check` limpo.
- Resultado: nenhuma quebra nova; o baseline legado é pré-existente e já estava documentado. T25–T28 totalmente cobertos e verdes.
- Bloqueios/riscos: baseline legado (47 erros + 1 falha) não saneado — fora do escopo desta correção de identidade, já registrado em sessões anteriores.
- Próximo passo pequeno: T30 — formalizar o roteiro de implantação/rollback (já existe um rascunho de uma conversa anterior nesta sessão; falta salvá-lo como documento formal).

### 2026-07-14 (T28) — auditoria final encontra e corrige uma terceira dívida real

- Estado final: CONCLUÍDA. Próxima: T29.
- Responsável/IA: Claude Code.
- Método: repeti o tipo de auditoria estática de T01/R07 — grep por padrões de busca isolada por número (`.filter(numero=`, `.get(numero=`, `origem__icontains`, `Q(numero=`, `.filter(matricula=`) em `dominial/services/`, `dominial/views/`, `dominial/utils/`, `dominial/admin.py` e `dominial/management/commands/`, excluindo testes/migrações, e classifiquei cada ocorrência (corrigir / código morto / diagnóstico / pesquisa administrativa / já seguro).
- **Achado novo e real:** `editar_lancamento` (`lancamento_views.py`) — a checagem que decide se um usuário pode editar um lançamento de um documento de OUTRO imóvel (por esse documento ser "referenciado como origem" na cadeia atual) usava `origem__icontains=lancamento.documento.numero`: um match textual de substring, sem checar cartório. Um homônimo do documento (mesmo número, cartório diferente, de fato não referenciado nesta cadeia) passava nesse teste só por coincidência de texto, autorizando indevidamente a edição. Isso não estava na lista de dívidas do checkpoint original — foi encontrado nesta auditoria.
- Corrigido: a checagem agora usa `LancamentoOrigemLeituraService.obter_origens` (o mesmo serviço que `hierarquia_arvore_service.py` já usa para resolver origens corretamente) e compara tipo + número normalizado + cartório do documento de cada origem do imóvel contra a identidade completa do documento do lançamento que se quer editar.
- Teste: `dominial/tests/test_divida_edicao_lancamento_homonimo.py` (2/2) — homônimo em cartório diferente e não referenciado é recusado (redirect); documento realmente referenciado continua sendo aceito (200). Usa `bulk_create` para o lançamento da origem real, para não disparar o sinal de criação automática (T11/T12) antes do cenário de teste estar montado.
- Demais achados, classificados sem exigir mudança: três arquivos de código morto não importados por nada (`hierarquia_arvore_service_backup.py`, `_corrigido.py`, `documento_service_consolidado.py`); `hierarquia_arvore_service_melhorado.py` usado só por um comando de diagnóstico hardcoded para dois documentos específicos (`testar_conexao_t1004_t2822.py`); comandos de management só de investigação/verificação (leem e reportam, não alimentam resolução ativa); `dominial/admin.py` (filtro de lista e ação "investigar duplicatas") é pesquisa textual administrativa para o staff, não relacionamento de negócio automático; `numero_lancamento` é campo de numeração interna do lançamento, conceito diferente da identidade do documento; e o fallback de `hierarquia_arvore_service.py:75` já é seguro por estar escopado a um único imóvel (comportamento testado desde antes desta branch).
- Comandos executados: `test_divida_edicao_lancamento_homonimo` isolado (2/2); combinado com as duas dívidas anteriores + T25/T26/T27/identidade canônica (88/88); `manage.py check` (OK); `makemigrations --check --dry-run` (sem mudanças); `git diff --check` (limpo); `dominial.tests` global (173 testes, 47 erros + 1 falha legados, baseline inalterado).
- Resultado: T28 fechada com uma correção real adicional, sem regressão.
- Bloqueios/riscos: os arquivos de código morto identificados não foram removidos (decisão de limpeza separada, fora do escopo desta correção de identidade).
- Próximo passo pequeno: T29 (teste integrado de regressão — rodar a suíte completa mais uma vez e revisar o conjunto).

### 2026-07-14 (dívidas pré-T28) — corrigidos os dois cartórios arbitrários (`Cartorios.objects.first()`)

- Estado final: CONCLUÍDA as duas correções; segue para T28.
- Responsável/IA: Claude Code.
- Contexto: com T25/T26/T27 fechadas, o usuário pediu para seguir até o fim (PR + teste no servidor de teste). As duas dívidas técnicas pré-T28 já estavam mapeadas desde 2026-07-14 (revisão do Codex) e foram corrigidas nesta sessão antes de avançar para T28.
- **Dívida 1 — `hierarquia_arvore_service.py:237`:** `_criar_documento_automatico` recebia só `(numero_documento, imovel)` e usava `Cartorios.objects.first()` como cartório quando uma origem não resolvia durante a reconstrução da árvore (`criar_documentos_automaticos=True`). Corrigido: a assinatura passou a receber `cartorio` explicitamente (o `origem.cartorio` já disponível no chamador, o mesmo usado por `_resolver_documento_por_codigo` momentos antes); sem cartório, retorna `None` em vez de adivinhar. Achado durante a investigação: existe `dominial/services/hierarquia_arvore_service_backup.py`, confirmado como não importado por nenhum outro arquivo (código morto), que já tinha exatamente essa correção (`_criar_documento_automatico(numero_documento, cartorio, imovel)`) — evidência de que essa correção já foi feita e revertida/perdida em algum momento anterior, e de que o padrão correto é bem estabelecido (mesma forma usada em `lancamento_origem_service.py` e `hierarquia_origem_service.py`).
- Teste da dívida 1: `dominial/tests/test_divida_cartorio_arbitrario_arvore.py` (2/2). Para exercitar o caminho de fallback (e não o sinal de criação automática já correto de T11/T12, que dispara em `Lancamento.objects.create()` normal), o teste usa `bulk_create` — mesma técnica já usada no teste CR-06. Os dois cartórios do fixture são criados em ordem tal que `Cartorios.objects.first()` devolveria o cartório errado se o bug ainda existisse, garantindo que o teste falharia sem a correção.
- **Dívida 2 — `documento_views.py:199` (`criar_documento_automatico`):** verificava existência de documento só por `imovel + numero` bruto (não normalizado, sem tipo/cartório), e tinha os mesmos dois fallbacks para `Cartorios.objects.first()` (um para o "primeiro documento da cadeia", outro fallback final). Corrigido: existência agora verificada por tipo + número normalizado (via `normalizar_numero_documento`); os dois fallbacks para `Cartorios.objects.first()` foram removidos, e sem cartório resolvível pelo contexto (matrícula do imóvel, ou lançamento com `cartorio_origem` definido) a view recusa a criação com mensagem de erro.
- Achado à parte: essa view (`criar_documento_automatico`, rota `criar-documento/<codigo_origem>/`) não está referenciada em nenhum template ou arquivo JS do projeto — confirmado por busca em `templates/` e `static/`. É um endpoint morto do ponto de vista de uso real (só alcançável chamando a URL diretamente), no mesmo padrão do `verificar_duplicata_ajax` já encontrado durante T27. Decisão: corrigir mesmo assim (a rota nomeada continua registrada e pode ser usada manualmente ou por integrações futuras), não remover — remover um endpoint é uma decisão de maior escopo que não foi pedida.
- Teste da dívida 2: `dominial/tests/test_divida_criar_documento_automatico_view.py` (3/3), incluindo o mesmo cuidado de usar `bulk_create` para isolar o caminho da view do sinal de auto-criação já correto.
- Comandos executados: cada dívida isolada, depois combinada com T25/T26/T27/identidade canônica (86/86); `manage.py check` (OK); `makemigrations --check --dry-run` (sem mudanças); `git diff --check` (limpo); `dominial.tests` global (171 testes, 47 erros + 1 falha legados, baseline inalterado).
- Resultado: as duas dívidas corrigidas sem regressão; nenhuma migração envolvida.
- Bloqueios/riscos: nenhum novo.
- Próximo passo pequeno: T28 (auditoria final de buscas por número isolado).

### 2026-07-14 (T27, fechamento) — teste de regressão confirma cartório ponta a ponta sem mudar código

- Estado final: CONCLUÍDA.
- Responsável/IA: Claude Code.
- Implementação: `dominial/tests/test_t27_regressao_cartorio_duplicata.py`. Cenário: dois documentos M123 homônimos em cartório A e cartório B; `LancamentoDuplicataService.processar_importacao_duplicata` confirma a duplicata do cartório A (mesmo caminho de `duplicata_views.importar_duplicata`); `LancamentoCriacaoService.criar_lancamento_completo` cria o lançamento original com `apos_importacao=true`; `HierarquiaArvoreService.construir_arvore_cadeia_dominial` reconstrói a árvore do imóvel destino.
- Resultado: passou na primeira execução, sem qualquer alteração em código de produção. `LancamentoOrigem` estruturado grava `cartorio_id` do cartório A e `numero_normalizado="123"`; a aresta reconstruída liga por ID ao documento do cartório A; o homônimo do cartório B não aparece nem como aresta nem como nó; nível do nó importado é 1. Confirma a previsão do Codex de que R03/R04/T14/T22/T26 já cobrem esse caminho.
- Comandos executados: teste isolado (1/1); combinado com `test_t26_selecao_inequivoca` + `test_t25_identidade_opcoes` + `test_identidade_documento` (81/81); `manage.py check` (OK); `makemigrations --check --dry-run` (sem mudanças); `git diff --check` (limpo); `dominial.tests` global (166 testes, 47 erros + 1 falha legados, baseline inalterado, +1 novo).
- Bloqueios/riscos: nenhum novo.
- Próximo passo pequeno: tratar as duas dívidas técnicas pré-T28 (`hierarquia_arvore_service.py:237`, `documento_views.py:199`).

### 2026-07-14 (T27, correção de rumo) — implementação descartada; tarefa redefinida

- Estado final: implementação anterior de T27 (prévia CRIAR/IMPORTAR/REUTILIZAR) revertida integralmente; T27 redefinida como teste de regressão, volta a PENDENTE.
- Responsável/IA: Claude Code (correção feita a partir de feedback do usuário; diagnóstico confirmado pelo Codex).
- O que aconteceu: logo após implementar e documentar T27 como "EM REVISÃO", o usuário — antes mesmo de testar — apontou que a implementação partiu de uma compreensão errada. Mensagem do usuário (resumo fiel): o fluxo esperado é checar tipo+número+cartório ao lançar uma origem; se não existe, criar direto; se já existe, avisar o usuário para ele confirmar que não errou o lançamento, e ao confirmar, "importar" o documento e toda a cadeia já lançada a partir dele, gerando uma nova aresta e recalculando a hierarquia. O usuário afirmou que isso **já está contemplado** por "o último PR que resolveu isso" e que esta branch deve focar **somente** na questão dos cartórios, não inventar funcionalidade nova.
- Investigação/diagnóstico: consultei o Codex com o histórico completo (mensagem do usuário, estado do backlog, código já escrito). Confirmou-se que: (1) o fluxo descrito pelo usuário — detectar duplicata, avisar, confirmar, importar cadeia (`ImportacaoCadeiaService`, modelo `DocumentoImportado` da migração 0031), criar o lançamento original — já existe no baseline do repositório, anterior a esta branch; (2) T25/T26 já corrigiram a identidade usada nessa detecção (tipo+número normalizado+cartório) e a validação da seleção, o que bate exatamente com "resolver a questão dos cartórios"; (3) a reconstrução da árvore após a importação já resolve o pai pela identidade completa e usa IDs nas conexões/níveis (`hierarquia_arvore_service.py`, R03/R04/T14) — não foi encontrada lacuna adicional de cartório nesse caminho pós-confirmação, exceto as duas dívidas já conhecidas (que não são deste caminho); (4) a entrada "T27 — Prévia: criar, reutilizar ou importar" já estava no backlog desde o commit reconstruído `0ff36d3`, mas sem critério funcional (CT/CR) correspondente nas seções detalhadas — não dá para provar que foi "alucinada", mas foi especificada sem base verificável, e eu a interpretei como uma funcionalidade nova (três rótulos numa UI) em vez de questionar se já não estava coberta.
- Ação tomada: revertidos via `git checkout --` os três arquivos de produção alterados (`dominial/services/lancamento_duplicata_service.py`, `dominial/views/lancamento_views.py`, `templates/dominial/duplicata_importacao.html`) para o estado exato do commit `b67d368` (T26); removido `dominial/tests/test_t27_previa_duplicata.py`. Confirmado `git diff --stat` só com mudanças em documentação, e suíte `test_t26_selecao_inequivoca` + `test_t25_identidade_opcoes` + `test_identidade_documento` voltando a 80/80 sem alterações de produção.
- Redefinição de T27 (recomendação do Codex, adotada): teste de regressão, não interface nova. Critério: dois documentos homônimos em cartórios diferentes; confirmar a duplicata do cartório escolhido; verificar que o `LancamentoOrigem` gravado guarda o cartório correto; reconstruir a árvore; afirmar que a aresta aponta por ID ao documento do cartório correto; afirmar os níveis; afirmar que o homônimo do outro cartório não aparece. Expectativa: deve passar sem exigir mudança de código.
- Lição registrada: ao encontrar uma entrada de backlog com título vago ("prévia: criar, reutilizar ou importar") e sem critério de aceite detalhado, verificar primeiro se o comportamento descrito já existe no código antes de projetar uma funcionalidade nova — especialmente quando o título sugere uma tela/UX que pode já estar coberta por fluxo legado. Perguntar ao usuário o contrato antes de codificar (o que fiz) não substitui essa checagem "isso já existe?" prévia.
- Bloqueios/riscos: nenhum novo além dos já conhecidos (duas dívidas pré-T28, T07 pendente).
- Próximo passo pequeno: implementar o teste de regressão de T27 redefinida.

### 2026-07-14 (T27, descartado) — prévia: criar, reutilizar ou importar

- Estado final: EM REVISÃO (critérios automatizados atendidos; aguarda revisão do usuário).
- Responsável/IA: Claude Code (contrato confirmado com o usuário antes de codificar; escopo original levantado com apoio do Codex).
- Hipótese ou objetivo: mostrar, antes da confirmação da importação de duplicata, o que será CRIADO (o lançamento no documento ativo), IMPORTADO (documentos da cadeia sem vínculo prévio) e REUTILIZADO (documentos já vinculados antes), para o usuário não confirmar às cegas.
- Decisão de contrato (confirmada pelo usuário via pergunta direta antes da implementação): CRIAR = lançamento previsto a partir de `form_data` (tipo via `LancamentoTipo.get_tipo_display()`, número, data); IMPORTAR = documento da cadeia sem `DocumentoImportado` para `documento_origem.imovel`; REUTILIZAR = documento já com esse registro. Descoberta relevante durante a investigação: `DocumentoImportado` não tem campo de imóvel de destino — o critério de "já importado" em `ImportacaoCadeiaService.importar_cadeia_dominial` é `(documento, imovel_origem)`, global por origem, não escopado ao imóvel de destino. T27 replica exatamente esse critério (não introduz um novo) para a prévia bater com o que a confirmação de fato faz; a limitação em si (potencial falso positivo de "já importado" se dois imóveis diferentes importarem o mesmo documento da mesma origem) foi registrada aqui, não corrigida — fora do escopo de T27.
- Arquivos alterados: `dominial/services/lancamento_duplicata_service.py` (`_status_importados`, `_lancamento_previsto`, `obter_dados_duplicata_para_template` ganha parâmetro opcional `form_data`), `dominial/views/lancamento_views.py` (constrói `form_data` antes do DTO e o repassa), `templates/dominial/duplicata_importacao.html` (bloco de prévia + badges CRIAR/IMPORTAR/REUTILIZAR por documento da cadeia), `dominial/tests/test_t27_previa_duplicata.py` (novo).
- Achado à parte: confirmado que `verificar_duplicata_ajax` (endpoint AJAX) e o campo `documentos_importaveis` do DTO não são usados por nenhum template/JS do frontend — o único caminho real é o POST síncrono em `novo_lancamento` que renderiza `duplicata_importacao.html` server-side, usando `cadeia_dominial` (não `documentos_importaveis`) tanto para exibição quanto para os campos ocultos enviados de volta. T27 focou nesse caminho real.
- Comandos executados: `test_t27_previa_duplicata` (7/7); combinado com `test_t26_selecao_inequivoca` + `test_t25_identidade_opcoes` + `test_identidade_documento` (87/87); `manage.py check` (OK); `makemigrations --check --dry-run` (sem mudanças); `git diff --check` (limpo); `dominial.tests` global (172 testes, 47 erros + 1 falha legados, baseline inalterado, +7 novos de T27).
- Resultado dos testes: 7/7 novos passaram; baseline global mantido; nenhum teste removido ou afrouxado.
- Bloqueios/riscos: aguarda revisão manual do usuário na tela real (visual da prévia); o fluxo POST completo (`novo_lancamento` → detecção de duplicata → render) não foi exercitado ponta a ponta por teste automatizado, só o DTO isolado e a renderização direta do template com contexto construído à mão — mesmo padrão de cobertura usado em T25. Mudanças ainda não commitadas (working tree).
- Próximo passo pequeno: aguardar revisão do usuário para fechar T27; depois tratar as duas dívidas técnicas pré-T28 (`hierarquia_arvore_service.py:237`, `documento_views.py:199`).

### 2026-07-14 (fechamento) — T25/T26 concluídas; decisão de sequenciamento até T30

- Estado final: T25 e T26 passam de EM REVISÃO para CONCLUÍDA.
- Responsável/IA: Claude Code (decisão de sequenciamento revisada por Codex).
- Hipótese ou objetivo: fechar formalmente T25/T26 após a homologação manual do usuário e decidir a ordem de trabalho até o próximo deploy no servidor de teste.
- Homologação manual: o usuário seguiu o roteiro de teste (seleção de documento e tela de duplicata com homônimos M123 em cartórios A/B, botão de novo lançamento por `documento_id`, importação de duplicata) em ambiente local e relatou "parece que está tudo funcionando". Isso satisfaz o critério "aguarda revisão do usuário" registrado nas evidências de T25/T26.
- Auditoria complementar: `auditar_identidade_documentos --fail-on-conflict --json` foi executada (somente leitura, sem migração) contra o banco real do servidor de teste (188.245.225.127, cópia de produção, 2524 documentos) via `docker cp` temporário + `docker exec` no container `cadeia_dominial_web`, sem alterar código, git ou banco. Resultado: zero conflitos, zero inválidos, zero documentos sem cartório. Arquivos temporários removidos do container após a checagem; nenhuma mudança persistente no servidor de teste.
- Decisão tomada (consulta ao Codex): não fazer deploy incremental de T25/T26 no servidor de teste agora. Terminar T27 (prévia: criar, reutilizar ou importar), depois tratar as duas dívidas técnicas pré-T28 (`hierarquia_arvore_service.py:237` com `Cartorios.objects.first()`; `documento_views.py:199` com busca por `imovel+numero`), depois T28 (auditoria final) e T29 (regressão), depois formalizar T30 (roteiro de implantação/rollback), e só então fazer um único deploy/homologação estruturado no servidor de teste cobrindo migrations 0043–0049 + dados reais + T25–T29 de uma vez.
- Razões: T25/T26 já têm testes automáticos e homologação manual suficientes, publicá-las isoladamente não agrega validação relevante; T27 pode exigir ajustes no mesmo contrato de seleção/DTO de identidade, mais caro de corrigir se T25/T26 já estiverem "públicas"; T28/T29 dependem explicitamente de T07–T27 completos; as dívidas técnicas pré-T28 tornariam qualquer homologação parcial incapaz de validar a correção de identidade ponta a ponta.
- Também levantado nesta sessão: um rascunho de roteiro de implantação/rollback (backup via `pg_dump`, preservar config local não commitada do servidor via `git stash`, troca de branch, rebuild/restart, verificação pós-deploy com `verificar_estrutura_ambiente`, rollback de código/migration/dado) foi produzido em conversa e ainda não foi salvo como arquivo formal de T30.
- Achado à parte (não bloqueia T25–T27): a branch `feature/identidade-documento-cartorio` ainda não foi enviada ao GitHub (só existe local); o servidor de teste roda `hotfix/arvore-duplicacao-cards` com `cadeia_dominial/settings_prod.py` e `docker-compose.yml` modificados localmente e não commitados (CSRF_TRUSTED_HOSTS parametrizado via env, formatação do compose) — precisam ser preservados (`git stash`/`pop`) antes de qualquer troca de branch no deploy futuro.
- Bloqueios/riscos: nenhum novo para T25/T26; T07 continua em revisão separadamente, pendente de homologação manual própria (cross-cartorio no servidor de teste, com dados reais).
- Próximo passo pequeno: iniciar T27 (prévia: criar, reutilizar ou importar).

### 2026-07-14 (noite) — T26 — seleção inequívoca por ID e validação backend

- Estado final: EM REVISÃO (critérios automatizados atendidos; aguarda revisão do usuário).
- Responsável/IA: Claude Code (retomada orientada por consulta ao Codex).
- Hipótese ou objetivo: fechar os dois pontos mapeados no checkpoint — (1) o botão de seleção de documento usava `novo_lancamento` sem `documento_id`, deixando a escolha do "documento ativo" a cargo de `imovel.documentos.first()`; (2) o backend de importação de duplicata aceitava `documento_origem_id`/`documentos_importaveis[]` como PKs arbitrários, sem checar que pertenciam à identidade/cadeia oferecida ao usuário.
- Arquivos alterados: `dominial/views/lancamento_views.py`, `templates/dominial/selecionar_documento_lancamento.html`, `dominial/services/lancamento_duplicata_service.py`, `dominial/tests/test_t26_selecao_inequivoca.py` (novo).
- Decisões tomadas:
  - `novo_lancamento_documento` (view `novo_lancamento` com `documento_id`) passou a usar `get_object_or_404(Documento, id=documento_id, imovel=imovel)` em vez de `Documento.objects.get(id=documento_id)` sem filtro de imóvel — um `documento_id` de outro imóvel agora resulta em 404 em vez de renderizar o formulário com imóvel/documento incompatíveis. O `if not documento_ativo:` morto (`.get()` nunca retorna falsy) foi removido junto.
  - O botão "Novo Lançamento" em `selecionar_documento_lancamento.html` agora usa `novo_lancamento_documento` com `documento_id=documento.id`, eliminando a dependência do "primeiro documento" implícito.
  - `LancamentoDuplicataService.processar_importacao_duplicata` não confia mais nos PKs recebidos por si só. Novo método privado `_validar_identidade_duplicata` reprocessa a origem/cartório originalmente submetidos (preservados como campos ocultos `origem_completa[]`/`cartorio_origem[]` no template de duplicata) através do mesmo `DuplicataVerificacaoService.verificar_duplicata_origem` usado na detecção original, e só aceita a importação se o `documento_origem_id` postado bater exatamente com o documento resolvido e se todo `documentos_importaveis[]` postado for subconjunto da cadeia dominial recalculada. Sem origem/cartório preservados, ou com qualquer PK fora da cadeia recalculada, a importação é recusada mesmo que os IDs existam no banco.
  - Nenhuma migração; nenhuma mudança de contrato visível ao usuário além da URL do botão.
- Comandos executados: `test_t26_selecao_inequivoca` (6/6, novo); `test_t25_identidade_opcoes` (7/7); `test_identidade_documento` (74/74 combinados); `manage.py check` (OK); `makemigrations --check --dry-run` (sem mudanças); `git diff --check` (limpo); `dominial.tests` global (165 testes, 47 erros + 1 falha legados — baseline inalterado, +6 testes novos).
- Resultado dos testes: 6/6 novos passaram (documento de outro imóvel recusado com 404; documento de outro imóvel aceito quando é o próprio; importação aceita quando identidade confere; documento fora da cadeia recusado; `documento_origem_id` incompatível com a origem informada recusado; importação sem origem preservada recusada); baseline global mantido.
- Bloqueios/riscos: `test_fase2_duplicata_integracao` continua com 12 erros pré-existentes no `setUp` (campo `descricao` removido de `DocumentoTipo`) — não relacionados a T26, parte do baseline de 47 erros já documentado; não foi possível exercitar T26 através desse arquivo de teste legado, coberto pelo novo `test_t26_selecao_inequivoca` em seu lugar.
- Próximo passo pequeno: aguardar revisão do usuário para fechar T26; depois T27 (prévia: criar, reutilizar ou importar).

### 2026-07-14 (tarde) — verificação final pós-T25

- Estado final: sem mudança de código; verificação de continuidade após sessão anterior ter travado.
- Responsável/IA: Claude Code.
- Hipótese ou objetivo: confirmar que o estado deixado pela sessão anterior (T25 EM REVISÃO) está íntegro antes de prosseguir para T26.
- Arquivos pretendidos: nenhum (somente verificação).
- Decisões tomadas: nenhuma alteração de código; documentação apenas.
- Comandos executados: `git status` e `git diff --check` (limpo); escopo do diff conferido (`lancamento_duplicata_service.py` + 2 templates + docs + `test_t25_identidade_opcoes.py`, sem arquivos fora do escopo de T25); `test_t25_identidade_opcoes` isolado (7/7 OK); suíte canônica (`test_migracao_identidade_canonica`, `test_migracao_identidade_documento`, `test_migracao_identidade_imovel`, `test_migracao_lancamento_origem_canonica`, `test_identidade_documento`) — 82/84 OK, 2 erros em `VerificarEstruturaAmbienteCommandTest`.
- Resultado dos testes: os 2 erros (`IndexError` em `_get_column_collations` do introspector SQLite do Django) foram reproduzidos também em `git stash` sobre o commit `3e94ee2` (árvore limpa, sem as mudanças da sessão) — confirmado que é um problema pré-existente do ambiente local (incompatibilidade Django 5.2/SQLite), não uma regressão introduzida por T25.
- Bloqueios/riscos: nenhum novo; o erro pré-existente do `VerificarEstruturaAmbienteCommandTest` continua sem investigação — não bloqueia T25/T26.
- Próximo passo pequeno: aguardar revisão do usuário para fechar T25; iniciar T26 (seleção inequívoca por ID + validação backend) em seguida.

### 2026-07-14 — T25 — identidade completa nas opções

- Estado final: EM REVISÃO (critérios automatizados atendidos; aguarda revisão do usuário).
- Responsável/IA: Claude Code (plano revisado por Codex).
- Hipótese ou objetivo: exibir tipo, número, cartório (CNS + localização) e imóvel nas opções documentais, distinguindo homônimos antes da seleção, sem mudar o contrato de seleção (T26).
- Arquivos pretendidos: serviço de duplicata, templates de duplicata/importação e de seleção de documento, novo módulo de testes.
- Decisões tomadas: T25 cobre as duas telas de opções (duplicata/importação e seleção de documento); o DTO é aditivo e preserva IDs/URLs/campos existentes; o contrato de seleção permanece para T26; nenhuma migração; corrigido `documento.get_tipo_display` → `documento.tipo.get_tipo_display` (tipo é FK, o original renderizava vazio).
- Comandos executados: `test_t25_identidade_opcoes` (7/7); `test_identidade_documento` (67/67); `test_fase2_duplicata_integracao` (12 erros preexistentes em `setUp` por `descricao` removido do modelo); `manage.py check` (OK); `makemigrations --check --dry-run` (sem mudanças); `git diff --check` (limpo); `dominial.tests` global (159 testes, 47 erros + 1 falha legados).
- Resultado dos testes: 7/7 novos passaram; canônica 67/67; baseline global mantido (47 erros + 1 falha, sem novas quebras).
- Bloqueios/riscos: dois caminhos ativos de criação automática por contexto incompleto contradizem o objetivo “homônimos nunca confundidos” e foram registrados como dívida para T28 (ver entrada seguinte).
- Próximo passo pequeno: fechar T25 após revisão; depois T26, seleção inequívoca por ID (botão da seleção deve usar `novo_lancamento_documento` com `documento_id`; backend de importação deve validar IDs contra a cadeia oferecida).

### 2026-07-14 — dívida identificada — criação automática por contexto incompleto

- Estado inicial: revisão de plano com Codex para retomar o trabalho.
- Responsável/IA: Codex (achado) + Claude Code (verificação no código).
- Hipótese ou objetivo: confirmar se o estado documentado “T01–T24 concluídas” corresponde ao código.
- Achados (verificados em código):
  1. `dominial/services/hierarquia_arvore_service.py:237` — `_criar_documento_automatico()` cria documento com `Cartorios.objects.first()` quando uma origem não resolve; acionado por `dominial/views/cadeia_dominial_views.py:64` (`criar_documentos_automaticos=True`) ao renderizar a árvore D3 (write-on-read).
  2. `dominial/views/documento_views.py:199` — `criar_documento_automatico` verifica existência por `imovel + numero`, sem tipo/cartório canônicos.
- Decisões tomadas: registrar como dívida em `TAREFAS.md` e `CHECKPOINT_ATUAL.md`; T28 deve classificar cada ocorrência e T26/T28 decidir entre corrigir a resolução ou remover o caminho automático.
- Comandos executados: leitura dos três pontos de código com verificação direta das linhas citadas.
- Resultado dos testes: não aplicável (achado de revisão estática).
- Bloqueios/riscos: não bloqueiam T25–T27 (apresentação/seleção), mas inviabilizam declarar “T01–T24 integralmente concluídas” e devem ser tratados antes de T28/T29.
- Próximo passo pequeno: incluir na auditoria final da T28; avaliar correção isolada se vier a bloquear a homologação da T07.

### 2026-07-13 — checkpoint para troca segura de sessão

- R01–R07 e T22–T24 estão concluídas; T25 é a próxima tarefa desbloqueada.
- A documentação de retomada foi revisada e o procedimento para interrupções urgentes foi adicionado ao README e ao checkpoint.
- `last.md` foi removido porque duplicava uma resposta antiga que indicava T22 como próxima tarefa; `CHECKPOINT_ATUAL.md` permanece como fonte única.
- Artefatos locais alheios (`*.sql`, bancos, caches, `node_modules`, pacotes e imagens) ficam fora do commit; a inclusão deve usar lista explícita de arquivos.
- Últimos portões: 98 testes integrados PostgreSQL e 17 focados SQLite passaram; checks e diff passaram; suíte global manteve 47 erros e 1 falha legados em 152 testes.
- Nenhuma migração foi aplicada ao banco compartilhado e nenhum push foi realizado.
- Commit funcional criado: `ade9ab1` (`feat(dominial): consolida identidade canonica e origens estruturadas`).
- Próximo passo: registrar este identificador em um commit documental final; depois, retomar pela T25.

### 2026-07-13 — T24 — leitura estruturada com fallback

- Estado final: CONCLUÍDA.
- Criados `OrigemLancamentoLeitura` e `LancamentoOrigemLeituraService`: a presença de qualquer estrutura desativa completamente o fallback textual daquele lançamento.
- O contrato expõe tipo, número informado/canônico, código apresentável, cartório individual, ordem, livro, folha e fonte.
- Duplicatas/importação, cadeia informativa, tronco, árvore ativa, cadeia completa, tabela e hierarquia de origens deixaram de ler `lancamento.origem` diretamente para criar relações.
- A regressão contraditória apontou o texto para A e a estrutura para B; todos os consumidores seguiram somente B. Outro teste confirmou o fallback legado quando não há estrutura.
- Um ciclo de importação no bootstrap foi encontrado na primeira execução e eliminado com import tardio no utilitário; a regressão voltou a passar.
- Testes: 69 focados e 98 integrados passaram no PostgreSQL; 17 passaram no SQLite; checks, compilação e diff passaram.
- A suíte global executou 152 testes e manteve 47 erros e 1 falha legados.
- Nenhuma migração foi aplicada ao banco compartilhado. Próximo passo pequeno: T25, apresentar identidade completa nas opções.

### 2026-07-13 — T23 — migração histórica segura

- Estado final: CONCLUÍDA.
- Criado `migrar_origens_estruturadas`, com `--dry-run`, `--json` e filtro opcional `--lancamento-id`.
- O comando só converte uma origem direta (`M`/`T` ou número simples) quando `cartorio_origem` está explicitamente gravado; não usa o cartório do documento como inferência.
- Múltiplas origens, texto descritivo, fim de cadeia misturado, valores inválidos e ausência de cartório são classificados com contagens e IDs, sem alteração.
- Lançamentos já estruturados são preservados; a execução real usa bloqueio dos lançamentos e uma transação para o lote inteiro.
- O teste de `--dry-run` confirmou ausência de `INSERT`, `UPDATE` e `DELETE`; repetição não duplicou e uma falha simulada no segundo registro reverteu o primeiro.
- Testes: 4 focados e 96 integrados passaram no PostgreSQL; 15 passaram no SQLite; `check`, `makemigrations --check --dry-run`, compilação e `git diff --check` passaram.
- A suíte global executou 150 testes e manteve exatamente 47 erros e 1 falha legados.
- O comando não foi executado no banco compartilhado. Próximo passo pequeno: T24, leitura estruturada com fallback textual durante a transição.

### 2026-07-13 — T22 — escrita estruturada

- Estado final: CONCLUÍDA.
- O signal funcional de `Lancamento` passou a reconciliar `LancamentoOrigem` tanto ao criar/editar quanto ao limpar o texto, sem modificar `Lancamento.origem`.
- O mapeamento temporário do formulário preserva cartório, livro e folha de cada origem; o fallback geral mantém o comportamento anterior quando não há valor individual.
- A reconciliação é transacional, detecta duplicidade canônica e preserva o ID da identidade ao reordenar; registros removidos do texto são excluídos do conjunto estruturado.
- Fins de cadeia continuam nos modelos próprios. Texto compatível só é estruturado quando o parser funcional produz uma identidade única.
- Testes: 74 focados e 92 integrados passaram no PostgreSQL; 11 de modelo/migração passaram no SQLite; `check`, `makemigrations --check --dry-run` e `git diff --check` passaram.
- A suíte global executou 146 testes e manteve 47 erros e 1 falha legados, sem aumento em relação ao baseline da R07.
- Nenhuma migração foi aplicada ao banco compartilhado. Próximo passo pequeno: T23, comando idempotente com `--dry-run` para origens históricas inequívocas.

### 2026-07-13 — R07 — regressão consolidada

- Estado final: CONCLUÍDA; T03, T11, T14, T17, T18 e T21 voltaram a CONCLUÍDA.
- CR-01 a CR-09 e CT-08/CT-18 permaneceram aprovados na árvore final.
- PostgreSQL: 90 testes integrados de identidade, origem e migrações passaram. SQLite: 9 testes de modelo/migração passaram.
- `manage.py check`, `makemigrations --check --dry-run`, `node --check` do consumidor D3 e `git diff --check` passaram.
- A auditoria estática não encontrou identidade implícita por número nos fluxos ativos reabertos. Restam buscas textuais/diagnósticas, serviços alternativos inativos e ocorrências já destinadas a T22/T28.
- A suíte global executou 144 testes e terminou com 47 erros e 1 falha: a quantidade de falhas é a mesma do baseline anterior às R01–R07. Causas: fixtures com campos removidos (`descricao`, `sncr`), `pytest` ausente em teste legado, `test_onr_post.py` inválido e uma expectativa incompatível com o próprio helper em teste antigo de níveis.
- A suíte global não foi declarada aprovada; o débito legado permanece explícito e deve ser saneado em tarefa própria.
- Nenhuma migração foi aplicada ao banco compartilhado e arquivos não rastreados alheios não foram alterados.
- T07 continua EM REVISÃO por homologação manual independente. Próximo passo pequeno: T22, integrar a escrita de origens estruturadas.

### 2026-07-13 — R06 — início do endurecimento do resolvedor e origem estruturada

- Estado final: CONCLUÍDA; T21 permanece EM REVISÃO até o fechamento consolidado da R07.
- O resolvedor revalida cada candidato retornado pela coluna gerada; incompatíveis ficam em `candidatos_invalidos` e não ocultam nem substituem um candidato válido.
- CR-08 cobriu candidato inválido realmente persistido e o estado legado inválido+válido, sem exceção não tratada.
- `LancamentoOrigem.numero` passou a preservar o valor informado; `numero_normalizado` é gerado pelo banco e usado pela constraint/índice.
- A migração `0049` audita e bloqueia conflitos/valores inválidos sem reescrever dados; avanço, reversão e gravação direta equivalente foram testados.
- Resultado: CR-08/CR-09 e 90 testes integrados passaram no PostgreSQL; 9 testes de modelo/migração passaram no SQLite; `makemigrations --check --dry-run` não detectou mudanças.
- A migração não foi aplicada ao banco compartilhado. T22 continua responsável por integrar a escrita estruturada aos fluxos funcionais.
- Próximo passo pequeno: R07, executar todos os portões e fechar as tarefas reabertas.

### 2026-07-13 — R05 — início da preservação de livro e folha

- Estado final: CONCLUÍDA; T11 permanece EM REVISÃO até o fechamento consolidado da R07.
- A falha foi reproduzida: o cache continha livro/folha individuais, mas o caminho múltiplo recuperava somente o cartório e gravava `0` nos dois campos.
- A leitura do mapeamento passou a devolver cartório, livro e folha; uma única função aplica a ordem de herança nos caminhos único e múltiplo.
- Prioridade: primeiro lançamento do documento de origem, valor individual, valor geral do lançamento e `0` apenas quando tudo estiver ausente.
- CR-07 preservou `11/111` e `22/222` para origens de cartórios distintos; o fallback geral `77/88` também foi aprovado.
- Resultado: 83 testes integrados e compilação dos módulos alterados passaram; `git diff --check` permaneceu limpo.
- Próximo passo pequeno: R06, criar primeiro CR-08 para o candidato legado inválido e CR-09 para a constraint canônica de `LancamentoOrigem`.

### 2026-07-13 — R04 — início das arestas e níveis por ID

- Estado final: CONCLUÍDA; T14 permanece EM REVISÃO até o fechamento consolidado da R07.
- A falha foi reproduzida: duas origens homônimas produziam a mesma chave textual `M999 -> M123`, eliminando uma aresta; o JavaScript também sobrescrevia o nó no mapa por número.
- O serviço ativo passou a usar IDs em `from`/`to`, deduplicação e cálculo de níveis, mantendo campos numéricos apenas para apresentação e diagnóstico.
- O D3 passou a usar ID em mapas, visitados, filhos, conexões extras e chaves de renderização; o organizador da view e os comandos diagnósticos foram alinhados ao contrato.
- CR-06 preservou os dois nós `M123`, as duas arestas e o nível correto independentemente do rótulo repetido.
- Resultado: 81 testes integrados passaram; `node --check` e compilação dos módulos Python alterados passaram.
- Próximo passo pequeno: R05/CR-07, comparar os caminhos de criação única e múltipla para restaurar livro/folha.

### 2026-07-13 — R03 — início da resolução contextual do tronco

- Estado final: CONCLUÍDA; corresponde à parte do tronco da T14, que permanece EM REVISÃO até R04/R07.
- A falha foi reproduzida: `identificar_tronco_principal()` escolhia o homônimo local A porque comparava apenas `doc.numero` antes de considerar o importado B.
- O documento inicial agora é localizado por imóvel, tipo estruturado, número canônico e cartório; as origens são resolvidas com o cartório do respectivo lançamento.
- A escolha textual legada da sessão só pode selecionar uma origem que já tenha sido resolvida contextualmente; sem lançamento com origem, ela não busca um documento pelo número.
- CR-05 passou nas duas ordens de criação e também com escolha de sessão; 80 testes integrados passaram.
- O contrato de conexões e os mapas de níveis não foram alterados e continuam reservados à R04/CR-06.
- Próximo passo pequeno: R04, mapear produtores/consumidores das arestas antes de trocar suas chaves por IDs.

### 2026-07-13 — R02 — unicidade canônica de Documento e Imóvel

- Estado final: CONCLUÍDA; T03, T17 e T18 permanecem EM REVISÃO até o fechamento consolidado da R07.
- Foram adicionados campos canônicos gerados/persistidos a `Documento` e `Imovel`; as constraints, o formulário, o resolvedor e o verificador estrutural passaram a usá-los.
- A migração `0048_identidade_canonica_gerada` audita conflitos e valores inválidos antes de alterar o schema, não reescreve os campos legados e possui reversão testada.
- CR-01 a CR-04 passaram; a equivalência entre expressão gerada e normalizador Python cobre prefixo minúsculo, espaços, zeros, pontuação e espaços internos.
- PostgreSQL: 77 testes integrados de identidade, origem e migrações passaram. SQLite 3.40.1: criação limpa do schema e 13 testes de modelo/formulário passaram.
- `manage.py check`, `makemigrations --check --dry-run` e `git diff --check` passaram.
- A migração não foi aplicada ao banco dev compartilhado. `LancamentoOrigem.numero_normalizado` continua reservado à R06/CR-09, que inclui o caminho real de gravação.
- Próximo passo pequeno: R03/CR-05, corrigir a resolução contextual do tronco principal.

### 2026-07-13 — R01 — persistência canônica

- Estado final: CONCLUÍDA; nenhuma alteração funcional ou de dados.
- Foram mapeadas gravações por formulário, serviços, views, importação, comandos e operações em massa.
- Decisão: preservar `numero`/`matricula` legados e adicionar campos canônicos gerados e persistidos pelo banco.
- Constraints futuras usarão os campos gerados, protegendo também `bulk_create`, `update` e SQL direto.
- A expressão remove espaços externos e prefixo M/T de apresentação, preservando zeros à esquerda, pontuação e espaços internos.
- Estratégias rejeitadas: proteção apenas em `save()`/formulário, constraint sobre texto bruto, reescrita automática dos campos legados e consolidação em migração.
- Documento completo: `DECISAO_PERSISTENCIA_CANONICA.md`.
- Premissa verificada: Django 5.2.3 possui `GeneratedField`; SQLite 3.40.1 e PostgreSQL 15 são os backends a validar na R02.
- Testes não executados: R01 foi exclusivamente arquitetural; CR-01 a CR-04 permanecem `NÃO EXECUTADO` e pertencem à R02.
- Próximo passo pequeno: R02, implementar campos gerados e constraints canônicas em uma migração posterior à 0047.

### 2026-07-13 — revisão geral do commit reconstruído

- Estado inicial: T01–T21 documentadas como concluídas, exceto T07; T22 indicada como próxima tarefa.
- Escopo revisado: commit `0ff36d3` contra `origin/main`, modelos, formulários, migrações, resolvedor, tabela, árvore, tronco, criação automática e testes.
- Resultado automatizado: 59 testes focados e 9 testes de migração aprovados; `manage.py check` e `makemigrations --check --dry-run` aprovados.
- Suíte completa: 122 testes; 47 erros e 1 falha legados já conhecidos, sem evidência de nova quebra proveniente apenas da reconstrução.
- Achado 1: constraints e formulário comparam o texto bruto, permitindo recriar depois da migração conflitos canônicos como `M123`/`123`.
- Achado 2: conexões, deduplicação e níveis da árvore ainda usam número como chave.
- Achado 3: o tronco principal ainda escolhe a origem por igualdade de número dentro da lista carregada.
- Achado 4: criação com múltiplas origens grava livro/folha como `0` em vez de herdar os metadados.
- Achado 5: `LancamentoOrigem` depende de `full_clean()` voluntário e o resolvedor pode propagar erro de candidato legado inválido.
- Decisão documental: reabrir T03, T11, T14, T17, T18 e T21; criar R01–R07; bloquear T22 até R07.
- Documentação detalhada: `REVISAO_GERAL_2026-07-13.md`.
- Próximo passo pequeno: R01, registrar a estratégia de persistência canônica e os testes CR-01 a CR-04 antes de alterar modelos/migrações.

### 2026-07-12 16:41 — T21 — modelo estruturado `LancamentoOrigem`

- Estado final: CONCLUÍDA.
- O novo model preserva a origem por lançamento com índice, tipo documental, número normalizado, cartório e metadados de livro/folha.
- A validação normaliza o número com a mesma regra do restante do sistema e converte inconsistências em `ValidationError`.
- Foi criada a migração 0046 e o ajuste de estado 0047 para estabilizar a chave primária sob `DEFAULT_AUTO_FIELD = BigAutoField`.
- Testes cobriram múltiplas origens no mesmo lançamento, cartórios distintos, normalização e bloqueio de duplicidade estrutural.
- Regressão conjunta com a suíte de identidade: 59 testes aprovados; `manage.py check`, `makemigrations --check --dry-run` e `git diff --check` sem erros.
- A nova tabela ainda não foi aplicada ao banco dev compartilhado.
- Próximo passo: T22, gravar origens estruturadas.

### 2026-07-12 16:34 — T20 — cartório `NOT NULL`

- Estado final: CONCLUÍDA.
- A migração 0045 lista e bloqueia imóveis sem cartório antes de alterar a coluna.
- Em schema avançado, o banco rejeita `NULL`; a reversão restaura tecnicamente a coluna anulável.
- Regressão conjunta T17–T20: 64 testes aprovados; modelos sincronizados, `manage.py check` e `git diff --check` sem erros.
- As migrações 0043–0045 não foram aplicadas ao banco dev compartilhado e exigem nova auditoria no ambiente alvo.
- Próximo passo: T21, modelo estruturado `LancamentoOrigem`.

### 2026-07-12 15:15 — T19 — impedir novas ausências de cartório

- Estado final: CONCLUÍDA; CT-07 aprovado.
- `Imovel.clean()` e a criação via `save()` recusam novos registros sem cartório, preservando atualização temporária de legados até T20.
- `cartorio` foi incluído em `ImovelForm.Meta.fields`, corrigindo a cópia do campo selecionado antes da validação do modelo.
- Suíte focada e regressão T17/T18: 61 testes aprovados.
- Operações em massa/SQL direto ficaram deliberadamente para o bloqueio de banco da T20.

### 2026-07-12 15:11 — T18 — constraint de identidade do Imovel

- Estado final: CONCLUÍDA.
- A constraint `unique_imovel_identidade_registral` usa `(tipo_documento_principal, matricula, cartorio)`.
- A migração 0044 audita conflitos canônicos antes do avanço e conflitos com a constraint antiga antes da reversão.
- A obrigatoriedade de cartório não foi antecipada: prevenção de novos `NULL` pertence à T19 e alteração de coluna à T20.
- Testes cobriram avanço limpo, bloqueio por conflito, coexistência de tipos homônimos, duplicata exata e reversão incompatível.
- Execução conjunta T17/T18: 59 testes aprovados; `--expect-final` aprovado no schema de teste; modelos sincronizados e `manage.py check` sem erros.
- A migração 0044 não foi aplicada ao banco dev compartilhado.
- Próximo passo: T19/CT-07, impedir novos registros sem cartório.

### 2026-07-12 14:48 — T17 — constraint de identidade de Documento

- Estado final: CONCLUÍDA; T02 também saiu de revisão.
- O modelo e a migração 0043 usam unicidade `(tipo, numero, cartorio)`.
- A migração audita identidades canônicas antes da alteração e interrompe conflitos/entradas inválidas sem consolidar dados.
- A reversão audita previamente se a constraint antiga `(numero, cartorio)` comporta os dados atuais e interrompe com mensagem clara quando não comporta.
- Testes separados cobriram avanço limpo, avanço bloqueado, constraint efetiva e reversão bloqueada.
- Execução conjunta: 56 testes aprovados, sem falhas esperadas; `makemigrations --check --dry-run` sem mudanças e `manage.py check` sem erros.
- A migração 0043 não foi aplicada ao banco dev compartilhado; no ambiente alvo, executar primeiro `auditar_identidade_documentos --fail-on-conflict`.
- Próximo passo: T18, constraint do documento principal de Imovel.

### 2026-07-12 14:31 — T16 — verificador estrutural por ambiente

- Estado final: CONCLUÍDA.
- Criado `verificar_estrutura_ambiente`, com seleção de `--database`, saída `--json`, `--fail-on-problem` e `--expect-final`.
- O comando informa migrações pendentes, migrações aplicadas sem arquivo, constraints únicas atuais e atendimento das constraints finais planejadas.
- Teste com captura de queries e auditoria estática confirmaram ausência de escrita ou execução de migrações.
- Suíte focada: 53 testes, 52 aprovados e uma falha esperada de T17; `manage.py check` sem erros.
- Banco dev PostgreSQL: zero migrações pendentes/desconhecidas; Documento ainda usa `(numero, cartorio_id)` e Imovel usa `(matricula, cartorio_id)`.
- `--expect-final` falha intencionalmente até as T17/T18 criarem as constraints com tipo.
- Próximo passo: T17, constraint de Documento.

### 2026-07-12 13:42 — T15 — auditoria somente leitura

- Estado final: CONCLUÍDA.
- Criado `auditar_identidade_documentos`, com saída humana ou `--json` e opção `--fail-on-conflict`.
- O comando agrupa por tipo, número normalizado e cartório; relata conflitos, números inválidos e documentos sem cartório sem escolher correções.
- Teste com captura de queries confirmou ausência de SQL de escrita; a auditoria estática também não encontrou chamadas de gravação.
- Suíte focada: 51 testes, 50 aprovados e uma falha esperada de T17; `manage.py check` sem erros.
- No banco dev, foram auditados 1.220 documentos: zero conflitos, zero inválidos e zero sem cartório.
- O comando deve ser repetido no banco espelhado de homologação antes das migrações.
- Próximo passo: T16, verificador de migrações e constraints por ambiente.

### 2026-07-12 13:38 — T14 — serviços ativos de árvore

- Estado final: CONCLUÍDA.
- Foi criado um resolvedor contextual de aresta por lançamento, reutilizado no tronco, importados, árvore e cadeia completa.
- Origens são resolvidas por tipo, número normalizado e `cartorio_origem`; ausências e ambiguidades não escolhem `.first()`.
- Conjuntos de processados, conexões e cálculo de níveis passaram a usar IDs de documentos.
- CT-18 cobriu pais da árvore, expansão da cadeia completa, documentos importados e tronco principal.
- Suíte focada: 48 testes, 47 aprovados e uma falha esperada de T17; `manage.py check` e auditoria estática sem erros.
- No banco dev, o imóvel 5 agora segue `M9443` para `M9442` de Amambai (ID 163), sem entrar em `T16921` ou nos homônimos de Ponta Porã.
- Próximo passo: T15, comando somente leitura de auditoria de dados.

### 2026-07-12 13:23 — T13 — `HierarquiaOrigemService`

- Estado final: CONCLUÍDA.
- Resolução e criação passaram a priorizar `lancamento.cartorio_origem`, com fallback explícito para o cartório do documento apenas quando ausente.
- A identidade inclui tipo, número normalizado e cartório; resultados ambíguos não são escolhidos nem recriados.
- A chave de origens processadas passou a incluir também o cartório.
- CT-16/CT-19 confirmaram resolução e criação em B sem selecionar ou alterar A.
- Suíte focada: 44 testes, 43 aprovados e uma falha esperada de T17; `manage.py check` sem erros.
- Próximo passo: T14/CT-18.

### 2026-07-12 13:21 — T12 — proibir alteração automática de cartório

- Estado final: CONCLUÍDA.
- Foram removidos os métodos legados que classificavam um homônimo sem lançamentos como edição válida e gravavam outro cartório nele.
- CT-20 confirmou que o início de matrícula em B preserva cartório e observações do documento homônimo em A.
- Suíte focada: 42 testes, 41 aprovados e uma falha esperada de T17; `manage.py check` sem erros.
- A auditoria não encontrou definições, chamadas ou marcações de observação da antiga alteração automática.
- Próximo passo: T13/CT-16 e CT-19.

### 2026-07-12 13:07 — T11 — criação automática de origem

- Estado final: CONCLUÍDA.
- A validação e os dois caminhos de criação passaram a resolver tipo, número normalizado e cartório antes de criar ou reutilizar uma origem.
- O fluxo não interpreta mais um homônimo de outro cartório como edição do registro existente.
- CT-19 confirmou a criação em B sem alterar A e a ausência de duplicação quando B já existe.
- Suíte focada: 41 testes, 40 aprovados e uma falha esperada de T17; `manage.py check` sem erros.
- Os métodos legados capazes de alterar cartório ficaram sem chamadores e serão removidos na T12.
- Próximo passo: T12/CT-20.

### 2026-07-12 13:03 — T10 — obtenção da cadeia de origem

- Estado final: CONCLUÍDA.
- A cadeia informativa passou a reutilizar a resolução contextual criada para a T09.
- CT-18/T10 confirmou que a cadeia contém a origem do `cartorio_origem` e exclui o homônimo de outro cartório.
- Suíte focada: 39 testes, 38 aprovados e uma falha esperada de T17; `manage.py check` sem erros.
- A auditoria estática não encontrou mais consultas de `Documento` por número isolado em `duplicata_verificacao_service.py`.
- Próximo passo: T11/CT-19.

### 2026-07-12 13:01 — T09 — recursão de documentos importáveis

- Estado final: CONCLUÍDA.
- O cálculo recursivo passou a resolver cada origem pelo tipo do prefixo, número normalizado e `lancamento.cartorio_origem`.
- Origem sem cartório, inexistente ou ambígua não é selecionada automaticamente.
- CT-18/T09 confirmou que o homônimo de outro cartório não entra na lista de importáveis.
- Suíte focada: 38 testes, 37 aprovados e uma falha esperada de T17; `manage.py check` sem erros.
- A busca isolada restante no serviço está em `obter_cadeia_dominial_origem` e pertence à T10.
- Próximo passo: T10/CT-18.

### 2026-07-12 13:00 — T08 — verificação inicial de duplicata

- Estado final: CONCLUÍDA.
- A busca inicial passou a resolver a origem por tipo do prefixo, número normalizado e cartório, sem selecionar homônimo de outro cartório.
- CT-17 e casos de normalização/distinção de tipo foram adicionados à suíte atual de identidade.
- Suíte focada: 37 testes, 36 aprovados e uma falha esperada de T17; `manage.py check` sem erros.
- A suíte legada `dominial.tests.test_duplicata_verificacao` tem 18 erros preexistentes antes dos testes, pois usa `DocumentoTipo(descricao=...)`, campo inexistente no modelo atual.
- As consultas recursivas por número isolado foram mantidas intencionalmente para T09 e T10.
- Próximo passo: T09/CT-18.

### 2026-07-12 12:50 — decisão de homologação

- O teste manual da T07 foi adiado para um servidor de testes com cópia controlada do banco e participação dos usuários.
- T07 permanece EM REVISÃO; o teste manual não foi declarado como aprovado.
- Ao final do desenvolvimento será criado um branch separado do `main` para implantação e validação nesse servidor.
- O caso local do imóvel 5 revelou que a carga inicial ainda pode oferecer uma origem inexistente no `cartorio_origem`; o achado permanece pendente de correção/reclassificação antes da aprovação da T07.

### 2026-07-11 11:10 — checkpoint solicitado

- Trabalho salvo para retomada em `CHECKPOINT_ATUAL.md`.
- T07 permanece em revisão aguardando o teste manual da tabela.
- Próxima tarefa prevista após a validação: T08/CT-17.

### 2026-07-11 11:09 — T07 — tabela da cadeia

- Estado: EM REVISÃO, aguardando teste manual.
- Todas as resoluções de Documento no serviço da tabela passaram a usar tipo, número normalizado e `cartorio_origem` do lançamento.
- Origem sem cartório ou ambígua não é selecionada automaticamente.
- A expansão de importados, escolha específica, maior origem, recursão e garantia de documentos usam o mesmo resolvedor contextual.
- Suíte focada: 35 testes, 34 aprovados e uma falha esperada de T17.
- Auditoria estática não encontrou mais `Documento.objects.filter(numero=...)` no serviço da tabela.
- Teste manual solicitado na rota `tis/<tis_id>/imovel/<imovel_id>/cadeia-tabela/`.

### 2026-07-11 10:59 — T06 — resolvedor central

- Estado final: CONCLUÍDA.
- Criado serviço com resultados explícitos `nao_encontrado`, `encontrado` e `ambiguo`.
- A consulta sempre restringe tipo e cartório; candidatos são comparados pelo número normalizado.
- Dados legados `M123` e canônicos `123` juntos geram ambiguidade, sem seleção por `.first()`.
- Suíte focada: 30 testes, 29 aprovados e uma falha esperada de T17.
- Não há alteração visual nem teste manual de navegador nesta tarefa.

### 2026-07-11 10:54 — T05 — DocumentoIdentidade

- Estado final: CONCLUÍDA.
- Criado valor imutável e comparável com tipo, número normalizado e `cartorio_id`.
- Tipo e formatos equivalentes são normalizados na construção.
- Identidade sem tipo/cartório e IDs não positivos são recusados.
- Suíte focada: 24 testes, 23 aprovados e uma falha esperada de T17.
- Não há alteração visual nem teste manual de navegador nesta tarefa.

### 2026-07-11 10:50 — T04 — normalização do número documental

- Estado final: CONCLUÍDA.
- Criada função pura que remove prefixo compatível e espaços de apresentação.
- Zeros à esquerda, pontuação e espaços internos são preservados.
- Prefixo incompatível, tipo desconhecido, texto vazio e prefixo sem número produzem erros explícitos.
- Suíte focada: 17 testes, 16 aprovados e uma falha esperada já conhecida de T17.
- Não há alteração visual nem teste manual de navegador nesta tarefa.

### 2026-07-11 10:46 — T02/T03 — testes-base e formulário

- Banco de testes passou a ser criado do zero após o ajuste da migração 0026.
- A suíte legada executou 54 testes, com 47 erros e 1 falha preexistentes; principais causas: fixtures com campos removidos (`descricao`, `sncr`), dependência `pytest` ausente e `test_onr_post.py` inválido.
- Foi criada uma suíte isolada com oito testes: sete passaram e um é falha esperada da constraint a ser corrigida em T17.
- Os testes revelaram que `clean_matricula()` lia `cartorio` cedo demais e não validava duplicatas. A validação foi movida para `clean()` e passou a considerar tipo+número+cartório.
- T03 concluída; T02 permanece em revisão até CT-05/T06 e remoção da falha esperada em T17.

### 2026-07-11 10:40 — T01 — auditoria de consultas

- Estado final: CONCLUÍDA.
- Foram classificados fluxos ativos, parcialmente qualificados, pesquisas legítimas e implementações de backup.
- A implementação ativa da árvore é `hierarquia_arvore_service.py`.
- Resultado detalhado em `AUDITORIA_CONSULTAS.md`.

### 2026-07-11 10:41 — Infraestrutura de testes — migração duplicada

- `python manage.py check` passou no contêiner dev.
- A criação limpa do banco de testes falhou porque `0025` e `0026` adicionavam `Documento.cri_atual` e `Documento.cri_origem` duas vezes.
- Decisão: manter `0026` no histórico como no-op; ambientes que já a aplicaram permanecem inalterados e bancos novos passam a ser criáveis.
- O banco dev não foi apagado nem alterado manualmente.

### 2026-07-11 — Criação do acompanhamento

- Foram criados backlog, plano de testes, matriz rastreável e este diário.
- Nenhuma alteração funcional ou migração foi realizada.
- A execução local dos testes ainda depende de um ambiente Python com Django instalado.
