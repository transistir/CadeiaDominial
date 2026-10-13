## Verdict: **APPROVE-WITH-NITS**

Não encontrei P0 nem P1. O P1-H está resolvido e, pelo que revisei, o PR está apto para merge, faltando só a autorização humana.

Não consegui rodar os testes: o sandbox desta sessão bloqueia `manage.py test`. A análise é estática. Os números de testes que aparecem abaixo vêm da evidência do orquestrador; não os reproduzi.

---

### 1. O guard do `save_model` cobre o vetor?

**Sim.**
- **Nome do campo:** o campo do model é `terra_indigena_id`, um `ForeignKey` (`dominial/models/imovel_models.py:23`). No form ele se chama `terra_indigena_id` e o atributo de ID é `obj.terra_indigena_id_id`. Os dois nomes estão corretos em `dominial/admin.py:1591-1592`.
- **`changed_data`:** `ModelChoiceField.has_changed` compara o pk inicial com o valor do POST como string. Quando o FK muda, `'terra_indigena_id'` entra em `changed_data`. Quando não muda, não entra, e o P1-D continua valendo.
- **Caminhos que contornariam o `save_model`:** nenhum no admin do Imovel.
  - O `ImovelAdmin` não tem `actions` customizadas, `list_editable` nem `inlines`.
  - O `delete_selected` é escopado por `get_queryset`.
  - Nenhum outro admin tem inline de `Imovel`. Os únicos `inlines` estão em TIs, User e Group, e são de atribuição.
- **Transação:** o `PermissionDenied` sobe de dentro do `transaction.atomic` do `changeform_view`, então tudo volta atrás. O `changeform_view` (`admin.py:1616-1620`) só captura `ValidationError`, logo o resultado é um 403 limpo.

### 2. Origem no `alterar_ti_view`

**Aceitável. Classifico como P2, uma decisão de produto, e não bloqueia.**

O cenário: um staff que só vê o imóvel X (em `tis_b`) por `UserImovel` legado e tem TI inteira em `tis_a` consegue mover X de `tis_b` para `tis_a`. A equipe de `tis_b` perde a visibilidade de X.

Não bloqueio porque:
- Não é regressão: no `develop` isso já era possível, e com destinos mais amplos.
- A concessão legada por imóvel foi explícita e já dava edição (P1-D).
- O `UserImovel` sai em 1 release (D7), e com ele o vetor desaparece.

Para um follow-up (pode ser na v1.2), recomendo exigir `usuario_tem_ti_inteira` também na **origem** ao mover, tanto no `alterar_ti_view` quanto no `save_model` com `eh_mudanca_de_ti`. Mover um imóvel é uma operação estrutural de tenancy, e não faz sentido para quem tem só legado.

### 3. Dropdown

- **`alterar_ti_view`** (`admin.py:1677-1683`): a lista mostra as TIs inteiras do usuário mais a TI atual do imóvel. Todos os destinos que aparecem são permitidos. Se o usuário escolher a TI atual, recebe o aviso "já está associado". Nada confuso aqui.
  - Detalhe: `tis_atribuidas_ids()` devolve `.values('pk')`, e o `.values_list('pk', flat=True)` em cima disso funciona. Pode trazer IDs repetidos por causa dos joins, o que não causa problema.
- **P2 de UX, no changeform de edição** (`admin.py:1567-1568`): na edição, o select ainda usa `tis_for_user`, que inclui TIs só-legadas. Se o usuário escolher uma delas, recebe uma página 403 em vez de um erro no form. A segurança está certa, mas a experiência é ruim. A correção seria usar na edição o mesmo queryset do `alterar_ti_view` (TIs inteiras mais a atual) e/ou validar no `ImovelAdminForm.clean()`.
- **Nit preexistente** (`admin.py:1693`): `nova_ti=abc` gera `ValueError` no `.get(id=...)`, e o resultado é um 500.

### 4. Testes

Os testes vacuous do P1-G foram corrigidos. A criação por UserTI e por superuser agora exige 302 e count+1, e o teste direto do `save_model` com `assertRaises` (`test_save_model_direto_bloqueia_criacao_em_ti_legada`) falharia se o guard fosse removido.

Ficam três P2:
- **`test_changeform_nao_move_imovel_para_ti_so_legado`** (`test_segregacao_usuario.py`, classe `AdminEdicaoImovelEscopoTest`) aceita `(200, 403)`.
  - Pela minha leitura, o POST é válido: o cartório é readonly para não-superuser, `proprietario` não é escopado e o queryset da edição inclui `tis_b`. Então o caminho real é o 403.
  - Aceitar 200 deixa o teste "passar" se o form ficar inválido por outro motivo (por exemplo, um campo novo obrigatório), sem nunca chegar ao guard.
  - Correção: `assertEqual(response.status_code, 403)`.
- **Falta um teste de regressão do P1-D no admin:** staff só-legado edita o imóvel pelo changeform **sem** trocar a TI e recebe 302 com o banco alterado. Hoje nada garante que o guard novo não quebre a edição legítima. Os testes P1-D atuais (linhas 2414-2439) não passam pelo changeform do admin.
- **Falta o caso positivo pelo changeform:** mover para uma TI com UserTI e receber 302. Hoje esse caso só é coberto pelo `alterar_ti`.

### 5. Apto para merge?

**Sim, pendente só da autorização humana.**
- O P1-H está fechado nos dois caminhos do admin (changeform e `alterar_ti_view`).
- O P1-D continua valendo pela lógica do código. Nenhum teste do changeform comprova isso ainda (ver item 4).
- Os P2 listados (origem no mover, select de edição, 403 estrito, teste de regressão do P1-D, nit do 500) podem ir num follow-up.
- As rodadas 1 a 4 já cobriram o resto do `prod-full.diff`.

---

**Próximo passo:** consolidar este verdict com os do kiro-cli e do agy. Se os três aprovarem, pedir a autorização de merge ao luandro. Vale abrir uma issue de follow-up com os P2 dos itens 2 a 4.
OPUS_EXIT=0
