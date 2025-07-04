# Generated by Django 5.2.3 on 2025-06-12 17:21

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='AlteracoesTipo',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False)),
                ('tipo', models.CharField(choices=[('registro', 'Registro'), ('averbacao', 'Averbação'), ('nao_classificado', 'Não Classificado')], max_length=50)),
            ],
        ),
        migrations.CreateModel(
            name='AverbacoesTipo',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False)),
                ('tipo', models.CharField(max_length=100)),
            ],
        ),
        migrations.CreateModel(
            name='Cartorios',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False)),
                ('nome', models.CharField(max_length=100)),
                ('cns', models.CharField(max_length=50, unique=True)),
                ('endereco', models.CharField(blank=True, max_length=255, null=True)),
                ('telefone', models.CharField(blank=True, max_length=15, null=True)),
                ('email', models.EmailField(blank=True, max_length=254, null=True)),
            ],
            options={
                'verbose_name': 'Cartório',
                'verbose_name_plural': 'Cartórios',
            },
        ),
        migrations.CreateModel(
            name='Pessoas',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False)),
                ('nome', models.CharField(max_length=100)),
                ('cpf', models.CharField(max_length=11, unique=True)),
                ('rg', models.CharField(blank=True, max_length=20, null=True)),
                ('data_nascimento', models.DateField(blank=True, null=True)),
                ('email', models.EmailField(blank=True, max_length=254, null=True)),
                ('telefone', models.CharField(blank=True, max_length=15, null=True)),
            ],
            options={
                'verbose_name': 'Pessoa',
                'verbose_name_plural': 'Pessoas',
            },
        ),
        migrations.CreateModel(
            name='RegistroTipo',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False)),
                ('tipo', models.CharField(max_length=100)),
            ],
        ),
        migrations.CreateModel(
            name='TerraIndigenaReferencia',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('codigo', models.CharField(max_length=50, unique=True)),
                ('nome', models.CharField(max_length=255)),
                ('etnia', models.CharField(blank=True, max_length=255, null=True)),
                ('estado', models.CharField(blank=True, max_length=2, null=True)),
                ('municipio', models.CharField(blank=True, max_length=255, null=True)),
                ('area_ha', models.FloatField(blank=True, null=True)),
                ('fase', models.CharField(blank=True, max_length=100, null=True)),
                ('modalidade', models.CharField(blank=True, max_length=100, null=True)),
                ('coordenacao_regional', models.CharField(blank=True, max_length=100, null=True)),
                ('data_regularizada', models.DateField(blank=True, null=True)),
                ('data_homologada', models.DateField(blank=True, null=True)),
                ('data_declarada', models.DateField(blank=True, null=True)),
                ('data_delimitada', models.DateField(blank=True, null=True)),
                ('data_em_estudo', models.DateField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Terra Indígena (Referência)',
                'verbose_name_plural': 'Terras Indígenas (Referência)',
                'ordering': ['nome'],
            },
        ),
        migrations.CreateModel(
            name='Imovel',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False)),
                ('nome', models.CharField(max_length=100)),
                ('matricula', models.CharField(max_length=50, unique=True)),
                ('sncr', models.CharField(max_length=50, unique=True)),
                ('sigef', models.CharField(blank=True, max_length=50, null=True)),
                ('descricao', models.TextField(blank=True, null=True)),
                ('observacoes', models.TextField(blank=True, null=True)),
                ('data_cadastro', models.DateField(auto_now_add=True)),
                ('cartorio', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, to='dominial.cartorios')),
                ('proprietario', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='dominial.pessoas')),
            ],
            options={
                'verbose_name': 'Imóvel',
                'verbose_name_plural': 'Imóveis',
            },
        ),
        migrations.CreateModel(
            name='Alteracoes',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False)),
                ('livro', models.CharField(blank=True, max_length=50, null=True)),
                ('folha', models.CharField(blank=True, max_length=50, null=True)),
                ('data_alteracao', models.DateField(blank=True, null=True)),
                ('titulo', models.CharField(blank=True, max_length=255, null=True)),
                ('livro_origem', models.CharField(blank=True, max_length=50, null=True)),
                ('folha_origem', models.CharField(blank=True, max_length=50, null=True)),
                ('data_origem', models.DateField(blank=True, null=True)),
                ('valor_transacao', models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True)),
                ('area', models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True)),
                ('observacoes', models.TextField(blank=True, null=True)),
                ('data_cadastro', models.DateField(auto_now_add=True)),
                ('tipo_alteracao_id', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='dominial.alteracoestipo')),
                ('averbacao_tipo', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='dominial.averbacoestipo')),
                ('cartorio', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='dominial.cartorios')),
                ('cartorio_origem', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='cartorio_responsavel', to='dominial.cartorios')),
                ('imovel_id', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='dominial.imovel')),
                ('adquirente', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='adquirente', to='dominial.pessoas')),
                ('transmitente', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='transmitente', to='dominial.pessoas')),
                ('registro_tipo', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='dominial.registrotipo')),
            ],
            options={
                'verbose_name': 'Alteração',
                'verbose_name_plural': 'Alterações',
            },
        ),
        migrations.CreateModel(
            name='TIs',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False)),
                ('nome', models.CharField(max_length=100)),
                ('codigo', models.CharField(max_length=50, unique=True)),
                ('etnia', models.CharField(max_length=50)),
                ('data_cadastro', models.DateField(auto_now_add=True)),
                ('terra_referencia', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, to='dominial.terraindigenareferencia')),
            ],
            options={
                'verbose_name': 'TI',
                'verbose_name_plural': 'TIs',
            },
        ),
        migrations.AddField(
            model_name='imovel',
            name='terra_indigena_id',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='dominial.tis'),
        ),
        migrations.CreateModel(
            name='TIs_Imovel',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('imovel', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='imovel', to='dominial.imovel')),
                ('tis_codigo', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='tis_codigo', to='dominial.tis')),
            ],
        ),
    ]
