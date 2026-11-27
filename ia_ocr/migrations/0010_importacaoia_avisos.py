from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ia_ocr', '0009_camposugerido_escolha_explicita'),
    ]

    operations = [
        migrations.AddField(
            model_name='importacaoia',
            name='avisos',
            field=models.JSONField(blank=True, default=list),
        ),
    ]
