"""Estado do formulário de lançamento reconstruído a partir de um POST."""

from types import SimpleNamespace

from dominial.views.lancamento_views import (
    _form_data_do_post, _origens_separadas_do_post,
)

from ..formulario import TEXTO_DA_ORIGEM


# ---------------------------------------------------------------------------
# Estado do formulário a partir de um POST
# ---------------------------------------------------------------------------

def estado_do_formulario(post):
    """``form_data``/origens/partes do POST, pelos helpers do formulário manual.

    É o que o ``novo_lancamento`` faz no re-render de erro (#157/#161): aqui
    serve o rascunho da sessão e o erro do salvar. Os helpers do ``dominial``
    leem ``request.POST``; um objeto com só esse atributo basta.
    """
    pedido = SimpleNamespace(POST=post)
    origens = _origens_separadas_do_post(pedido)
    for origem in origens:
        # O helper manual só conhece número de dígitos puros e cortaria o
        # ``.718`` de ``M42.718`` no input visível; o texto oculto segue
        # inteiro e é ele que vai no POST.
        achado = TEXTO_DA_ORIGEM.match((origem.get('texto') or '').strip())
        if achado:
            origem['tipo_origem'], origem['numero_origem'] = achado.groups()
    return {
        'form_data': _form_data_do_post(pedido),
        'origens_separadas': origens,
        'transmitentes': _pessoas_do_post(post, 'transmitente'),
        'adquirentes': _pessoas_do_post(post, 'adquirente'),
    }


def _pessoas_do_post(post, papel):
    """``[{nome, id}]`` do POST — como o re-render de erro do formulário manual."""
    ids = post.getlist(f'{papel}[]')
    return [
        {'nome': nome.strip(), 'id': ids[posicao] if posicao < len(ids) else ''}
        for posicao, nome in enumerate(post.getlist(f'{papel}_nome[]'))
        if nome.strip()
    ]
