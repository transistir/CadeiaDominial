root agent idle; waiting up to 30m0s for 2 background task(s)
I will now wait for the test suite execution to finish.
I am waiting for the background test suite run to complete.
Aguardando a conclusão dos testes em background.
Aguardando o término da execução dos testes.
Aguardando a conclusão da suíte de testes de segregação.
# Veredito: **APPROVE**

> **Declaração formal:** **Sem P0/P1**. O apontamento **P1-H** está completamente **resolvido**. O PR #133 está tecnicamente **apto para merge** (pendente apenas de autorização humana).

---

## 1. Findings por Severidade

- **P0:** Nenhum.
- **P1:** Nenhum remanescente.
  - **P1-H ([`dominial/admin.py:1591-1593, 1700-1701`](file:///root/dev/cadeia-dominial/CadeiaDominial/worktrees/issue-132-integracao/dominial/admin.py#L1591)):** **RESOLVIDO**.
    1. No formulário de edição do admin ([`ImovelAdmin.save_model`](file:///root/dev/cadeia-dominial/CadeiaDominial/worktrees/issue-132-integracao/dominial/admin.py#L1578-L1594)), a mudança de TI é detectada com precisão via `'terra_indigena_id' in form.changed_data`. Se a TI mudou, exige-se `usuario_tem_ti_inteira(request.user, obj.terra_indigena_id_id)`, impedindo a introdução de imóvel em TI onde o usuário só possui acesso legado `UserImovel`. Edições legítimas em outros campos mantêm `eh_mudanca_de_ti = False`, preservando o contrato P1-D.
    2. Na ação customizada [`alterar_ti_view`](file:///root/dev/cadeia-dominial/CadeiaDominial/worktrees/issue-132-integracao/dominial/admin.py#L1648-L1749), o dropdown foi saneado para não-superusuários (`tis_atribuidas_ids + [ti_atual.id]`) e há barreira server-side estrita com `raise PermissionDenied(MENSAGEM_TI_SEM_ACESSO)` logo após a resolução da `nova_ti`.
- **P2 (Nits/UX — não bloqueantes):**
  - [`dominial/admin.py:1568`](file:///root/dev/cadeia-dominial/CadeiaDominial/worktrees/issue-132-integracao/dominial/admin.py#L1568): No changeform padrão, `formfield_for_foreignkey` ainda entrega `tis_for_user(request.user)`. Se um staff selecionar uma TI de outro imóvel legado dele, o formulário passa na validação de choices e é barrado com HTTP 403 no `save_model`. A segurança é 100% estrita (fail-closed); o comportamento é no máximo uma fricção de UX esperada para manter o formulário resiliente a imóveis legados.

---

## 2. Respostas às Perguntas de Fechamento

### 1. O guard do `save_model` cobre o vetor? Há caminhos no admin que salvam `Imovel` sem passar por `save_model`? `changed_data` contém `'terra_indigena_id'`?
- **Sim, cobre o vetor integralmente.**
  - **Nome do campo:** No modelo [`Imovel`](file:///root/dev/cadeia-dominial/CadeiaDominial/worktrees/issue-132-integracao/dominial/models/imovel_models.py#L23), o campo FK foi definido expressamente como `terra_indigena_id = models.ForeignKey('TIs', ...)`. O [`ImovelAdminForm`](file:///root/dev/cadeia-dominial/CadeiaDominial/worktrees/issue-132-integracao/dominial/admin.py#L1482) usa `fields = '__all__'`. Logo, o nome do campo no formulário Django é exatamente `'terra_indigena_id'`. Quando o POST submete um valor diferente do inicial, `form.has_changed()` registra `'terra_indigena_id'` em `form.changed_data`.
  - **Atribuição no objeto:** No fluxo do `changeform_view`, `new_object = form.save(commit=False)` atualiza o atributo `obj.terra_indigena_id_id` com a PK da nova TI antes de despachar para `save_model`. Portanto, `obj.terra_indigena_id_id` avalia a **TI de destino**, sendo validada por `usuario_tem_ti_inteira`.
  - **Bypasses de `save_model` no Admin:**
    - **Bulk Actions / `list_editable`:** Não existem no [`ImovelAdmin`](file:///root/dev/cadeia-dominial/CadeiaDominial/worktrees/issue-132-integracao/dominial/admin.py#L1523). Não há `list_editable` e não há actions de edição em lote registradas para o modelo. A única action nativa do Django é `delete_selected`, que não altera TI nem salva instâncias.
    - **`save_related`:** Não é sobrescrito e, por especificação do Django, apenas persiste formsets inline e relações M2M após `save_model`. O modelo `Imovel` é gravado unicamente por `save_model`.
    - **Formsets / Inlines:** `Imovel` não participa como inline de nenhum outro `ModelAdmin` (apenas `GroupTI` e `UserTI` são inlines em `TIsAdmin`).

### 2. `alterar_ti_view`: a barreira cobre o destino; e quanto à ORIGEM?
- **O comportamento é totalmente seguro e aceitável:**
  - **Destino:** A barreira server-side [`admin.py:1700-1701`](file:///root/dev/cadeia-dominial/CadeiaDominial/worktrees/issue-132-integracao/dominial/admin.py#L1700) exige categoricamente `usuario_tem_ti_inteira(request.user, nova_ti.id)`. O usuário tem atribuição plena sobre o tenant receptor (podendo inclusive criar imóveis nele).
  - **Origem:** O usuário só consegue carregar o imóvel e submeter a alteração porque possui autorização prévia sobre aquele registro específico (`Imovel.objects.for_user()` e `has_change_permission(request, imovel)`).
  - **Avaliação de risco cross-tenant:** O vetor P1-H existia porque um usuário podia injetar novos imóveis em uma TI onde não possuía governança completa (usando a brecha para contornar P1-G). No sentido inverso (mover um imóvel que ele legitimamente edita para uma TI sob sua governança plena), não há quebra de integridade no destino e a ação sobre a origem é respaldada pela permissão de alteração do próprio imóvel. Portanto, não há escalada de privilégio.

### 3. Dropdown: `ti_atual.id` incluso no select
- **Sem efeitos colaterais adversos.**
  - Na [`alterar_ti_view`](file:///root/dev/cadeia-dominial/CadeiaDominial/worktrees/issue-132-integracao/dominial/admin.py#L1695-L1697), caso o usuário selecione a própria `ti_atual`, a view intercepta antes de qualquer validação de permissão:
    ```python
    if nova_ti.id == ti_atual.id:
        messages.warning(request, 'O imóvel já está associado a esta Terra Indígena.')
        return redirect('admin:dominial_imovel_change', imovel_id)
    ```
    Isso impede que uma submissão redundante caia em 403 e devolve feedback amigável ao usuário.
  - A inclusão de `ti_atual.id` garante que templates com `<select>` não renderizem valores órfãos ou forcem seleção incorreta ao abrir a página para imóveis herdados de escopo legado.

### 4. Avaliação dos Testes
- **Os testes estão robustos, completos e sem asserts vacuous:**
  - **`AdminCriacaoImovelEscopoTest` ([`test_segregacao_usuario.py:2523-2580`](file:///root/dev/cadeia-dominial/CadeiaDominial/worktrees/issue-132-integracao/dominial/tests/test_segregacao_usuario.py#L2523)):**
    - `test_staff_so_com_userimovel_legado_nao_cria_no_admin`: O status `302` foi expurgado; aceita estritamente `(200, 403)` e assevera invariabilidade do banco (`count == count_before`).
    - `test_staff_com_userti_cria_no_admin` e `test_superuser_cria_em_qualquer_ti`: Assertam categoricamente `302` **e** `count_before + 1` (sem condicionais que permitiam passar com formulário inválido).
    - `test_save_model_direto_bloqueia_criacao_em_ti_legada`: Teste unitário direto chamando `ImovelAdmin.save_model` com `assertRaises(PermissionDenied)`.
  - **`AdminEdicaoImovelEscopoTest` ([`test_segregacao_usuario.py:2583-2699`](file:///root/dev/cadeia-dominial/CadeiaDominial/worktrees/issue-132-integracao/dominial/tests/test_segregacao_usuario.py#L2583)):**
    - `test_changeform_nao_move_imovel_para_ti_so_legado`: Garante que tentativa via changeform mantém a TI original no banco.
    - `test_alterar_ti_view_destino_legado_eh_barrado`: Garante HTTP 403 explícito e banco inalterado ao tentar mover via `alterar_ti_view` para destino sem `UserTI`.
    - `test_alterar_ti_view_para_ti_com_userti_funciona`: Garante HTTP 302 e persistência no banco quando o destino possui `UserTI`.

### 5. Aptidão do PR para Merge
- **Sim, o PR inteiro está plenamente apto para merge:**
  - A rodada r5 endereçou os últimos apontamentos de segurança levantados na r4 (P1-H e P2).
  - A suíte completa de segregação (`Ran 259 tests in 41.622s`) e a suíte focada de escopo administrativo executaram com **100% de sucesso (0 falhas)** e `System check identified no issues (0 silenced)`.
  - O PR cumpre com rigor os requisitos de segregação da issue #132 e não introduz novas vulnerabilidades.

---

**Próxima ação concreta:** PR aprovado por consenso pelas ferramentas de auditoria; aguardar **autorização humana explícita** para realizar o merge do PR #133 na branch `develop`.
AGY_EXIT=0
