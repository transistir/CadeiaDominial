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
