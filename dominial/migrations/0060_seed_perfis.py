"""Cria os dois perfis do MVP e classifica grupos legados como equipes (#132)."""

from django.db import migrations


PERFIS = (
    ('Perfil: Editor', False),
    ('Perfil: Administrador', True),
)


def _permissoes_dominial(apps, db_alias):
    """Garante e devolve as permissões padrão usadas pelo admin do app."""

    ContentType = apps.get_model('contenttypes', 'ContentType')
    Permission = apps.get_model('auth', 'Permission')
    permissoes = []

    for model in apps.get_app_config('dominial').get_models():
        content_type, _ = ContentType.objects.using(db_alias).get_or_create(
            app_label='dominial',
            model=model._meta.model_name,
        )
        for action in model._meta.default_permissions:
            permission, _ = Permission.objects.using(db_alias).get_or_create(
                content_type_id=content_type.pk,
                codename=f'{action}_{model._meta.model_name}',
                defaults={'name': f'Can {action} {model._meta.verbose_name}'},
            )
            permissoes.append(permission)

    return permissoes


def seed_perfis(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    GrupoAcesso = apps.get_model('dominial', 'GrupoAcesso')
    db_alias = schema_editor.connection.alias

    # Todo grupo que já existia antes desta migration representa uma equipe.
    grupos_preexistentes = list(Group.objects.using(db_alias).all())
    for group in grupos_preexistentes:
        GrupoAcesso.objects.using(db_alias).get_or_create(
            group_id=group.pk,
            defaults={'tipo': 'equipe'},
        )

    permissoes_admin = _permissoes_dominial(apps, db_alias)
    for nome, eh_administrador in PERFIS:
        group, _ = Group.objects.using(db_alias).get_or_create(name=nome)
        acesso, _ = GrupoAcesso.objects.using(db_alias).get_or_create(
            group_id=group.pk,
            defaults={'tipo': 'perfil', 'protegido': True},
        )
        campos_alterados = []
        if acesso.tipo != 'perfil':
            acesso.tipo = 'perfil'
            campos_alterados.append('tipo')
        if not acesso.protegido:
            acesso.protegido = True
            campos_alterados.append('protegido')
        if campos_alterados:
            acesso.save(update_fields=campos_alterados, using=db_alias)

        if eh_administrador:
            group.permissions.set(permissoes_admin)
        else:
            group.permissions.clear()


class Migration(migrations.Migration):

    dependencies = [
        ('dominial', '0059_userti_groupti_grupoacesso'),
    ]

    operations = [
        migrations.RunPython(seed_perfis, reverse_code=None),
    ]
