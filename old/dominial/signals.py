"""
Signals Django para processamento automático
"""
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Lancamento
from .services.lancamento_origem_service import LancamentoOrigemService
import logging

logger = logging.getLogger(__name__)

@receiver(post_save, sender=Lancamento)
def processar_origens_automaticas_signal(sender, instance, created, **kwargs):
    """
    Signal para processar origens automaticamente sempre que um lançamento for salvo
    """
    # Só processar se o lançamento tem origem
    if not instance.origem or not instance.origem.strip():
        return
    
    # Só processar se o lançamento tem documento e imóvel
    if not instance.documento or not instance.documento.imovel:
        return
    
    try:
        # Processar origens para criar documentos automáticos
        resultado = LancamentoOrigemService.processar_origens_automaticas(
            instance, instance.origem, instance.documento.imovel
        )
        
        if resultado:
            logger.info(f"Signal: {resultado} (Lançamento {instance.id})")
        
    except Exception as e:
        logger.error(f"Erro ao processar origens automaticamente para lançamento {instance.id}: {e}")
