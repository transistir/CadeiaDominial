Vou conferir primeiro a fila obrigatória e o delta r4; depois valido os pontos de segurança diretamente no código e nos testes antes de emitir o veredito final.
[tool] Creating task list: Revisar o delta final da PR #133 com foco em P1-F/P1-G e ...
[tool] status: Completed

[tool] Reading ROADMAP.md:1-300

[tool] Reading SKILL.md:1-300

[tool] Reading r4-delta.diff:1-400

[tool] Reading r3-kirosol.md:1-300, r3-opus.md:1-300, r3-agy.md:1-300

[tool] Searching for 'imovel_id' in views
[denied] tool permission approval is not supported in non-interactive mode. Use --trust-all-tools to auto-approve.
[tool] status: Failed
[tool] status: Completed
[tool] status: Completed
[tool] status: Completed
[tool] status: Completed
O delta corrige literalmente P1-F e adiciona duas barreiras para P1-G. O ponto ainda sensível é a edição no admin: vou verificar se o queryset legado permite mover um imóvel entre TIs sem atribuição inteira e se há validação server-side nesse caminho.
[tool] Reading admin.py:1451-1730, admin.py:2-181

[tool] Reading managers.py:2-261

[tool] Reading imovel_forms.py:1-180

[tool] Reading imovel_views.py:1-140, urls.py:1-90

[tool] Searching for 'class AtribuicaoAuditoriaMixin|def save_model\(|terra_ind...' in dominial

[tool] Searching for 'def .*\([^)]*\w+_id=None|if (not )?\w+_id\s*:' in views

[tool] Searching for 'admin:dominial_imovel_(add|change)|dominial_imovel_(add|c...' in 
[tool] status: Completed
[tool] status: Completed
[tool] status: Completed
[tool] status: Completed
[tool] status: Completed
[tool] status: Completed
[tool] status: Completed

[tool] Completing #1, #2
[tool] status: Completed
A leitura estática confirmou o risco: no `change`, o campo aceita qualquer TI de `tis_for_user`, inclusive uma TI visível só por outro `UserImovel`, e `save_model` não revalida o destino. Vou agora executar os testes r4, confirmar os nomes resolvidos pelo admin e checar a integridade do diff.
[tool] Reading test_segregacao_usuario.py:71-310, test_segregacao_usuario.py:2321-2580, admin.py:1641-1770

[tool] Running: ../../venv/bin/python manage.py test dominial.tests.test_segregacao_usuario.CriacaoImovelEscopoTITest.test_get_imovel_id_zero_em_ti_alheia_404 dominial.tests.test_segregacao_usuario.CriacaoImovelEs...

[tool] Running: ../../venv/bin/python manage.py shell -c "from django.urls import reverse, resolve; from django.core.exceptions import PermissionDenied; from django.core.handlers.exception import get_exception_res...

[tool] Running: git diff --check 15a48bd1..20e89ea9 -- dominial/ && git diff --stat 15a48bd1..20e89ea9 -- dominial/ && git status --short
[denied] tool permission approval is not supported in non-interactive mode. Use --trust-all-tools to auto-approve.
[denied] tool permission approval is not supported in non-interactive mode. Use --trust-all-tools to auto-approve.
[denied] tool permission approval is not supported in non-interactive mode. Use --trust-all-tools to auto-approve.
[tool] status: Failed
[tool] status: Failed
[tool] status: Failed
[tool] status: Completed
Os testes locais não chegaram a iniciar porque o harness recusou comandos de shell em modo não interativo. A evidência estática, porém, fechou o vetor de edição e revelou que ele também existe na ação customizada `alterar_ti_view`; agora vou confirmar se isso pertence ao delta produtivo da PR e documentar exatamente a correção necessária.
[tool] Searching for 'ImovelAdmin|alterar_ti_view|formfield_for_foreignkey|tis_...' in jev

[tool] Finding lib/python*/site-packages/django/{contrib/admin/options.p... in venv

[tool] Searching for 'alterar.ti|mover|mudan.ca.*TI|terra_indigena_id.*tis_b|im...' in tests

[tool] Reading prod-full.diff:6101-6520
[denied] tool permission approval is not supported in non-interactive mode. Use --trust-all-tools to auto-approve.
[tool] status: Failed
[tool] status: Completed
[tool] status: Completed
[tool] status: Completed

[tool] Reading prod-full.diff:1401-1740, test_segregacao_usuario.py:2691-2800
[tool] status: Completed

[tool] Searching the web
[denied] tool permission approval is not supported in non-interactive mode. Use --trust-all-tools to auto-approve.
[tool] status: Failed

[tool] Reading lancamento_views.py:421-600, tis_views.py:141-210, autocomplete_views.py:71-210, api_views.py:241-370
[tool] status: Completed

[tool] Searching for 'class Imovel\b|DEFAULT_AUTO_FIELD|Imovel\.objects\.(creat...' in 

[tool] Searching for '\+.*[ \t]+$|^\+<<<<<<<|^\+=======|^\+>>>>>>>' in jev

[tool] Reading test_segregacao_usuario.py:2441-2575
[tool] status: Completed
[tool] status: Completed
[tool] status: Completed

[tool] Reading imovel_models.py:1-80, settings.py:146-175
[tool] status: Completed

[tool] Searching for 'eh_adicao|kwargs\['queryset'\] = tis_for_user|if not chan...' in dominial
[tool] status: Completed
Fechamento da auditoria: P1-F está resolvido e a criação no admin está protegida, mas a edição ainda permite uma escrita cross-tenant ao trocar a TI — tanto no formulário padrão quanto na ação customizada. Isso bloqueia o APPROVE.
[tool] Completing #3, #4
[tool] status: Completed

[tool] Goal complete
[tool] status: Completed
# Veredito: **REQUEST-CHANGES**

**Sem P0.** O **P1-F está resolvido** e o caminho de **criação** do P1-G está protegido. Porém, restou um **P1 na mudança de TI durante a edição administrativa**, inclusive na ação customizada `alterar_ti_view`.

## Findings

### P1 — Staff pode mover imóvel para TI visível apenas por `UserImovel`

**Arquivos:** `dominial/admin.py:1562-1568,1587,1670-1719`; `dominial/managers.py:135-151,204-215`

Cenário:

1. Staff tem acesso inteiro à TI A e `change_imovel`.
2. Possui apenas um `UserImovel` legado em algum imóvel da TI B.
3. `tis_for_user()` inclui A e B, embora `usuario_tem_ti_inteira(user, B)` seja falso.
4. O staff edita um imóvel da TI A e escolhe TI B.

No formulário padrão:

- `formfield_for_foreignkey` usa `tis_for_user()` na edição (`admin.py:1568`), portanto oferece a TI B.
- `save_model` valida autorização somente quando `not change` (`admin.py:1587`).
- Com `change=True`, o imóvel é salvo na TI B sem atribuição inteira.

A mesma brecha existe na ação customizada:

- lista destinos por `tis_for_user()` (`admin.py:1670`);
- resolve o destino por `tis_for_user()` (`admin.py:1680`);
- atribui e salva diretamente (`admin.py:1697,1719`), sem passar por `save_model`.

Isso não é aceitável como compatibilidade legada: `UserImovel` concede edição do imóvel explicitamente atribuído, não autorização para introduzir outros imóveis — e toda a cadeia vinculada — naquela TI. É uma escrita cross-tenant e, portanto, **P1 bloqueante**.

**Correção recomendada:**

- Em `save_model`, quando `terra_indigena_id` estiver em `form.changed_data`, exigir `usuario_tem_ti_inteira()` para a TI de destino. Isso preserva a edição normal do imóvel legado quando sua TI não muda.
- Na UX de edição, oferecer apenas a TI atual mais destinos com atribuição inteira, em vez de todo `tis_for_user()`.
- Aplicar a mesma validação server-side em `alterar_ti_view`.
- Adicionar regressões para formulário padrão e ação customizada: staff com TI A inteira + `UserImovel` em B tenta mover imóvel de A para B; esperar 403/form inválido e TI inalterada.

### P2 — Testes positivos do admin podem passar sem confirmar criação

**Arquivo:** `dominial/tests/test_segregacao_usuario.py:2542-2570`

Os testes de UserTI e superuser aceitam status `200` e só verificam o incremento do contador quando recebem `302`. Portanto, podem passar mesmo se a criação autorizada deixar de funcionar e o admin apenas reexibir o formulário com erro.

Devem exigir `302` e `count_before + 1`. O teste negativo também deveria fixar o comportamento esperado: normalmente o queryset rejeita o valor e devolve `200`; um teste direto do `save_model` pode comprovar separadamente a barreira `PermissionDenied`.

## Respostas de fechamento

### 1. P1-F

- Não restou truthiness de `imovel_id` em `imovel_form`: os três pontos relevantes usam `is None`/`is not None` em `dominial/views/imovel_views.py:19,23,87,91`.
- Os demais `imovel_id` nas views são IDs obrigatórios e passam por lookups escopados. As APIs que usam `all(...)` rejeitam zero, falhando fechado.
- Existe um caso semelhante, mas não cross-tenant: `documento_id=None` em `dominial/views/lancamento_views.py:427-438` ainda usa `if documento_id`. Assim, `documento_id=0` é tratado como rota sem documento e seleciona o primeiro documento do imóvel já autorizado. É uma inconsistência P2, não escalada de privilégio.
- `get_object_or_404(..., pk=0)` retorna 404 **se não houver registro com pk zero**. Django não rejeita zero por definição; o modelo usa `AutoField` (`dominial/models/imovel_models.py:19`) e IDs normais são gerados positivos, sem inserções explícitas de zero encontradas. Mesmo que existisse um pk zero, o lookup continuaria limitado por `for_user` e pela TI.
- O guard inicial continua correto: a rota de criação passa `imovel_id=None` e exige TI inteira; qualquer rota de edição, inclusive ID zero, passa pelo lookup escopado.

### 2. P1-G

- A detecção por `url_name.endswith('_add')` é confiável para as URLs canônicas do admin: `dominial_imovel_add` e `dominial_imovel_change`. O teste usa corretamente `reverse('admin:dominial_imovel_add')`.
- O código também trata `resolver_match=None`; nesse caso só perde a restrição de UX, mas a barreira de criação em `save_model` permanece.
- `PermissionDenied` levantado no `save_model`, quando alcançado, propaga para o handler 403 do Django. `changeform_view` captura apenas `ValidationError`, não `PermissionDenied`.
- Em um POST normal para destino ausente do queryset, o formulário pode ser rejeitado antes do `save_model` e retornar `200`, razão pela qual o teste atual não comprova especificamente o 403.
- `AtribuicaoAuditoriaMixin` não implementa `save_model`; ele implementa `save_formset`. O `super().save_model(...)` segue o MRO até `ModelAdmin.save_model`, e a auditoria de formsets continua intacta.
- **A edição não está coberta**, conforme o P1 acima.

### 3. Regressões do delta

Não encontrei problemas de import, indentação ou ordem transacional. O guard de criação antes de `transaction.atomic()` é apropriado: nega antes de qualquer escrita, enquanto `super().save_model` e a sincronização continuam na mesma transação.

A única regressão/gap material é a autorização incompleta da mudança de TI. O diff completo confirma que o uso de `tis_for_user()` nesses caminhos faz parte da PR.

### 4. Aptidão para merge

Ainda **não está apto para merge**. P1-F está resolvido e a criação do P1-G foi corrigida, mas P1-G permanece incompleto na edição/movimentação administrativa.

Não consegui reproduzir os testes localmente porque o harness bloqueou comandos de shell antes da execução. A evidência informada pelo orquestrador — 344 testes pós-fix, suítes direcionadas verdes e `check` sem issues — sustenta as correções testadas, mas não cobre o vetor de movimentação acima.

**Próximo passo:** exigir TI inteira quando `terra_indigena_id` mudar nos dois fluxos administrativos e adicionar testes de não movimentação para destino só-legado.
KIROSOL_EXIT=0
