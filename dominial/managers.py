"""
Managers e helpers de segregação de dados por usuário (issue #132).

Regra única de autorização:
- ``is_superuser`` enxerga todos os registros (bypass).
- Usuário comum autenticado enxerga apenas os imóveis atribuídos a ele via
  ``UserImovel``, e — por herança de FK — apenas os documentos e lançamentos
  desses imóveis.
- Usuário anônimo (ou ``None``) não enxerga nada.

``Cartorios`` e ``Pessoas`` são tabelas de referência GLOBAL para o app: os
autocompletes precisam oferecer qualquer cartório/pessoa já cadastrado, senão
o usuário recria registros duplicados. O admin é o caso oposto — lá a listagem
de ``Pessoas`` é um cadastro de PII navegável, e por isso é escopada por
``pessoas_for_user`` (ver ``PessoasAdmin``).

O filtro em si é definido em um único lugar (``Imovel.objects.for_user``); os
helpers de documentos, lançamentos, TIs e pessoas abaixo derivam dele.
"""

from django.db import models
from django.db.models import Q


def usuario_ve_tudo(user):
    """Retorna True se o usuário deve ignorar a segregação (superuser)."""
    return bool(user is not None and getattr(user, 'is_superuser', False))


def usuario_autenticado(user):
    """Retorna True se há um usuário autenticado (não anônimo, não None)."""
    return bool(user is not None and getattr(user, 'is_authenticated', False))


def imoveis_diretos_ids(user):
    """
    PKs dos imóveis atribuídos um-a-um ao usuário, como subquery.

    LEGADO: a atribuição por imóvel (``UserImovel``) sai da UI e é migrada para
    nível de TI numa fase posterior da issue #132; este termo permanece como
    rede de rollback até lá.
    """
    from .models import UserImovel

    return UserImovel.objects.filter(user=user).values('imovel_id')


class SegregacaoQuerySet(models.QuerySet):
    """QuerySet de ``Imovel`` com filtro de segregação por usuário."""

    def for_user(self, user):
        if not usuario_autenticado(user):
            return self.none()
        if usuario_ve_tudo(user):
            return self
        return self.filter(pk__in=imoveis_diretos_ids(user))


class SegregacaoManager(models.Manager.from_queryset(SegregacaoQuerySet)):
    """Manager padrão de ``Imovel``, expondo ``for_user(user)``."""

    pass


def documentos_for_user(user):
    """Documentos visíveis ao usuário (via imóvel atribuído)."""
    from .models import Documento, Imovel

    if not usuario_autenticado(user):
        return Documento.objects.none()
    if usuario_ve_tudo(user):
        return Documento.objects.all()
    return Documento.objects.filter(imovel__in=Imovel.objects.for_user(user))


def lancamentos_for_user(user):
    """Lançamentos visíveis ao usuário (via documento → imóvel atribuído)."""
    from .models import Imovel, Lancamento

    if not usuario_autenticado(user):
        return Lancamento.objects.none()
    if usuario_ve_tudo(user):
        return Lancamento.objects.all()
    return Lancamento.objects.filter(documento__imovel__in=Imovel.objects.for_user(user))


def tis_for_user(user):
    """
    TIs visíveis ao usuário: apenas as que possuem ao menos um imóvel atribuído.

    Superuser vê todas as TIs, inclusive as que ainda não têm imóveis.
    """
    from .models import Imovel, TIs

    if not usuario_autenticado(user):
        return TIs.objects.none()
    if usuario_ve_tudo(user):
        return TIs.objects.all()
    return TIs.objects.filter(imovel__in=Imovel.objects.for_user(user)).distinct()


def pessoas_for_user(user):
    """
    Pessoas ligadas a algum imóvel atribuído ao usuário.

    Uso restrito ao admin: ``Pessoas`` guarda CPF/RG/data de nascimento, e a
    listagem do admin é um cadastro navegável — sem escopo, qualquer staff
    lê o PII do sistema inteiro. Os autocompletes do app continuam globais
    (ver docstring do módulo).

    Um vínculo conta em qualquer uma das pontas: proprietário do imóvel, parte
    de um lançamento (FK direta ou ``LancamentoPessoa``) ou parte de uma
    alteração.
    """
    from .models import Imovel, Pessoas

    if not usuario_autenticado(user):
        return Pessoas.objects.none()
    if usuario_ve_tudo(user):
        return Pessoas.objects.all()
    imoveis = Imovel.objects.for_user(user)
    return Pessoas.objects.filter(
        Q(imovel__in=imoveis)
        | Q(transmitente_lancamento__documento__imovel__in=imoveis)
        | Q(adquirente_lancamento__documento__imovel__in=imoveis)
        | Q(lancamentopessoa__lancamento__documento__imovel__in=imoveis)
        | Q(transmitente__imovel_id__in=imoveis)
        | Q(adquirente__imovel_id__in=imoveis)
    ).distinct()
