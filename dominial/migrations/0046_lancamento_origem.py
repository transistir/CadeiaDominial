"""Cria a tabela estruturada de origens de lançamento."""

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('dominial', '0045_imovel_cartorio_not_null'),
    ]

    operations = [
        migrations.CreateModel(
            name='LancamentoOrigem',
            fields=[
                (
                    'id',
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name='ID',
                    ),
                ),
                (
                    'indice_origem',
                    models.PositiveIntegerField(
                        help_text='Índice da origem no conjunto original do lançamento.'
                    ),
                ),
                (
                    'tipo_documento',
                    models.CharField(
                        choices=[('matricula', 'Matrícula'), ('transcricao', 'Transcrição')],
                        help_text='Tipo documental da origem.',
                        max_length=20,
                    ),
                ),
                (
                    'numero',
                    models.CharField(
                        help_text='Número canônico da origem, sem prefixo de apresentação.',
                        max_length=50,
                    ),
                ),
                (
                    'livro',
                    models.CharField(
                        blank=True,
                        help_text='Livro associado a esta origem.',
                        max_length=50,
                        null=True,
                    ),
                ),
                (
                    'folha',
                    models.CharField(
                        blank=True,
                        help_text='Folha associada a esta origem.',
                        max_length=50,
                        null=True,
                    ),
                ),
                (
                    'cartorio',
                    models.ForeignKey(
                        help_text='Cartório específico desta origem.',
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name='lancamentos_origem_estruturada',
                        to='dominial.cartorios',
                    ),
                ),
                (
                    'lancamento',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='origens_estruturadas',
                        to='dominial.lancamento',
                    ),
                ),
            ],
            options={
                'verbose_name': 'Origem de Lançamento',
                'verbose_name_plural': 'Origens de Lançamento',
                'ordering': ['lancamento_id', 'indice_origem', 'id'],
                'unique_together': {('lancamento', 'indice_origem')},
                'constraints': [
                    models.UniqueConstraint(
                        fields=['lancamento', 'tipo_documento', 'numero', 'cartorio'],
                        name='unique_lancamento_origem_identidade',
                    ),
                ],
                'indexes': [
                    models.Index(fields=['lancamento', 'indice_origem'], name='dom_lan_origem_idx'),
                    models.Index(fields=['tipo_documento', 'numero', 'cartorio'], name='dom_lan_origem_id_idx'),
                ],
            },
        ),
    ]
