"""
Service para gerenciar documentos compartilhados entre imóveis.
Permite que documentos sejam acessados e editados de diferentes imóveis.
"""

from django.db.models import Q
from typing import List, Dict, Any, Optional
from ..models import Documento, DocumentoImportado, Imovel


class DocumentoCompartilhadoService:
    """
    Service para gerenciar documentos que são compartilhados entre imóveis.
    """
    
    @staticmethod
    def obter_documentos_acessiveis(imovel: Imovel) -> List[Documento]:
        """
        Obtém todos os documentos que um imóvel pode acessar.
        Inclui documentos próprios e documentos importados.
        
        Args:
            imovel: Imóvel para buscar documentos acessíveis
            
        Returns:
            Lista de documentos acessíveis
        """
        # Documentos próprios do imóvel
        documentos_proprios = Documento.objects.filter(imovel=imovel)\
            .select_related('cartorio', 'tipo')\
            .prefetch_related('lancamentos')\
            .order_by('-data')
        
        # Documentos importados - CORREÇÃO: buscar documentos que foram importados POR este imóvel
        # O campo imovel_origem representa o imóvel DE ONDE veio o documento
        documentos_importados = DocumentoImportado.objects.filter(
            imovel_origem=imovel  # Este imóvel importou estes documentos
        ).select_related(
            'documento', 
            'documento__cartorio', 
            'documento__tipo',
            'documento__imovel'  # Imóvel de origem do documento
        ).prefetch_related('documento__lancamentos')
        
        # Documentos referenciados por lançamentos (sistema de árvore da cadeia dominial)
        documentos_referenciados = DocumentoCompartilhadoService._obter_documentos_referenciados_por_lancamentos(imovel)
        
        # Converter para lista e adicionar metadados
        documentos_list = list(documentos_proprios)
        
        # Adicionar documentos importados via tabela DocumentoImportado
        for doc_importado in documentos_importados:
            doc = doc_importado.documento
            doc.is_importado = True
            doc.imovel_origem = doc_importado.documento.imovel  # Imóvel de origem do documento
            doc.data_importacao = doc_importado.data_importacao
            doc.tipo_importacao = 'tabela_importacao'
            documentos_list.append(doc)
        
        # Adicionar documentos referenciados por lançamentos
        for doc_ref in documentos_referenciados:
            # Verificar se já não foi adicionado
            if not any(d.id == doc_ref['documento'].id for d in documentos_list):
                doc = doc_ref['documento']
                doc.is_importado = True
                doc.imovel_origem = doc_ref['imovel_origem']
                doc.data_importacao = doc_ref['data_referencia']
                doc.tipo_importacao = 'referencia_lancamento'
                documentos_list.append(doc)
        
        # Ordenar por data
        documentos_list.sort(key=lambda x: x.data, reverse=True)
        
        return documentos_list
    
    @staticmethod
    def _obter_documentos_referenciados_por_lancamentos(imovel: Imovel) -> List[Dict]:
        """
        Obtém documentos que são referenciados por lançamentos deste imóvel.
        Baseado no sistema de árvore da cadeia dominial.
        
        Args:
            imovel: Imóvel para buscar documentos referenciados
            
        Returns:
            Lista de dicionários com documentos e metadados
        """
        from ..models import Lancamento
        from django.utils import timezone
        
        documentos_referenciados = []
        documentos_processados = set()
        
        # Buscar todos os lançamentos deste imóvel
        lancamentos = Lancamento.objects.filter(
            documento__imovel=imovel,
            origem__isnull=False
        ).exclude(origem='')
        
        # Para cada lançamento, verificar se a origem é um documento de outro imóvel
        for lancamento in lancamentos:
            origens = [o.strip() for o in lancamento.origem.split(';') if o.strip()]
            
            for origem_numero in origens:
                # Buscar documento com este número que está em outro imóvel
                doc_referenciado = Documento.objects.filter(
                    numero=origem_numero
                ).exclude(
                    imovel=imovel
                ).select_related('cartorio', 'tipo', 'imovel').first()
                
                if doc_referenciado and doc_referenciado.id not in documentos_processados:
                    documentos_processados.add(doc_referenciado.id)
                    documentos_referenciados.append({
                        'documento': doc_referenciado,
                        'imovel_origem': doc_referenciado.imovel,
                        'data_referencia': lancamento.data or timezone.now(),
                        'lancamento_referencia': lancamento
                    })
                    
                    # ADIÇÃO: Buscar documentos que fazem parte da cadeia dominial deste documento
                    documentos_cadeia = DocumentoCompartilhadoService._obter_documentos_cadeia_dominial(doc_referenciado)
                    for doc_cadeia in documentos_cadeia:
                        if doc_cadeia['documento'].id not in documentos_processados:
                            documentos_processados.add(doc_cadeia['documento'].id)
                            documentos_referenciados.append(doc_cadeia)
        
        return documentos_referenciados
    
    @staticmethod
    def _obter_documentos_cadeia_dominial(documento_origem: Documento) -> List[Dict]:
        """
        Obtém documentos que fazem parte da cadeia dominial de um documento.
        Busca documentos que são referenciados como origem por este documento.
        
        Args:
            documento_origem: Documento para buscar a cadeia dominial
            
        Returns:
            Lista de dicionários com documentos da cadeia dominial
        """
        from ..models import Lancamento
        from django.utils import timezone
        
        documentos_cadeia = []
        documentos_processados = set()
        
        def buscar_cadeia_recursiva(documento):
            if documento.id in documentos_processados:
                return
            
            documentos_processados.add(documento.id)
            
            # Buscar lançamentos deste documento
            lancamentos = Lancamento.objects.filter(documento=documento)
            
            for lancamento in lancamentos:
                if lancamento.origem:
                    origens = [o.strip() for o in lancamento.origem.split(';') if o.strip()]
                    
                    for origem_numero in origens:
                        # Buscar documento com este número
                        doc_cadeia = Documento.objects.filter(
                            numero=origem_numero
                        ).select_related('cartorio', 'tipo', 'imovel').first()
                        
                        if doc_cadeia and doc_cadeia.id not in documentos_processados:
                            documentos_cadeia.append({
                                'documento': doc_cadeia,
                                'imovel_origem': doc_cadeia.imovel,
                                'data_referencia': lancamento.data or timezone.now(),
                                'lancamento_referencia': lancamento,
                                'nivel_cadeia': 'cadeia_dominial'
                            })
                            
                            # Buscar recursivamente a cadeia deste documento
                            buscar_cadeia_recursiva(doc_cadeia)
        
        # Iniciar busca recursiva
        buscar_cadeia_recursiva(documento_origem)
        
        return documentos_cadeia
    
    @staticmethod
    def verificar_acesso_documento(documento_id: int, imovel: Imovel) -> Dict[str, Any]:
        """
        Verifica se um imóvel tem acesso a um documento específico.
        
        Args:
            documento_id: ID do documento
            imovel: Imóvel que está tentando acessar
            
        Returns:
            Dict com informações sobre o acesso
        """
        try:
            documento = Documento.objects.get(id=documento_id)
            
            # Verificar se é documento próprio
            if documento.imovel == imovel:
                return {
                    'tem_acesso': True,
                    'documento': documento,
                    'tipo_acesso': 'proprio',
                    'is_importado': False
                }
            
            # Verificar se é documento importado via tabela DocumentoImportado
            is_importado_tabela = DocumentoImportado.objects.filter(
                documento=documento,
                imovel_origem=imovel  # Este imóvel importou o documento
            ).exists()
            
            if is_importado_tabela:
                return {
                    'tem_acesso': True,
                    'documento': documento,
                    'tipo_acesso': 'importado_tabela',
                    'is_importado': True
                }
            
            # Verificar se é documento referenciado por lançamentos
            is_referenciado_lancamento = DocumentoCompartilhadoService._verificar_documento_referenciado_por_lancamento(
                documento, imovel
            )
            
            if is_referenciado_lancamento:
                return {
                    'tem_acesso': True,
                    'documento': documento,
                    'tipo_acesso': 'referenciado_lancamento',
                    'is_importado': True
                }
            
            # ADIÇÃO: Verificar se é documento da cadeia dominial de documentos acessíveis
            is_cadeia_dominial = DocumentoCompartilhadoService._verificar_documento_cadeia_dominial(
                documento, imovel
            )
            
            if is_cadeia_dominial:
                return {
                    'tem_acesso': True,
                    'documento': documento,
                    'tipo_acesso': 'cadeia_dominial',
                    'is_importado': True
                }
            
            # Sem acesso
            return {
                'tem_acesso': False,
                'documento': None,
                'tipo_acesso': 'nenhum',
                'is_importado': False,
                'mensagem': 'Documento não encontrado ou não importado para este imóvel.'
            }
            
        except Documento.DoesNotExist:
            return {
                'tem_acesso': False,
                'documento': None,
                'tipo_acesso': 'nenhum',
                'is_importado': False,
                'mensagem': 'Documento não encontrado.'
            }
    
    @staticmethod
    def _verificar_documento_referenciado_por_lancamento(documento: Documento, imovel: Imovel) -> bool:
        """
        Verifica se um documento é referenciado por lançamentos deste imóvel.
        
        Args:
            documento: Documento a verificar
            imovel: Imóvel para verificar lançamentos
            
        Returns:
            True se o documento é referenciado por lançamentos
        """
        from ..models import Lancamento
        
        # Buscar lançamentos deste imóvel que referenciam este documento
        lancamentos = Lancamento.objects.filter(
            documento__imovel=imovel,
            origem__isnull=False
        ).exclude(origem='')
        
        for lancamento in lancamentos:
            origens = [o.strip() for o in lancamento.origem.split(';') if o.strip()]
            if documento.numero in origens:
                return True
        
        return False
    
    @staticmethod
    def _verificar_documento_cadeia_dominial(documento: Documento, imovel: Imovel) -> bool:
        """
        Verifica se um documento faz parte da cadeia dominial de documentos acessíveis.
        
        Args:
            documento: Documento a verificar
            imovel: Imóvel para verificar acesso
            
        Returns:
            True se o documento faz parte da cadeia dominial
        """
        # Obter documentos acessíveis do imóvel
        documentos_acessiveis = DocumentoCompartilhadoService.obter_documentos_acessiveis(imovel)
        
        # Para cada documento acessível, verificar se o documento faz parte da sua cadeia dominial
        for doc_acessivel in documentos_acessiveis:
            if getattr(doc_acessivel, 'is_importado', False):
                # Buscar documentos da cadeia dominial deste documento acessível
                documentos_cadeia = DocumentoCompartilhadoService._obter_documentos_cadeia_dominial(doc_acessivel)
                
                for doc_cadeia in documentos_cadeia:
                    if doc_cadeia['documento'].id == documento.id:
                        return True
        
        return False
    
    @staticmethod
    def obter_documento_com_acesso(documento_id: int, imovel: Imovel) -> Optional[Documento]:
        """
        Obtém um documento verificando se o imóvel tem acesso.
        
        Args:
            documento_id: ID do documento
            imovel: Imóvel que está tentando acessar
            
        Returns:
            Documento se tiver acesso, None caso contrário
        """
        resultado = DocumentoCompartilhadoService.verificar_acesso_documento(documento_id, imovel)
        
        if resultado['tem_acesso']:
            documento = resultado['documento']
            if resultado['is_importado']:
                if resultado['tipo_acesso'] == 'importado_tabela':
                    # Adicionar metadados de importação via tabela
                    doc_importado = DocumentoImportado.objects.get(
                        documento=documento,
                        imovel_origem=imovel  # Este imóvel importou o documento
                    )
                    documento.is_importado = True
                    documento.imovel_origem = doc_importado.documento.imovel  # Imóvel de origem do documento
                    documento.data_importacao = doc_importado.data_importacao
                    documento.tipo_importacao = 'tabela_importacao'
                
                elif resultado['tipo_acesso'] == 'referenciado_lancamento':
                    # Adicionar metadados de importação via referência de lançamento
                    from ..models import Lancamento
                    from django.utils import timezone
                    
                    # Buscar o lançamento que referencia este documento
                    lancamento_ref = Lancamento.objects.filter(
                        documento__imovel=imovel,
                        origem__icontains=documento.numero
                    ).first()
                    
                    documento.is_importado = True
                    documento.imovel_origem = documento.imovel  # Imóvel de origem do documento
                    documento.data_importacao = lancamento_ref.data if lancamento_ref else timezone.now()
                    documento.tipo_importacao = 'referencia_lancamento'
                
                elif resultado['tipo_acesso'] == 'cadeia_dominial':
                    # Adicionar metadados de importação via cadeia dominial
                    from django.utils import timezone
                    
                    documento.is_importado = True
                    documento.imovel_origem = documento.imovel  # Imóvel de origem do documento
                    documento.data_importacao = timezone.now()  # Data atual como referência
                    documento.tipo_importacao = 'cadeia_dominial'
            
            return documento
        
        return None
    
    @staticmethod
    def obter_imoveis_com_acesso(documento: Documento) -> List[Imovel]:
        """
        Obtém todos os imóveis que têm acesso a um documento.
        
        Args:
            documento: Documento para verificar acesso
            
        Returns:
            Lista de imóveis com acesso
        """
        imoveis = [documento.imovel]  # Imóvel proprietário
        
        # Imóveis que importaram o documento
        importacoes = DocumentoImportado.objects.filter(
            documento=documento
        ).select_related('imovel_origem')
        
        for importacao in importacoes:
            if importacao.imovel_origem not in imoveis:
                imoveis.append(importacao.imovel_origem)
        
        return imoveis
    
    @staticmethod
    def compartilhar_documento(documento: Documento, imovel_destino: Imovel, usuario=None) -> bool:
        """
        Compartilha um documento com outro imóvel (importação).
        
        Args:
            documento: Documento a ser compartilhado
            imovel_destino: Imóvel que receberá o documento
            usuario: Usuário que está fazendo o compartilhamento
            
        Returns:
            True se compartilhado com sucesso, False caso contrário
        """
        try:
            # Verificar se já não foi compartilhado
            if DocumentoImportado.objects.filter(
                documento=documento,
                imovel_origem=imovel_destino
            ).exists():
                return True  # Já foi compartilhado
            
            # Criar registro de importação
            DocumentoImportado.objects.create(
                documento=documento,
                imovel_origem=imovel_destino,
                importado_por=usuario
            )
            
            return True
            
        except Exception as e:
            print(f"Erro ao compartilhar documento: {str(e)}")
            return False
    
    @staticmethod
    def remover_compartilhamento(documento: Documento, imovel: Imovel) -> bool:
        """
        Remove o compartilhamento de um documento com um imóvel.
        
        Args:
            documento: Documento
            imovel: Imóvel para remover compartilhamento
            
        Returns:
            True se removido com sucesso, False caso contrário
        """
        try:
            # Remover registro de importação
            DocumentoImportado.objects.filter(
                documento=documento,
                imovel_origem=imovel
            ).delete()
            
            return True
            
        except Exception as e:
            print(f"Erro ao remover compartilhamento: {str(e)}")
            return False
    
    @staticmethod
    def obter_estatisticas_compartilhamento(imovel: Imovel) -> Dict[str, Any]:
        """
        Obtém estatísticas de compartilhamento de um imóvel.
        
        Args:
            imovel: Imóvel para obter estatísticas
            
        Returns:
            Dict com estatísticas
        """
        # Documentos próprios
        documentos_proprios = Documento.objects.filter(imovel=imovel).count()
        
        # Documentos importados
        documentos_importados = DocumentoImportado.objects.filter(
            documento__imovel=imovel
        ).count()
        
        # Documentos compartilhados com outros imóveis
        documentos_compartilhados = DocumentoImportado.objects.filter(
            documento__imovel=imovel
        ).count()
        
        return {
            'documentos_proprios': documentos_proprios,
            'documentos_importados': documentos_importados,
            'documentos_compartilhados': documentos_compartilhados,
            'total_documentos_acessiveis': documentos_proprios + documentos_importados
        } 