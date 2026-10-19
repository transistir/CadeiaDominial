# Migração da fase de extração/revisão (issue #262 / I-5), escrita à mão.

from django.db import migrations, models
import django.db.models.deletion
from django.db.models import Count, F, Q
from django.conf import settings


def copiar_payload_servico(apps, schema_editor):
    """payload bruto → payload_servico."""
    ExtracaoSugerida = apps.get_model('ia_ocr', 'ExtracaoSugerida')
    db_alias = schema_editor.connection.alias
    ExtracaoSugerida.objects.using(db_alias).update(
        payload_servico=F('payload')
    )


def marcar_campos_legado(apps, schema_editor):
    """Campos preexistentes (sem tipo de valor): o codec I-5 exige a marca."""
    CampoSugerido = apps.get_model('ia_ocr', 'CampoSugerido')
    db_alias = schema_editor.connection.alias
    CampoSugerido.objects.using(db_alias).update(
        tipo_valor='texto',
        requer_revisao=True,
        motivos_revisao=['legado'],
    )


def checar_duplicatas_campo(apps, schema_editor):
    """Nenhuma dupla (extracao, chave) pode existir antes da constraint."""
    CampoSugerido = apps.get_model('ia_ocr', 'CampoSugerido')
    db_alias = schema_editor.connection.alias
    duplicatas = (
        CampoSugerido.objects.using(db_alias)
        .values('extracao_id', 'chave')
        .annotate(total=Count('pk'))
        .filter(total__gt=1)
        .count()
    )
    if duplicatas:
        # Só a contagem na mensagem: chave é estrutura, valor é PII.
        raise RuntimeError(
            f'{duplicatas} par(es) (extracao, chave) duplicados: não é '
            'possível aplicar uniq_campo_por_extracao_chave.'
        )


def noop(apps, schema_editor):
    pass


def reverso_raw_normalized(apps, schema_editor):
    """Ao voltar para o NOT NULL, NULL vira '' (estado da 0004)."""
    CampoSugerido = apps.get_model('ia_ocr', 'CampoSugerido')
    db_alias = schema_editor.connection.alias
    CampoSugerido.objects.using(db_alias).filter(raw__isnull=True).update(raw='')
    CampoSugerido.objects.using(db_alias).filter(
        normalized__isnull=True
    ).update(normalized='')


class Migration(migrations.Migration):
    # Não-atômica: no Postgres, o RunPython de reversão (NULL->'') roda antes
    # dos AlterField de volta para NOT NULL na mesma transação e provoca
    # 'cannot ALTER TABLE ... because it has pending trigger events'.

    atomic = False

    dependencies = [
        # Mesmo raciocínio de ia_ocr/migrations/0001_initial.py:14-23: as
        # tabelas dominial necessárias (Pessoas, Cartorios) nascem na
        # 0001_initial, bastando essa dependência. Dependendo da última do
        # dominial, os testes de rollback histórico (dominial/tests/
        # migration_utils.py) faria a ia_ocr entrar no plano fake do dominial
        # e suas tabelas com FK pendurada seriam órfãs no flush do
        # TransactionTestCase.
        ('ia_ocr', '0005_paginaocr_versao'),
        ('dominial', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='ocrjob',
            name='extracao_reserva',
            field=models.UUIDField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='ocrjob',
            name='extracao_reservada_ate',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='extracaosugerida',
            name='payload_servico',
            # Entra nullable: a troca para NOT NULL fica para depois da cópia.
            field=models.JSONField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='extracaosugerida',
            name='solicitada_por',
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='+',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name='extracaosugerida',
            name='finalizada_em',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='extracaosugerida',
            name='finalizada_por',
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='+',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.RunPython(copiar_payload_servico, noop),
        migrations.AddField(
            model_name='camposugerido',
            name='tipo_valor',
            field=models.CharField(
                choices=[
                    ('texto', 'Texto'),
                    ('data', 'Data'),
                    ('decimal', 'Decimal'),
                    ('area', 'Área'),
                    ('booleano', 'Booleano'),
                    ('enum', 'Enum'),
                    ('cartorio', 'Cartório'),
                    ('parte', 'Parte'),
                    ('ato', 'Ato'),
                ],
                default='texto',
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='camposugerido',
            name='motivos_revisao',
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name='camposugerido',
            name='match_candidatos',
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name='camposugerido',
            name='pessoa_escolhida',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='+',
                to='dominial.pessoas',
            ),
        ),
        migrations.AddField(
            model_name='camposugerido',
            name='cartorio_escolhido',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='+',
                to='dominial.cartorios',
            ),
        ),
        migrations.AddField(
            model_name='camposugerido',
            name='criar_novo',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='camposugerido',
            name='area_convertida',
            field=models.BooleanField(default=False),
        ),
        migrations.RunPython(marcar_campos_legado, noop),
        migrations.RunPython(checar_duplicatas_campo, noop),
        # Decisão #290/16-10 (#262): o serviço devolve o texto CORRIGIDO —
        # o usuário não confirma mais o texto do OCR. O texto corrigido é
        # guardado separado do original e o job persiste o dpi do OCR
        # (para converter bbox em coordenada de PDF).
        migrations.AddField(
            model_name='ocrjob',
            name='dpi',
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='paginaocr',
            name='texto_corrigido',
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='paginaocr',
            name='corrigido_em',
            field=models.DateTimeField(blank=True, null=True),
        ),
        # Decisão #290/17-10 (#262): a evidência guarda o bbox do trecho em
        # pixels do OCR ([x0, y0, x1, y1] ou NULL); a conversão para ponto
        # de PDF é do template (usa o dpi persistido no job).
        migrations.AddField(
            model_name='camposugerido',
            name='evidencia_bbox',
            field=models.JSONField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='extracaosugerida',
            name='payload_servico',
            field=models.JSONField(),
        ),
        migrations.AlterField(
            model_name='camposugerido',
            name='raw',
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='camposugerido',
            name='normalized',
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddConstraint(
            model_name='extracaosugerida',
            constraint=models.UniqueConstraint(
                condition=Q(finalizada_em__isnull=False),
                fields=['ocr_job'],
                name='uniq_extracao_finalizada_por_job',
            ),
        ),
        migrations.AddConstraint(
            model_name='camposugerido',
            constraint=models.UniqueConstraint(
                fields=['extracao', 'chave'],
                name='uniq_campo_por_extracao_chave',
            ),
        ),
        # Depois dos AlterField de raw/normalized: no desfaça (ordem
        # inversa) este RunPython roda ANTES deles, preenchendo NULL com ''
        # antes da volta ao NOT NULL.
        migrations.RunPython(noop, reverso_raw_normalized),
    ]
