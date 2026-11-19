"""Save do bloco de decisões da revisão (``salvar_bloco_ocr``) e a
validação do contrato JSON do POST (``_decisoes_bloco``).

Extraídos do monólito de views (etapa 3, limite de 400 linhas). Nenhum
nome deste módulo é alvo de patch pelo pacote; helpers de outros módulos
vêm por import direto do dono e são chamada direta. O decorator
``_respostas_json_ocr`` é aplicado em tempo de IMPORTAÇÃO, então vem por
import direto do módulo dono (patch em decorator já aplicado não teria
efeito nem no monólito). O call site usa ``services.salvar_bloco`` como
ATRIBUTO DE MÓDULO — os testes fazem
``mock.patch('ia_ocr.views.services.salvar_bloco')``, que resolve no
módulo ``ia_ocr.services``, reexportado pelo pacote de views. Ver o
docstring do ``__init__.py``.
"""
import json

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from .. import revisao, services, valores
from ..estados import TransicaoConcorrente, TransicaoInvalida
from .jobs import _contexto_job, _sem_atos_elegivel
from .resposta import _avisos_da_resposta, _respostas_json_ocr


def _recusar_decisao(code, chave=None):
    erro = services.ExtracaoRecusada(code)
    erro.chave = chave
    raise erro


_ESCOLHA_DA_TELA = {
    'pessoa_id': 'pessoa_escolhida_id',
    'cartorio_id': 'cartorio_escolhido_id',
}


def _decisoes_bloco(dados):
    """Valida o contrato JSON e indexa a lista pelo JSON Pointer de cada linha."""
    if not isinstance(dados, dict):
        _recusar_decisao('corpo_invalido')
    if not isinstance(dados.get('versao'), str):
        _recusar_decisao('versao_invalida')
    if not isinstance(dados.get('decisoes'), list):
        _recusar_decisao('decisoes_invalidas')
    decisoes = {}
    for decisao in dados['decisoes']:
        if not isinstance(decisao, dict):
            _recusar_decisao('decisao_invalida')
        chave = decisao.get('chave')
        if not isinstance(chave, str) or not chave:
            _recusar_decisao('chave_invalida')
        if chave in decisoes:
            _recusar_decisao('chave_duplicada', chave)
        if not isinstance(decisao.get('incluir'), bool):
            _recusar_decisao('decisao_invalida', chave)
        for nome in ('conferido', 'confirmo_conversao'):
            if nome in decisao and not isinstance(decisao[nome], bool):
                _recusar_decisao('decisao_invalida', chave)
        for nome in ('valor', 'ha_convertido'):
            if decisao.get(nome) is not None and not isinstance(decisao[nome], str):
                _recusar_decisao('valor_invalido', chave)
        if 'versao' in decisao and not isinstance(decisao['versao'], str):
            _recusar_decisao('versao_invalida', chave)
        escolha = decisao.get('escolha')
        if escolha is not None:
            if not isinstance(escolha, dict):
                _recusar_decisao('escolha_invalida', chave)
            # A tela manda pessoa_id/cartorio_id; o motor usa os nomes do modelo.
            for curto, nome in _ESCOLHA_DA_TELA.items():
                if curto in escolha:
                    if nome in escolha:
                        _recusar_decisao('escolha_invalida', chave)
                    escolha[nome] = escolha.pop(curto)
            for nome, valor in escolha.items():
                if nome == 'criar_novo' and isinstance(valor, bool):
                    continue
                if nome in ('pessoa_escolhida_id', 'cartorio_escolhido_id'):
                    if valor is None or (type(valor) is int and valor > 0):
                        continue
                _recusar_decisao('escolha_invalida', chave)
        decisoes[chave] = {nome: valor for nome, valor in decisao.items() if nome != 'chave'}
    return decisoes


def _chave_valor_invalido(extracao, decisoes):
    """Localiza a linha após rollback, reaplicando o motor só em memória.

    ValorInvalido ainda não carrega a chave; não expomos seu texto ao cliente.
    """
    campos = {campo.chave: campo for campo in extracao.campos.all()}
    for chave, decisao in decisoes.items():
        argumentos = {
            nome: decisao[nome] for nome in (
                'incluir', 'valor', 'conferido', 'escolha',
                'ha_convertido', 'confirmo_conversao',
            ) if nome in decisao
        }
        try:
            revisao.aplicar_linha(campos[chave], **argumentos)
        except valores.ValorInvalido:
            return chave
        except revisao.EscolhaIncompativel:
            return chave
    return None


@_respostas_json_ocr
@login_required
@require_POST
def salvar_bloco_ocr(request, tis_id, imovel_id, documento_id, job_id):
    """Salva decisões de revisão com controle otimista da versão do bloco."""
    _tis, _imovel, _documento, job = _contexto_job(
        request, tis_id, imovel_id, documento_id, job_id,
    )
    try:
        dados = json.loads(request.body)
    except (ValueError, UnicodeDecodeError):
        return JsonResponse({'erro': 'json_invalido'}, status=400)
    try:
        decisoes = _decisoes_bloco(dados)
        # ``valor: null`` explícito pede o OCR; só a chave ausente preserva.
        com_valor = {item['chave'] for item in dados['decisoes'] if 'valor' in item}
        extracao = job.extracao_vigente()
        if extracao is None:
            raise services.ExtracaoRecusada('sem_extracao')
        obrigatorias = {
            chave for chave in decisoes if revisao.campo_obrigatorio(chave)
        }
        corrigidos = dict(extracao.campos.filter(
            chave__in=obrigatorias, valor_final__isnull=False,
        ).values_list('chave', 'valor_final'))
        for chave in obrigatorias:
            decisao = decisoes[chave]
            decisao['incluir'] = True
            # Sem a chave ``valor`` o motor volta ao OCR: preserva a correção salva.
            if chave not in com_valor and chave in corrigidos:
                decisao['valor'] = corrigidos[chave]
        _salva, versao, partes_invalidadas, campos_novos = services.salvar_bloco(
            extracao, decisoes, request.user, dados['versao'],
        )
    except revisao.EscolhaIncompativel as exc:
        return JsonResponse({
            'erro': exc.code, 'chave': exc.chave,
        }, status=422)
    except services.ConflitoVersao as exc:
        return JsonResponse({
            'erro': 'conflito_versao', 'chaves': exc.chaves_afetadas,
        }, status=409)
    except services.ExtracaoRecusada as exc:
        return JsonResponse({
            'erro': exc.code, 'chave': getattr(exc, 'chave', None),
        }, status=422)
    except valores.ValorInvalido as exc:
        return JsonResponse({
            'erro': 'valor_invalido',
            'chave': getattr(exc, 'chave', None)
            or _chave_valor_invalido(extracao, decisoes),
        }, status=422)
    except TransicaoInvalida as exc:
        return JsonResponse({'erro': exc.code or 'estado_invalido'}, status=409)
    except TransicaoConcorrente:
        return JsonResponse({'erro': 'transicao_concorrente'}, status=409)
    return JsonResponse({
        'ok': True,
        'versao': versao,
        # A escolha de cadastro foi zerada nessas partes: a tela relê os
        # candidatos recomputados pelo servidor quando puder recarregar.
        'partes_invalidadas': partes_invalidadas,
        # Linhas obrigatórias criadas pelo novo tipo: sem card na tela atual,
        # o cliente recarrega quando puder para exibi-las.
        'campos_novos': campos_novos,
        # Só chave/motivo: a tela reabilita o finalizar sem expor dados da revisão.
        # Com sem atos, ``pendencias()`` só traz ``nenhum_ato``; o helper
        # acrescenta os bloqueios de campo sem duplicar.
        'pendencias': [
            {'chave': item['chave'], 'motivo': item['motivo']}
            for item in services._com_bloqueios_de_campo(
                revisao.pendencias(_salva), _salva,
            )
        ],
        # Issue #262: um bloqueio de campo criado no save não aparece em
        # ``pendencias`` (sem atos ela é sempre nenhum_ato); a tela precisa
        # saber que a confirmação sem atos deixou de ser suficiente.
        'sem_atos_elegivel': _sem_atos_elegivel(_salva),
        # #324 (PR #343, P2): os avisos e os selos "não consta no documento"
        # só eram calculados na abertura da página — preencher livro/folha
        # deixava o aviso na tela, e mudar o número da origem podia esconder
        # ou criar um. A lista inteira vem da MESMA fonte da abertura
        # (``_avisos_descritos``) sobre o estado recém-salvo; a tela troca a
        # lista, a contagem e os selos por ela. Só chave, motivo, o texto de
        # negócio e se o aviso é de "não consta" (o selo do card) — nada do
        # valor revisado.
        'avisos': _avisos_da_resposta(request, _salva),
    })
