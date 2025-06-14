# Generated by Django 5.2.3 on 2025-06-11 19:20

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('dominial', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='TerraIndigenaReferencia',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nome', models.CharField(max_length=200, unique=True)),
                ('codigo', models.CharField(max_length=50, unique=True)),
                ('etnia', models.CharField(max_length=100)),
                ('estado', models.CharField(max_length=2)),
                ('area_ha', models.DecimalField(blank=True, decimal_places=2, max_digits=15, null=True)),
                ('populacao', models.IntegerField(blank=True, null=True)),
                ('data_atualizacao', models.DateField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Terra Indígena de Referência',
                'verbose_name_plural': 'Terras Indígenas de Referência',
                'ordering': ['nome'],
            },
        ),
        migrations.AlterModelOptions(
            name='alteracoes',
            options={'verbose_name': 'Alteração', 'verbose_name_plural': 'Alterações'},
        ),
        migrations.AlterModelOptions(
            name='cartorios',
            options={'verbose_name': 'Cartório', 'verbose_name_plural': 'Cartórios'},
        ),
        migrations.AlterModelOptions(
            name='imovel',
            options={'verbose_name': 'Imóvel', 'verbose_name_plural': 'Imóveis'},
        ),
        migrations.AlterModelOptions(
            name='pessoas',
            options={'verbose_name': 'Pessoa', 'verbose_name_plural': 'Pessoas'},
        ),
        migrations.AlterModelOptions(
            name='tis',
            options={'verbose_name': 'TI', 'verbose_name_plural': 'TIs'},
        ),
        migrations.AddField(
            model_name='tis',
            name='terra_referencia',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, to='dominial.terraindigenareferencia'),
        ),
    ]
