# P1 do review Greptile (#322/PR #327): a escolha explícita do revisor
# precisa sobreviver à confirmação do próprio valor sugerido — o
# ``valor_final`` volta nulo (canonico == normalized) e a precedência do
# tipo não via decisão alguma. Aditiva: toda linha existente começa sem
# escolha (default=False), sem data migration.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ia_ocr', '0008_alter_importacaoia_modelo'),
    ]

    operations = [
        migrations.AddField(
            model_name='camposugerido',
            name='escolha_explicita',
            field=models.BooleanField(default=False),
        ),
    ]
