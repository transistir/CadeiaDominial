"""
Issue #110 — Soft-delete + UNIQUE parcial em Cartorios.

Adiciona:
  1. Campo deleted_at (soft-delete, padrão AGENTS.md Q2=B)
  2. Índice parcial `WHERE deleted_at IS NULL` (perf admin/autocomplete)
  3. UNIQUE constraint em `cns` vira PARCIAL `WHERE deleted_at IS NULL`
     (evita bomba-relógio: CNS sintético colide com CNS oficial após soft-delete)
  4. Tabela CartorioMergeLog (auditoria irreversível por merge)
"""
from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):

    dependencies = [
        ('dominial', '0056_normaliza_none_textual'),
    ]

    operations = [
        # 1. Campo deleted_at (soft-delete, AGENTS.md Q2=B)
        migrations.AddField(
            model_name='cartorios',
            name='deleted_at',
            field=models.DateTimeField(
                blank=True,
                null=True,
                default=None,
                db_index=True,
                help_text='Soft-delete LGPD. NULL = ativo. Conforme AGENTS.md Q2=B.',
                verbose_name='Soft-delete',
            ),
        ),
        # 2. (removido) Índice parcial cartorio_ativo_idx.
        #    Era redundante com cartorio_cns_ativo_unique — ambos
        #    indexam `WHERE deleted_at IS NULL` na mesma coluna. O
        #    UNIQUE parcial já cria índice implícito. Removido em
        #    revisão PR #136 (achado #2). Como o índice foi criado
        #    em homolog, esta migration faz o DROP correspondente.
        migrations.RemoveIndex(
            model_name='cartorios',
            name='cartorio_ativo_idx',
        ),
        # 3. UNIQUE em cns vira PARCIAL `WHERE deleted_at IS NULL`
        #    O AlterField remove o unique=True (Django gera SQL DROP CONSTRAINT).
        #    Em seguida, AddConstraint cria a nova UniqueConstraint parcial.
        migrations.AlterField(
            model_name='cartorios',
            name='cns',
            field=models.CharField(
                max_length=20,
                help_text='CNS — código CNJ. UNIQUE apenas entre cartórios ativos.',
            ),
        ),
        migrations.AddConstraint(
            model_name='cartorios',
            constraint=models.UniqueConstraint(
                fields=['cns'],
                condition=Q(deleted_at__isnull=True),
                name='cartorio_cns_ativo_unique',
            ),
        ),
        # 4. Tabela de auditoria (irreversível)
        migrations.CreateModel(
            name='CartorioMergeLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('ghost_id', models.IntegerField(
                    help_text='ID do cartório soft-deletado (source do merge)',
                )),
                ('target_id', models.IntegerField(
                    help_text='ID do cartório que recebeu os vínculos',
                )),
                ('fase', models.IntegerField(
                    help_text='Fase do plano: 1 (órfãos), 2 (secundários), 3 (críticos)',
                )),
                ('fk_breakdown_json', models.JSONField(
                    help_text='Contagem de FKs reatribuídas por modelo/campo',
                )),
                ('decisao_csv_sha256', models.CharField(
                    max_length=64,
                    help_text='SHA-256 do decisao.csv usado',
                )),
                ('applied_at', models.DateTimeField(auto_now_add=True)),
                ('applied_by', models.CharField(
                    max_length=200,
                    help_text='Usuário que executou o command (getpass.getuser())',
                )),
                ('git_commit', models.CharField(
                    max_length=40,
                    blank=True,
                    default='',
                    help_text='SHA do commit no momento do apply',
                )),
                ('status', models.CharField(
                    max_length=20,
                    default='SUCCESS',
                    help_text='SUCCESS | SKIPPED_CONFLICT | ERROR',
                )),
                ('detalhes_json', models.JSONField(
                    blank=True,
                    null=True,
                    help_text='Detalhes extras (conflitos, warnings, etc.)',
                )),
            ],
            options={
                'verbose_name': 'Log de Merge de Cartórios',
                'verbose_name_plural': 'Logs de Merge de Cartórios',
                'ordering': ['-applied_at'],
            },
        ),
    ]
