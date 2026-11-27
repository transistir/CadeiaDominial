"""Bloqueios de negócio por ato na revisão do formulário (#341/#332)."""

from datetime import datetime

from dominial.models import Cartorios, LancamentoTipo

from ..classe_pendencia import eh_bloqueante
from ..formulario import _area_em_outra_unidade

MENSAGEM_AREA_SEM_DECISAO = (
    '❌ A área foi lida em unidade diferente de hectare. Preencha a área em '
    'hectares ou marque o descarte explícito. Nada foi gravado.'
)
MENSAGEM_CARTORIO_NAO_CADASTRADO = (
    "❌ O cartório da transmissão '{nome}' não está cadastrado. Selecione um "
    'cartório da lista ou cadastre-o antes de salvar. Nada foi gravado.'
)
MENSAGEM_CARTORIO_ORIGEM_NAO_CADASTRADO = (
    "❌ O cartório de origem '{nome}' não está cadastrado. Selecione um "
    'cartório da lista ou cadastre-o antes de salvar. Nada foi gravado.'
)
MENSAGEM_INICIO_SEM_ORIGEM = (
    '❌ Informe a origem deste início de matrícula ou marque fim de cadeia / '
    'sem documento anterior. Nada foi gravado.'
)
MENSAGEM_DATA_ABERTURA = (
    '❌ Informe a data do ato de abertura. Nada foi gravado.'
)

MOTIVO_AREA_SEM_DECISAO = 'unidade_area'
MOTIVO_CARTORIO_TRANSMISSAO = 'cartorio_transmissao_nao_cadastrado'
MOTIVO_CARTORIO_ORIGEM = 'cartorio_origem_nao_cadastrado'
MOTIVO_INICIO_SEM_ORIGEM = 'inicio_sem_origem'
MOTIVO_INICIO_SEM_DATA = 'inicio_sem_data'

ROTULO_ORIGEM = 'Origem'
ROTULO_DATA = 'Data'
ROTULO_CARTORIO_TRANSMISSAO = 'Cartório da transmissão'
ROTULO_CARTORIO_ORIGEM = 'Cartório da origem'


def _item(motivo, rotulo, texto, **extras):
    return {
        'motivo': motivo, 'rotulo': rotulo, 'texto': texto, **extras,
    }


def bloqueios_do_post_itens(post, extracao, indice, linhas):
    """Bloqueios do POST como ``{motivo, rotulo, texto}`` (banner #332)."""
    bloqueios = []
    area = _area_em_outra_unidade(
        extracao, int(indice), linhas, f'/acts/{int(indice)}',
    )
    if (
        area is not None
        and not (post.get('area') or '').strip()
        and post.get('descartar_area') != '1'
    ):
        bloqueios.append(_item(
            MOTIVO_AREA_SEM_DECISAO, area['rotulo'], MENSAGEM_AREA_SEM_DECISAO,
            rotulo_descarte=area.get('rotulo_descarte'),
        ))
    nome = _cartorio_da_transmissao_nao_cadastrado(post)
    if nome:
        bloqueios.append(_item(
            MOTIVO_CARTORIO_TRANSMISSAO, ROTULO_CARTORIO_TRANSMISSAO,
            MENSAGEM_CARTORIO_NAO_CADASTRADO.format(nome=nome),
        ))
    for nome_origem in _cartorios_de_origem_nao_cadastrados(post):
        bloqueios.append(_item(
            MOTIVO_CARTORIO_ORIGEM, ROTULO_CARTORIO_ORIGEM,
            MENSAGEM_CARTORIO_ORIGEM_NAO_CADASTRADO.format(nome=nome_origem),
        ))
    if _inicio_sem_origem(post):
        bloqueios.append(_item(
            MOTIVO_INICIO_SEM_ORIGEM, ROTULO_ORIGEM, MENSAGEM_INICIO_SEM_ORIGEM,
        ))
    if _inicio_sem_data(post):
        # A mensagem específica vale só para o início de matrícula; nos
        # demais tipos a falta de data segue a mensagem do service.
        bloqueios.append(_item(
            MOTIVO_INICIO_SEM_DATA, ROTULO_DATA, MENSAGEM_DATA_ABERTURA,
        ))
    return [
        {**item, 'bloqueante': eh_bloqueante(item['motivo'])}
        for item in bloqueios
    ]


def bloqueios_do_post(post, extracao, indice, linhas):
    """Bloqueios avaliados no POST de um ato, sem persistir nada."""
    return [
        item['texto']
        for item in bloqueios_do_post_itens(post, extracao, indice, linhas)
    ]


def bloqueios_do_prefill(prefill):
    """Bloqueios que o GET mostra no banner, sem desabilitar o formulário."""
    form_data = prefill.get('form_data', {})
    if not _tipo_eh_inicio(form_data.get('tipo_lancamento')):
        return []
    bloqueios = []
    if not any(
        _origem_tem_identidade(origem) or origem.get('fim_cadeia')
        for origem in prefill.get('origens_separadas', ())
    ):
        bloqueios.append(_item(
            MOTIVO_INICIO_SEM_ORIGEM, ROTULO_ORIGEM, MENSAGEM_INICIO_SEM_ORIGEM,
        ))
    if not _data_do_post_valida(form_data.get('data')):
        bloqueios.append(_item(
            MOTIVO_INICIO_SEM_DATA, ROTULO_DATA, MENSAGEM_DATA_ABERTURA,
        ))
    return bloqueios


def _cartorio_da_transmissao_nao_cadastrado(post):
    nome = (post.get('cartorio_transmissao_nome') or '').strip()
    if not nome or (post.get('cartorio_transmissao') or '').strip():
        return None
    if Cartorios.objects.filter(nome__iexact=nome).exists():
        return None
    return nome


def _cartorios_de_origem_nao_cadastrados(post):
    """Cartórios de origem que o service criaria ou onde estouraria (#388).

    O nome é consultado CRU (sem strip) com ``iexact``, exatamente como
    ``lancamento_campos_service``: achado único usa o cadastro, zero
    resultados cria um cartório com CNS fictício e mais de um estoura
    ``MultipleObjectsReturned``. Só passa o nome com 1 único cadastro.

    O id preenchido é conferido PRIMEIRO e é bloqueado DE PROPÓSITO quando
    inválido (``ValueError``) ou inexistente (``DoesNotExist``). Nisto o
    bloqueio é mais rígido que o service, que cairia para o nome: um id
    obsoleto vindo da revisão não é confiável para decidir o cadastro.

    Na revisão OCR, barramos o salvamento para impedir a criação indevida
    de cartórios com CNS fictício. NÃO alterar o comportamento do formulário
    manual (o bloqueio vive no caminho da revisão, que é o único que chama
    bloqueios_do_post). NÃO mexer no service para apos_importacao=True
    global: apos_importacao=True também é usado pela importação manual de
    duplicata (dominial/views/duplicata_views.py) e pelo revisar_extras.py;
    mudar o service quebraria o fluxo manual.
    """
    origens = post.getlist('origem_completa[]') or post.getlist('origem_completa')
    ids = post.getlist('cartorio_origem[]') or post.getlist('cartorio_origem')
    nomes = post.getlist('cartorio_origem_nome[]') or post.getlist('cartorio_origem_nome')

    nao_cadastrados = []

    def acrescentar(nome_exibicao):
        if nome_exibicao and nome_exibicao not in nao_cadastrados:
            nao_cadastrados.append(nome_exibicao)

    for i, origem in enumerate(origens):
        if not (origem or '').strip():
            continue
        cid = (ids[i] if i < len(ids) else '').strip()
        nome_cru = nomes[i] if i < len(nomes) else ''
        nome = (nome_cru or '').strip()

        if cid:
            try:
                Cartorios.objects.get(pk=cid)
            except (ValueError, TypeError, Cartorios.DoesNotExist):
                # O id é tentado antes do nome: inválido estoura e inexistente
                # impede o caminho de nome que o service seguiria.
                acrescentar(nome or cid)
            continue

        if not nome:
            continue

        # O service consulta o texto cru; espaço sobrando não casa e vira
        # cartório duplicado. Nome ambíguo estoura no ``get``.
        if Cartorios.objects.filter(nome__iexact=nome_cru).count() != 1:
            acrescentar(nome)

    return nao_cadastrados


def _data_do_post_valida(valor):
    """A MESMA validação de data do service: só ``aaaa-mm-dd`` válido.

    O service grava ``None`` para string fora desse formato (mesmo com
    conteúdo); deixar passar aqui faria o bloqueio de abertura não valer
    para um input não-date como ``18/06/2015``.
    """
    valor = (valor or '').strip()
    if len(valor) != 10 or valor.count('-') != 2:
        return False
    try:
        datetime.strptime(valor, '%Y-%m-%d')
    except ValueError:
        return False
    return True


def _inicio_sem_data(post):
    if not _tipo_eh_inicio(post.get('tipo_lancamento')):
        return False
    return not _data_do_post_valida(post.get('data'))


def _inicio_sem_origem(post):
    if not _tipo_eh_inicio(post.get('tipo_lancamento')):
        return False
    origens = post.getlist('origem_completa[]')
    fim_cadeia = post.getlist('fim_cadeia[]')
    return not any((origem or '').strip() for origem in origens) and not fim_cadeia


def _tipo_eh_inicio(tipo_id):
    if not str(tipo_id or '').strip():
        return False
    return LancamentoTipo.objects.filter(
        pk=tipo_id, tipo='inicio_matricula',
    ).exists()


def _origem_tem_identidade(origem):
    return bool((origem.get('texto') or '').strip())
