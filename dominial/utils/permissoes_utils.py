"""
Gate de permissão por perfil para ações de produto que não dependem de um
objeto já existente (issue #132, fase 3).

Difere de ``segregacao_utils.py``: aquele módulo decide se um usuário pode
ver/mexer num imóvel que já existe (posse de objeto). Este módulo decide se
um usuário pode executar uma ação de produto que não é escopada por objeto —
hoje, cadastrar uma nova Terra Indígena.
"""

from ..managers import usuario_autenticado

# Mesmo nome usado em `dominial.admin.PERFIS['admin']`. Não importar de
# `admin.py` aqui para não criar uma dependência circular (o admin importa de
# models/managers; um módulo de utils não deve depender do admin). Se o nome
# do grupo mudar, atualizar os dois lugares.
GRUPO_PERFIL_ADMINISTRADOR = 'Perfil: Administrador'


def usuario_pode_criar_ti(user):
    """
    Retorna True se ``user`` pode cadastrar uma nova Terra Indígena.

    Regra (fase 3, F8): usuário autenticado que seja superusuário OU membro
    do grupo protegido "Perfil: Administrador". Anônimo ou None → False.

    Importante: ``is_staff`` isolado NÃO é o critério, mesmo que pareça uma
    aproximação razoável. ``is_staff`` só significa "pode acessar /admin/" e
    pode existir numa conta legada sem qualquer perfil de produto coerente —
    por exemplo, uma conta criada antes da introdução dos grupos de perfil,
    ou uma conta de staff técnico sem responsabilidade de cadastro. Aceitar
    ``is_staff`` aqui deixaria essas contas cadastrarem TI sem que o produto
    tenha decidido isso conscientemente (risco 7 do plano da fase 3). O
    critério correto é o grupo de perfil explícito; a rotina de seed dos
    perfis mantém `is_staff=True` como CONSEQUÊNCIA de pertencer ao grupo
    Administrador, nunca o contrário.
    """
    if not usuario_autenticado(user):
        return False
    if getattr(user, 'is_superuser', False):
        return True
    return user.groups.filter(name=GRUPO_PERFIL_ADMINISTRADOR).exists()
