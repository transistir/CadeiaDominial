from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('dominial', '0049_lancamento_origem_identidade_canonica'),
    ]

    operations = [
        migrations.AlterField(
            model_name='fimcadeia',
            name='classificacao',
            field=models.CharField(choices=[('origem_lidima', 'Origem Lídima'), ('sem_origem', 'Sem Origem'), ('inconclusa', 'Situação Inconclusa')], max_length=50),
        ),
    ]
