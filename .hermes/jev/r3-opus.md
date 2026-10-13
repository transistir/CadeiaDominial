# Verdict rodada 3 — PR #133: **APPROVE-WITH-NITS**

Não encontrei P0 nem P1 novos. P1-D e P1-E estão resolvidos.

Não rodei testes nesta rodada porque a sandbox pediu aprovação para `manage.py test` e eu não insisti. O veredito vem da leitura do código. As contagens de testes citadas abaixo são as do brief, não reproduzidas por mim.

## 1. P1-D: resolvido
- `dominial/urls.py:29`: `imovel_cadastro` não passa `imovel_id`. Já `imovel_editar` (`:31`) passa um `<int:imovel_id>`, que nunca é `None`, e o id 0 continua passando pelo `for_user`. Então `imovel_id is None` é a condição certa.
- `dominial/views/imovel_views.py:19-28`: na edição, quem barra é `get_object_or_404(Imovel.objects.for_user(...), terra_indigena_id=tis)`. Isso impede editar imóvel de outra TI, e a linha `imovel.terra_indigena_id = tis` (`:38`) não consegue mover o imóvel de TI.
- O documento automático (`:86`) só é criado quando `not imovel_id`. O usuário com UserImovel legado não dispara efeitos colaterais de criação ao editar.
- As outras rotas estão coerentes:
  - `imovel_detail` com POST (`tis_views.py:165-189`) só edita e usa `for_user`, igual a `imovel_editar`.
  - `imovel_cadastro` é a única rota de criação. Não há `Imovel.objects.create` em views ou services.
  - O admin é só para staff e não mudou.

## 2. P1-E: resolvido
- `lancamento_duplicata_service.py:86-108`: se aparece uma duplicata acessível, a função retorna na hora, em qualquer ordem. A inacessível só volta no fim, e sempre a primeira encontrada. O formato `{tem_duplicata, acessivel:False, mensagem}` é o mesmo de antes.
- O consumidor (`lancamento_criacao_service.py:101-117`) só lê `tem_duplicata`, `acessivel` e `mensagem`, então o contrato continua igual.
- Casos de borda:
  - **Várias inacessíveis:** volta a primeira, como antes.
  - **Fim de cadeia ou cartório inexistente:** continuam no `continue` de antes, sem mudança.
  - **Misto acessível + inacessível:** abre a tela de importação. Depois dela, a verificação é pulada e a origem inacessível cai no D1 em `processar_origens_automaticas`, como esperado.
- Mudança pequena de comportamento: o loop agora segue depois de achar uma inacessível. Se uma origem posterior lançar exceção, o consumidor devolve `ERRO_DUPLICATA` (`:93-99`), ou seja, falha fechado. Para mim isso é aceitável.

## 3. P2
- **A regra `print(` na varredura:** não abre buraco. Uma linha que começa com `print(` não monta resposta HTTP. Uma chamada `messages.error(`/`JsonResponse(` quebrada em várias linhas, com o `str(e)` numa linha de continuação, continua sendo pega. Não há `print(...); return ...` na mesma linha (fiz grep e veio vazio).
- **`pode_criar_imovel`:** `tis_detail.html:138-142` envolve só o `<div>` do botão. Esse é o único link para `imovel_cadastro` nos templates (conferi com grep), e nada mais ficou escondido.

## 4. Varredura final do regex em `dominial/` (fora de testes e comandos de gerenciamento)

| Local | Situação |
|---|---|
| `services/lancamento_criacao_service.py:254,461` e `hierarquia_arvore_service.py:398` | Linhas `print(`, aceitáveis |
| `views/lancamento_views.py:590` | `'...' in str(e)` só compara texto, não vai para a resposta |
| `models/lancamento_models.py:217`, `forms/imovel_forms.py:89` | `str(erro)` de `ValueError`/`TypeError` vindo de `normalizar_numero_documento`. As mensagens são fixas e de domínio, escritas para o usuário (`documento_identidade_utils.py:23-77`). Não vazam nada |
| `admin.py:62`, `lancamento_criacao_service.py:23,174`, `lancamento_views.py:1024`, `mensagens_erro.py:1` | Comentários ou docstrings |
| `management/commands/*`, `migrations/*` | stdout de CLI, não é HTTP |

Não restou nenhum `str(e)` em caminho que chegue a uma resposta HTTP.

## Nits (P2, nenhum bloqueia)
1. `lancamento_criacao_service.py:254,461`: os `print(f"... {str(e)}")` mandam a mensagem de validação, que pode ter número de documento, para o stdout do worker. Fica para depois: trocar por `logger.debug`, junto com a limpeza geral dos `print("DEBUG…")`.
2. `test_s8_sem_str_e.py`: a varredura agora cobre todos os `services/*.py`. Vale pensar em incluir também `forms/` e `utils/` como blindagem futura. Hoje os dois estão limpos.
3. `test_p1e_duplicata_ordem.py`: falta um caso com duas inacessíveis, para fixar que volta a primeira.
4. `dominial/forms.py` (legado) fica escondido pelo pacote `dominial/forms/`. É código morto que confunde quem faz grep, e não é escopo deste PR.

**Próximo passo:** com o meu APPROVE-WITH-NITS, falta o veredito do kiro-cli/Codex nesta rodada 3. Depois disso, o merge na `develop` precisa da sua autorização explícita.
OPUS_EXIT=0
