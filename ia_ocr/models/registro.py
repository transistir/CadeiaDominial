from django.conf import settings
from django.db import models

from .extracao import CampoSugerido
from .job import OcrJob


class PendenciaLimpezaArquivo(models.Model):
    # Sem FK: a intenção é gravada na mesma transação que exclui o
    # DocumentoDigital, antes da remoção física. Ela é removida quando a limpeza
    # conclui e permanece para o suporte somente se a limpeza falhar; nesse
    # momento, o DocumentoDigital já foi excluído.
    documento_digital_id = models.PositiveBigIntegerField()
    documento_id = models.PositiveBigIntegerField(null=True, blank=True)
    caminho_storage = models.CharField(max_length=500)
    criado_em = models.DateTimeField(auto_now_add=True)
    resolvido_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Pendência de limpeza de arquivo'
        verbose_name_plural = 'Pendências de limpeza de arquivo'
        ordering = ['-criado_em']

    def __str__(self):
        # O caminho e o nome do arquivo podem conter PII e não entram no repr.
        return f'Pendência {self.pk} (documento_digital {self.documento_digital_id})'


class ImportacaoIA(models.Model):
    """Vínculo de auditoria entre a revisão importada e o registro gravado (I-6).

    Um vínculo por objeto criado na importação (``unique_together`` modelo +
    objeto_id). As FKs são ``SET_NULL`` de propósito: excluir o PDF apaga o
    job (e com ele extrações e linhas) mas NÃO pode apagar a prova de que o
    lançamento veio da importação assistida — ``documento_digital_id`` é uma
    cópia sem FK (mesmo padrão de ``PendenciaLimpezaArquivo``) e ``pagina``
    sobrevive desnormalizada. O lançamento também pode ser excluído depois:
    o vínculo permanece como rastro.
    """

    MODELO_CHOICES = [
        ('Lancamento', 'Lançamento'),
        ('LancamentoPessoa', 'Pessoa do lançamento'),
        ('LancamentoOrigem', 'Origem de lançamento'),
        ('Documento', 'Documento de origem'),
        ('Pessoas', 'Pessoa'),
        ('Cartorios', 'Cartório'),
    ]

    ocr_job = models.ForeignKey(
        OcrJob, on_delete=models.SET_NULL, null=True,
        related_name='importacoes',
    )
    documento_digital_id = models.PositiveBigIntegerField()
    campo = models.ForeignKey(
        CampoSugerido, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='+',
    )
    pagina = models.PositiveIntegerField(null=True, blank=True)
    modelo = models.CharField(max_length=30, choices=MODELO_CHOICES)
    objeto_id = models.PositiveBigIntegerField()
    lancamento = models.ForeignKey(
        'dominial.Lancamento', on_delete=models.SET_NULL, null=True,
        blank=True, related_name='importacoes_ia',
    )
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
        related_name='+',
    )
    # "Importar e corrigir depois" (#332): avisos informativos do ato no
    # momento do save. Só motivo/rotulo/texto de negócio — nunca PII.
    avisos = models.JSONField(default=list, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Importação assistida (IA)'
        verbose_name_plural = 'Importações assistidas (IA)'
        ordering = ['-criado_em']
        unique_together = ('modelo', 'objeto_id')

    def __str__(self):
        # Sem nome de pessoa/cartório no repr: o __str__ vive em tracebacks.
        return f'{self.modelo} {self.objeto_id} (job {self.ocr_job_id})'
