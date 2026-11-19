"""Resposta da importação: linhas por chave, erros por campo e replay."""
from dominial.models import LancamentoOrigem

from .. import destinos, revisao
from ..models import ImportacaoIA
from .ato_documento import _url_lancamento
from .avisos import _avisos_gravados_da_extracao, _texto_do_aviso_gravado
from .cartorios import _avisos_livro_folha_da_origem


# Inverso do mapa de destinos: campo do modelo → padrão de chave de linha.
# ``_chave_de_erro`` concreta o padrão com o índice do ato (e da parte, nos
# erros de LancamentoPessoa/Pessoas); campos sem padrão caem no próprio ato.
_PADRAO_POR_CAMPO: dict[str, list[str]] = {}
for _chave, _entrada in destinos.DESTINOS.items():
    if isinstance(_entrada, tuple) and _entrada[1] is not None:
        _PADRAO_POR_CAMPO.setdefault(
            f'{_entrada[0]}.{_entrada[1]}', [],
        ).append(_chave)
# Pessoas não tem linha própria no mapa (só chega via parte): os erros de
# nome/CPF/RG ancoram na linha da parte que os originou, não no ato (#263
# rodada 2 — o message_dict caía em ``/acts/i`` sem a tela saber onde).
_PADRAO_POR_CAMPO['dominial.Pessoas.nome'] = ['/acts/*/partes/*/nome']
_PADRAO_POR_CAMPO['dominial.Pessoas.cpf'] = [
    '/acts/*/partes/*/documento_identificacao/valor',
]
_PADRAO_POR_CAMPO['dominial.Pessoas.rg'] = [
    '/acts/*/partes/*/documento_identificacao/valor',
]


def pendencias_para_resposta(extracao):
    """Pendências estruturadas da revisão invalidada, para a resposta 422.

    A recusa em si já vem do ``RevisaoInvalidada``; o que falta à tela é
    saber ONDE — cada pendência com sua chave de linha. Uma PARTE ou um
    CARTÓRIO que a revisão finalizou como escolha e voltou a ficar
    pendente só acontece quando o cadastro escolhido desapareceu (FKs
    ``SET_NULL``): o motivo vira ``decisao_perdida`` na linha da parte
    (#263 rodada 2) ou do cartório — origem, transmissão (rodada 3).
    """
    linhas = _linhas_por_chave(extracao)
    saida = []
    for pendencia in revisao.pendencias(extracao):
        motivo = pendencia['motivo']
        campo = linhas.get(pendencia['chave'])
        if (
            motivo == 'escolha_pendente'
            and campo is not None
            and campo.tipo_valor in ('parte', 'cartorio')
        ):
            motivo = 'decisao_perdida'
        saida.append({'chave': pendencia['chave'], 'motivo': motivo})
    return saida


# ---------------------------------------------------------------------------
# Erros por campo
# ---------------------------------------------------------------------------

class _Erros:
    """Erros do ato ancorados nas chaves de linha que a tela conhece."""

    def __init__(self, chave_ato):
        self.chave_ato = chave_ato
        self.itens = []

    def add(self, chave, codigo, mensagem, **extras):
        item = {'chave': chave, 'codigo': codigo, 'mensagem': mensagem}
        item.update(extras)
        self.itens.append(item)

    def do_modelo(self, exc, campo_modelo, chave_parte=None):
        """``message_dict`` do Django → erro por chave de linha."""
        dicionario = getattr(exc, 'message_dict', None)
        if not isinstance(dicionario, dict):
            # ValidationError de texto (ex.: cartório da origem): sem campo.
            self.add(
                self.chave_ato, 'lancamento_invalido', ' '.join(exc.messages),
            )
            return
        for campo, mensagens in dicionario.items():
            if campo == '__all__':
                chave, codigo = self.chave_ato, 'lancamento_invalido'
            else:
                chave = _chave_de_erro(
                    f'{campo_modelo}.{campo}', self.chave_ato, chave_parte,
                )
                codigo = 'campo_invalido'
            for mensagem in mensagens:
                self.add(chave, codigo, mensagem)


def _chave_de_erro(campo_modelo, chave_ato, chave_parte=None):
    """Campo do modelo → chave de linha concreta; sem padrão, o próprio ato."""
    for padrao in _PADRAO_POR_CAMPO.get(campo_modelo, ()):
        if chave_parte is not None and '/partes/*' in padrao:
            sufixo = padrao.split('/partes/*', 1)[1]
            return f'{chave_parte}{sufixo}'
        if '/partes/' not in padrao:
            return padrao.replace('/acts/*', chave_ato, 1)
    return chave_ato


# ---------------------------------------------------------------------------
# Respostas
# ---------------------------------------------------------------------------

def _linha_resposta(chave, rotulo, status, lancamento=None, avisos=None,
                    erros=None):
    linha = {
        'chave': chave,
        'rotulo': rotulo,
        'status': status,
        'lancamento_id': lancamento.pk if lancamento is not None else None,
        'url': _url_lancamento(lancamento) if lancamento is not None else None,
        'avisos': avisos or [],
    }
    if erros is not None:
        linha['erros'] = erros
    return linha


def _resultado_gravado(extracao):
    """Remonta a resposta 200 do job já importado (idempotência)."""
    linhas = _linhas_por_chave(extracao)
    por_ato = {}
    vinculos = ImportacaoIA.objects.filter(
        ocr_job_id=extracao.ocr_job_id, modelo='Lancamento',
    ).select_related('campo', 'lancamento__documento__imovel')
    for vinculo in vinculos:
        if vinculo.campo is not None and vinculo.lancamento is not None:
            por_ato[vinculo.campo.chave] = vinculo.lancamento
    respostas = []
    chaves_de_ato = [
        chave for chave, campo in linhas.items()
        if campo.tipo_valor == 'ato'
    ]
    # #324: o aviso de livro/folha da origem sai do que ficou GRAVADO no
    # lançamento, e o de homônimo de outro tipo (#267) sai do registro que a
    # importação gravou no payload da extração — ele não se recalcula (o
    # documento declarado já existe). Os dois na ORDEM da primeira resposta
    # (homônimo, livro, folha); os demais avisos (rótulo, origem restrita)
    # não são persistidos e continuam fora do replay.
    avisos_gravados = _avisos_gravados_da_extracao(extracao)
    com_origem = set(
        LancamentoOrigem.objects.filter(
            lancamento_id__in=[lanc.pk for lanc in por_ato.values()],
        ).values_list('lancamento_id', flat=True)
    )
    for chave in sorted(chaves_de_ato, key=_indice_do_ato):
        lancamento = por_ato.get(chave)
        avisos = []
        if lancamento is not None:
            registros = avisos_gravados.get(chave)
            for registro in registros if isinstance(registros, list) else ():
                texto = _texto_do_aviso_gravado(registro)
                if texto is not None:
                    avisos.append(texto)
        if lancamento is not None and lancamento.pk in com_origem:
            avisos.extend(_avisos_livro_folha_da_origem(
                lancamento.livro_origem, lancamento.folha_origem,
            ))
        respostas.append(_linha_resposta(
            chave, _rotulo(chave, linhas),
            'criado' if lancamento is not None else 'ignorado',
            lancamento=lancamento, avisos=avisos,
        ))
    return {'ok': True, 'linhas': respostas}


def _indice_do_ato(chave):
    """Índice NUMÉRICO do ato na chave ``/acts/N`` (#263 rodada 8).

    A ordenação de texto do ``sorted`` punha ``/acts/10`` antes de
    ``/acts/2`` no replay do job importado; o índice inteiro devolve a
    ordem do payload. Linhas ``ato`` são sempre ``/acts/N`` (o mapa de
    destinos só atribui o tipo à raiz do ato).
    """
    return int(chave.rsplit('/', 1)[1])


def _linhas_por_chave(extracao):
    return {campo.chave: campo for campo in extracao.campos.all()}


def _rotulo(chave, linhas):
    campo = linhas.get(chave)
    return campo.normalized if campo is not None else None


def _rotulo_efetivo(chave, linhas):
    """Rótulo que DECIDE tipo/número na gravação: ``valor_final``,
    ``normalized`` ou ``raw``.

    P1 (#322 rodada 4): no payload real o rótulo chega com
    ``normalized=None`` e o carimbo no ``raw`` — a linha estrutural do ato
    (``/acts/N``, a que o ``_rotulo`` exibe) só guarda o ``normalized``, e
    ler só ela escondia o rótulo: o ``tipo_sugerido`` decidia sozinho, a
    gravação divergia do ``classificar_atos`` (que lê ``normalized or
    raw``) e a duplicata que a base bloqueava passava. O ``raw`` vive na
    FOLHA ``/acts/N/rotulo`` (linha de conferência, ``SEM_DESTINO``), que
    traz os dois campos do payload.

    P1 (#322 rodada 5): o rótulo CORRIGIDO pelo revisor (``valor_final``)
    vence — sem ele a correção feita na tela era ignorada e a gravação
    decidia pelo carimbo do OCR que ficou no ``normalized``/``raw``.
    ``valor_final`` VAZIO (revisor limpou o campo: ``aplicar_linha``
    grava ``''``) não decide nada — a leitura cai no ``normalized``/``raw``
    de antes.

    P1 (#322 rodada 6): linha DESCARTADA não decide — ``aplicar_linha``
    com ``incluir=False`` preserva o ``valor_final`` da edição e só marca
    ``descartado``; ler o valor sem olhar o status deixava a edição
    descartada vencer e a gravação criava o lançamento que o usuário tinha
    descartado. Descarte PULA o candidato (mesma convenção de
    ``revisao.identidade_parte``): a folha descartada cai na linha
    estrutural e a estrutural descartada cai na folha; as duas
    descartadas não decidem nada.

    Devolve, na folha e, sem ela, na linha estrutural, o primeiro não
    vazio entre ``valor_final``, ``normalized`` e ``raw`` — ``None``
    quando nada existe (o parser devolve ``reconhecido=False`` e o
    ``tipo_sugerido`` decide). A leitura é a MESMA da revisão
    (``revisao.rotulo_efetivo``, #322 rodada 7): uma única regra decide o
    tipo nos dois caminhos.
    """
    return revisao.rotulo_efetivo(chave, linhas)
