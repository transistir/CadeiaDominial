Vou auditar primeiro os três fixes contra o contrato e os fluxos adjacentes; depois faço uma varredura específica dos services e executo apenas testes pontuais se a leitura deixar alguma dúvida.
[tool] Creating task list: Re-review de segurança do PR #133, confirmando os três ...
[tool] status: Completed

[tool] Reading ROADMAP.md:1, c3-c9-contrato.md:1, p1-fixes.diff:1

[tool] Generating codebase overview

[tool] Searching for 'str\s*\(\s*(e|exc|exception|err|error)\s*\)' in services
[tool] status: Completed
[tool] status: Completed
[tool] status: Completed
O diff confirma os três pontos declarados, mas a varredura ampla encontrou conversões de exceção fora dos três services adicionados ao canário, inclusive um retorno explícito em `hierarquia_service.py`. Agora vou rastrear se esses valores alcançam respostas ao usuário e verificar os guards de todas as rotas de escrita adjacentes antes do verdict.
[tool] Completing #1
[tool] status: Completed
[tool] status: Failed

[tool] Reading lancamento_criacao_service.py:36-305, lancamento_duplicata_service.py:2-361, lancamento_views.py:481-1050, duplicata_views.py:2-187, api_views.py:251-395

[tool] Reading lancamento_origem_service.py:2-126, lancamento_origem_service.py:421-745, lancamento_origem_service.py:1021-1220, managers.py:2-311

[tool] Searching for 'except\s+.*\s+as\s+\w+|str\s*\(|\{\s*(e|exc|erro|error)\s...' in services

[tool] Searching for 'HierarquiaService|LancamentoCriacaoService|ImportacaoCade...' in dominial

[tool] Searching for 'def (novo_|editar_|excluir_|importar_|imovel_form|arquiva...' in views
[tool] status: Completed
[tool] status: Completed
[tool] status: Completed
[tool] status: Completed
[tool] status: Completed
Há um risco novo no P1-A: o service encerra a varredura na primeira origem restrita; como o fix agora ignora esse resultado no criador, uma duplicata acessível em posição posterior pode deixar de abrir a importação. Também vou confirmar o comportamento do endpoint AJAX e, em paralelo, fechar a análise dos retornos crus de `ValidationError`.
[tool] Searching for 'verificar_duplicata_ajax|dados_template|tem_duplicata' in dominial

[tool] Reading lancamento_criacao_service.py:286-465, hierarquia_service.py:121-240, documento_service.py:2-161, cadeia_completa_service.py:481-560, hierarquia_arvore_service.py:371-450, status_cadeia_service.py:101-175

[tool] Searching for 'validar_hierarquia\(|\['erro'\]|\.get\(['\"]erro['\"]|men...' in 

[tool] Finding **/{tis_detail,duplicata_importacao}.html in 

[tool] Reading imovel_views.py:2-126, documento_views.py:2-251, tis_views.py:121-250, lancamento_views.py:411-510

[tool] Searching for 'except\s+[^:\n]+\s+as\s+(e|exc|erro|error)\s*:' in services
[tool] status: Completed
[tool] status: Completed
[tool] status: Completed
[tool] status: Completed
[tool] status: Completed
[tool] status: Completed

[tool] Reading tis_detail.html:2-181, urls.py:2-126, lancamento_criacao_service.py:451-570, lancamento_origem_service.py:741-930

[tool] Searching for 'UserImovel|userimovel|imovel_editar|imovel_form' in tests

[tool] Searching for 'processar_origens_automaticas\(' in dominial

[tool] Reading test_segregacao_usuario.py:2411-2500, duplicata_importacao.html:2-201

[tool] Searching for 'verificar-duplicata|dados_template|verificarDuplicata|tem...' in 

[tool] Reading importacao_cadeia_service.py:2-276, api_views.py:81-205, test_s8_sem_str_e.py:2-241
[tool] status: Completed
[tool] status: Completed
[tool] status: Completed
[tool] status: Completed
[tool] status: Completed
[tool] status: Completed
A leitura fechou dois problemas bloqueantes: (1) origens mistas podem pular uma duplicata acessível posterior; (2) o guard de TI inteira foi aplicado também à edição e quebra o acesso legado por imóvel que o próprio manager ainda declara suportado. Vou validar os caminhos felizes existentes e uma reprodução focada dos dois cenários antes de consolidar o REQUEST-CHANGES.
[tool] Reading signals.py:2-81, lancamento_origem_service.py:126-390, lancamento_campos_service.py:131-280

[tool] Reading test_segregacao_usuario.py:86-315, test_segregacao_usuario.py:3931-4060, test_issue_210_divergencia_cartorio.py:221-340

[tool] Searching for 'imovel_editar|imovel_cadastro|exportar_cadeia_tis_excel' in templates

[tool] Searching for 'raise ValidationError|ValidationError\(' in services
[tool] status: Completed
[tool] status: Completed
[tool] status: Completed
[tool] status: Completed

[tool] Creating test_pr133_rereview.py
[denied] tool permission approval is not supported in non-interactive mode. Use --trust-all-tools to auto-approve.
[tool] status: Failed

[tool] Running: cat > /tmp/test_pr133_rereview.py <<'PY'
from unittest.mock import patch
from django.contrib.messages.storage.fallback import FallbackStorage
from django.core.exceptions import ValidationError
from...
[denied] tool permission approval is not supported in non-interactive mode. Use --trust-all-tools to auto-approve.
[tool] status: Failed

[tool] Running: /root/dev/cadeia-dominial/CadeiaDominial/venv/bin/python manage.py test dominial.tests.test_segregacao_usuario.D1EscritaViaViewTest dominial.tests.test_segregacao_usuario.CriacaoImovelEscopoTITest ...
[denied] tool permission approval is not supported in non-interactive mode. Use --trust-all-tools to auto-approve.
[tool] status: Failed
Os testes não puderam ser executados porque o CLI está em modo não interativo sem autoaprovação de ferramentas; a tentativa focada foi bloqueada antes de iniciar o Django. A evidência estática já é conclusiva, e vou fazer uma última validação independente dos três findings contra as fontes para evitar falso positivo.
[tool] Spawning agent crew
[denied] tool permission approval is not supported in non-interactive mode. Use --trust-all-tools to auto-approve.
[tool] status: Failed

[tool] Completing #2, #3, #4, #5
[tool] status: Completed

[tool] Goal complete
[tool] status: Completed
# Verdict: **REQUEST-CHANGES**

Não encontrei P0. Os quatro vazamentos originalmente apontados em P1-C foram corrigidos, e o caminho simples do P1-A funciona. Porém encontrei **três bloqueadores P1**, dois deles regressões introduzidas pelos fixes.

## P1 — Origem restrita pode ocultar duplicata acessível posterior

**Arquivos:**  
- `dominial/services/lancamento_duplicata_service.py:84-91`  
- `dominial/services/lancamento_criacao_service.py:101-109`

`verificar_duplicata_antes_criacao` retorna imediatamente ao encontrar a primeira duplicata inacessível. O criador agora ignora esse resultado e continua a criação, mas não volta a examinar as demais origens.

Cenário:

1. origem 1: `M2000`, restrita;
2. origem 2: `M3001`, duplicata acessível.

A posição 1 produz `acessivel=False`; o criador segue pelo D1 e a posição 2 nunca abre a tela de importação. Isso permite contornar o fluxo normal de confirmação/importação de uma duplicata acessível mudando a ordem das origens.

O documento cross-TI restrito **não é criado nem importado**: esse aspecto do D1 está correto. O problema é a duplicata acessível posterior ser ignorada.

**Correção:** em `verificar_duplicata_antes_criacao`, guardar que houve origem restrita e continuar o loop. Duplicata acessível deve ter prioridade; retornar `acessivel=False` somente ao final, se nenhuma acessível tiver sido encontrada. Adicionar E2E com origens mistas nas duas ordens.

## P1 — Guard de criação também bloqueia edição legítima

**Arquivos:**  
- `dominial/views/imovel_views.py:19-20`  
- `dominial/managers.py:176-189`  
- `templates/dominial/tis_detail.html:95`

`usuario_tem_ti_inteira` é o guard correto para **criar** imóvel: aceita `UserTI`, equipe parcial/global e superuser, excluindo corretamente `UserImovel`.

Entretanto, o guard foi colocado incondicionalmente no topo de `imovel_form`, antes de distinguir `imovel_id`. Assim, ele também bloqueia a edição de imóvel concedido diretamente por `UserImovel`, embora:

- `Imovel.objects.for_user()` ainda declare e implemente esse acesso legado;
- `tis_for_user()` permite que esse usuário veja a TI;
- `tis_detail.html:95` oferece o link de edição.

O usuário vê seu imóvel, clica em “Editar” e recebe 404. Além disso, o segundo writer, `imovel_detail`, continua aceitando esse mesmo acesso via `for_user`, deixando duas rotas de edição com autorizações diferentes.

**Correção:**

```python
if imovel_id is None and not usuario_tem_ti_inteira(request.user, tis_id):
    raise Http404
```

Na edição, manter o guard existente:

```python
get_object_or_404(
    Imovel.objects.for_user(request.user),
    pk=imovel_id,
    terra_indigena_id=tis,
)
```

Também é recomendável esconder em `tis_detail.html:139` o botão “Cadastrar Novo Imóvel” para quem não possui a TI inteira; hoje o link inevitavelmente termina em 404.

## P1 — S8 ainda não cobre todos os services e há propagação de exceção

**Arquivos:**  
- `dominial/tests/test_s8_sem_str_e.py:41-48`  
- `dominial/services/lancamento_criacao_service.py:253-266`  
- `dominial/services/lancamento_criacao_service.py:460-469`  
- consumidor: `dominial/views/lancamento_views.py:572`

O canário foi ampliado somente para três nomes hardcoded, não para `dominial/services/*.py`. Por isso não detecta que `LancamentoCriacaoService` ainda:

- usa `str(e)` em prints/fallback;
- devolve `e.messages` sem classificação para a view;
- permite que qualquer `ValidationError` levantada por uma dependência entre na mensagem apresentada ao usuário.

Embora o ramo `str(e)` do retorno seja normalmente inalcançável para `django.core.exceptions.ValidationError` — que possui `messages` — uma exceção-isca `ValidationError('SEGREDO-XYZ /opt/app/x.py')` ainda é devolvida por `e.messages` e chega a `messages.error`.

Também permanece `str(e)` em `dominial/services/hierarquia_service.py:153-156`; não encontrei consumidor de produção desse retorno, portanto não o considero vazamento ativo, mas uma varredura realmente global deve detectá-lo.

**Correção:**

1. Enumerar automaticamente todos os `*.py` de `services/`, em vez de manter `services_alvo`.
2. Separar erros de domínio explicitamente seguros de `ValidationError` inesperada.
3. Para `ValidationError` não reconhecida: `logger.exception(...)` e `ERRO_CRIACAO`/`ERRO_ATUALIZACAO`.
4. Adicionar teste com `ValidationError`-isca em criação e edição.

## O que está correto

- Origem restrita isolada segue para D1, grava a `LancamentoOrigem`, não cria/importa `Documento` e emite `MENSAGEM_ORIGEM_RESTRITA`.
- A duplicata acessível isolada continua abrindo `duplicata_importacao.html`.
- `importar_duplicata` recalcula a duplicata, exige `acessivel=True` e revalida todos os IDs.
- `escolher_origem_documento` continua sem oráculo cross-TI.
- A edição de lançamento usa o mesmo D1 e não cria vínculo cross-TI.
- Os quatro pontos alterados em `importacao_cadeia_service`, `lancamento_duplicata_service` e `cartorio_verificacao_service` agora usam mensagens fixas e `logger.exception` nos blocos corretos.
- `novo_documento`, `novo_lancamento` e as rotas de importação resolvem o imóvel com `for_user` e/ou revalidam o documento no service.

Não consegui executar os testes focados: o CLI bloqueou a execução antes de iniciar o Django com `tool permission approval is not supported in non-interactive mode`. Nenhum arquivo do repositório foi alterado.
KIROSOL_EXIT=0
