# Generated by Django 5.2.3 on 2025-06-25 15:12

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('dominial', '0013_alter_lancamento_options_tis_area_tis_estado'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='tis',
            name='estado',
        ),
        migrations.CreateModel(
            name='TIsEstado',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('estado', models.CharField(choices=[('AC', 'Acre'), ('AL', 'Alagoas'), ('AM', 'Amazonas'), ('AP', 'Amapá'), ('BA', 'Bahia'), ('CE', 'Ceará'), ('DF', 'Distrito Federal'), ('ES', 'Espírito Santo'), ('GO', 'Goiás'), ('MA', 'Maranhão'), ('MG', 'Minas Gerais'), ('MS', 'Mato Grosso do Sul'), ('MT', 'Mato Grosso'), ('PA', 'Pará'), ('PB', 'Paraíba'), ('PE', 'Pernambuco'), ('PI', 'Piauí'), ('PR', 'Paraná'), ('RJ', 'Rio de Janeiro'), ('RN', 'Rio Grande do Norte'), ('RO', 'Rondônia'), ('RR', 'Roraima'), ('RS', 'Rio Grande do Sul'), ('SC', 'Santa Catarina'), ('SE', 'Sergipe'), ('SP', 'São Paulo'), ('TO', 'Tocantins')], max_length=2)),
                ('tis', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='estados', to='dominial.tis')),
            ],
            options={
                'verbose_name': 'Estado da TI',
                'verbose_name_plural': 'Estados das TIs',
                'ordering': ['estado'],
                'unique_together': {('tis', 'estado')},
            },
        ),
    ]
