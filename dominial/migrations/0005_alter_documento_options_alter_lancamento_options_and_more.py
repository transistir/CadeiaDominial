# Generated by Django 5.2.3 on 2025-06-17 19:48

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('dominial', '0004_documentotipo_lancamentotipo_documento_lancamento'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='documento',
            options={'ordering': ['-data'], 'verbose_name': 'Documento', 'verbose_name_plural': 'Documentos'},
        ),
        migrations.AlterModelOptions(
            name='lancamento',
            options={'ordering': ['-data'], 'verbose_name': 'Lançamento', 'verbose_name_plural': 'Lançamentos'},
        ),
        migrations.AlterModelOptions(
            name='lancamentotipo',
            options={},
        ),
        migrations.AddField(
            model_name='lancamentotipo',
            name='requer_detalhes',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='lancamentotipo',
            name='requer_transmissao',
            field=models.BooleanField(default=False),
        ),
        migrations.AlterField(
            model_name='documento',
            name='imovel',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='documentos', to='dominial.imovel'),
        ),
        migrations.AlterField(
            model_name='documentotipo',
            name='id',
            field=models.AutoField(primary_key=True, serialize=False),
        ),
        migrations.AlterField(
            model_name='documentotipo',
            name='tipo',
            field=models.CharField(choices=[('transcricao', 'Transcrição'), ('matricula', 'Matrícula')], max_length=50),
        ),
        migrations.AlterField(
            model_name='lancamento',
            name='documento',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='lancamentos', to='dominial.documento'),
        ),
        migrations.AlterField(
            model_name='lancamentotipo',
            name='id',
            field=models.AutoField(primary_key=True, serialize=False),
        ),
        migrations.AlterField(
            model_name='lancamentotipo',
            name='tipo',
            field=models.CharField(choices=[('transacao', 'Transação'), ('averbacao', 'Averbação'), ('matricula_cadeia', 'Matrícula de Cadeia'), ('registro', 'Registro')], max_length=50),
        ),
    ]
