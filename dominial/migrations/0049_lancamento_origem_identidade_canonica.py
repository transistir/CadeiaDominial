"""Protege a identidade canônica das origens estruturadas no banco."""

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


def auditar_lancamentos_origem(apps, schema_editor):
    LancamentoOrigem = apps.get_model('dominial', 'LancamentoOrigem')
    grupos = defaultdict(list)
    impedimentos = []

    for origem in LancamentoOrigem.objects.order_by('pk'):
        try:
            numero = _normalizar(origem.numero, origem.tipo_documento)
        except ValueError as erro:
            impedimentos.append(f'lancamento_origem {origem.pk}: {erro}')
            continue
        grupos[
            (
                origem.lancamento_id,
                origem.tipo_documento,
                numero,
                origem.cartorio_id,
            )
        ].append(origem.pk)

    for chave, ids in grupos.items():
        if len(ids) > 1:
            impedimentos.append(f'identidade_lancamento_origem={chave!r} ids={ids}')

    if impedimentos:
        raise RuntimeError(
            'Migração canônica de LancamentoOrigem interrompida pela auditoria:\n'
            + '\n'.join(impedimentos)
        )


class Migration(migrations.Migration):

    dependencies = [
        ('dominial', '0048_identidade_canonica_gerada'),
    ]

    operations = [
        migrations.RunPython(
            auditar_lancamentos_origem,
            migrations.RunPython.noop,
        ),
        migrations.RemoveConstraint(
            model_name='lancamentoorigem',
            name='unique_lancamento_origem_identidade',
        ),
        migrations.RemoveIndex(
            model_name='lancamentoorigem',
            name='dom_lan_origem_id_idx',
        ),
        migrations.AlterField(
            model_name='lancamentoorigem',
            name='numero',
            field=models.CharField(
                help_text=(
                    'Número informado para a origem; prefixo de apresentação '
                    'é preservado.'
                ),
                max_length=50,
            ),
        ),
        migrations.AddField(
            model_name='lancamentoorigem',
            name='numero_normalizado',
            field=models.GeneratedField(
                db_persist=True,
                expression=_expressao_canonica('numero'),
                output_field=models.CharField(max_length=50),
            ),
        ),
        migrations.AddConstraint(
            model_name='lancamentoorigem',
            constraint=models.UniqueConstraint(
                fields=(
                    'lancamento',
                    'tipo_documento',
                    'numero_normalizado',
                    'cartorio',
                ),
                name='unique_lancamento_origem_identidade',
            ),
        ),
        migrations.AddIndex(
            model_name='lancamentoorigem',
            index=models.Index(
                fields=('tipo_documento', 'numero_normalizado', 'cartorio'),
                name='dom_lan_origem_id_idx',
            ),
        ),
    ]
