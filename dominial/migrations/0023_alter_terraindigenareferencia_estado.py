# Generated by Django 5.2.3 on 2025-07-09 00:40

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('dominial', '0022_alter_pessoas_nome_length'),
    ]

    operations = [
        migrations.AlterField(
            model_name='terraindigenareferencia',
            name='estado',
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
    ]
