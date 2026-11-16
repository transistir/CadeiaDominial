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
#
# P1 estendido (review Opus 5, rodada 10): revisões já FINALIZADAS cujo
# card de tipo nunca foi conferido também são decisão. ``requer_revisao``
# falso não virava pendência e a finalização (``services.py``) só grava
# ``finalizada_em`` — mas em revisão finalizada o ``normalized`` é o que o
# revisor VIU e aprovou antes do deploy (no ``develop`` o tipo vinha dele);
# sem a flag, o rótulo do OCR passaria a vencer depois do deploy. Linha
# ``descartado`` continua não decidindo em nenhum dos dois caminhos.

from django.db import migrations, models
from django.db.models import Q


def marcar_escolha_confirmada(apps, schema_editor):
    """Backfill P1: confirmações antigas de tipo voltam a ser decisão.

    'aceito'/'importado' é decisão gravada; revisão finalizada
    (``extracao.finalizada_em``) é decisão implícita — o revisor fechou
    vendo o ``normalized``. Descartada nunca decide.
    """
    CampoSugerido = apps.get_model('ia_ocr', 'CampoSugerido')
    CampoSugerido.objects.filter(
        Q(chave__endswith='/tipo_sugerido'),
        ~Q(status_revisao='descartado'),
        Q(status_revisao__in=('aceito', 'importado'))
        | Q(extracao__finalizada_em__isnull=False),
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
