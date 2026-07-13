"""Troca a unicidade parcial de Documento pela identidade registral completa."""

from collections import defaultdict

from django.db import migrations


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
    Documento = apps.get_model('dominial', 'Documento')
    grupos = defaultdict(list)
    invalidos = []

    documentos = Documento.objects.select_related('tipo').order_by('pk')
    for documento in documentos:
        if not documento.cartorio_id:
            invalidos.append(f'documento {documento.pk}: sem cartório')
            continue
        try:
            numero = _normalizar(documento.numero, documento.tipo.tipo)
        except ValueError as erro:
            invalidos.append(f'documento {documento.pk}: {erro}')
            continue
        grupos[(documento.tipo.tipo, numero, documento.cartorio_id)].append(
            documento.pk
        )

    conflitos = [
        f'identidade={chave!r} documentos={ids}'
        for chave, ids in grupos.items()
        if len(ids) > 1
    ]
    if invalidos or conflitos:
        detalhes = '\n'.join(invalidos + conflitos)
        raise RuntimeError(
            'Migração de Documento interrompida pela auditoria de identidade:\n'
            f'{detalhes}\n'
            'Execute auditar_identidade_documentos antes de tentar novamente.'
        )


def auditar_reversao(apps, schema_editor):
    Documento = apps.get_model('dominial', 'Documento')
    grupos = defaultdict(list)
    for documento in Documento.objects.order_by('pk'):
        grupos[(documento.numero, documento.cartorio_id)].append(documento.pk)

    conflitos = [
        f'numero_cartorio={chave!r} documentos={ids}'
        for chave, ids in grupos.items()
        if len(ids) > 1
    ]
    if conflitos:
        raise RuntimeError(
            'Reversão de Documento interrompida: a constraint antiga '
            '(numero, cartorio) não comporta os dados atuais:\n'
            + '\n'.join(conflitos)
        )


class Migration(migrations.Migration):

    dependencies = [
        ('dominial', '0042_fix_matricula_unique_constraint'),
    ]

    operations = [
        migrations.RunPython(auditar_identidades, migrations.RunPython.noop),
        migrations.AlterUniqueTogether(
            name='documento',
            unique_together={('tipo', 'numero', 'cartorio')},
        ),
        # Na reversão esta auditoria roda antes de restaurar a constraint antiga.
        migrations.RunPython(migrations.RunPython.noop, auditar_reversao),
    ]
