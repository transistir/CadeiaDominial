# P1 do review Greptile (#322/PR #327): a escolha explícita do revisor
# precisa sobreviver à confirmação do próprio valor sugerido — o
# ``valor_final`` volta nulo (canonico == normalized) e a precedência do
# tipo não via decisão alguma.
#
# P1 do review frontier (Codex/Opus, #322/PR #327): sem backfill, a 0009
# perdia as confirmações ANTIGAS. Linhas ``/acts/N/tipo_sugerido`` já
# revisadas com ``status_revisao='aceito'`` (o revisor CONFERIU o card) e
# ``valor_final`` nulo nasciam com ``escolha_explicita=False`` — em
# ``revisao._valor_explicito`` deixavam de contar como decisão e o rótulo
# do OCR ('Av-5') vencia a sugestão confirmada ('registro'): a importação
# gravava averbação onde o revisor aprovou registro. O ``RunPython`` abaixo
# marca a flag nessas linhas: 'aceito' é exatamente o estado que
# ``aplicar_linha`` grava quando o card foi conferido, e 'importado' é o
# estado posterior da linha já importada (``importacao.py``) — os dois são
# decisão do revisor e voltam a valer como fonte única da precedência
# (``_valor_explicito``), que não mudou.

from django.db import migrations, models


def marcar_escolha_confirmada(apps, schema_editor):
    """Backfill P1: confirmações antigas de tipo voltam a ser decisão."""
    CampoSugerido = apps.get_model('ia_ocr', 'CampoSugerido')
    CampoSugerido.objects.filter(
        chave__endswith='/tipo_sugerido',
        status_revisao__in=('aceito', 'importado'),
    ).update(escolha_explicita=True)


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
        # Aditivo e reverso noop: a flag volta ao default=False, estado em
        # que a linha nunca foi confirmada — nada a desfazer além da coluna.
        migrations.RunPython(marcar_escolha_confirmada, migrations.RunPython.noop),
    ]
