# Veredito: **REQUEST-CHANGES** (um P1 novo, introduzido pelo fix P1-B; correção de 1 linha)

Os fixes P1-A e P1-C estão corretos. O P1-B fecha a brecha na criação, mas o guard também pega a edição e quebra um fluxo legítimo.

## P1 novo: o guard do P1-B bloqueia a edição para quem tem `UserImovel` legado

**Onde:** `dominial/views/imovel_views.py:19-20`

**Por quê:** o guard `usuario_tem_ti_inteira` roda no topo da view, então vale para as duas rotas:
- `imovel_cadastro`
- `imovel_editar` (`urls.py:31`)

Esse helper ignora `UserImovel` de propósito (`managers.py:204-215`). O efeito é este:

| Passo | O que acontece com o usuário `dono` (só `UserImovel` do imóvel A) |
|---|---|
| `tis_detail` | O imóvel aparece na lista, porque `for_user` inclui `UserImovel` |
| Botão "Editar" (`tis_detail.html:95`) | **404**. No develop isso dava 200 |
| `imovel_detail` (`tis_views.py:164-189`) | Continua aceitando POST com o mesmo `ImovelForm` só com `for_user` |

Então isso não ganha segurança nenhuma, porque a mesma edição continua possível pela outra rota. Só deixa as duas rotas incoerentes e quebra o botão para usuários legados. O D5 trata de operações sobre a TI inteira (XLS, criação), não de editar um imóvel já atribuído. Os 5 testes novos só cobrem a criação, então isso passou sem ser pego.

**Correção:** aplicar o guard só na criação. A edição já fica protegida pelo `for_user` com `terra_indigena_id=tis`.
```python
tis = get_object_or_404(TIs, pk=tis_id)  # (ou manter o guard antes, mas só p/ criação)
if not imovel_id and not usuario_tem_ti_inteira(request.user, tis_id):
    raise Http404
```
Também vale adicionar um teste: `dono` faz GET em `imovel_editar` do imóvel A e recebe 200; faz GET em `imovel_cadastro` da TI A e recebe 404.

**Nit relacionado:** o botão "Cadastrar Novo Imóvel" (`tis_detail.html:139`) aparece para todos, e quem tem só `UserImovel` cai num 404. Seria bom esconder o botão com uma flag `pode_criar_imovel` no contexto de `tis_detail`.

## P1-A: resolvido
- **Sem bypass novo.** Quando `acessivel=False`, o fluxo segue para `processar_origens_automaticas`. Ali o pré-check `_origem_restrita` (`lancamento_origem_service.py:484/723/1174`) pula a origem restrita e emite `OrigemRestritaError`, então não há vínculo com documento de outra TI. O resultado inacessível não carrega id nem objeto (`duplicata_verificacao_service.py:121-128`).
- **A duplicata acessível continua abrindo a tela de importação.** O `else` no `lancamento_criacao_service.py:114` está correto.
- **Outras entradas:**
  - A atualização (editar lançamento) não chama a verificação de duplicata; só a linha 88 chama.
  - `verificar_duplicata_ajax` só devolve a mensagem fixa.
  - Não encontrei outra tela vazia.
- **P2 (nova borda exposta pelo fix, não é regressão):** `lancamento_duplicata_service.py:84-91` retorna na primeira origem com duplicata. Com origens `[inacessível, acessível]`, a duplicata acessível nunca é oferecida para importação. Com a ordem invertida, ela é. O comportamento depende da ordem.
  - **Correção:** guardar o resultado inacessível, continuar o loop, devolver a primeira acessível que aparecer e, no fim, a inacessível.

## P1-C: resolvido
- Os 4 pontos estão corrigidos. Os `logger.exception` estão nos `except` certos e usam formatação `%s` com `estado`, `doc_id` ou `documento_importado_id`, que vão só para o log, não para o usuário.
- As mensagens novas são fixas. As que já existiam interpolam o próprio `usuario_id` ou o id que o cliente pediu, o que não vaza nada.
- Varredura completa de `dominial/services/*.py`:
  - **Nit:** `hierarquia_service.py:156` ainda tem `'erro': str(e)`. Só que `validar_hierarquia` não tem chamador fora dos testes, então não chega ao usuário hoje. Sugiro mensagem fixa mais `logger.exception` por higiene.
  - `lancamento_criacao_service.py:262/466` usa `ValidationError.messages`, que é mensagem de validação feita para o usuário. Está OK.
  - `hierarquia_arvore_service.py:398` é um `print`, vai para o stdout. Está OK.
- **Nit:** `test_s8_sem_str_e.py:183-189` lista só 3 services fixos. Varrer o diretório `services/` inteiro pegaria o `hierarquia_service` e qualquer service novo no futuro.

## Regressões dos diffs
- Os imports estão OK: `Http404` e `usuario_tem_ti_inteira` em `imovel_views`, `logging` e `logger` nos dois services. Não há mudança de assinatura.
- A única regressão é a ordem e o escopo do guard do P1-B, descrita acima.

Não rodei testes; todos os findings vêm da leitura do código. O P1 sai direto das linhas citadas: o guard roda antes do `if imovel_id`, e o helper exclui `UserImovel`.

**Próximo passo:** aplicar o guard só quando `not imovel_id` e adicionar o teste do `dono` (GET em `imovel_editar` dá 200, GET em `imovel_cadastro` dá 404). Com isso eu dou APPROVE-WITH-NITS.
OPUS_EXIT=0
