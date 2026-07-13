from django.core.management import call_command
from django.db import transaction
from ..models import Cartorios
import logging

logger = logging.getLogger(__name__)

class CartorioVerificacaoService:
    """
    Serviço para verificação e importação automática de cartórios
    """
    
    @staticmethod
    def verificar_cartorios_estado(estado):
        """
        Verifica se existem cartórios para um estado específico
        
        Args:
            estado (str): Sigla do estado
            
        Returns:
            dict: Dicionário com informações sobre a existência de cartórios
        """
        try:
            logger.info(f"Verificando cartórios para o estado: {estado}")
            cartorios_count = Cartorios.objects.filter(estado=estado).count()
            logger.info(f"Total de cartórios encontrados para {estado}: {cartorios_count}")
            
            return {
                'existem_cartorios': cartorios_count > 0,
                'total_cartorios': cartorios_count,
                'estado': estado
            }
        except Exception as e:
            logger.error(f"Erro ao verificar cartórios para {estado}: {str(e)}")
            return {
                'existem_cartorios': False,
                'total_cartorios': 0,
                'estado': estado,
                'erro': str(e)
            }
    
    @staticmethod
    def importar_cartorios_estado(estado):
        """
        Importa cartórios de um estado específico
        
        Args:
            estado (str): Sigla do estado
            
        Returns:
            dict: Dicionário com resultado da importação
        """
        try:
            logger.info(f"Iniciando importação de cartórios para o estado: {estado}")
            
            # Contar cartórios antes da importação
            cartorios_antes = Cartorios.objects.filter(estado=estado).count()
            logger.info(f"Cartórios antes da importação: {cartorios_antes}")
            
            with transaction.atomic():
                # Executa o comando de importação
                logger.info(f"Executando comando importar_cartorios_estado para {estado}")
                call_command('importar_cartorios_estado', estado)
                
                # Conta quantos cartórios foram importados
                cartorios_depois = Cartorios.objects.filter(estado=estado).count()
                cartorios_importados = cartorios_depois - cartorios_antes
                
                logger.info(f"Cartórios após importação: {cartorios_depois}")
                logger.info(f"Cartórios importados: {cartorios_importados}")
                
                return {
                    'success': True,
                    'message': f'Cartórios do estado {estado} importados com sucesso!',
                    'total_cartorios': cartorios_depois,
                    'cartorios_importados': cartorios_importados,
                    'estado': estado
                }
        except Exception as e:
            logger.error(f"Erro ao importar cartórios para {estado}: {str(e)}")
            return {
                'success': False,
                'error': f'Erro ao importar cartórios: {str(e)}',
                'estado': estado
            } 