"""
Data migration defensiva (#132).

Atribui todos os imóveis existentes a cada superuser. Não é necessária para o
acesso funcionar hoje — ``for_user()`` já bypassa a segregação para
``is_superuser`` — mas garante que, se o flag de superuser for removido de
alguém no futuro, essa pessoa não perca acesso ao acervo existente.
"""

from django.db import migrations


def atribuir_imoveis_aos_superusers(apps, schema_editor):
    User = apps.get_model('auth', 'User')
    Imovel = apps.get_model('dominial', 'Imovel')
    UserImovel = apps.get_model('dominial', 'UserImovel')

    superusers = list(User.objects.filter(is_superuser=True))
    if not superusers:
        return

    imovel_ids = list(Imovel.objects.values_list('id', flat=True))
    if not imovel_ids:
        return

    existentes = set(
        UserImovel.objects.filter(user__in=superusers).values_list('user_id', 'imovel_id')
    )

    UserImovel.objects.bulk_create([
        UserImovel(user_id=user.id, imovel_id=imovel_id, atribuido_por_id=user.id)
        for user in superusers
        for imovel_id in imovel_ids
        if (user.id, imovel_id) not in existentes
    ])


def remover_atribuicoes_dos_superusers(apps, schema_editor):
    User = apps.get_model('auth', 'User')
    UserImovel = apps.get_model('dominial', 'UserImovel')

    UserImovel.objects.filter(user__in=User.objects.filter(is_superuser=True)).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('dominial', '0057_userimovel'),
        ('auth', '0012_alter_user_first_name_max_length'),
    ]

    operations = [
        migrations.RunPython(
            atribuir_imoveis_aos_superusers,
            remover_atribuicoes_dos_superusers,
        ),
    ]
