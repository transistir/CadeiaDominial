"""
Service para gerenciar CRI (Cartórios de Registro de Imóveis)
"""

from ..models import Documento, Imovel, Cartorios


class CRIService:
    """
    Service para gerenciar CRI dos documentos
    """
    
    @staticmethod
    def definir_cri_documento(documento, imovel, cri_origem=None):
        """
        Define o CRI de um documento
        
        Args:
            documento: Objeto Documento
            imovel: Objeto Imovel
            cri_origem: CRI da origem (opcional, para documentos criados automaticamente)
        """
        if cri_origem:
            # Documento criado automaticamente: herda CRI da origem
            documento.cri_origem = cri_origem
            documento.cri_atual = imovel.cartorio
        else:
            # Documento criado manualmente: usa CRI atual do imóvel
            documento.cri_atual = imovel.cartorio
            documento.cri_origem = None
    
    @staticmethod
    def obter_cri_documento(documento):
        """
        Obtém o CRI efetivo de um documento
        
        Returns:
            Cartorios: O CRI que deve ser usado para os lançamentos deste documento
        """
        # Se o documento tem CRI da origem, usar ele
        if documento.cri_origem:
            return documento.cri_origem
        # Senão, usar CRI atual
        elif documento.cri_atual:
            return documento.cri_atual
        # Fallback: usar cartório do documento
        else:
            return documento.cartorio
    
    @staticmethod
    def obter_cri_imovel(imovel):
        """
        Obtém o CRI atual de um imóvel
        
        Returns:
            Cartorios: O CRI atual do imóvel
        """
        return imovel.cartorio
    
    @staticmethod
    def validar_cri_cartorio(cartorio):
        """
        Valida se um cartório é um CRI válido
        
        Args:
            cartorio: Objeto Cartorios
            
        Returns:
            bool: True se é um CRI válido
        """
        return cartorio and cartorio.tipo == 'CRI'
    
    @staticmethod
    def obter_cri_disponiveis():
        """
        Obtém lista de CRI disponíveis
        
        Returns:
            QuerySet: Lista de cartórios do tipo CRI
        """
        return Cartorios.objects.filter(tipo='CRI').order_by('estado', 'cidade', 'nome')
    
    @staticmethod
    def criar_documento_com_cri(imovel, dados_documento, cri_origem=None):
        """
        Cria um documento com CRI apropriado
        
        Args:
            imovel: Objeto Imovel
            dados_documento: Dict com dados do documento
            cri_origem: CRI da origem (opcional)
            
        Returns:
            Documento: Documento criado com CRI definido
        """
        # Garantir que campos obrigatórios tenham valores válidos
        dados_limpos = dados_documento.copy()
        
        # Garantir que livro e folha não sejam None ou vazios
        if not dados_limpos.get('livro') or dados_limpos.get('livro') == '':
            dados_limpos['livro'] = '0'
        if not dados_limpos.get('folha') or dados_limpos.get('folha') == '':
            dados_limpos['folha'] = '0'
        
        documento = Documento.objects.create(**dados_limpos)
        
        # Definir CRI do documento
        CRIService.definir_cri_documento(documento, imovel, cri_origem)
        documento.save()
        
        return documento 