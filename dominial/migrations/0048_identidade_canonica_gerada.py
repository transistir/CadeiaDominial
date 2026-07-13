"""Protege a identidade pela representação canônica gerada no banco."""

from collections import defaultdict

from django.db import migrations, models
from django.db.models.functions import Substr, Trim, Upper
from django.db.models.lookups import In


def _expressao_canonica(nome_campo):
    numero_limpo = Trim(models.F(nome_campo))
    primeiro_caractere = Upper(Substr(numero_limpo, 1, 1))
    return models.Case(
        models.When(
            In(
                primeiro_caractere,
                [models.Value('M'), models.Value('T')],
            ),
            then=Trim(Substr(numero_limpo, 2)),
        ),
        default=numero_limpo,
        output_field=models.CharField(max_length=50),
    )


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


def auditar_identidades_canonicas(apps, schema_editor):
    Documento = apps.get_model('dominial', 'Documento')
    Imovel = apps.get_model('dominial', 'Imovel')
    impedimentos = []

    grupos_documentos = defaultdict(list)
    for documento in Documento.objects.select_related('tipo').order_by('pk'):
        try:
            numero = _normalizar(documento.numero, documento.tipo.tipo)
        except ValueError as erro:
            impedimentos.append(f'documento {documento.pk}: {erro}')
            continue
        grupos_documentos[
            (documento.tipo.tipo, numero, documento.cartorio_id)
        ].append(documento.pk)

    for chave, ids in grupos_documentos.items():
        if len(ids) > 1:
            impedimentos.append(f'identidade_documento={chave!r} ids={ids}')

    grupos_imoveis = defaultdict(list)
    for imovel in Imovel.objects.order_by('pk'):
        try:
            numero = _normalizar(
                imovel.matricula,
                imovel.tipo_documento_principal,
            )
        except ValueError as erro:
            impedimentos.append(f'imovel {imovel.pk}: {erro}')
            continue
        grupos_imoveis[
            (imovel.tipo_documento_principal, numero, imovel.cartorio_id)
        ].append(imovel.pk)

    for chave, ids in grupos_imoveis.items():
        if len(ids) > 1:
            impedimentos.append(f'identidade_imovel={chave!r} ids={ids}')

    if impedimentos:
        raise RuntimeError(
            'Migração canônica interrompida pela auditoria de identidade:\n'
            + '\n'.join(impedimentos)
        )


class Migration(migrations.Migration):

    dependencies = [
        ('dominial', '0047_alter_lancamentoorigem_id'),
    ]

    operations = [
        migrations.RunPython(
            auditar_identidades_canonicas,
            migrations.RunPython.noop,
        ),
        migrations.AlterUniqueTogether(
            name='documento',
            unique_together=set(),
        ),
        migrations.RemoveConstraint(
            model_name='imovel',
            name='unique_imovel_identidade_registral',
        ),
        migrations.AddField(
            model_name='documento',
            name='numero_normalizado',
            field=models.GeneratedField(
                db_persist=True,
                expression=_expressao_canonica('numero'),
                output_field=models.CharField(max_length=50),
            ),
        ),
        migrations.AddField(
            model_name='imovel',
            name='matricula_normalizada',
            field=models.GeneratedField(
                db_persist=True,
                expression=_expressao_canonica('matricula'),
                output_field=models.CharField(max_length=50),
            ),
        ),
        migrations.AddConstraint(
            model_name='documento',
            constraint=models.UniqueConstraint(
                fields=('tipo', 'numero_normalizado', 'cartorio'),
                name='unique_documento_identidade_canonica',
            ),
        ),
        migrations.AddConstraint(
            model_name='imovel',
            constraint=models.UniqueConstraint(
                fields=(
                    'tipo_documento_principal',
                    'matricula_normalizada',
                    'cartorio',
                ),
                name='unique_imovel_identidade_registral',
            ),
        ),
    ]
