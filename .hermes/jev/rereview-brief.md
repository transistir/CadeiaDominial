# Brief de RE-REVIEW (rodada 2) — PR #133 (v1.1.0 segregação #132)

Você é revisor sênior de segurança Django. Na rodada 1 você (ou seu par) deu
REQUEST-CHANGES com 3 P1. Os 3 foram corrigidos em commits novos. Este é o
RE-REVIEW: confirme se os fixes estão corretos E se não introduziram problema
novo. Dê verdict: **APPROVE / APPROVE-WITH-NITS / REQUEST-CHANGES**.

## Os 3 P1 da rodada 1 e o que foi feito

**P1-A (Opus)** — Com `DUPLICATA_VERIFICACAO_ENABLED=True`, origem que só existe
em outra TI devolve `tem_duplicata=True, acessivel=False`; a criação tratava como
duplicata_encontrada e renderizava `duplicata_importacao.html` com
`duplicata_info=None` — tela vazia sem saída, tornando o D1 ("salva sem vincular
+ aviso") inalcançável pela UI.
FIX (commit e96e7144): em `lancamento_criacao_service.py:101-113`, quando
`acessivel=False` NÃO retorna o branch de duplicata — segue o fluxo, onde o
pré-check D1 do C4 (`_origem_restrita`/`OrigemRestritaError`) salva sem vincular
+ `MENSAGEM_ORIGEM_RESTRITA`. Teste E2E novo `D1EscritaViaViewTest`.

**P1-B (Opus + kiro-cli)** — `imovel_form` criava imóvel em TI alheia: na criação
(`imovel_id=None`) a TI era resolvida sem escopo (`get_object_or_404(TIs, pk=…)`),
o guard `for_user` só roda na edição.
FIX (commit ddff6eb7): `imovel_views.py:17-19` — `if not
usuario_tem_ti_inteira(request.user, tis_id): raise Http404` no topo (helper do
C8/D5: exclui UserImovel legado, bypass só superuser/equipe global). 5 testes
novos em `CriacaoImovelEscopoTITest`.

**P1-C (kiro-cli)** — S8 contornável: `str(e)` em dicts de services que chegam ao
usuário (importacao_cadeia:145→messages.error; lancamento_duplicata:184;
cartorio_verificacao:40 e :84→JSON api_views). O canário do C9 varria só views/admin.
FIX (commit bcec3a1b): os 4 pontos → mensagens fixas + `logger.exception`;
varredura do `test_s8_sem_str_e` estendida aos 3 services + 3 testes
comportamentais com exceção-isca (`SEGREDO-XYZ` não pode chegar à resposta).

## O que conferir AGORA (foco do re-review)

1. **P1-A está correto e completo?** O caminho `acessivel=False → D1` realmente
   salva sem vincular + aviso, SEM criar um bypass novo: um usuário ainda NÃO
   pode importar/vincular documento de outra TI por essa rota? A duplicata
   ACESSÍVEL (tem_duplicata=True, acessivel=True) continua abrindo a tela de
   importação normal? Há outra entrada (editar_lancamento, escolher_origem,
   importar_duplicata) onde o mesmo "tela vazia" ou bypass possa ocorrer?
2. **P1-B**: `usuario_tem_ti_inteira` é o guard certo para CRIAÇÃO (produto: quem
   pode criar imóvel numa TI)? O 404 seco não quebra fluxo legítimo (ex.: link em
   `tis_detail.html` para usuário que vê a TI mas não a tem inteira)? A edição
   continua protegida? Alguma outra view de escrita (novo_documento, novo_lancamento,
   importar) resolve TI sem escopo do mesmo jeito?
3. **P1-C**: restou `str(e)`/`str(exc)` em QUALQUER service cujo retorno chega a
   view/JSON/messages? (varra `dominial/services/*.py`). Os `logger.exception`
   estão nos blocos except certos? Alguma mensagem fixa nova vaza dado (ex.:
   interpola estado/id)?
4. **Regressões dos fixes**: algo nos 3 diffs que quebre outro caminho
   (import de Http404/logger, assinatura, ordem de guard antes/depois de
   get_object_or_404, etc.).

## Como navegar

- Repo: `/root/dev/cadeia-dominial/CadeiaDominial/worktrees/issue-132-integracao`
- **Diff só dos 3 fixes** (449 linhas): `.hermes/jev/p1-fixes.diff`
- Diff de produção completo (7.4K linhas): `.hermes/jev/prod-full.diff`
- Contrato: `.hermes/plans/c3-c9-contrato.md`
- Baseline develop pré-merge: `/tmp/wt-baseline-develop/` (se /tmp estiver fora do
  sandbox, use `git show b1fcb785:dominial/…` para o estado develop de um arquivo).

## Estado verificado (evidência)

- segregacao 246/246 · test_s8_sem_str_e 6/6 · escopo_global 30/30 ·
  210_divergencia OK · 157 OK · t27 OK · check 0 issues (run combinado 313 OK).
- Suíte completa (1076) pré-fixes: 0 falhas novas vs develop. Os 30 erros dos
  módulos de duplicata (test_duplicata_verificacao 18 + fase2_duplicata 12) são
  débito PRÉ-EXISTENTE do develop, inalterados.

Não rode a suíte completa (lenta). Leia os diffs + fontes. Se precisar confirmar
um finding, rode UM teste específico. Responda em português. Específico:
arquivo:linha + por que + correção. Se APPROVE, diga explicitamente que não achou
P0/P1 novo e que os 3 P1 estão resolvidos.
