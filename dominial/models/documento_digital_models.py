from django.db import models
from django.conf import settings


class DocumentoDigital(models.Model):
    documento = models.ForeignKey(
        'Documento',
        on_delete=models.CASCADE,
        related_name='arquivos_digitais'
    )
    arquivo = models.FileField(upload_to='documentos_digitais/%Y/%m/')
    nome_original = models.CharField(max_length=255)
    tipo_mime = models.CharField(max_length=100)
    tamanho_bytes = models.PositiveIntegerField()
    data_upload = models.DateTimeField(auto_now_add=True)
    upload_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT
    )

    class Meta:
        verbose_name = "Documento Digital"
        verbose_name_plural = "Documentos Digitais"
        ordering = ['-data_upload']

    def __str__(self):
        return f"{self.nome_original} ({self.documento})"

    @property
    def tamanho_formatado(self):
        """Retorna tamanho formatado (KB/MB)."""
        if self.tamanho_bytes < 1024:
            return f"{self.tamanho_bytes} B"
        elif self.tamanho_bytes < 1024 * 1024:
            return f"{self.tamanho_bytes / 1024:.1f} KB"
        else:
            return f"{self.tamanho_bytes / (1024 * 1024):.1f} MB"

    @property
    def is_pdf(self):
        return self.tipo_mime == 'application/pdf'

    @property
    def is_imagem(self):
        return self.tipo_mime in ('image/png', 'image/jpeg', 'image/webp')
