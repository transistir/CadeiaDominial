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
"""

from django.db import models
from django.db.models import Q


def usuario_ve_tudo(user):
    """Retorna True se o usuário deve ignorar a segregação (superuser)."""
    return bool(user is not None and getattr(user, 'is_superuser', False))


def usuario_autenticado(user):
    """Retorna True se há um usuário autenticado (não anônimo, não None)."""
    return bool(user is not None and getattr(user, 'is_authenticated', False))


class SegregacaoQuerySet(models.QuerySet):
    """QuerySet de ``Imovel`` com filtro de segregação por usuário."""

    def for_user(self, user):
        if not usuario_autenticado(user):
            return self.none()
        if usuario_ve_tudo(user):
            return self
        return self.filter(usuarios_atribuidos__user=user)


class SegregacaoManager(models.Manager.from_queryset(SegregacaoQuerySet)):
    """Manager padrão de ``Imovel``, expondo ``for_user(user)``."""

    pass


def documentos_for_user(user):
    """Documentos visíveis ao usuário (via imóvel atribuído)."""
    from .models import Documento

    if not usuario_autenticado(user):
        return Documento.objects.none()
    if usuario_ve_tudo(user):
        return Documento.objects.all()
    return Documento.objects.filter(imovel__usuarios_atribuidos__user=user)


def lancamentos_for_user(user):
    """Lançamentos visíveis ao usuário (via documento → imóvel atribuído)."""
    from .models import Lancamento

    if not usuario_autenticado(user):
        return Lancamento.objects.none()
    if usuario_ve_tudo(user):
        return Lancamento.objects.all()
    return Lancamento.objects.filter(documento__imovel__usuarios_atribuidos__user=user)


def tis_for_user(user):
    """
    TIs visíveis ao usuário: apenas as que possuem ao menos um imóvel atribuído.

    Superuser vê todas as TIs, inclusive as que ainda não têm imóveis.
    """
    from .models import TIs

    if not usuario_autenticado(user):
        return TIs.objects.none()
    if usuario_ve_tudo(user):
        return TIs.objects.all()
    return TIs.objects.filter(imovel__usuarios_atribuidos__user=user).distinct()


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
    from .models import Pessoas

    if not usuario_autenticado(user):
        return Pessoas.objects.none()
    if usuario_ve_tudo(user):
        return Pessoas.objects.all()
    return Pessoas.objects.filter(
        Q(imovel__usuarios_atribuidos__user=user)
        | Q(transmitente_lancamento__documento__imovel__usuarios_atribuidos__user=user)
        | Q(adquirente_lancamento__documento__imovel__usuarios_atribuidos__user=user)
        | Q(lancamentopessoa__lancamento__documento__imovel__usuarios_atribuidos__user=user)
        | Q(transmitente__imovel_id__usuarios_atribuidos__user=user)
        | Q(adquirente__imovel_id__usuarios_atribuidos__user=user)
    ).distinct()
