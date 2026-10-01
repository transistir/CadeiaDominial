# Contrato executável C3–C9 (+ pré-requisitos C2a/C2b) — #132 integração v1.1.0

- Branch `feat/issue-132-integracao-v110` · HEAD `b4163140` (C2) · merge C1 `6306fcca` · develop `b1fcb785` · PR head `9c95b117`
- Autor: revisor sênior (Opus 5.5), 2026-10-01 · Executor: júnior em TDD
- Linhas citadas = código no HEAD `b4163140`. Se a linha não bater, ache pelo nome da função — não chute.

## 0. Regras para quem executa

1. Faça na ordem da seção 5. Para cada commit: teste novo primeiro (mostre o RED), depois implemente (GREEN). Cole a evidência no corpo do commit.
2. Rode os testes do worktree: `/root/dev/cadeia-dominial/CadeiaDominial/venv/bin/python manage.py test dominial.tests.<modulo>` (o rótulo é `dominial.tests`, nunca `dominial`).
3. Proibido: usar superuser para um teste passar (só vale quando o assunto do teste é o superuser: D4 e o bypass); afrouxar guard; usar `ESCOPO_GLOBAL` em produção fora da allowlist do T11; usar `Imovel.objects.*` sem `for_user` ou `Documento.objects.*` sem `imovel=` em `views/*.py`/`admin.py` (é o canário `ManagerOptInRegressaoTest`).
4. "NÃO VERIFICADO — parar e perguntar" quer dizer: pare, reporte ao orquestrador e espere. Não decida sozinho.
5. Hook de pre-commit vermelho só por módulos da Fase 4 (seção 7): pare e pergunte se repete o procedimento do C2. Não use `--no-verify` por conta própria.
6. Comparar suítes: `... manage.py test dominial.tests 2>&1 | grep -E '^(ERROR|FAIL):' | sort > /caminho/no/worktree/x.txt`. Só falha NOVA importa.

## 1. Estado verificado nesta sessão (evidência rodada)

| Medição | Resultado |
|---|---|
| `test_escopo_global` | 29/29 OK |
| Suíte completa `dominial.tests` no HEAD | Ran 1027 · failures=122 · errors=113 · skipped=1 |
| Baseline develop puro (`/tmp/baseline-develop-full.log`) | Ran 794 · failures=4 · errors=55 (59 nomes, listados na seção 7.4) |
| `test_issue_179` + `test_issue_204` | 14 F + 9 E (XLS por TI quebrado, ver A3) |
| `test_segregacao_usuario` | 194/195 (falha só o canário `ManagerOptInRegressaoTest`) |

O log `/tmp/c2-suite-full2.log` (122 F/199 E) é anterior ao HEAD atual. Use os números acima.

## 2. Achados novos que mudam o plano (leia antes de tudo)

- **A1 — CRÍTICO, erro do merge C1.** `dominial/services/lancamento_criacao_service.py:176-177` chama `LancamentoOrigemService.processar_cartorio_origem(lancamento, request.POST)`. Esse método não existe em `LancamentoOrigemService`. Só existe `LancamentoService.processar_cartorio_origem(request, tipo_lanc, lancamento)` (`lancamento_service.py:115`), com outra assinatura. Nem o develop nem o PR têm essa chamada; os dois têm só o comentário `# Cartório de origem processado no service consolidado`. Efeito: **toda criação de lançamento** levanta AttributeError dentro do atomic e devolve `ERRO_CRIACAO`. Evidência: traceback `AttributeError: type object 'LancamentoOrigemService' has no attribute 'processar_cartorio_origem'` em `test_issue_241`/`test_issue_144_fase2`. Hoje outras falhas de fixture escondem o erro. Correção: commit **C2a**.
- **A2 — Lacuna do C2.** `hierarquia_arvore_service.py` **não** está no diff do `b4163140`, embora a mensagem do commit diga que está. O arquivo ainda faz `None → Documento.objects.all()` em :40-41, :79-80 e :108-109. Além disso, `_resolver_documento_por_codigo(..., documentos_queryset=None)` (:218-245) cai em `DocumentoIdentidadeService.resolver(queryset=None)`, que usa `Documento.objects`, ou seja, escopo global (`documento_identidade_service.py:44-45`). Os 4 testes T11 de árvore (`test_escopo_global.py:121-153`) passam **por acidente**: o TypeError vem do Mock (`Field 'id' expected a number…` / `'Mock' object is not iterable`), não do endurecimento. Hoje a produção passa escopo em todos os call sites (`cadeia_dominial_views.py:107-111`, `lancamento_views.py:123-126`, `hierarquia_service.py:176-184`, `cadeia_completa_service.py:102-105,449-452`, `status_cadeia_service.py:118-121`). Então é dívida de contrato, não vazamento ativo. Mas o C3 mexe nesse arquivo. Correção: commit **C2b**.
- **A3 — O XLS por TI está quebrado, além de inseguro.** `cadeia_dominial_views.py:652` chama `CadeiaCompletaService()` sem escopo. O TypeError do C2 é engolido aba a aba (:661), e toda aba vira "Erro ao exportar este imóvel.". Junta-se ao S1: a TI está sem escopo (:568) e há `Imovel.objects.filter` (:575), que é o canário.
- **A4 — Http404 dentro de `try/except Exception`.** Em `exportar_cadeia_dominial_excel_tis`, o `get_object_or_404` (:568) fica dentro do `try` (:567). Uma TI inexistente vira 500 com `str(e)` (:692-702). O guard do C8 tem de ficar **fora** do `try`.
- **A5 — Precedente para reaproveitar.** `duplicata_verificacao_service.py:114-129` (`conflito_global`) já faz "existe fora do escopo → só booleano + mensagem fixa". C3, C4 e C6 seguem o mesmo padrão, por meio de um helper único (seção 3).
- **A6 — Como a escrita cross-TI se comporta hoje.**
  - (a) Lançamento comum: `_validar_origem_existente` (`hierarquia_utils.py:514-603`) devolve False e o usuário não recebe nenhuma mensagem.
  - (b) `inicio_matricula`: a mesma função devolve True (:563-579). Aí `_criar_documento_origem` (`lancamento_origem_service.py:1079-1137`) tenta criar o documento e bate no `IntegrityError` da `unique_documento_identidade_canonica`, que é **global** (`documento_models.py:100-103`). O erro é engolido em :485-488/:700-705 e sai a mensagem enganosa "verifique os avisos na árvore". É o "IntegrityError anônimo" do D1.
- **A7 — `escolher_origem_documento` já está correto e não deve mudar.** `api_views.py:282-286` responde 400 genérico para origem fora do escopo. **Não** troque por uma mensagem "outra TI": viraria oráculo de doc_id (dá para enumerar `documento:<id>`). O C4 só acrescenta o teste de regressão.

## 3. Peças compartilhadas (cada uma nasce no commit indicado)

### 3.1 Constantes — `dominial/utils/segregacao_utils.py`, depois da linha 17

```python
# D1 (#132): origem que aponta para documento de TI não atribuída.            [C3]
MENSAGEM_ORIGEM_RESTRITA = 'Origem em outra TI — sem acesso / solicite ao admin'
# D3 (#132, S2): a matrícula consultada existe, mas fora do escopo.          [C6]
MENSAGEM_DOCUMENTO_OUTRA_TI = 'Documento existe em outra TI — solicite acesso ao administrador.'
# D4 (#132, S7/#210)                                                         [C7]
MENSAGEM_CARTORIO_SO_SUPERUSER = 'Somente o superusuário pode alterar o cartório de um imóvel.'
# D5 (#132, S1/#179)                                                         [C8]
MENSAGEM_TI_SEM_ACESSO = 'Terra Indígena não encontrada ou não atribuída ao seu usuário.'
```

### 3.2 Helper de existência — `dominial/managers.py`, no fim do arquivo (depois da :257) [C3]

```python
def identidade_existe_fora_do_escopo(documentos_queryset, *, tipo, numero_normalizado, cartorio_id):
    """D1/D3 (#132): True se a identidade registral (tipo, número normalizado,
    cartório) existe no banco mas NÃO dentro de ``documentos_queryset``.

    Devolve só booleano — nunca objeto, id, número, imóvel ou TI. Única
    consulta global permitida para distinguir "origem restrita" de "origem
    inexistente" (mesmo padrão de ``conflito_global`` em
    ``DuplicataVerificacaoService.verificar_duplicata_origem``).
    """
    from .models import Documento

    escopo = documentos_no_escopo(documentos_queryset)  # None → TypeError (C2)
    if not (tipo and numero_normalizado and cartorio_id):
        return False
    filtro = {
        'tipo__tipo': tipo,
        'numero_normalizado': numero_normalizado,
        'cartorio_id': cartorio_id,
    }
    if escopo.filter(**filtro).exists():
        return False
    return Documento.objects.filter(**filtro).exists()
```

Com `ESCOPO_GLOBAL` ou com superuser, o resultado é sempre False. `managers.py` já está na allowlist do T11.

### 3.3 Helper de fixture — novo `dominial/tests/segregacao_fixtures.py` [C2a]

O nome do arquivo não começa com `test_`, então o discovery não o executa.

```python
"""Fixtures de segregação para testes (#132): acesso por UserTI a um usuário
COMUM — nunca superuser, nunca afrouxando guard de produção."""
from django.contrib.auth.models import User

from dominial.models import UserTI


def atribuir_tis(user, *tis, atribuido_por=None):
    for ti in tis:
        UserTI.objects.get_or_create(user=user, tis=ti, defaults={'atribuido_por': atribuido_por})
    return user


def usuario_com_tis(username, *tis, password='senha-teste', atribuido_por=None):
    user = User.objects.create_user(username=username, password=password)
    return atribuir_tis(user, *tis, atribuido_por=atribuido_por)
```

Antes de usar, leia `acesso_models.py:23-27`. Se `atribuido_por` for NOT NULL, `atribuido_por` vira obrigatório no helper e os chamadores passam um superuser **atribuidor**. Esse superuser não é o usuário logado no teste.

### 3.4 Cenário de teste D1–D5 — `test_segregacao_usuario.py`, nova base depois da :205 [C3]

```python
class OrigemOutraTIBaseTestCase(SegregacaoFase2BaseTestCase):
    """Imóvel C1 (TI C) com um lançamento que cita M3001 (C2, mesma TI) e
    M2000 (documento_b, TI B — fora do escopo de `via_ti`)."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.lanc_c1_origens = Lancamento.objects.create(
            documento=cls.documento_c1, tipo=cls.lanc_tipo,
            numero_lancamento='R1M3000', data=date(2024, 3, 1),
            origem='M3001; M2000', cartorio_origem=cls.cartorio,
        )
        for indice, numero in enumerate(('M3001', 'M2000')):
            LancamentoOrigem.objects.create(
                lancamento=cls.lanc_c1_origens, indice_origem=indice,
                tipo_documento='matricula', numero=numero,
                cartorio=cls.cartorio, livro='', folha='',
            )
        cls.lanc_c2 = Lancamento.objects.create(
            documento=cls.documento_c2, tipo=cls.lanc_tipo,
            numero_lancamento='R1M3001', data=date(2024, 3, 1),
        )
```

`documento_b`, `lancamento_b` (`R1M2000`), `via_ti` (TIs C e Vazia), `via_equipe`, `membro_global`, `sem_nada`, `dono` (UserImovel do imóvel A) e `superuser` já existem (`test_segregacao_usuario.py:91-205`). Importe `LancamentoOrigem` de `dominial.models`.

## 4. Commits

### C2a — hotfix do merge (A1)

- **Mudança**: em `lancamento_criacao_service.py:175-177`, apague a linha 177 e deixe o mesmo texto do develop:
  ```python
                  # Processar cartório de origem
                  print("DEBUG: Processando cartório de origem...")
                  # Cartório de origem processado no service consolidado
  ```
- **Fixture**: crie `segregacao_fixtures.py` (3.3). Em `test_issue_241_criacao_lancamento_atomica.py`, todo request do `RequestFactory` recebe `request.user = usuario_com_tis('t241', <TI do fixture>)`. Hoje dá `AttributeError: 'WSGIRequest' object has no attribute 'user'` (`lancamento_criacao_service.py:52`).
- **RED → GREEN**: com a fixture corrigida, T2 (`test_t2_criacao_com_cartorio_valido_persiste_tudo`) fica RED com ERRO_CRIACAO. Depois de apagar a linha, fica GREEN.
- **Verde**: `test_issue_241` 4/4 · `test_escopo_global` 29/29 · `test_segregacao_usuario` 194/195.
- **Commit**: `fix(#132): C2a — remove chamada inexistente introduzida no merge C1 (criação de lançamento)`

### C2b — endurecer `hierarquia_arvore_service` (A2) + T11 que detecta de verdade

- **Produção**: importe `from ..managers import documentos_no_escopo` em `hierarquia_arvore_service.py`. Na primeira linha útil de cada função abaixo, troque o fallback `if documentos_queryset is None: ... = Documento.objects.all()` por `documentos_queryset = documentos_no_escopo(documentos_queryset)`. As assinaturas continuam iguais (compatibilidade posicional):
  - `construir_arvore_cadeia_dominial` (:40-41) · `_identificar_documento_principal` (:79-80) · `_construir_arvore_a_partir_documento` (:108-109)
  - `_resolver_documento_por_codigo` (:218): coloque a normalização **antes** do `if not cartorio`
  - `_resolver_origem` (:248) · `_buscar_documentos_pais` (:281) · `_buscar_documentos_pais_e_pendencias` (:291)
- **T11** (`test_escopo_global.py`): em `FuncoesEndurecidasTest`, crie `REGEX_ESCOPO = r'Escopo de documentos|documentos_queryset|keyword-only argument|positional argument'`. Troque **todos** os `assertRaises(TypeError)` por `assertRaisesRegex(TypeError, self.REGEX_ESCOPO)`.
  - RED esperado: os 4 testes de árvore (:121-153).
  - Se **outro** teste T11 ficar RED, é mais uma lacuna do C2: parar e perguntar, com a lista e a mensagem de cada um.
- **Adaptar testes** (mesma política do C2: `documentos_queryset=ESCOPO_GLOBAL`, importado de `dominial.managers`, só onde o teste não é sobre segregação). Chamadas sem escopo, achadas por grep:
  - `test_divida_cartorio_arbitrario_arvore.py:64` · `test_exportacao_cadeia.py:475` · `test_fim_cadeia_destacamento_select.py:358` · `test_hierarquia_arvore_cartorio_origem.py:79,86`
  - `test_hierarquia_arvore_fim_cadeia.py:72,78,88,125,131,144,158,170,179,186,196,215,230`
  - `test_identidade_documento.py:1211` · `test_issue_144_origem_cartorio.py:146,241,294,311,318,340,354`
  - `test_issue_230_documento_automatico_tipo.py:347,387` · `test_lancamento_origem_leitura_service.py:143` · `test_t27_regressao_cartorio_duplicata.py:105`
  - Chamadas em várias linhas: confira se o kwarg já existe. Depois rode os módulos; qualquer `TypeError: Escopo de documentos inválido` é uma chamada que escapou.
- **Verde**: `test_escopo_global` 29/29 com o regex. Os módulos acima não têm falha nova contra o HEAD (compare as listas ordenadas). `test_segregacao_usuario` 194/195.
- **Commit**: `fix(#132): C2b — hierarquia_arvore_service exige escopo (lacuna do C2) + T11 não-vacuoso`

### C3 — D1 na LEITURA: origem restrita sem dados

**Formato do marcador.**

| Superfície | Marcador |
|---|---|
| Tabela (item da cadeia) | 2 chaves novas: `'origens_restritas': int` (contagem de identidades distintas) e `'mensagem_origem_restrita': str` (`MENSAGEM_ORIGEM_RESTRITA` se >0, senão `''`) |
| Árvore (pendência) | `{'numero': '', 'tipo_documento': '', 'cartorio_nome': '', 'status': 'restrito', 'candidatos': [], 'mensagem': MENSAGEM_ORIGEM_RESTRITA}` |

- O marcador nunca leva doc_id, `documento:<id>`, número, cartório, imóvel ou TI.
- Origem restrita **não vira botão**: `origens_disponiveis` continua só com as resolvidas.
- O texto de origem do próprio lançamento (`formatar_origem_completa`, `formatacao_utils.py:134+`) é dado do usuário e continua igual. Esse texto lê só as `LancamentoOrigem` do lançamento e não resolve o documento alvo (`formatacao_utils.py:86-114`).

**Produção**

1. Crie as peças 3.1 (`MENSAGEM_ORIGEM_RESTRITA`) e 3.2.
2. `hierarquia_utils.py`: função nova logo depois de `obter_origens_resolvidas` (:159).
   ```python
   def contar_origens_restritas(documento, lancamentos=None, *, documentos_queryset):
       """D1 (#132): quantas origens distintas do documento apontam para um
       documento que existe, mas fora de ``documentos_queryset`` (outra TI).
       Só a contagem sai daqui. Inexistente, ambígua no escopo ou sem cartório
       não conta."""
       from ..managers import documentos_no_escopo, identidade_existe_fora_do_escopo

       documentos_queryset = documentos_no_escopo(documentos_queryset)
       if lancamentos is None:
           lancamentos = documento.lancamentos.all()
       vistas, restritas = set(), 0
       for lancamento in sorted(lancamentos, key=lambda lancamento: lancamento.pk):
           for origem in _obter_origens_lancamento(lancamento):
               tipo = _tipo_do_codigo(origem.codigo)
               if not origem.cartorio_id or not tipo:
                   continue
               try:
                   identidade = DocumentoIdentidade(tipo, origem.codigo, origem.cartorio_id)
               except (TypeError, ValueError):
                   continue
               chave = (identidade.tipo, identidade.numero_normalizado, identidade.cartorio_id)
               if chave in vistas:
                   continue
               vistas.add(chave)
               if identidade_existe_fora_do_escopo(
                   documentos_queryset, tipo=identidade.tipo,
                   numero_normalizado=identidade.numero_normalizado,
                   cartorio_id=identidade.cartorio_id,
               ):
                   restritas += 1
       return restritas
   ```
3. `cadeia_dominial_tabela_service.py`: importe `contar_origens_restritas` (no bloco das :14-18) e `MENSAGEM_ORIGEM_RESTRITA`. Método novo:
   ```python
   def _origens_restritas(self, documento, lancamentos):
       """D1 (#132): (contagem, mensagem) das origens em outra TI, sem dados delas."""
       quantidade = contar_origens_restritas(
           documento, lancamentos, documentos_queryset=self.documentos_queryset
       )
       return quantidade, (MENSAGEM_ORIGEM_RESTRITA if quantidade else '')
   ```
   Chame-o nos dois laços, `get_cadeia_dominial_tabela` (dict :198-205) e `obter_cadeia_tabela` (dict :367-374), e acrescente as 2 chaves ao dict.
4. `api_views.py` `get_cadeia_dominial_atualizada`: em `item_serializado` (:470-479), acrescente `'origens_restritas': item.get('origens_restritas', 0)` e `'mensagem_origem_restrita': item.get('mensagem_origem_restrita', '')`.
5. `templates/dominial/cadeia_dominial_tabela.html`: depois da :301 (o `{% endif %}` do `tem_multiplas_origens`, ou seja, fora dele):
   ```django
   {% if item.origens_restritas %}
       <div class="origem-restrita" data-origens-restritas="{{ item.origens_restritas }}">🔒 {{ item.mensagem_origem_restrita }}</div>
   {% endif %}
   ```
6. `static/dominial/js/cadeia_dominial_tabela.js`: depois da :355 (fim do `if (item.tem_multiplas_origens…)`):
   ```js
   // D1 (#132): origem em TI não atribuída — só o aviso, sem dados dela.
   if (item.origens_restritas) {
       lancamentosHtml += `<div class="origem-restrita" data-origens-restritas="${item.origens_restritas}">🔒 ${item.mensagem_origem_restrita}</div>`;
   }
   ```
7. `hierarquia_arvore_service.py` `_resolver_origem` (:247-278): logo antes do `return None, pendencia` final, cole o trecho abaixo. Importe `identidade_existe_fora_do_escopo` de `..managers` e `MENSAGEM_ORIGEM_RESTRITA` de `..utils.segregacao_utils`.
   ```python
   if resultado.status == 'nao_encontrado' and identidade_existe_fora_do_escopo(
       documentos_queryset, tipo=identidade.tipo,
       numero_normalizado=identidade.numero_normalizado, cartorio_id=identidade.cartorio_id,
   ):
       # D1 (#132): nada da outra TI — nem número, cartório, candidatos ou id.
       return None, {'numero': '', 'tipo_documento': '', 'cartorio_nome': '',
                     'status': 'restrito', 'candidatos': [],
                     'mensagem': MENSAGEM_ORIGEM_RESTRITA}
   ```
   O guard de criação automática (:321-326) só cria quando o status é `'nao_encontrado'`. Então uma origem `'restrito'` **nunca** cria documento. Não mexa no guard; só acrescente um comentário dizendo isso.
8. `static/dominial/js/cadeia_dominial_d3/card_overlays.js:170`: primeira linha do `map`:
   `if (o.status === "restrito") { return \`• ${o.mensagem}\`; }`.

**Testes T-D1-leitura**: crie a classe `OrigemRestritaLeituraTest(OrigemOutraTIBaseTestCase)` em `test_segregacao_usuario.py`, mais 1 teste em `test_escopo_global.py`.

1. `test_helper_identidade_fora_do_escopo`: com `documentos_for_user(via_ti)`:
   - M2000/cartório → True
   - M3001 → False
   - M9999 → False
   - com `ESCOPO_GLOBAL` → False
   - `documentos_queryset=None` → TypeError
2. `test_tabela_marca_origem_restrita_sem_dados`: `CadeiaDominialTabelaService(user=via_ti).obter_cadeia_tabela(imovel_c1)`, item do `documento_c1`:
   - `origens_restritas == 1` e `mensagem_origem_restrita == MENSAGEM_ORIGEM_RESTRITA`
   - `[o['numero'] for o in origens_disponiveis] == ['M3001']`
   - `json.dumps` das chaves `origens_disponiveis`, `origens_restritas`, `mensagem_origem_restrita` e `escolha_atual` não contém `f'documento:{documento_b.pk}'` nem `'M2000'`
3. `test_tabela_superuser_sem_restrita`: com o superuser, `origens_restritas == 0` e `'M2000'` aparece nos números de `origens_disponiveis`.
4. `test_origem_inexistente_nao_conta`: acrescente outro lançamento em `documento_c1` com uma `LancamentoOrigem` M9999/cartório. A contagem continua 1.
5. `test_view_tabela_mostra_aviso_e_nao_vaza`: `force_login(via_ti)` e GET `reverse('cadeia_dominial_tabela', args=[tis_c.id, imovel_c1.id])`. Espera:
   - status 200 e `assertContains(MENSAGEM_ORIGEM_RESTRITA)`
   - `assertNotContains` de `'Imóvel B'`, `'TI Beta'`, `f'documento:{documento_b.pk}'` e `'R1M2000'`
6. `test_api_atualizada_serializa_restrita`: GET `reverse('get_cadeia_dominial_atualizada', args=[tis_c.id, imovel_c1.id])`. O item do C1 tem as 2 chaves, e `f'documento:{documento_b.pk}'` não aparece no content.
7. `test_arvore_pendencia_restrita_sem_dados`: `HierarquiaArvoreService.construir_arvore_cadeia_dominial(imovel_c1, documentos_queryset=documentos_for_user(via_ti))`. Espera:
   - o nó C1 tem exatamente 1 pendência, igual ao dict da tabela de formato acima
   - nenhum nó tem `id == documento_b.pk`
8. `test_arvore_restrita_nunca_cria_documento`: crie `Documento(imovel=imovel_c1, numero='M3999', …)` (não é o principal) com um lançamento que cita M2000 (LancamentoOrigem). Chame `_buscar_documentos_pais_e_pendencias(doc, imovel_c1, True, documentos_for_user(via_ti))`. Espera `([], [pendência restrita])` e `Documento.objects.count()` igual ao de antes.
9. Em `test_escopo_global.py`: `test_hierarquia_utils_contar_origens_restritas`, chamado sem escopo → `assertRaisesRegex(TypeError, REGEX_ESCOPO)`.

**Verde**: os testes novos · `test_escopo_global` 30/30 · `test_segregacao_usuario` (194 + novos)/(195 + novos) · sem falha nova em `test_issue_201_origens_cadeia_tabela`, `test_issue_201b_ordem_cadeia`, `test_issue_144_origem_cartorio` e `test_hierarquia_arvore_*`.
**Commit**: `feat(#132): C3 — D1 leitura: origem em outra TI vira aviso restrito sem dados`

### C4 — D1 na ESCRITA: não vincular, mensagem explícita, nunca IntegrityError

**Fluxo decidido**

- O lançamento **salva**.
- A `LancamentoOrigem` com a identidade digitada é gravada como hoje (`_sincronizar_origens_estruturadas`, :184-189). É dado do usuário e não tem FK para o Documento.
- **Nenhum** Documento é criado ou importado para a origem restrita.
- A mensagem de retorno cita **a posição** e `MENSAGEM_ORIGEM_RESTRITA`.
- Quando a TI for atribuída, a leitura do C3 passa a resolver a origem sozinha.

**Produção** (`lancamento_origem_service.py`)

1. Imports: `from ..managers import identidade_existe_fora_do_escopo` e `from ..utils.segregacao_utils import MENSAGEM_ORIGEM_RESTRITA`.
2. Depois de `OrigemAmbiguaError` (:25):
   ```python
   class OrigemRestritaError(Exception):
       """D1 (#132): a origem existe, mas em TI fora do escopo. Mensagem fixa."""
       def __init__(self):
           super().__init__(MENSAGEM_ORIGEM_RESTRITA)
   ```
3. Método novo:
   ```python
   @staticmethod
   def _origem_restrita(tipo, numero, cartorio, documentos_queryset):
       """True quando (tipo, número, cartório) existe só fora do escopo (D1)."""
       if not tipo or not cartorio:
           return False
       try:
           identidade = DocumentoIdentidade(tipo, numero, cartorio.pk)
       except (TypeError, ValueError):
           return False
       return identidade_existe_fora_do_escopo(
           documentos_queryset, tipo=identidade.tipo,
           numero_normalizado=identidade.numero_normalizado,
           cartorio_id=identidade.cartorio_id,
       )
   ```
4. **Ponto único de criação**, `_criar_documento_origem`: logo depois do `_resolver_documento_estrito` (:1096-1099) e antes de `_obter_livro_folha_origem`:
   ```python
   if documento_origem is None and LancamentoOrigemService._origem_restrita(
       origem_info['tipo'], origem_info['numero'], cartorio_origem, documentos_queryset,
   ):
       raise OrigemRestritaError()
   ```
5. `_processar_origens_normais`, caminho de origem única (:449-495). Crie `restritas = []`. Antes do `processar_origens_para_documentos` (:457):
   ```python
   chave = LancamentoOrigemService._chave_identidade_texto(origem_unica)
   if chave and LancamentoOrigemService._origem_restrita(
       chave[0], origem_unica, dados_origem['cartorio'], documentos_queryset,
   ):
       logger.info("Origem %s do lançamento %s em TI fora do escopo; não vinculada",
                   indice_unico + 1, lancamento.pk)
       return LancamentoOrigemService._montar_mensagem_origens(
           1, 0, 0, 'da origem identificada', restritas=[indice_unico])
   ```
   No laço de criação (:478-488), ponha `except OrigemRestritaError: restritas.append(indice_unico); continue` **antes** do `except Exception`. O retorno final (:492) passa a receber `restritas=restritas`.
6. `_processar_multiplas_origens` (:629-715): crie `restritas = []` em :641. Depois do bloco `if not cartorio:` (:655-664), cole o mesmo pré-check com `cartorio` e `indice_origem`. No pré-check, faça `identificadas += 1`, `restritas.append(indice_origem)` e `continue`. No `try` (:687-705), ponha `except OrigemRestritaError: restritas.append(indice_origem); continue` antes do `except Exception`. O retorno (:712) passa `restritas=restritas`.
7. `_montar_mensagem_origens(identificadas, criados, falhas, complemento, restritas=())` (:520-538):
   ```python
   aviso = ''
   if restritas:
       posicoes = ', '.join(str(i + 1) for i in sorted(set(restritas)))
       aviso = f'Origem(ns) na(s) posição(ões) {posicoes} não vinculada(s): {MENSAGEM_ORIGEM_RESTRITA}.'
   identificadas -= len(restritas)
   if identificadas <= 0:
       return aviso
   base = <corpo atual inalterado, usando `identificadas` já descontada>
   return f'{base} {aviso}'.strip()
   ```
8. `api_views.escolher_origem_documento`: **sem mudança** (A7).

**Testes T-D1-escrita**: classe `OrigemRestritaEscritaTest(OrigemOutraTIBaseTestCase)`. Para todos os casos, `escopo = documentos_for_user(via_ti)`.

1. `test_lancamento_comum_salva_sem_vincular`: lançamento L em `documento_c1` (tipo registro, `origem='M2000'`, `cartorio_origem=cartorio`). `processar_origens_automaticas(L, 'M2000', imovel_c1, documentos_queryset=escopo)`. Espera:
   - a mensagem contém `MENSAGEM_ORIGEM_RESTRITA` e `'posição(ões) 1'`
   - `Documento.objects.count()` e `DocumentoImportado.objects.count()` iguais aos de antes
   - existe `LancamentoOrigem(lancamento=L, numero='M2000')`
2. `test_inicio_matricula_nao_tenta_criar`: mesmo cenário com tipo `inicio_matricula` (`LancamentoTipo.objects.get_or_create`). Envolva em `self.assertNoLogs('dominial.services.lancamento_origem_service', level='ERROR')`. Espera as mesmas asserções do teste 1.
3. `test_multiplas_origens_mistas`: `'M3001; M2000'` com 2 `LancamentoOrigem`. A mensagem contém `'posição(ões) 2'` e a constante, e a contagem de Documento não muda.
4. `test_ponto_unico_bloqueia`: `_criar_documento_origem(imovel_c1, L, {'tipo': 'matricula', 'numero': 'M2000'}, cartorio, documentos_queryset=escopo)` levanta `OrigemRestritaError`, e `str(exc) == MENSAGEM_ORIGEM_RESTRITA`.
5. `test_superuser_sem_aviso`: com `documentos_queryset=Documento.objects.all()`, a mensagem não contém a constante.
6. `test_escolher_origem_documento_sem_oraculo`: `force_login(via_ti)` e POST JSON `{documento_id: documento_c1.pk, origem_identidade: f'documento:{documento_b.pk}', tis_id, imovel_id}`. Espera:
   - 400 com `error == 'Origem não pertence às origens resolvidas do documento'`
   - o mesmo POST com `documento:999999` devolve status e corpo idênticos
   - a sessão não ganha `origem_documento_<id>`

**Verde**: os novos testes · sem falha nova em `test_issue_144_fase2`, `test_issue_144_origem_cartorio`, `test_t26_selecao_inequivoca`, `test_t27_regressao_cartorio_duplicata` e `test_issue_230_documento_automatico_tipo` (compare com o pós-C3).
**Commit**: `feat(#132): C4 — D1 escrita: origem em outra TI não vincula e explica (sem IntegrityError)`

### C5 — D2 (#152): auditoria com regressão, sem mudança de produção

**Conclusão: D2 já está completo depois do C1.**

- O lançamento é resolvido só por `lancamentos_for_user(user)` (`lancamento_views.py:84-92`).
- `lancamentos_for_user` (`managers.py:124-132`) e `documentos_for_user` (:113-121) usam o mesmo predicado, `imovel__in=Imovel.objects.for_user(user)`. Logo, o lançamento é visível ⇔ o documento é acessível, que é exatamente o teste de D2.
- O imóvel vem de `for_user` (:644 e :1000).
- A escrita confere de novo em `lancamento_criacao_service.py:299-300`.
- `LancamentoForaDaCadeiaError` (:133-134) é proteção de contexto contra homônimo, não autorização. Mantenha.

Fora do D2, só registrar: `lancamento_detail` (:1159) usa `get_object_or_404(Lancamento, …, documento__imovel=imovel)`. Documento compartilhado dá 404 na leitura. Não vaza nada; é uma inconsistência de UX para uma issue futura.

**Testes**

1. `test_issue_152_excluir_lancamento_compartilhado.py` tem 8 falhas, todas 404 de usuário sem TI. No setUp, `atribuir_tis(<usuário logado>, <TI(s) dos imóveis do fixture>)`. Se o fixture usa 2 TIs para simular um documento compartilhado, atribua as duas.
2. Classe `D2AcessoAoDocumentoTest(OrigemOutraTIBaseTestCase)` em `test_segregacao_usuario.py`:
   - `test_mesma_ti_edita_doc_compartilhado`: `force_login(via_ti)`, GET `reverse('editar_lancamento', args=[tis_c.id, imovel_c1.id, lanc_c2.id])` → 200.
   - `test_mesma_ti_exclui_doc_compartilhado`: POST `reverse('excluir_lancamento', …lanc_c2…)` → 302, e `lanc_c2` deixa de existir.
   - `test_outra_ti_404`: `lancamento_b` pela URL do `imovel_c1`. GET editar → 404 e POST excluir → 404. `lancamento_b` continua existindo.
   - `test_service_recusa_sem_acesso_ao_documento`: `RequestFactory().post(...)` com `request.user = via_ti`. `LancamentoCriacaoService.atualizar_lancamento_completo(request, lancamento_b, imovel_c1) == (False, NAO_AUTORIZADO_LANCAMENTO)`.
   - `test_equipe_global_edita`: `membro_global`, GET editar `lanc_c2` via `imovel_c1` → 200.

**Verde**: `test_issue_152` 8/8 · `test_divida_edicao_lancamento_homonimo` verde · novos testes verdes.
**Commit**: `test(#132): C5 — D2 regressão: acesso ao documento ⇒ edita/exclui lançamento compartilhado`

### C6 — D3 (S2): `buscar_m_anterior` informa só que o documento existe

**Produção**

- `lancamento_views.py`:
  - import (:8): acrescente `identidade_existe_fora_do_escopo`
  - import novo: `from ..utils.segregacao_utils import MENSAGEM_DOCUMENTO_OUTRA_TI`
- Corpo (:1115-1151):
  - Troque `Documento.objects` por `escopo = documentos_for_user(request.user)`. Mantenha **exatamente** o filtro atual (`numero_normalizado=…, cartorio_id=…, tipo_id__tipo='matricula'`), o `select_related` e o `.first()`. Não "corrija" o `tipo_id__tipo`.
  - Se `documento is None`:
    ```python
    if identidade_existe_fora_do_escopo(escopo, tipo='matricula',
            numero_normalizado=numero_normalizado, cartorio_id=cartorio_id):
        # D3 (#132): só o fato de existir — sem id, matrícula, imóvel ou TI.
        return JsonResponse({'encontrado': True, 'restrito': True, 'doc_id': None,
            'matricula': None, 'imovel_nome': None, 'outra_ti': True,
            'mesma_ti': False, 'mensagem': MENSAGEM_DOCUMENTO_OUTRA_TI})
    ```
  - As duas respostas que já existem ganham `'restrito': False, 'mensagem': None`.
  - Atualize o contrato JSON na docstring (:1080-1088).
- `static/dominial/js/origem_simples.js` `renderMAnterior` (:215): primeiro ramo novo:
  `if (dados.encontrado && dados.restrito) { div.className = 'm-anterior-info m-anterior-other-ti'; div.textContent = \`⚠ ${dados.mensagem}\`; } else if …`.

**Testes T-D3**: classe `BuscarMAnteriorD3Test(SegregacaoFase2BaseTestCase)`, GET `reverse('buscar_m_anterior')`.

1. `test_outra_ti_so_existencia`: `via_ti` com `numero=M2000`, `cartorio_id`, `tis_id=tis_c`. Espera:
   - `assertEqual(resp.json(), {...})` com o **dict inteiro** acima; isso prova que não há chave extra
   - `assertNotContains` de `'Imóvel B'`, `'TI Beta'` e `'TI-B'`
2. `test_mesma_ti_retorna_dados`: M3001 → `doc_id == documento_c2.pk`, `'Imóvel C2'`, `mesma_ti` True, `restrito` False.
3. `test_inexistente`: M9999 → `encontrado` False, `restrito` False.
4. `test_sem_nada_ve_restrito`: `sem_nada` com M3001 → `restrito` True, `doc_id` None.
5. `test_superuser_ve_dados`: M2000 com `tis_id=tis_c` → `doc_id == documento_b.pk`, `outra_ti` True, `restrito` False.
6. `test_userimovel_legado`: `dono` com M1000 → dados completos.

Rode também os testes já existentes do #167 (`git grep -l buscar.m.anterior dominial/tests`). Falha por usuário sem TI é da Fase 4 categoria A; corrija no próprio C6.
**Verde**: os 6 testes novos · módulos #167 verdes · canário verde (C6 não pode introduzir `Documento.objects` na view).
**Commit**: `fix(#132): C6 — D3 buscar_m_anterior não vaza documento de outra TI`

### C7 — D4 (S7/#210): cartório só para superuser

**Decisão**: a **edição** do cartório de um imóvel existente fica restrita ao superuser. Na **criação**, o cartório é escolhido livremente por quem pode criar o imóvel. Ver R2.

**Produção**

1. Constante `MENSAGEM_CARTORIO_SO_SUPERUSER` (3.1).
2. `imovel_documento_service.py:152`: a assinatura vira `sincronizar_cartorio_documento_principal(imovel, *, user)`. Primeiras linhas:
   ```python
   from django.core.exceptions import PermissionDenied
   from ..managers import usuario_ve_tudo
   if not usuario_ve_tudo(user):
       raise PermissionDenied(MENSAGEM_CARTORIO_SO_SUPERUSER)
   ```
3. `forms/imovel_forms.py`:
   - `__init__(self, *args, user=None, **kwargs)`: faça `self.user = user` antes do `super().__init__`.
   - No `clean`, logo depois de calcular `cartorio_mudou` (:109) e **antes** da checagem combinada (:115):
     ```python
     if cartorio_mudou and not usuario_ve_tudo(self.user):
         self.add_error('cartorio', MENSAGEM_CARTORIO_SO_SUPERUSER)
         return cleaned_data
     ```
   - No `save` (:139), passe `user=self.user`.
4. Views:
   - `imovel_views.py:23` e `:107`: `ImovelForm(..., user=request.user)`
   - `imovel_views.py:73`: `sincronizar_cartorio_documento_principal(imovel, user=request.user)`
   - `tis_views.py:163` e `:176`: `ImovelForm(..., user=request.user)`. Leia `tis_views.py:155-180`. Se esse caminho usa `save(commit=False)` e pula a sincronização, mantenha o comportamento; só passe o `user`.
5. `admin.py` `ImovelAdmin` (:1520):
   ```python
   def get_readonly_fields(self, request, obj=None):
       campos = list(super().get_readonly_fields(request, obj))
       if obj is not None and not request.user.is_superuser:
           campos.append('cartorio')
       return campos
   ```
   - `save_model` (:1568): passe `user=request.user`.
   - Confira em :1495-1513 que, com `cartorio` readonly, `ImovelAdminForm.clean` dá `cartorio_mudou=False`. Se não der, NÃO VERIFICADO — parar.

**Testes T-D4**: classe `CartorioSoSuperuserTest(SegregacaoFase2BaseTestCase)` com `cartorio2 = Cartorios(nome='CRI Dois', cns='222222', estado='SP', cidade='São Paulo')`.

1. `test_usuario_comum_nao_troca_cartorio`: `force_login(via_ti)` e POST `reverse('imovel_editar', args=[tis_c.id, imovel_c1.id])` com os dados do imóvel e `cartorio=cartorio2`. Monte os dados copiando o helper de POST de edição de `test_issue_210_divergencia_cartorio.py`. Espera:
   - o imóvel e o documento principal continuam no `cartorio`
   - `MENSAGEM_CARTORIO_SO_SUPERUSER` aparece na resposta
2. `test_superuser_troca_e_sincroniza`: o mesmo POST com o superuser. O imóvel e o documento principal passam para `cartorio2`.
3. `test_service_exige_superuser`:
   - `user=via_ti` → PermissionDenied
   - `user=None` → PermissionDenied
   - sem o kwarg → TypeError
4. `test_admin_cartorio_readonly`: `ImovelAdmin(Imovel, admin.site).get_readonly_fields(req, imovel_c1)` contém `'cartorio'` para um staff comum. Não contém para o superuser nem para `obj=None`.
5. Adaptar `test_issue_210_divergencia_cartorio.py`:
   - as ~10 chamadas diretas ao service ganham `user=self.superuser`, criado no setUp
   - os 3 testes que falham hoje (view/form) logam como superuser quando editam o cartório
   - isso não é "afrouxar": por D4, o assunto do teste é o superuser

**Verde**: `test_issue_210` 100% · novos testes · `test_segregacao_usuario` sem regressão nos testes de admin.
**Commit**: `fix(#132): C7 — D4 cartório do imóvel só editável por superuser (form/admin/service)`

### C8 — D5 (S1/#179): XLS por TI só com a TI inteira atribuída

**Produção**

1. `managers.py`, helper novo:
   ```python
   def usuario_tem_ti_inteira(user, tis_id):
       """D5 (#132): a TI inteira está atribuída (equipe, equipe global ou
       UserTI). UserImovel legado NÃO conta. Superuser: sempre."""
       from .models import TIs
       if not usuario_autenticado(user):
           return False
       if usuario_ve_tudo(user):
           return True
       return TIs.objects.filter(pk=tis_id, pk__in=tis_atribuidas_ids(user)).exists()
   ```
2. `cadeia_dominial_views.py` `exportar_cadeia_dominial_excel_tis` (:555-702):
   ```python
   from ..managers import usuario_tem_ti_inteira
   if not usuario_tem_ti_inteira(request.user, tis_id):      # FORA do try (A4)
       raise Http404(MENSAGEM_TI_SEM_ACESSO)
   tis = get_object_or_404(TIs, id=tis_id)                    # sai de :568, fora do try
   try:
       imoveis = list(Imovel.objects.for_user(request.user)   # :574-578 (canário)
           .filter(terra_indigena_id=tis)
           .select_related('cartorio', 'proprietario').order_by('matricula', 'id'))
       ...
       contexto = CadeiaCompletaService(user=request.user).get_cadeia_completa(tis.id, imovel.id)  # :652
       ...
   except Exception:
       logger.exception(...)  # mantém
       resposta = HttpResponse('Erro ao gerar Excel. Tente novamente; se persistir, contate o administrador.', content_type='text/plain')
       resposta.status_code = 500
       return resposta
   ```
   Importe `Http404` e `MENSAGEM_TI_SEM_ACESSO` se faltarem. Essa view sai da lista do C9 (o `str(e)` dela é removido aqui).

**Testes**

1. Adaptar `test_issue_179_xls_consolidado_tis.py` (`request.user` em :255 e :1008) e `test_issue_204_xls_rotulo_a4.py` (:132): troque `SimpleNamespace(is_authenticated=True)` por `usuario_com_tis('<nome>', <TI do fixture>)`. Isso também conserta os 2 testes de export individual do 204, porque `__wrapped__` ainda passa pelo `require_imovel_atribuido`.
2. Classe `XlsPorTIEscopoTest(OrigemOutraTIBaseTestCase)`, GET `reverse('exportar_cadeia_tis_excel', args=[...])`:
   - `via_ti`/`tis_c` → 200 xlsx. `openpyxl.load_workbook`: 3 abas (Resumo + C1 + C2). Nenhuma célula contém `'R1M2000'` nem `'Imóvel B'`.
   - `via_ti`/`tis_b` → 404. `dono`/`tis_a` (só UserImovel) → 404.
   - `via_equipe`/`tis_c` → 200. `membro_global`/`tis_b` → 200. `superuser`/`tis_b` → 200. TI 999999 com o superuser → 404, não 500.
   - `patch.object(CadeiaCompletaService, 'get_cadeia_completa', side_effect=Exception('SEGREDO /opt/x.py'))`: espera 200, abas com "Erro ao exportar este imóvel." e nenhuma célula com `SEGREDO`.
   - `patch('dominial.views.cadeia_dominial_views.criar_estilos', side_effect=Exception('SEGREDO'))`: espera 500 e `b'SEGREDO' not in content`.

**Verde (obrigatório)**: `test_segregacao_usuario` **195/195** + novos (o canário `ManagerOptInRegressaoTest` volta a verde) · `test_issue_179` + `test_issue_204` 46/46 · `test_escopo_global` verde.
**Commit**: `fix(#132): C8 — D5 XLS por TI exige a TI inteira atribuída + escopo no CadeiaCompletaService`

### C9 — S8 (sem `str(e)` nas respostas) e badge #174

**(a) Padrão de mensagem**

- Crie `dominial/utils/mensagens_erro.py` com `ERRO_INTERNO = 'Erro interno. Tente novamente; se persistir, contate o administrador.'`.
- Em cada ponto: `logger.exception('<contexto> (ids)', …)` + uma mensagem fixa. O traceback vai para o log, nunca para a resposta.
- `api_views.py` não tem logger: acrescente `import logging; logger = logging.getLogger(__name__)` e troque `traceback.print_exc()` por `logger.exception`.

| arquivo:linha | Onde | Novo texto da resposta |
|---|---|---|
| `api_views.py:188` | criar_cartorio | `'Erro ao criar cartório.'` |
| `api_views.py:310`, `:364`, `:493`, `:526` | escolher_origem_documento / escolher_origem_lancamento / get_cadeia_dominial_atualizada / limpar_escolhas_origem | `ERRO_INTERNO` |
| `cadeia_dominial_views.py:142`, `:799` | JSON da árvore | `ERRO_INTERNO` |
| `cadeia_dominial_views.py:444`, `:495` | HTML de erro do PDF | remova a linha/bloco `Erro: {str(e)}` (o texto fixo já existente fica) |
| `cadeia_dominial_views.py:549` | XLS individual | `'Erro ao gerar Excel. Tente novamente; se persistir, contate o administrador.'` |
| `documento_views.py:138`, `:334`, `:335`, `:383` | excluir/criar documento | `'Erro ao excluir documento.'` / `'Erro ao criar documento.'` / `ERRO_INTERNO` |
| `duplicata_views.py:113`, `:132`, `:175` | importação | `'⚠️ Importação realizada, mas houve erro ao criar o lançamento.'` / `'❌ Erro inesperado.'` / `'❌ Erro ao processar a importação.'` |
| `imovel_views.py:97` | salvar imóvel | `'Erro ao salvar imóvel.'` |
| `tis_views.py:79`, `:142`, `:174`, `:196`, `:223` | TI/imóvel | `'Erro ao cadastrar Terra Indígena.'` / `'Erro ao excluir Terra Indígena.'` / `'Erro ao atualizar imóvel.'` / `'Erro ao excluir imóvel.'` / `'Erro ao alterar status do imóvel.'` |

`lancamento_views.py:589` (`… in str(e)`) é lógica, não resposta. Fica como está.

**(b) Badge #174: o que o C1/C2 deixou e o que falta**

- Produção completa: `tis_views.py:110-118` calcula o mapa com `imoveis_queryset=imoveis_ordenados` (escopado) e `documentos_for_user`. `tis_detail.html:83-90` renderiza o badge.
- Falta só o fixture: `test_tis_detail_renderiza_badge_e_traco` (`test_issue_174_status_cadeia.py:166-174`) falha porque `t174` não tem TI e a lista fica vazia. Correção: `atribuir_tis(self.user, self.tis)` em `StatusCadeiaBase.setUp` (:28-31).

**Testes**

- Arquivo novo `dominial/tests/test_s8_sem_str_e.py`:
  - **Varredura estática**: `views/*.py` + `admin.py`, regex `str\((e|exc|erro)\)|\{(e|exc|erro)\}`. Falha fora da allowlist `{'lancamento_views.py': ["in str(e)"]}`.
  - **Comportamental**: `patch.object(CadeiaDominialTabelaService, 'obter_cadeia_tabela', side_effect=Exception('SEGREDO /opt/app/x.py'))` + GET `get_cadeia_dominial_atualizada` com um usuário que tem a TI. Espera:
    - 500 com `error == ERRO_INTERNO`
    - `'SEGREDO'` ausente do content
    - `assertLogs('dominial.views.api_views', 'ERROR')`
  - Idem para `escolher_origem_documento`, com patch de `dominial.views.api_views.obter_origens_resolvidas`.
- Classe `BadgeStatusCadeiaEscopoTest(OrigemOutraTIBaseTestCase)`:
  - `lancamento_b` ganha `OrigemFimCadeia(fim_cadeia=True, tipo_fim_cadeia='destacamento_publico', classificacao_fim_cadeia='origem_lidima', indice_origem=0)`.
  - GET `tis_detail` de `tis_c`: `via_ti` **não** vê `cadeia-badge-lidima`, porque o fim de cadeia está fora do escopo. O superuser vê. Se o superuser não vir, é NÃO VERIFICADO (lógica do #174): reportar, não ajustar.

**Verde**: `test_s8_sem_str_e` · `test_issue_174` 100% · os módulos das views tocadas sem falha nova.
**Commit**: `fix(#132): C9 — S8 respostas sem str(e) + badge #174 com escopo testado`

## 5. Ordem de execução

```
C2a → C2b → C3 → C4 ─┬→ C5 ─┐
                     ├→ C6 ─┤
                     ├→ C7 ─┼→ C9 → Fase 4 → suíte = baseline
                     └→ C8 ─┘
```

- C2a vem antes de tudo: sem ele nenhum teste de criação de lançamento é confiável. C2a também cria o helper 3.3.
- C2b vem antes do C3, porque o C3 mexe em `_resolver_origem`.
- C3 vem antes de C4 e C6 (constante + helper 3.2) e de C5/C8/C9 (base de teste 3.4).
- C5, C6, C7 e C8 mexem em arquivos de produção disjuntos (C5: nenhum · C6: `lancamento_views`/`origem_simples.js` · C7: forms/admin/`imovel_*`/`tis_views` · C8: `cadeia_dominial_views`/`managers`). **Podem ser paralelos**, com uma ressalva: todos acrescentam no fim de `managers.py`, `segregacao_utils.py` e `test_segregacao_usuario.py`. Em paralelo, cada um escreve num bloco delimitado e o rebase é sequencial. Para um júnior só: faça em série.
- C9 vem depois de C4, C7 e C8, porque edita linhas próximas das deles (`api_views`, `tis_views`, `cadeia_dominial_views`).
- A Fase 4 vem por último. Os módulos que são dos commits ficam fora dela: 152 (C5), 210 (C7), 179/204 (C8), 174 (C9) e 241 (C2a).

## 6. Riscos e ambiguidades

- **R1**: o marcador restrito não leva o código digitado. Segui o brief ("sem número, sem cartório, sem imóvel"). Mostrar o código digitado é uma mudança de 1 linha, porque é dado do próprio lançamento. **Decisão de produto: não faça sem aprovação.**
- **R2 — NÃO VERIFICADO, parar e perguntar** se o C7 tiver de bloquear também a **criação**. O padrão adotado é gatear só a edição.
- **R3 — NÃO VERIFICADO**: nos testes do C4, não sei se `_buscar_dados_origem` acha o cartório de uma origem única só por `cartorio_origem`. Se `dados_origem['cartorio']` vier None, copie o padrão de mapeamento de `test_issue_144_fase2.py` (`definir_mapeamento`). Se não ficar claro, parar.
- **R4 — NÃO VERIFICADO, perguntar**: `tis_detail` (`tis_views.py:86`) usa `get_object_or_404(TIs, id=…)` sem escopo. O nome da TI aparece para quem não tem a TI (lista vazia). Não faz parte de D1–D6. Confira o que `TisDetailOrderingTest` espera antes de propor qualquer coisa.
- **R5 — NÃO VERIFICADO**: `escolher_origem_lancamento` (`api_views.py:347-354`) coloca instâncias de modelo em `JsonResponse`. Pela leitura, o resultado é sempre 500. Bug funcional pré-existente: o C9 só troca a mensagem. Abrir issue.
- **R6**: `DocumentoIdentidadeService.resolver(queryset=None)` cai no escopo global (`documento_identidade_service.py:44-45`). Os chamadores de produção passam `queryset`. Tornar o argumento obrigatório quebra um número desconhecido de testes. Dívida para depois da v1.1.0.
- **R7**: `status_por_imovel(imoveis_queryset=None)` cai em todos os imóveis da TI (`status_cadeia_service.py`). A view passa o escopo. Dívida.
- **R8**: `contar_origens_restritas` faz até 2 queries por origem não resolvida, por documento. Se algum teste de teto de queries quebrar no C3: **parar** e reportar as contagens.
- **R9**: se o regex do T11 (C2b) expuser mais testes vacuosos: **parar** e reportar.
- **R10**: dizer que a origem existe (D1/D3) é decisão de produto aceita, não vazamento. Os testes documentam isso.
- **R11 — NÃO VERIFICADO, investigar antes do C9**: `cadeia_dominial_views.py:349` monta `'imovel_nome': importacao.imovel_origem.nome` (cadeias que importam um documento). Pode expor o nome de imóvel de TI não atribuída. Confira se `importacao` vem filtrado por escopo. Se não vier, parar e perguntar (provável C3b).
- **R12**: `UserTI.atribuido_por` pode ser NOT NULL (3.3). Leia antes de usar o helper.

## 7. Fase 4: os testes do develop que falham por usuário sem TI

### 7.1 Estratégia

- Use o helper compartilhado `dominial/tests/segregacao_fixtures.py` (3.3) e conserte módulo a módulo, na causa:
  - **A** — client logado sem TI (`404 != 200/302/400`, "Not Found" no HTML, `Content-Type text/html, not application/json`, `KeyError` de contexto como `'origens_separadas'`): no setUp/setUpTestData, `atribuir_tis(user, <todas as TIs cujos imóveis o teste toca>)`.
  - **B** — `RequestFactory` sem `request.user` (`'WSGIRequest' object has no attribute 'user'`): `request.user = usuario_com_tis(...)`.
  - **C** — `SimpleNamespace(is_authenticated=True)` (`Field 'id' expected a number but got namespace`): troque por um usuário real com `usuario_com_tis`.
  - **D** — service chamado sem escopo no teste (`CadeiaCompletaService()`, `StatusCadeiaService.status_por_imovel(tis_id)`): passe `documentos_queryset=ESCOPO_GLOBAL` (mesma política do C2).
  - **E** — 302 (`q=… retornou 302`): veja o `Location`. Se for login, `force_login(usuario_com_tis(...))`. Se for o redirect de "sem imóveis", use a correção da categoria A.
  - **F** — stub ou mock desatualizado (ex.: `T9SignalOrigemAmbiguaTest…resolver() got an unexpected keyword argument 'queryset'`): ajuste a assinatura do stub (`queryset=None`). Produção não muda.
- **Proibido**: superuser (salvo quando o teste é sobre o superuser), `ESCOPO_GLOBAL` em produção, afrouxar guard, apagar teste.
- Se a **intenção** de um teste contradiz D1–D5 (ex.: espera ver um documento de outra TI), **parar** e reportar. Não reescreva a intenção.
- Classificar um módulo: `venv/bin/python manage.py test dominial.tests.<mod> 2>&1 | grep -E "^(ERROR|FAIL):|^[A-Za-z]*Error:" | cut -c1-160`.

### 7.2 Módulos (HEAD `b4163140`, contagem atual menos o baseline; a categoria é estimada pelo histograma de erros)

| Módulo | Novas | Categoria provável | Dono |
|---|---|---|---|
| test_issue_218_livro_folha_swap | 24 | A | F4 |
| test_issue_227_cri_autocomplete_origem | 21 | A/E | F4 |
| test_issue_144_fase2 | 21 | A+B (+ERRO_CRIACAO do A1) | F4 (depois do C2a) |
| test_issue_179_xls_consolidado_tis | 19 | C | **C8** |
| test_issue_159_162_form_bugs | 15 | A | F4 |
| test_issue_201b_ordem_cadeia | 12 | A | F4 |
| test_issue_201_origens_cadeia_tabela | 8 | A | F4 |
| test_issue_152_excluir_lancamento_compartilhado | 8 | A | **C5** |
| test_issue_171_arvore_modal | 5 | A | F4 |
| test_issue_144_origem_cartorio | 5 | A+F | F4 |
| test_exportacao_cadeia | 5 | C(3)+D(2) | F4 |
| test_issue_241_criacao_lancamento_atomica | 4 | B | **C2a** |
| test_issue_204_xls_rotulo_a4 | 4 | C | **C8** |
| test_issue_168_tab_sigla | 4 | A | F4 |
| test_issue_210_divergencia_cartorio | 3 | A | **C7** |
| test_issue_166_cri_export | 3 | C | F4 |
| test_issue_157_transmissao_persistencia | 3 | A | F4 |
| test_issue_230_documento_automatico_tipo | 2 | A | F4 |
| test_issue_193_uf_sugestoes_cri | 2 | A/E | F4 |
| test_issue_13_area_pt_br | 2 | A | F4 |
| test_greptile_p2_n1_query | 2 | D | F4 |
| test_issue_172_suprimir_troncos | +1 (`test_estatisticas_sem_troncos`) | D | F4 |
| test_t27_regressao_cartorio_duplicata | 1 | A | F4 |
| test_issue_245_edicao_documento_restrita | 1 | A | F4 |
| test_issue_229_cartorio_por_origem | 1 | A | F4 |
| test_issue_174_status_cadeia | 1 | A | **C9** |
| test_segregacao_usuario | 1 (canário) | — | **C8** |

`test_issue_145_pdf_averboes` estava no baseline (2 erros) e passou depois do merge. Não trate como regressão.

### 7.3 Critério de saída da Fase 4

A lista ordenada de `^(ERROR|FAIL):` da suíte completa tem de ser ⊆ a lista do baseline (7.4). Diferença esperada: só os nomes do `test_issue_145` somem.

### 7.4 Baseline develop puro (59 entradas; guardado aqui porque o `/tmp` é limpo)

- `test_documento_importado_service` (8 E): get_documentos_importados_ids, get_documentos_importados_imovel, get_info_importacao_none, get_info_importacao_success, get_tooltip_importacao_none, get_tooltip_importacao_success, is_documento_importado_false, is_documento_importado_true
- `test_documento_lancamento` (7 E + 1 F): criar_documento_matricula, criar_documento_transmissao, criar_lancamento_averbacao, criar_lancamento_registro, validacao_averbacao_sem_detalhes, validacao_registro_sem_adquirente, validacao_registro_sem_transmitente; F: abordagem_conservadora_sem_niveis_negativos
- `test_duplicata_verificacao` (18 E): criar_documento_importado, get_documentos_importados_imovel, get_importador_info, get_origem_info, is_documento_importado, str_representation, calcular_documentos_importaveis, obter_cadeia_dominial_origem, verificacao_desabilitada, verificar_duplicata_mesmo_imovel, verificar_duplicata_origem_existente, verificar_duplicata_origem_inexistente, verificar_performance_consulta, desfazer_importacao, importar_cadeia_dominial_imovel_inexistente, importar_cadeia_dominial_sucesso, marcar_documento_importado, verificar_documentos_importados
- `test_fase2_duplicata_integracao` (12 E): obter_dados_duplicata_para_template, obter_dados_duplicata_sem_duplicata, processar_importacao_duplicata_documento_inexistente, processar_importacao_duplicata_sem_documento_origem, processar_importacao_duplicata_sucesso, url_cancelar_importacao, url_importar_duplicata, url_verificar_duplicata_ajax, verificar_duplicata_antes_criacao_com_duplicata, verificar_duplicata_antes_criacao_sem_duplicata, verificar_duplicata_cartorio_inexistente, verificar_duplicata_sem_origem
- `test_identidade_documento` (2 E): comando_relata_migracoes_e_constraints_sem_escrever, expect_final_aprova_quando_constraints_finais_estao_presentes
- `test_issue_145_pdf_averboes` (2 E): averbacao_em_matricula_aparece_no_html_e_no_pdf, averbacao_em_transcricao_sumida_do_pdf
- `test_issue_172_suprimir_troncos` (4 E): pdf_documentos_de_todos_os_troncos_permanecem, pdf_nao_exibe_rotulos_com_tronco_secundario, pdf_nao_exibe_rotulos_em_sequencia_personalizada, pdf_nao_exibe_rotulos_tronco
- `test_issue_118_livro_folha_origem` (3 F): aplicar_campos_documento_usa_livro_documento_quando_fornecido, regra_petrea_preserva_livro_ja_no_documento, regra_petrea_usa_livro_transacao_para_documento_atual
- Erros de import: `test_api_cnj` e `test_onr_post` (1 cada, `unittest.loader._FailedTest`)

## 8. Critérios de verde consolidados

| Depois de | Tem de passar |
|---|---|
| todo commit | `test_escopo_global` 100% · nenhuma falha nova contra o commit anterior |
| C2a | `test_issue_241` 4/4 |
| C2b | módulos de árvore listados no C2b sem falha nova · T11 com regex |
| C3 | `OrigemRestritaLeituraTest` · T11 +1 |
| C4 | `OrigemRestritaEscritaTest` · módulos #144/#230/T26/T27 sem falha nova |
| C5 | `test_issue_152` 8/8 · `D2AcessoAoDocumentoTest` |
| C6 | `BuscarMAnteriorD3Test` · módulos #167 |
| C7 | `test_issue_210` 100% · `CartorioSoSuperuserTest` |
| C8 | **`test_segregacao_usuario` 195/195 + novos** · 179+204 46/46 |
| C9 | `test_s8_sem_str_e` · `test_issue_174` 100% |
| Fase 4 | suíte completa ⊆ baseline 7.4 |

D6 (go-live com atribuição fina por TI) é runbook. Não entra em C3–C9.
