"""Semeia os destacamentos do patrimônio público disponíveis no select do
formulário de lançamento (issue #104): as 27 unidades federativas e as duas
coroas imperiais.

Idempotente: usa ``get_or_create`` por ``nome``, então rodar de novo não
duplica nem sobrescreve registros já editados pelo admin.
"""

from django.db import migrations

ESTADOS = [
    ('Estado do Acre', 'AC'),
    ('Estado de Alagoas', 'AL'),
    ('Estado do Amazonas', 'AM'),
    ('Estado do Amapá', 'AP'),
    ('Estado da Bahia', 'BA'),
    ('Estado do Ceará', 'CE'),
    ('Distrito Federal', 'DF'),
    ('Estado do Espírito Santo', 'ES'),
    ('Estado de Goiás', 'GO'),
    ('Estado do Maranhão', 'MA'),
    ('Estado de Minas Gerais', 'MG'),
    ('Estado do Mato Grosso do Sul', 'MS'),
    ('Estado do Mato Grosso', 'MT'),
    ('Estado do Pará', 'PA'),
    ('Estado da Paraíba', 'PB'),
    ('Estado de Pernambuco', 'PE'),
    ('Estado do Piauí', 'PI'),
    ('Estado do Paraná', 'PR'),
    ('Estado do Rio de Janeiro', 'RJ'),
    ('Estado do Rio Grande do Norte', 'RN'),
    ('Estado de Rondônia', 'RO'),
    ('Estado de Roraima', 'RR'),
    ('Estado do Rio Grande do Sul', 'RS'),
    ('Estado de Santa Catarina', 'SC'),
    ('Estado de Sergipe', 'SE'),
    ('Estado de São Paulo', 'SP'),
    ('Estado do Tocantins', 'TO'),
]

COROAS = [
    ('Coroa do Império Brasileiro', 'IMP-BR'),
    ('Coroa do Império Português', 'IMP-PT'),
]

DESTACAMENTOS = ESTADOS + COROAS


def semear_destacamentos(apps, schema_editor):
    FimCadeia = apps.get_model('dominial', 'FimCadeia')
    for nome, sigla in DESTACAMENTOS:
        FimCadeia.objects.get_or_create(
            nome=nome,
            defaults={
                'tipo': 'destacamento_publico',
                'classificacao': 'origem_lidima',
                'sigla': sigla,
                'ativo': True,
            },
        )


def remover_destacamentos(apps, schema_editor):
    FimCadeia = apps.get_model('dominial', 'FimCadeia')
    FimCadeia.objects.filter(
        nome__in=[nome for nome, _ in DESTACAMENTOS],
        tipo='destacamento_publico',
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('dominial', '0052_add_info_adicional_fim_cadeia'),
    ]

    operations = [
        migrations.RunPython(semear_destacamentos, remover_destacamentos),
    ]
