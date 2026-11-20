"""Bloqueios de negócio por ato na revisão do formulário (#341/#332)."""

from dominial.models import Cartorios, LancamentoTipo

from ..formulario import area_exige_decisao

MENSAGEM_AREA_SEM_DECISAO = (
    '❌ A área foi lida em unidade diferente de hectare. Preencha a área em '
    'hectares ou marque o descarte explícito. Nada foi gravado.'
)
MENSAGEM_CARTORIO_NAO_CADASTRADO = (
    "❌ O cartório da transmissão '{nome}' não está cadastrado. Selecione um "
    'cartório da lista ou cadastre-o antes de salvar. Nada foi gravado.'
)
MENSAGEM_INICIO_SEM_ORIGEM = (
    '❌ Informe a origem deste início de matrícula ou marque fim de cadeia / '
    'sem documento anterior. Nada foi gravado.'
)


def bloqueios_do_post(post, extracao, indice, linhas):
    """Bloqueios avaliados no POST de um ato, sem persistir nada."""
    bloqueios = []
    if (
        area_exige_decisao(extracao, indice, linhas)
        and not (post.get('area') or '').strip()
        and post.get('descartar_area') != '1'
    ):
        bloqueios.append(MENSAGEM_AREA_SEM_DECISAO)
    nome = _cartorio_da_transmissao_nao_cadastrado(post)
    if nome:
        bloqueios.append(MENSAGEM_CARTORIO_NAO_CADASTRADO.format(nome=nome))
    if _inicio_sem_origem(post):
        bloqueios.append(MENSAGEM_INICIO_SEM_ORIGEM)
    return bloqueios


def bloqueios_do_prefill(prefill):
    """Bloqueios que o GET mostra no banner, sem desabilitar o formulário."""
    form_data = prefill.get('form_data', {})
    if _tipo_eh_inicio(form_data.get('tipo_lancamento')) and not any(
        _origem_tem_identidade(origem) or origem.get('fim_cadeia')
        for origem in prefill.get('origens_separadas', ())
    ):
        return [MENSAGEM_INICIO_SEM_ORIGEM]
    return []


def _cartorio_da_transmissao_nao_cadastrado(post):
    nome = (post.get('cartorio_transmissao_nome') or '').strip()
    if not nome or (post.get('cartorio_transmissao') or '').strip():
        return None
    if Cartorios.objects.filter(nome__iexact=nome).exists():
        return None
    return nome


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
