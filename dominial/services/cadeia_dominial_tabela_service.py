"""
Service para visualização de tabela da cadeia dominial
"""

import re
from ..models import Documento


class CadeiaDominialTabelaService:
    """
    Service para gerenciar a visualização de tabela da cadeia dominial
    """
    
    @staticmethod
    def obter_cadeia_tabela(imovel, escolhas_origem=None):
        """
        Retorna a cadeia dominial em formato de tabela com lançamentos expandíveis
        
        Args:
            imovel: Objeto Imovel
            escolhas_origem: Dict com escolhas de origem do usuário
            
        Returns:
            list: Lista de documentos com dados para tabela
        """
        if escolhas_origem is None:
            escolhas_origem = {}
        
        # Por enquanto, usar o tronco principal existente
        from .hierarquia_service import HierarquiaService
        tronco_principal = HierarquiaService.obter_tronco_principal(imovel)
        
        cadeia_completa = []
        for documento in tronco_principal:
            # Carregar lançamentos com pessoas
            lancamentos = documento.lancamentos.select_related('tipo').prefetch_related(
                'pessoas__pessoa'
            ).order_by('id')
            
            # Verificar se tem múltiplas origens
            tem_multiplas_origens = False
            origens_disponiveis = []
            
            for lancamento in lancamentos:
                if lancamento.tipo.tipo == 'inicio_matricula' and lancamento.origem:
                    origens = CadeiaDominialTabelaService.extrair_origens_disponiveis(
                        lancamento.origem, imovel
                    )
                    if len(origens) > 1:
                        tem_multiplas_origens = True
                        origens_disponiveis = origens
                        break
            
            cadeia_completa.append({
                'documento': documento,
                'lancamentos': lancamentos,
                'tem_multiplas_origens': tem_multiplas_origens,
                'origens_disponiveis': origens_disponiveis,
                'escolha_atual': escolhas_origem.get(str(documento.id))
            })
        
        return cadeia_completa
    
    @staticmethod
    def extrair_origens_disponiveis(origem_texto, imovel):
        """
        Extrai as origens disponíveis de um texto de origem
        
        Args:
            origem_texto: Texto contendo as origens
            imovel: Objeto Imovel
            
        Returns:
            list: Lista de origens disponíveis
        """
        if not origem_texto:
            return []
        
        origens = []
        # Dividir por ponto e vírgula se houver múltiplas origens
        origens_split = [o.strip() for o in origem_texto.split(';') if o.strip()]
        
        for origem in origens_split:
            # Extrair códigos de matrícula/transcrição
            codigos = re.findall(r'[MT]\d+', origem)
            
            for codigo in codigos:
                doc_existente = Documento.objects.filter(
                    imovel=imovel, numero=codigo
                ).first()
                if doc_existente:
                    origens.append({
                        'numero': codigo,
                        'documento': doc_existente,
                        'escolhida': False  # Será definida pelo contexto
                    })
        
        return origens 