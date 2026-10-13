Vou conferir primeiro a fila obrigatória e, em seguida, auditar o delta r5 contra o código atual, os testes e os verdicts anteriores. O foco será exclusivamente nas 248 linhas indicadas, com validação explícita dos caminhos de salvamento do Django Admin.
[tool] Creating task list: Revisar o delta final r5 do PR #133, validar a correção...
[tool] status: Completed

[tool] Reading ROADMAP.md:1, r5-delta.diff:1, r4-kirosol.md:1, r4-opus.md:1, r4-agy.md:1

[tool] Searching for 'class ImovelAdmin|def save_model|def alterar_ti_view|clas...' in .
[tool] status: Completed
[tool] status: Completed

[tool] Completing #1
[tool] status: Completed
O delta implementa exatamente as duas barreiras pedidas na r4. Agora vou fechar três detalhes que decidem o verdict: nome real do campo no `ModelForm`, existência de ações/formsets que alterem o pai fora de `save_model`, e autorização da origem só-legada.
[tool] Reading admin.py:1441-1810, imovel_models.py:2-121, managers.py:2-241

[tool] Reading test_segregacao_usuario.py:2-181, test_segregacao_usuario.py:2441-2770

[tool] Searching for 'Imovel\.objects\.(filter|get|all).*\.(update|delete)\(|\....' in dominial

[tool] Finding venv/lib/python*/site-packages/django/contrib/admin/optio... in .
[tool] status: Completed
[tool] status: Completed
[tool] status: Completed
[tool] status: Completed

[tool] Searching for 'changeform|change_imovel|edita.*legad|legad.*edita|sem mo...' in tests

[tool] Reading admin.py:91-245, listing ..

[tool] Spawning agent crew
[denied] tool permission approval is not supported in non-interactive mode. Use --trust-all-tools to auto-approve.
[denied] tool permission approval is not supported in non-interactive mode. Use --trust-all-tools to auto-approve.
[tool] status: Failed
[tool] status: Failed
[tool] status: Completed

[tool] Reading admin.py:101-170, test_segregacao_usuario.py:2386-2440, listing CadeiaDominial
[denied] tool permission approval is not supported in non-interactive mode. Use --trust-all-tools to auto-approve.
[tool] status: Failed

[tool] Reading admin.py:101-170, test_segregacao_usuario.py:2386-2440
[tool] status: Completed
A auditoria estática fechou os caminhos: o changeform padrão sempre chama `save_model`; `save_related` ocorre depois e não altera o FK do pai; o `ImovelAdmin` não declara inlines nem bulk action de movimentação. A única gravação administrativa direta é `alterar_ti_view`, que agora tem guard próprio. Vou executar as regressões r5 e confirmar em runtime o nome/semântica de `changed_data`.
[tool] Completing #2
[tool] status: Completed

[tool] Running: ../../venv/bin/python manage.py test dominial.tests.test_segregacao_usuario.AdminCriacaoImovelEscopoTest dominial.tests.test_segregacao_usuario.AdminEdicaoImovelEscopoTest --verbosity 2

[tool] Running: ../../venv/bin/python manage.py shell -c "from dominial.admin import ImovelAdminForm; from dominial.models import Imovel; f=ImovelAdminForm.base_fields['terra_indigena_id']; print('form_field=', 't...

[tool] Running: ../../venv/bin/python manage.py check && git diff --check 20e89ea9..8603f00f -- dominial/admin.py dominial/tests/test_segregacao_usuario.py
[denied] tool permission approval is not supported in non-interactive mode. Use --trust-all-tools to auto-approve.
[denied] tool permission approval is not supported in non-interactive mode. Use --trust-all-tools to auto-approve.
[denied] tool permission approval is not supported in non-interactive mode. Use --trust-all-tools to auto-approve.
[tool] status: Failed
[tool] status: Failed
[tool] status: Failed
O ambiente recusou todos os comandos de shell antes da execução, portanto não vou alegar testes locais. A revisão estática confirma a correção; resta classificar uma pequena fragilidade de cobertura: o teste negativo do changeform ainda aceita `200` ou `403`, embora o fixture torne o destino uma escolha válida e o resultado esperado do guard seja deterministicamente `403`.
[tool] Finding lib/python*/site-packages/django/contrib/admin/options.py in venv

[tool] Searching for 'eh_mudanca_de_ti =|barreira real — destino|ids_inteiras...' in dominial

[tool] Getting symbols in admin.py
[denied] tool permission approval is not supported in non-interactive mode. Use --trust-all-tools to auto-approve.
[tool] status: Failed
[tool] status: Completed
[tool] status: Completed

[tool] Searching for 'eh_mudanca_de_ti|if not usuario_tem_ti_inteira\(request.u...' in dominial
[tool] status: Completed

[tool] Completing #3, #4
[tool] status: Completed

[tool] Completing #5
[tool] status: Completed

[tool] Goal complete
[tool] status: Completed
# Veredito: **APPROVE-WITH-NITS**

**Sem P0/P1. O P1-H está resolvido. O PR #133 está tecnicamente apto para merge em `develop`, pendente somente de autorização humana.**

## Findings

### P0
Nenhum.

### P1
Nenhum remanescente.

- O changeform revalida mudanças de TI em `dominial/admin.py:1591-1592`.
- A ação customizada revalida o destino em `dominial/admin.py:1700`.
- Não encontrei outro caminho administrativo de movimentação que contorne ambas as barreiras.

### P2 — teste do changeform ainda não prova deterministicamente o guard

**Arquivo:** `dominial/tests/test_segregacao_usuario.py:2647-2661`

O teste aceita `(200, 403)`. Neste fixture, `tis_b` está em `tis_for_user()` devido ao `UserImovel` legado; portanto, o formulário deveria ser válido e o resultado esperado do `save_model` é deterministicamente **403**.

O assert de banco inalterado impede que o vetor real passe — um `302` com movimentação falharia —, então não é bloqueante. Porém, aceitar `200` pode mascarar uma invalidação acidental anterior ao `save_model`.

Nit recomendado:

```python
self.assertEqual(response.status_code, 403)
```

Opcionalmente, adicionar também:
- teste direto de `save_model(change=True, changed_data=['terra_indigena_id'])`;
- sucesso pelo changeform padrão ao mover entre duas TIs inteiras.

## Respostas

### 1. Guard, `changed_data` e caminhos de persistência

**O guard cobre o vetor.**

O nome do campo no `ModelForm` é realmente `terra_indigena_id`:

- modelo: `dominial/models/imovel_models.py:23`;
- `ImovelAdminForm.Meta.fields = '__all__'`: `dominial/admin.py:1491-1493`;
- atributo SQL/ID correspondente: `terra_indigena_id_id`.

Quando o POST troca o FK, o `ModelChoiceField.has_changed()` compara o PK inicial com o submetido e inclui **`terra_indigena_id`** em `form.changed_data`. O uso em `admin.py:1591` está correto.

No fluxo padrão Django Admin:

1. `save_form()` constrói o objeto;
2. `save_model()` salva o pai;
3. `save_related()` salva M2M e formsets.

`save_related` e `save_formset` não substituem o salvamento do FK escalar do objeto pai. O `AtribuicaoAuditoriaMixin.save_formset`, em `admin.py:123-135`, trata apenas `UserImovel`, `UserTI` e `GroupTI`; o `ImovelAdmin` não declara inline capaz de trocar a TI.

Também não há bulk action no `ImovelAdmin` que faça `QuerySet.update(terra_indigena_id=...)`. A ação padrão `delete_selected` exclui, não move.

A única exceção é `alterar_ti_view`, que chama `imovel.save()` diretamente e não passa por `save_model`; ela agora possui seu próprio guard em `admin.py:1700`.

### 2. Origem acessível apenas por `UserImovel`

**Aceitável no contrato atual.**

A origem é resolvida por:

- `Imovel.objects.for_user(request.user)` em `admin.py:1657`;
- `has_change_permission(request, imovel)` em `admin.py:1667`.

Logo, o usuário só consegue mover o imóvel específico explicitamente concedido por `UserImovel`. O destino exige acesso integral por `UserTI`/equipe/superuser.

Embora retirar o imóvel da TI de origem afete os demais usuários dela, isso é consequência de editar um objeto para o qual o staff possui autorização explícita. Exigir também TI inteira na origem seria uma nova política de produto e reduziria a compatibilidade legada; não é necessário para fechar o P1-H descrito.

### 3. Dropdown e TI atual

Em `alterar_ti_view`, a composição está correta:

- TIs inteiras;
- mais `ti_atual.id`;
- superuser continua vendo tudo.

Isso garante que um imóvel cuja TI deixou de ser integralmente atribuída continue exibindo sua TI atual. Se o usuário selecionar a própria TI atual, o fluxo retorna o aviso antes do guard; não há bloqueio incoerente.

Observação de UX: o **changeform padrão** ainda usa `tis_for_user()` em `admin.py:1563-1568`, podendo exibir outras TIs visíveis apenas por vínculos legados. Selecioná-las agora termina em 403. É potencialmente confuso, mas no máximo P2 de UX e não reabre o vetor.

### 4. Testes

A cobertura é suficiente para segurança:

- P1-G autorizado exige `302 + count+1`;
- P1-G legado nunca aceita `302`;
- teste direto confirma `PermissionDenied` na criação;
- `alterar_ti_view` exige exatamente 403 para destino legado;
- banco permanece inalterado nos casos negativos;
- destino com `UserTI` exige `302` e banco atualizado.

Resta apenas a permissividade `(200, 403)` do teste do changeform indicada acima. Ela enfraquece a precisão do teste, mas não permite que uma movimentação indevida passe silenciosamente.

### 5. Aptidão global

Considerando que:

- as rodadas 1–4 já auditaram o restante do `prod-full.diff`;
- o delta fecha exatamente os dois caminhos do P1-H;
- não há novo P0/P1;
- a evidência do orquestrador registra 259/259 testes de segregação, combinado 319 OK e `check` sem issues;

o PR está **apto para merge**, pendente somente de autorização humana.

Não consegui repetir a execução local: o harness recusou os comandos de shell antes de iniciá-los por limitação de permissão em modo não interativo. A conclusão combina auditoria estática do delta com a evidência dinâmica fornecida pelo orquestrador.

**Próximo passo:** obter a autorização humana explícita para merge do PR #133 em `develop`; o P2 pode ser apertado antes ou em follow-up.
KIROSOL_EXIT=0
