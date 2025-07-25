# Generated by Django 5.2.3 on 2025-06-21 17:26

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('dominial', '0011_alter_pessoas_cpf'),
    ]

    operations = [
        migrations.AlterField(
            model_name='alteracoes',
            name='area',
            field=models.DecimalField(blank=True, decimal_places=4, max_digits=12, null=True),
        ),
        migrations.AlterField(
            model_name='lancamento',
            name='area',
            field=models.DecimalField(blank=True, decimal_places=4, max_digits=12, null=True),
        ),
        migrations.AlterField(
            model_name='lancamentotipo',
            name='tipo',
            field=models.CharField(choices=[('averbacao', 'Averbação'), ('registro', 'Registro'), ('inicio_matricula', 'Início de Matrícula')], max_length=50),
        ),
    ]
