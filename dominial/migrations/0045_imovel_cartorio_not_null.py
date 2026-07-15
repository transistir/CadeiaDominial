"""Torna obrigatório o cartório do imóvel após auditoria explícita."""

from django.db import migrations, models
import django.db.models.deletion


def auditar_cartorios(apps, schema_editor):
    Imovel = apps.get_model('dominial', 'Imovel')
    ids_sem_cartorio = list(
        Imovel.objects.filter(cartorio__isnull=True)
        .order_by('pk')
        .values_list('pk', flat=True)
    )
    if ids_sem_cartorio:
        raise RuntimeError(
            'Migração NOT NULL de Imovel interrompida: existem imóveis sem '
            f'cartório: {ids_sem_cartorio}. '
            'A correção deve ser explícita e auditada antes da migração.'
        )


class Migration(migrations.Migration):

    dependencies = [
        ('dominial', '0044_imovel_identidade_constraint'),
    ]

    operations = [
        migrations.RunPython(auditar_cartorios, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='imovel',
            name='cartorio',
            field=models.ForeignKey(
                help_text='Cartório obrigatório da identidade registral do imóvel.',
                on_delete=django.db.models.deletion.PROTECT,
                to='dominial.cartorios',
            ),
        ),
    ]
