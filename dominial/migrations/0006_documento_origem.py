# Generated by Django 5.2.3 on 2025-06-17 20:11

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('dominial', '0005_alter_documento_options_alter_lancamento_options_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='documento',
            name='origem',
            field=models.TextField(blank=True, null=True),
        ),
    ]
