"""
Modelo para rastreamento de documentos importados de outras cadeias dominiais.
"""

from django.db import models
from django.contrib.auth.models import User


class DocumentoImportado(models.Model):
    """
    Modelo para rastrear documentos que foram importados de outras cadeias dominiais.
    
    Este modelo permite:
    - Identificar quais documentos foram importados
    - Rastrear de qual imóvel foram importados
    - Registrar quem fez a importação e quando
    - Evitar importações duplicadas
    """
    
    documento = models.ForeignKey(
        'Documento',
        on_delete=models.CASCADE,
        verbose_name="Documento",
        help_text="Documento que foi importado"
    )
    
    imovel_origem = models.ForeignKey(
        'Imovel',
        on_delete=models.CASCADE,
        verbose_name="Imóvel de Origem",
        help_text="Imóvel de onde o documento foi importado"
    )
    
    data_importacao = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Data de Importação",
        help_text="Data e hora em que o documento foi importado"
    )
    
    importado_por = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        verbose_name="Importado por",
        help_text="Usuário que fez a importação",
        null=True,
        blank=True
    )
    
    class Meta:
        verbose_name = "Documento Importado"
        verbose_name_plural = "Documentos Importados"
        unique_together = ('documento', 'imovel_origem')
        db_table = 'dominial_documentoimportado'
        ordering = ['-data_importacao']
        
        # Índices para performance
        indexes = [
            models.Index(fields=['documento']),
            models.Index(fields=['imovel_origem']),
            models.Index(fields=['data_importacao']),
            models.Index(fields=['importado_por']),
        ]

    def __str__(self):
        return f"Documento {self.documento.numero} importado de {self.imovel_origem.matricula}"
    
    def get_origem_info(self):
        """
        Retorna informações formatadas sobre a origem do documento.
        
        Returns:
            str: Informações formatadas da origem
        """
        return f"Importado de {self.imovel_origem.matricula} em {self.data_importacao.strftime('%d/%m/%Y %H:%M')}"
    
    def get_importador_info(self):
        """
        Retorna informações sobre quem fez a importação.
        
        Returns:
            str: Nome do usuário que fez a importação
        """
        if self.importado_por:
            return self.importado_por.get_full_name() or self.importado_por.username
        return "Sistema"
    
    @classmethod
    def is_documento_importado(cls, documento, imovel_origem=None):
        """
        Verifica se um documento foi importado.
        
        Args:
            documento: Documento a verificar
            imovel_origem: Imóvel de origem específico (opcional)
            
        Returns:
            bool: True se o documento foi importado
        """
        if imovel_origem:
            return cls.objects.filter(
                documento=documento,
                imovel_origem=imovel_origem
            ).exists()
        else:
            return cls.objects.filter(documento=documento).exists()
    
    @classmethod
    def get_documentos_importados_imovel(cls, imovel_id):
        """
        Obtém todos os documentos importados para um imóvel.
        
        Args:
            imovel_id: ID do imóvel
            
        Returns:
            QuerySet: Documentos importados para o imóvel
        """
        return cls.objects.filter(
            documento__imovel_id=imovel_id
        ).select_related(
            'documento',
            'documento__tipo',
            'documento__cartorio',
            'imovel_origem',
            'importado_por'
        ) 