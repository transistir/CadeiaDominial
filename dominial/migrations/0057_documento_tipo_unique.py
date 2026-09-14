"""Garante uma única linha por tipo semântico de documento."""

from django.db import migrations, models
from django.db.models import Count


def auditar_documento_tipo_duplicado(apps, schema_editor):
    DocumentoTipo = apps.get_model('dominial', 'DocumentoTipo')
    db_alias = schema_editor.connection.alias
    duplicatas = list(
        DocumentoTipo.objects.using(db_alias)
        .values('tipo')
        .annotate(total=Count('id'))
        .filter(total__gt=1)
        .order_by('tipo')
    )
    if duplicatas:
        detalhes = ', '.join(
            f"{item['tipo']!r}: {item['total']} registros"
            for item in duplicatas
        )
        raise RuntimeError(
            'Migração 0057 interrompida: existem tipos de documento '
            f'duplicados ({detalhes}). Faça o saneamento manual e peça '
            'orientação antes de executar novamente; nenhum registro foi unido.'
        )


class Migration(migrations.Migration):
    dependencies = [
        ('dominial', '0056_normaliza_none_textual'),
    ]

    operations = [
        migrations.RunPython(
            auditar_documento_tipo_duplicado,
            migrations.RunPython.noop,
        ),
        migrations.AddConstraint(
            model_name='documentotipo',
            constraint=models.UniqueConstraint(
                fields=('tipo',),
                name='unique_documento_tipo_tipo',
            ),
        ),
    ]
