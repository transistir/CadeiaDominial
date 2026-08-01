"""Semeia os destacamentos do patrimônio público disponíveis no select do
formulário de lançamento (issue #104): as 27 unidades federativas e as duas
coroas imperiais.

Só essas 29 opções devem aparecer no select. Cadastros anteriores de
destacamento — INCRA, números de matrícula digitados como texto livre — são
DESATIVADOS, nunca apagados: quem quiser um deles de volta é só reativar pelo
admin, sem perder o histórico.

``update_or_create`` por ``nome`` normaliza tipo, classificação e sigla dos 29,
porque bases antigas têm registros com o nome certo e a sigla errada (ex.:
'Estado da Bahia' gravado com sigla 'Estado da Bahia' em vez de 'BA'). Rodar de
novo converge para o mesmo estado.
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

NOMES_COMBINADOS = [nome for nome, _ in DESTACAMENTOS]


def desativar_destacamentos_legados(apps):
    """Tira do select os destacamentos que não foram combinados, preservando o
       registro para o admin reativar se precisar."""
    FimCadeia = apps.get_model('dominial', 'FimCadeia')
    return (
        FimCadeia.objects
        .filter(tipo='destacamento_publico')
        .exclude(nome__in=NOMES_COMBINADOS)
        .update(ativo=False)
    )


def semear_destacamentos(apps, schema_editor):
    FimCadeia = apps.get_model('dominial', 'FimCadeia')
    for nome, sigla in DESTACAMENTOS:
        FimCadeia.objects.update_or_create(
            nome=nome,
            defaults={
                'tipo': 'destacamento_publico',
                'classificacao': 'origem_lidima',
                'sigla': sigla,
                'ativo': True,
            },
        )
    desativar_destacamentos_legados(apps)


def remover_destacamentos(apps, schema_editor):
    """Remove os 29 semeados. As desativações de registros legados não são
       revertidas: não dá para saber quais já estavam inativos antes."""
    FimCadeia = apps.get_model('dominial', 'FimCadeia')
    FimCadeia.objects.filter(
        nome__in=NOMES_COMBINADOS,
        tipo='destacamento_publico',
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('dominial', '0052_add_info_adicional_fim_cadeia'),
    ]

    operations = [
        migrations.RunPython(semear_destacamentos, remover_destacamentos),
    ]
