"""Reaplica o seed de destacamentos do patrimônio público (issue #104).

A 0053 original usava ``get_or_create``, então em bancos que já a rodaram os
registros antigos ficaram como estavam: 'Incra' e números de matrícula
continuaram ativos no select, e 'Estado da Bahia' manteve a sigla errada
('Estado da Bahia' em vez de 'BA'). A 0053 foi corrigida para
``update_or_create`` + desativação dos legados, mas quem já migrou não a executa
de novo — daí esta migração, que só chama a mesma rotina idempotente.
"""

from importlib import import_module

from django.db import migrations

SEED = import_module(
    'dominial.migrations.0053_seed_fim_cadeia_destacamento_publico'
)


def normalizar(apps, schema_editor):
    SEED.semear_destacamentos(apps, schema_editor)


class Migration(migrations.Migration):

    dependencies = [
        ('dominial', '0053_seed_fim_cadeia_destacamento_publico'),
    ]

    operations = [
        migrations.RunPython(normalizar, migrations.RunPython.noop),
    ]
