"""Inclui o tipo na identidade única do documento principal do imóvel."""

from collections import defaultdict

from django.db import migrations, models


def _normalizar(numero, tipo):
    if not isinstance(numero, str) or not numero.strip():
        raise ValueError('número vazio ou inválido')
    if tipo not in {'matricula', 'transcricao'}:
        raise ValueError(f'tipo inválido: {tipo!r}')

    numero = numero.strip()
    prefixo = numero[0].upper()
    esperado = 'M' if tipo == 'matricula' else 'T'
    if prefixo in {'M', 'T'}:
        if prefixo != esperado:
            raise ValueError(
                f'prefixo {prefixo!r} incompatível com tipo {tipo!r}'
            )
        numero = numero[1:].strip()
    if not numero:
        raise ValueError('número contém apenas o prefixo')
    return numero


def auditar_identidades(apps, schema_editor):
    Imovel = apps.get_model('dominial', 'Imovel')
    grupos = defaultdict(list)
    invalidos = []

    for imovel in Imovel.objects.order_by('pk'):
        try:
            numero = _normalizar(
                imovel.matricula,
                imovel.tipo_documento_principal,
            )
        except ValueError as erro:
            invalidos.append(f'imovel {imovel.pk}: {erro}')
            continue

        # A obrigatoriedade do cartório pertence às T19/T20. Até lá, NULL não
        # participa de conflito de unicidade no PostgreSQL.
        if imovel.cartorio_id:
            chave = (
                imovel.tipo_documento_principal,
                numero,
                imovel.cartorio_id,
            )
            grupos[chave].append(imovel.pk)

    conflitos = [
        f'identidade={chave!r} imoveis={ids}'
        for chave, ids in grupos.items()
        if len(ids) > 1
    ]
    if invalidos or conflitos:
        raise RuntimeError(
            'Migração de Imovel interrompida pela auditoria de identidade:\n'
            + '\n'.join(invalidos + conflitos)
        )


def auditar_reversao(apps, schema_editor):
    Imovel = apps.get_model('dominial', 'Imovel')
    grupos = defaultdict(list)
    for imovel in Imovel.objects.order_by('pk'):
        if imovel.cartorio_id:
            grupos[(imovel.matricula, imovel.cartorio_id)].append(imovel.pk)

    conflitos = [
        f'matricula_cartorio={chave!r} imoveis={ids}'
        for chave, ids in grupos.items()
        if len(ids) > 1
    ]
    if conflitos:
        raise RuntimeError(
            'Reversão de Imovel interrompida: a constraint antiga '
            '(matricula, cartorio) não comporta os dados atuais:\n'
            + '\n'.join(conflitos)
        )


class Migration(migrations.Migration):

    dependencies = [
        ('dominial', '0043_documento_identidade_constraint'),
    ]

    operations = [
        migrations.RunPython(auditar_identidades, migrations.RunPython.noop),
        migrations.RemoveConstraint(
            model_name='imovel',
            name='unique_matricula_por_cartorio',
        ),
        migrations.AddConstraint(
            model_name='imovel',
            constraint=models.UniqueConstraint(
                fields=(
                    'tipo_documento_principal',
                    'matricula',
                    'cartorio',
                ),
                name='unique_imovel_identidade_registral',
            ),
        ),
        migrations.RunPython(migrations.RunPython.noop, auditar_reversao),
    ]
