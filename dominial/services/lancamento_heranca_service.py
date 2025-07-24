"""
Service para herdar dados do primeiro lançamento do documento
"""
from ..models import Lancamento

class LancamentoHerancaService:
    @staticmethod
    def obter_dados_primeiro_lancamento(documento):
        """
        Obtém os dados do primeiro lançamento do documento para herança
        HERANÇA MELHORADA: Se os campos de origem não estiverem preenchidos,
        usa os campos do documento como fallback
        
        Args:
            documento: Objeto Documento
            
        Returns:
            dict: Dados do primeiro lançamento ou None se não existir
        """
        primeiro_lancamento = Lancamento.objects.filter(
            documento=documento
        ).order_by('id').first()
        
        if not primeiro_lancamento:
            return None
        
        # HERANÇA MELHORADA: Usar campos do documento como fallback
        livro_origem = primeiro_lancamento.livro_origem
        folha_origem = primeiro_lancamento.folha_origem
        
        # Se os campos de origem não estiverem preenchidos, usar os campos do documento
        if not livro_origem and documento.livro and documento.livro != '0':
            livro_origem = documento.livro
        
        if not folha_origem and documento.folha and documento.folha != '0':
            folha_origem = documento.folha
        
        return {
            'livro_origem': livro_origem,
            'folha_origem': folha_origem,
            'cartorio_origem': primeiro_lancamento.cartorio_origem,
            # Não herdar campos que podem causar problemas com "None"
            # 'data_origem': primeiro_lancamento.data_origem,
            # 'origem': primeiro_lancamento.origem,
            # 'area': primeiro_lancamento.area,
            # 'forma': primeiro_lancamento.forma,
            # 'descricao': primeiro_lancamento.descricao,
            # 'titulo': primeiro_lancamento.titulo
        }
    
    @staticmethod
    def obter_cartorio_origem_documento(documento):
        """
        Obtém o cartório de origem do primeiro lançamento que criou o documento
        
        Args:
            documento: Objeto Documento
            
        Returns:
            Cartorios: Cartório de origem ou cartório do documento como fallback
        """
        primeiro_lancamento = Lancamento.objects.filter(
            documento=documento
        ).order_by('id').first()
        
        if primeiro_lancamento and primeiro_lancamento.cartorio_origem:
            return primeiro_lancamento.cartorio_origem
        
        # Fallback: usar cartório do documento
        return documento.cartorio
    
    @staticmethod
    def herdar_dados_para_novo_lancamento(documento, lancamento):
        """
        Herda dados do primeiro lançamento para um novo lançamento
        
        Args:
            documento: Objeto Documento
            lancamento: Objeto Lancamento (novo lançamento)
            
        Returns:
            bool: True se dados foram herdados, False caso contrário
        """
        dados_primeiro = LancamentoHerancaService.obter_dados_primeiro_lancamento(documento)
        
        if not dados_primeiro:
            return False
        
        # Herdar dados apenas se não estiverem preenchidos no novo lançamento
        if not lancamento.livro_origem and dados_primeiro['livro_origem']:
            lancamento.livro_origem = dados_primeiro['livro_origem']
        
        if not lancamento.folha_origem and dados_primeiro['folha_origem']:
            lancamento.folha_origem = dados_primeiro['folha_origem']
        
        if not lancamento.cartorio_origem and dados_primeiro['cartorio_origem']:
            lancamento.cartorio_origem = dados_primeiro['cartorio_origem']
        
        if not lancamento.data_origem and dados_primeiro['data_origem']:
            lancamento.data_origem = dados_primeiro['data_origem']
        
        if not lancamento.origem and dados_primeiro['origem']:
            lancamento.origem = dados_primeiro['origem']
        
        if not lancamento.area and dados_primeiro['area']:
            lancamento.area = dados_primeiro['area']
        
        if not lancamento.forma and dados_primeiro['forma']:
            lancamento.forma = dados_primeiro['forma']
        
        if not lancamento.descricao and dados_primeiro['descricao']:
            lancamento.descricao = dados_primeiro['descricao']
        
        if not lancamento.titulo and dados_primeiro['titulo']:
            lancamento.titulo = dados_primeiro['titulo']
        
        return True 