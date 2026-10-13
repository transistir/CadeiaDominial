Vou validar primeiro o delta da rodada 3 e os contratos/rotas afetados; depois farei a varredura de exposição de exceções e executarei testes direcionados antes do veredito.
[tool] Creating task list: Revisão final de segurança do PR #133, com validação ...
[tool] status: Completed

[tool] Reading ROADMAP.md:1-240, r2-kirosol.md:1-240, r2-opus.md:1-240, c3-c9-contrato.md:1-280

[tool] Reading r3-delta.diff:1-500, p1-fixes.diff:1-850

[tool] Searching codebase map
[tool] status: Completed
[tool] status: Completed
[tool] status: Completed
O delta confirma as correções declaradas. Agora estou confrontando-as com o código efetivo: rotas de imóvel, todos os writers adjacentes e o contrato completo da detecção de duplicatas, incluindo entradas especiais e falhas de cartório.
[tool] Completing #1
[tool] status: Completed

[tool] Reading urls.py:2-91, imovel_views.py:2-181, tis_views.py:76-255, managers.py:2-291, admin.py:601-860, tis_detail.html:76-165

[tool] Reading lancamento_duplicata_service.py:2-241, lancamento_criacao_service.py:36-165, duplicata_verificacao_service.py:2-191, lancamento_origem_service.py:391-780

[tool] Searching for 'str\s*\(\s*(e|exc|erro)\s*\)|\{\s*(e|exc|erro)\s*\}' in dominial

[tool] Searching for 'imovel_cadastro|imovel_editar|imovel_detail|ImovelAdmin|I...' in 
[tool] status: Completed
[tool] status: Completed
[tool] status: Completed
[tool] status: Completed
Há um edge case relevante no P1-D: o guard usa `is None`, mas o restante da mesma view ainda usa truthiness (`if imovel_id` / `if not imovel_id`). Como o converter `<int:imovel_id>` aceita `0`, a URL de edição com ID zero pode ser interpretada como criação depois de ultrapassar o guard. Vou reproduzir isso em banco de teste e fechar também a análise do admin e da higiene HTTP.
[tool] Reading admin.py:1471-1670, admin.py:361-440, imovel_forms.py:2-131, forms.py:81-210

[tool] Reading lancamento_views.py:536-635, lancamento_views.py:991-1060, test_s8_sem_str_e.py:2-101, lancamento_criacao_service.py:236-315, lancamento_criacao_service.py:441-505, hierarquia_service.py:136-190, hierarquia_arvore_service.py:381-420

[tool] Searching for 'except\s+[^:\n]+\s+as\s+[A-Za-z_][A-Za-z0-9_]*\s*:' in dominial

[tool] Searching for '^diff --git ' in prod-full.diff
[tool] status: Completed
[tool] status: Completed
[tool] status: Completed
[tool] status: Completed

[tool] Searching for 'add_imovel|has_add_permission|Perfil: Administrador|PERMI...' in dominial

[tool] Reading api_views.py:151-540, cadeia_dominial_views.py:401-540, cadeia_completa_service.py:481-555, status_cadeia_service.py:96-165, documento_service.py:106-175, imovel_documento_service.py:171-280

[tool] Searching for 'Cadastrar Novo Imóvel|imovel/cadastro|imovel_cadastro' in 
[tool] status: Completed
[tool] status: Completed
[tool] status: Completed

[tool] Reading test_segregacao_usuario.py:81-260, test_segregacao_usuario.py:2336-2455, test_segregacao_usuario.py:2526-2620, 0060_seed_perfis.py:2-96
[tool] status: Completed

[tool] Creating test_pr133_review.py
[denied] tool permission approval is not supported in non-interactive mode. Use --trust-all-tools to auto-approve.
[tool] status: Failed

[tool] Running: /root/dev/cadeia-dominial/CadeiaDominial/venv/bin/python manage.py test dominial.tests.test_p1e_duplicata_ordem dominial.tests.test_s8_sem_str_e dominial.tests.test_segregacao_usuario.CriacaoImovel...
[denied] tool permission approval is not supported in non-interactive mode. Use --trust-all-tools to auto-approve.
[tool] status: Failed
A execução local está bloqueada pelo modo não interativo do harness antes de iniciar o Django. A reprodução dinâmica não rodou; vou então confirmar o vetor por evidência estrutural e pela implementação do converter de URL instalada, sem alterar o repositório.
[tool] Finding lib/python*/site-packages/django/urls/converters.py in venv

[tool] Pattern search: if $COND:
    $$$BODY

[tool] Pattern search: def formfield_for_foreignkey($$$ARGS)...

[tool] Reading lancamento_duplicata_service.py:201-380, test_p1e_duplicata_ordem.py:2-161, test_segregacao_usuario.py:2386-2505
[denied] tool permission approval is not supported in non-interactive mode. Use --trust-all-tools to auto-approve.
[tool] status: Failed
[tool] status: Completed
[tool] status: Completed
[tool] status: Completed
[tool] status: Failed

[tool] Reading listing lib
[denied] tool permission approval is not supported in non-interactive mode. Use --trust-all-tools to auto-approve.
[tool] status: Failed
A análise estática fechou dois bypasses de criação no escopo de imóvel: ID `0` na rota pública e criação no admin usando uma TI visível apenas por `UserImovel`. O P1-E, por outro lado, preserva o consumidor e os casos especiais. Vou pedir uma auditoria independente desses pontos antes do veredito.
[tool] Spawning agent crew
[denied] tool permission approval is not supported in non-interactive mode. Use --trust-all-tools to auto-approve.
[tool] status: Failed

[tool] Completing #2, #3, #4
[tool] status: Completed

[tool] Searching the web
[denied] tool permission approval is not supported in non-interactive mode. Use --trust-all-tools to auto-approve.
[tool] status: Failed

[tool] Looking up: usuario_tem_ti_inteira, tis_for_user, ImovelAdmin.formfield_for_foreignkey, ImovelAdmin.save_model, LancamentoDuplicataService.verificar_duplicata_antes_criacao, LancamentoCriacaoService.criar_lancamento_completo
[tool] status: Completed
Validação encerrada: o harness recusou tanto o comando de testes quanto a criação de um teste temporário e a auditoria por subagente (`tool permission approval is not supported in non-interactive mode`). As verificações estáticas, porém, são conclusivas para os dois bypasses; os resultados de suíte fornecidos no brief continuam sendo a única evidência dinâmica disponível.
[tool] Completing #5
[tool] status: Completed

[tool] Completing #6
[tool] status: Completed

[tool] Goal complete
[tool] status: Completed
# Veredito: **REQUEST-CHANGES**

Sem P0. O **P1-E está resolvido**, mas o **P1-D não está completamente resolvido**: restaram dois caminhos de criação sem TI inteira.

## P1 — `imovel_id=0` transforma a rota de edição em criação cross-tenant

**Arquivos:** `dominial/views/imovel_views.py:19-23,87-91`; `dominial/urls.py:31`

O guard usa a condição correta para distinguir criação nominal:

```python
if imovel_id is None and not usuario_tem_ti_inteira(...):
```

Porém o restante da view ainda usa truthiness:

```python
if imovel_id:       # não busca imóvel quando id=0
...
if not imovel_id:   # cria documento e trata como novo imóvel
```

O converter Django `<int:imovel_id>` aceita `0`. Assim, um usuário autenticado pode acessar:

```text
/tis/<TI_ALHEIA>/imovel/0/editar/
```

Com `imovel_id=0`:

1. o guard de criação não roda, pois `0 is None` é falso;
2. o `get_object_or_404(...for_user...)` não roda, pois `bool(0)` é falso;
3. o formulário recebe `instance=None`;
4. um POST válido salva um novo imóvel na TI da URL e cria seu documento principal.

**Correção:** usar semântica explícita em toda a view:

```python
if imovel_id is not None:
    imovel = get_object_or_404(...)

if imovel_id is None:
    # criação do documento principal
```

Adicionar regressão GET e POST para `imovel_editar` com `imovel_id=0`, esperando 404 e nenhuma criação.

## P1 — Admin ainda permite criação com acesso apenas por `UserImovel`

**Arquivos:** `dominial/admin.py:1555-1558`; `dominial/managers.py:135-151,204-215`; `dominial/migrations/0060_seed_perfis.py:27-35,69`

`ImovelAdmin.formfield_for_foreignkey` oferece:

```python
kwargs['queryset'] = tis_for_user(request.user)
```

Mas `tis_for_user` inclui a TI visível por `UserImovel` legado, enquanto `usuario_tem_ti_inteira` explicitamente não considera esse vínculo. O perfil Administrador recebe `add_imovel`, e não há revalidação equivalente no `save_model`.

Consequentemente, um staff com `add_imovel` e somente `UserImovel` pode criar outro imóvel nessa TI pelo admin, embora a rota pública corretamente negue essa criação.

**Correção:** no formulário de **adição**, limitar o queryset às TIs inteiramente atribuídas e revalidar no servidor antes do save. Na edição, preservar `tis_for_user` para não voltar a quebrar o acesso legado. Adicionar teste de POST no admin.

`imovel_detail` está coerente: só edita um imóvel existente resolvido por `Imovel.objects.for_user()`.

## P1-E — Resolvido

**Arquivos:** `dominial/services/lancamento_duplicata_service.py:44-106`; `dominial/services/lancamento_criacao_service.py:101-117`

O novo fluxo está correto:

- guarda a primeira duplicata inacessível;
- continua procurando;
- retorna imediatamente uma duplicata acessível;
- só devolve a inacessível no fim, quando não apareceu nenhuma acessível.

O contrato do consumidor permanece válido: acessível abre importação; inacessível segue para D1, onde as origens são processadas sem vínculo cross-TI.

Também não encontrei regressão em:

- múltiplas inacessíveis: preserva a primeira mensagem genérica;
- mistura com fim de cadeia: essas entradas continuam ignoradas;
- cartório numérico inexistente: continua sendo pulado;
- cartório malformado: a exceção sobe até o catch do consumidor e falha fechado com `ERRO_DUPLICATA`.

## P2 / nits

- `dominial/tests/test_s8_sem_str_e.py:53-56`: ignorar a linha inteira iniciada por `print(` é um pouco amplo — futuramente, `print(str(e)); return JsonResponse(...)` na mesma linha escaparia. **Não existe esse vazamento atualmente**, portanto é apenas nit de robustez.
- A varredura final não encontrou `str(e)`/`{e}` cru chegando a resposta HTTP em views, admin ou services. O match em `lancamento_views.py:590` só classifica internamente a exceção; a resposta continua fixa.
- `pode_criar_imovel` protege o único botão produtivo “Cadastrar Novo Imóvel” e não esconde as ações de edição.

Não consegui executar os testes independentemente: o harness bloqueou o comando antes de iniciar o Django com `tool permission approval is not supported in non-interactive mode`. A análise estática dos dois bypasses é conclusiva; as suítes verdes informadas no brief não cobrem `imovel_id=0` nem criação pelo admin.
KIROSOL_EXIT=0
