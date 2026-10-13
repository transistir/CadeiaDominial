# Brief RE-REVIEW rodada 3 — PR #133 (v1.1.0 segregação #132)

Você é revisor sênior de segurança Django. Rodada 1: 3 P1 (A/B/C) → corrigidos.
Rodada 2: você confirmou A/C resolvidos e apontou P1-D (guard P1-B bloqueava
edição legada) + P1-E (duplicata ordem-dependente) + nits. Tudo foi corrigido.
Esta é a rodada FINAL: verdict **APPROVE / APPROVE-WITH-NITS / REQUEST-CHANGES**.

## O que foi feito desde a rodada 2 (commits 4953af61 + 15a48bd1)

**P1-D** — `imovel_views.py`: guard agora `if imovel_id is None and not
usuario_tem_ti_inteira(request.user, tis_id): raise Http404` (só criação;
edição protegida pelo `for_user` existente). Testes novos: `dono` UserImovel
legado → GET imovel_editar 200 / GET imovel_cadastro 404 (classe
CriacaoImovelEscopoTITest, 5 testes do P1-B intactos).

**P1-E** — `lancamento_duplicata_service.py verificar_duplicata_antes_criacao`:
variável `inacessivel` guarda o primeiro resultado acessivel=False e o loop
CONTINUA; duplicata acessível retorna imediato (prioridade); `inacessivel` só
é retornado no fim se nenhuma acessível apareceu. Testes novos em
`dominial/tests/test_p1e_duplicata_ordem.py` (4 cenários com patch sequencial:
2 ordens + só inacessível + sem duplicata).

**P2 higiene** (commit 15a48bd1):
1. `hierarquia_service.py:154-158` — str(e) → 'Erro ao validar hierarquia.' + logger.exception.
2. `lancamento_criacao_service.py:262,466` — fallback morto `else str(e)` → `else 'erro de validação'` (comportamento `e.messages` preservado — validação para o usuário, como você/Opus aprovou).
3. `test_s8_sem_str_e.py` — varredura agora cobre TODOS os `services/*.py` (os.listdir); regra nova: linhas `print(` ignoradas (stdout não é vetor HTTP).
4. `tis_detail` — contexto `pode_criar_imovel` (usuario_tem_ti_inteira) + botão 'Cadastrar Novo Imóvel' envolto em `{% if pode_criar_imovel %}` (coerente com o guard da view; legado não vê botão que daria 404). 2 testes novos.

## FOCO desta rodada

1. P1-D correto? Alguma rota de criação/edição de imóvel que ficou
   inconsistente (imovel_form vs imovel_detail vs admin)? O `imovel_id is None`
   é a condição certa (URL imovel_cadastro não passa imovel_id — confira urls.py:29-31)?
2. P1-E correto? O retorno tardio de `inacessivel` preserva o contrato que o
   consumidor (lancamento_criacao_service.py:101-117) espera? Algum caso
   (multiplas inacessíveis, misto com fim_cadeia, cartório inexistente) que
   mude de comportamento indevidamente?
3. P2: a regra `print(` na varredura abre buraco real (algum lugar que monta
   resposta HTTP com str(e) numa linha que começa com print)? O
   `pode_criar_imovel` no template cobre o botão certo sem esconder outra coisa?
4. Varredura final: restou algum `str(e)`/`{e}` em caminho que chega a resposta
   HTTP (views, admin, services)? (rode o regex `str\((e|exc|erro)\)|\{(e|exc|erro)\}`
   em dominial/ se quiser — comentários e print() são aceitáveis.)
5. Regressão geral dos diffs.

## Material

- Repo: `/root/dev/cadeia-dominial/CadeiaDominial/worktrees/issue-132-integracao`
- **Delta desde a rodada 2** (371 linhas): `.hermes/jev/r3-delta.diff`
- Fixes P1 completos (761 linhas): `.hermes/jev/p1-fixes.diff`
- Produção inteira vs develop (7.7K linhas): `.hermes/jev/prod-full.diff`
- Verdicts anteriores: `.hermes/jev/r2-opus.md`, `.hermes/jev/r2-kirosol.md`
- Contrato: `.hermes/plans/c3-c9-contrato.md`
- Estado develop de um arquivo: `git show b1fcb785:dominial/caminho/arquivo.py`

## Estado verificado (evidência)

segregacao 250/250 · test_s8 6/6 · p1e 4/4 · escopo_global 30/30 ·
144_fase2+origem+157 OK · combinado pós-P2 328 OK · check 0 issues ·
suíte completa pré-P1D/E: 1076 testes, 0 falhas novas vs develop (53 = débito
pré-existente). manage.py test dominial.tests.test_X roda UM módulo se quiser
confirmar algo (Python: venv/bin/python na raiz do repo).

Responda em português. Findings por severidade (P0/P1/P2) com arquivo:linha.
Se APPROVE, diga explicitamente: sem P0/P1 novos, P1-D/E resolvidos.
