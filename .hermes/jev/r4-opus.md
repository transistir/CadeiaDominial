# Veredito r4: **REQUEST-CHANGES**

P1-F e P1-G estão corrigidos no que se propõem. Mas encontrei um caminho que produz o mesmo efeito do P1-G: um staff com acesso só legado consegue **mover** um imóvel para uma TI legado. Isso dá o mesmo resultado que criar o imóvel lá. A correção é pequena.

**Limitação:** o sandbox desta sessão bloqueou o `manage.py test`. Esta revisão é só estática, e não rodei nenhum teste.

---

## 1. P1-F — resolvido ✅

- **Uso de truthiness:** não sobrou nenhum em `imovel_form`. As três checagens (`imovel_views.py:19,23,87,91`) usam `is None` / `is not None`.
- **Outras views com id opcional:**
  - `novo_lancamento` usa `if documento_id:` (`lancamento_views.py:438`). Com id=0 cai no caminho sem documento, e o imóvel já vem escopado por `for_user` + `tis` na linha 433. Não abre nada.
  - `imoveis` (`tis_views.py:154`) e o autocomplete (`autocomplete_views.py:193`) são só leitura e filtrados por `for_user`. Também não abrem nada.
- **pk=0 dá 404?** Sim. O `AutoField` começa em 1, e mesmo que existisse um pk 0 a busca continua filtrada por `for_user` e `terra_indigena_id=tis`. Seria uma edição legítima, não um bypass.
- **Guard do topo:** continua correto. A rota `cadastro` sempre chega com `imovel_id=None`, e o conversor `<int:>` não aceita valores negativos.
- **Edição web não consegue mover de TI:** a busca exige `terra_indigena_id=tis` e a linha 38 força o valor da URL.

## 2. P1-G — resolvido para a criação ✅, mas a TI ainda muda por dois caminhos de edição ❌

- **Detecção de `_add`:** é confiável. O admin registra `'%s_%s_add'`, que vira `dominial_imovel_add` (a edição é `dominial_imovel_change`), e o popup usa a mesma URL.
- **`PermissionDenied` no `save_model`:** vira 403. O `changeform_view` sobrescrito só captura `ValidationError`, então a exceção sobe até o handler do Django, e o `atomic` do admin faz o rollback.
- **`super().save_model`:** continua funcionando. O `AtribuicaoAuditoriaMixin` não define `save_model`, então a chamada vai direto para `ModelAdmin.save_model`.

### P1-H (novo) — mover o imóvel para uma TI só legado contorna o P1-G

**Caminho 1: edição pelo formulário do admin**
- Arquivos: `dominial/admin.py:1567-1568` e `:1587`.
- Na edição, o queryset é `tis_for_user`, que inclui as TIs legado. O `save_model` só revalida quando `not change`.
- Cenário A: um staff com `UserImovel` em X (TI L1) e Y (TI L2) edita X e troca a TI para L2. O formulário valida e o imóvel é gravado na L2.
- Cenário B: um staff com `UserTI` em A e legado em L cria o imóvel em A (permitido) e depois o move para L. É o P1-G em dois passos.

**Caminho 2: `alterar_ti_view`**
- Arquivo: `dominial/admin.py:1670,1680`.
- O destino é `tis_for_user(...).get(id=nova_ti_id)`, que também aceita TIs só legado.

**Contexto:** não é regressão. No develop (`b1fcb785`) o `ImovelAdmin` nem tinha `formfield_for_foreignkey`, então dava para mover para qualquer TI. Mas o efeito é o mesmo que fez o P1-G ser classificado como P1, e o #132 existe justamente para fechar esse tipo de caminho.

**Correção sugerida:**
```python
# save_model
if (not change or 'terra_indigena_id' in form.changed_data) and \
        not usuario_tem_ti_inteira(request.user, obj.terra_indigena_id_id):
    raise PermissionDenied(MENSAGEM_TI_SEM_ACESSO)

# alterar_ti_view, logo após obter nova_ti
if not usuario_tem_ti_inteira(request.user, nova_ti.id):
    raise PermissionDenied(MENSAGEM_TI_SEM_ACESSO)
```
- Opcional: em `alterar_ti_view`, montar `todas_tis` com as TIs atribuídas (como na adição), para o dropdown ficar coerente com a regra.
- Testes a adicionar:
  - mover pelo formulário de edição para uma TI legado: count na TI de destino não muda e a resposta é 403 ou 200;
  - `alterar_ti_view` com destino legado: resposta 403;
  - mover para uma TI com `UserTI`: continua funcionando.

### P2 — os testes do P1-G são fracos (`test_segregacao_usuario.py:2525-2560`)
- **Teste (a):** aceita 200, 302 ou 403. Com a restrição do formfield, o POST com `tis_a` falha na validação do formulário (escolha inválida) e devolve 200. Ou seja, **a barreira do `save_model` nunca é exercitada pelo teste**. Sugestões:
  - afirmar 200 com o erro no campo `terra_indigena_id`;
  - adicionar um teste que chame `ImovelAdmin.save_model` direto, ou que faça mock do formfield, e afirme `PermissionDenied`.
- **Testes (b) e (c):** passam mesmo com 200, ou seja, com o formulário inválido e nada criado. Deveriam afirmar `302` e `count + 1`.

## 3. Regressões no diff
Nenhuma:
- os imports novos (`tis_atribuidas_ids`, `usuario_tem_ti_inteira`, `MENSAGEM_TI_SEM_ACESSO`) são usados;
- a indentação está correta;
- o guard vem antes do `transaction.atomic()`, o que é correto (falha antes de qualquer escrita);
- `obj.terra_indigena_id_id` não é nulo, porque o FK é obrigatório.

**Nit:** a linha 1562 é longa. Dá para trocar por `getattr(request.resolver_match, 'url_name', '') or ''` com `.endswith('_add')`.

## 4. APPROVE do PR inteiro?
Ainda não. Com o P1-H corrigido (as 2 guardas acima e os 3 testes) e os asserts do P2 apertados, eu daria **APPROVE**. Pelo diff, o restante do `prod-full.diff` revisado nas rodadas 1–3 não é afetado por este delta.

**Próximo passo:** aplicar as duas guardas do P1-H em `dominial/admin.py` (no `save_model` e no `alterar_ti_view`), com os testes, e mandar como delta r5. Quem rodar a suíte precisa de um ambiente onde o `manage.py test` seja permitido.
OPUS_EXIT=0
