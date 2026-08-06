"""
Guards de posse para views que modificam dados segregados (issue #132).

O filtro de leitura (``Imovel.objects.for_user(user)``) já impede que um
usuário liste o que não lhe pertence. Estes helpers cobrem o caso em que o
usuário conhece a URL de um imóvel não atribuído: a resposta é 404 — não 403 —
para não revelar a existência do registro.
"""

from functools import wraps

from django.http import Http404

from ..managers import usuario_autenticado, usuario_ve_tudo

MENSAGEM_SEM_ACESSO = 'Imóvel não encontrado ou não atribuído ao seu usuário.'
MENSAGEM_SEM_IMOVEIS = 'Nenhum imóvel atribuído ao seu usuário.'


def usuario_tem_acesso_imovel(user, imovel_id):
    """
    Retorna True se o usuário pode acessar o imóvel informado.

    Aceita tanto um id quanto uma instância de ``Imovel``.
    """
    from ..models import Imovel

    if not usuario_autenticado(user):
        return False
    if usuario_ve_tudo(user):
        return True
    if imovel_id is None:
        return False
    if isinstance(imovel_id, Imovel):
        imovel_id = imovel_id.pk
    return Imovel.objects.filter(pk=imovel_id, usuarios_atribuidos__user=user).exists()


def require_imovel_atribuido(view_func):
    """
    Exige que o usuário tenha o imóvel da URL atribuído.

    Usado nas views cujo imóvel não é resolvido por
    ``get_object_or_404(Imovel.objects.for_user(...))`` no início — tipicamente
    as que repassam ``imovel_id`` direto a um service.
    """

    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        imovel_id = kwargs.get('imovel_id')
        if imovel_id is None and len(args) >= 2:
            # Assinaturas posicionais do tipo view(request, tis_id, imovel_id)
            imovel_id = args[1]
        if not usuario_tem_acesso_imovel(request.user, imovel_id):
            raise Http404(MENSAGEM_SEM_ACESSO)
        return view_func(request, *args, **kwargs)

    return _wrapped
