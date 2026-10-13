# Veredito: **REQUEST-CHANGES**

O **P1-E está 100% resolvido** e a **higiene P2 está impecável**. No entanto, há um **P1 de segurança cross-tenant em aberto no P1-D** (`imovel_id=0` permite criação arbitrária em TI alheia sem autorização), além de uma inconsistência de escopo na criação via admin.

---

## Findings por severidade

### P1 — Bypass de criação cross-tenant via `imovel_id=0` na rota de edição
- **Arquivo/Linhas:** [`dominial/views/imovel_views.py:19-28, 87-91`](file:///root/dev/cadeia-dominial/CadeiaDominial/worktrees/issue-132-integracao/dominial/views/imovel_views.py#L19-L28) e [`dominial/urls.py:31`](file:///root/dev/cadeia-dominial/CadeiaDominial/worktrees/issue-132-integracao/dominial/urls.py#L31)
- **Causa raiz:** O conversor Django `<int:imovel_id>` na rota `imovel_editar` aceita `0`. Houve uma colisão semântica entre o teste de identidade `is None` no guard e os testes de verdade lógica (`if imovel_id:` / `if not imovel_id:`) no restante da view:
  1. O guard avalia `0 is None and ...` → `False`. Não levanta `Http404`.
  2. `tis = get_object_or_404(TIs, pk=tis_id)` busca a TI globalmente (sem `tis_for_user`).
  3. `imovel = None`. A linha 23 faz `if imovel_id:` (`if 0:`), que é **falso** em Python. Logo, o `get_object_or_404(Imovel.objects.for_user(...))` **não é executado**!
  4. O formulário é instanciado com `instance=None` (`imovel` permaneceu `None`).
  5. No POST, o formulário valida e trata como **criação de novo imóvel**.
  6. A linha 87 avalia `if not imovel_id:` (`if not 0:`), que é **verdadeiro**, criando automaticamente o documento de matrícula principal.
  7. O imóvel é salvo na TI da URL e o endpoint redireciona com 302 (`'Imóvel cadastrado com sucesso!'`).
- **Evidência comprovada (executada no ambiente de teste):**
  Um usuário comum (`attacker_0`) sem nenhuma atribuição à `TI 999` disparou `POST /tis/999/imovel/0/editar/`.
  **Resultado:** HTTP 302, criação efetiva de 1 imóvel e 1 documento de matrícula vinculados à `TI 999`.
- **Correção recomendada:**
  Inverter e tornar a verificação estrita em [`imovel_views.py`](file:///root/dev/cadeia-dominial/CadeiaDominial/worktrees/issue-132-integracao/dominial/views/imovel_views.py):
  ```python
  tis = get_object_or_404(TIs, pk=tis_id)
  imovel = None
  if imovel_id is not None:
      imovel = get_object_or_404(
          Imovel.objects.for_user(request.user),
          pk=imovel_id,
          terra_indigena_id=tis,
      )
  elif not usuario_tem_ti_inteira(request.user, tis_id):
      raise Http404
  ```
  E nas linhas 87 e 91, substituir `if not imovel_id:` por `if imovel_id is None:`.
  *(Com isso, `imovel_id=0` cai no `if imovel_id is not None`, tenta buscar `pk=0` via `for_user` e retorna 404 imediatamente).*

---

### P1 (Autorização) — Admin `ImovelAdmin` permite criação de imóvel com escopo restrito a `UserImovel`
- **Arquivo/Linhas:** [`dominial/admin.py:1555-1558`](file:///root/dev/cadeia-dominial/CadeiaDominial/worktrees/issue-132-integracao/dominial/admin.py#L1555-L1558)
- **Causa raiz:** `ImovelAdmin.formfield_for_foreignkey` define:
  ```python
  if db_field.name == 'terra_indigena_id':
      kwargs['queryset'] = tis_for_user(request.user)
  ```
  `tis_for_user` inclui TIs visíveis exclusivamente por `UserImovel` legado ([`dominial/managers.py:148-151`](file:///root/dev/cadeia-dominial/CadeiaDominial/worktrees/issue-132-integracao/dominial/managers.py#L148-L151)), enquanto `usuario_tem_ti_inteira` as rejeita. Um staff comum que tenha a permissão `add_imovel` (concedida a `Perfil: Administrador`) e possua apenas `UserImovel` consegue acessar `/admin/dominial/imovel/add/` e cadastrar novos imóveis naquela TI via admin, burlando a regra D5 de criação por TI inteira.
- **Correção recomendada:** No formulário de **adição** do admin (quando `request.resolver_match.url_name.endswith('_add')` ou sem `obj`), limitar o queryset do campo `terra_indigena_id` às TIs atribuídas integralmente (`usuario_tem_ti_inteira`), ou validar em `save_model` se `not change and not usuario_tem_ti_inteira(request.user, obj.terra_indigena_id_id)`.

---

## Análise detalhada dos 5 pontos do foco

### 1. P1-D: Inconsistência e o edge-case `imovel_id=0`
- O `imovel_id is None` diferencia corretamente a rota de criação nominal `imovel_cadastro` (onde `imovel_id` não é passado na URL, logo é `None`).
- Contudo, como demonstrado no finding **P1** acima, a URL de edição `imovel_editar` aceita `imovel_id=0`. Devido à assimetria entre `is None` e `if imovel_id:`, a requisição com `0` fura o guard de criação e não executa a busca no banco, caindo silenciosamente no fluxo de criação com `instance=None`.
- `imovel_detail` está consistente (sempre requer `imovel_id` e filtra via `Imovel.objects.for_user`).

### 2. P1-E: Resolvido e robusto
- O loop em [`dominial/services/lancamento_duplicata_service.py:47-109`](file:///root/dev/cadeia-dominial/CadeiaDominial/worktrees/issue-132-integracao/dominial/services/lancamento_duplicata_service.py#L47-L109) funciona perfeitamente:
  - Inicializa `inacessivel = None`.
  - Ao encontrar duplicata inacessível, armazena a primeira ocorrência em `inacessivel` e continua (`continue`).
  - Ao encontrar duplicata acessível, retorna **imediatamente**, garantindo prioridade absoluta independente da ordem das origens no POST.
  - Ao final do loop, se nenhuma acessível apareceu, retorna `inacessivel`.
- **Contrato preservado:** O consumidor [`lancamento_criacao_service.py:101-114`](file:///root/dev/cadeia-dominial/CadeiaDominial/worktrees/issue-132-integracao/dominial/services/lancamento_criacao_service.py#L101-L114) recebe a tupla `{tem_duplicata, acessivel, mensagem}` esperada. Quando `acessivel=False`, segue o caminho D1 sem exibir modal vazio e sem criar vínculos indevidos.
- **Casos de borda:**
  - *Múltiplas inacessíveis:* Preserva a primeira ocorrência com mensagem genérica opaca.
  - *Fim de cadeia e cartório inexistente:* Permanecem com `continue`, sem interferência.
  - *Origem malformada:* Sobe exceção para o catch fechado com `ERRO_DUPLICATA`.
- Os 4 testes em [`dominial/tests/test_p1e_duplicata_ordem.py`](file:///root/dev/cadeia-dominial/CadeiaDominial/worktrees/issue-132-integracao/dominial/tests/test_p1e_duplicata_ordem.py) cobrem as permutações e executaram com sucesso (`Ran 4 tests ... OK`).

### 3. P2: Regra `print(` e template `tis_detail.html`
- **Regra `print(`:** A varredura de todas as ocorrências em `services/`, `views/` e `admin.py` confirmou que nenhum comando `print(` monta resposta HTTP ou atribui retorno. O filtro em [`test_s8_sem_str_e.py:55-56`](file:///root/dev/cadeia-dominial/CadeiaDominial/worktrees/issue-132-integracao/dominial/tests/test_s8_sem_str_e.py#L55-L56) é seguro.
- **Template:** A flag `pode_criar_imovel` em [`templates/dominial/tis_detail.html:138-142`](file:///root/dev/cadeia-dominial/CadeiaDominial/worktrees/issue-132-integracao/templates/dominial/tis_detail.html#L138-L142) encapsula exclusivamente o `<div>` com o botão de cadastro de imóvel, alinhando a interface com a autorização da view e sem esconder listas, paginações ou outros botões.

### 4. Varredura final de `str(e)` / `{e}` em caminhos HTTP
- Foi realizada varredura completa por regex em `views/`, `services/` e `admin.py`:
  - `hierarquia_service.py:161`: Corrigido para `'Erro ao validar hierarquia.'`.
  - `lancamento_criacao_service.py:262, 466`: Fallbacks corrigidos para `'erro de validação'`.
  - `lancamento_views.py:590`: Apenas comparação booleana (`'...' in str(e)`), o texto não é enviado na resposta HTTP.
  - `admin.py:1597`, `imovel_views.py:104, 114`, `tis_views.py:179`: Usam exclusivamente mensagens limpas do Django (`e.messages` de `ValidationError` e `form.errors`).
- **Nenhum vazamento de `str(e)`/`{e}` alcança respostas HTTP.**

### 5. Regressão geral dos diffs
- O delta da rodada 3 é coeso e bem testado. A única falha estrutural remanescente é o edge case `imovel_id=0` decorrente de `if imovel_id:` em [`imovel_views.py`](file:///root/dev/cadeia-dominial/CadeiaDominial/worktrees/issue-132-integracao/dominial/views/imovel_views.py).

---

## Próximo passo concreto

Ajustar [`dominial/views/imovel_views.py`](file:///root/dev/cadeia-dominial/CadeiaDominial/worktrees/issue-132-integracao/dominial/views/imovel_views.py) para tratar `imovel_id is not None` de forma explícita na busca de instância (garantindo 404 para `imovel_id=0`) e adicionar teste de regressão (GET e POST com `imovel_id=0` esperando 404). Com esse ajuste, o PR estará pronto para aprovação unânime.
AGY_EXIT=0
