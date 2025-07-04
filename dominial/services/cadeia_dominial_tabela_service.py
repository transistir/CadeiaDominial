"""
Service para visualização de tabela da cadeia dominial
"""

import re
from django.shortcuts import get_object_or_404
from ..models import TIs, Imovel, Documento, Lancamento
from ..services.hierarquia_service import HierarquiaService


class CadeiaDominialTabelaService:
    """
    Service para gerenciar a visualização de tabela da cadeia dominial
    """
    
    def __init__(self):
        self.hierarquia_service = HierarquiaService()
    
    def get_cadeia_dominial_tabela(self, tis_id, imovel_id, session=None):
        """
        Obtém dados da cadeia dominial em formato de tabela
        """
        tis = get_object_or_404(TIs, id=tis_id)
        imovel = get_object_or_404(Imovel, id=imovel_id)
        
        # Extrair escolhas de origem da sessão
        escolhas_origem = {}
        if session:
            for key, value in session.items():
                if key.startswith('origem_documento_'):
                    documento_id = key.replace('origem_documento_', '')
                    escolhas_origem[documento_id] = value
        
        # Obter tronco principal considerando escolhas
        tronco_principal = self.hierarquia_service.obter_tronco_principal(imovel, escolhas_origem)
        
        # Processar cada documento (manter ordem por data)
        cadeia_processada = []
        documentos_ordenados = sorted(tronco_principal, key=lambda x: x.data)
        for documento in documentos_ordenados:
            # Carregar lançamentos
            lancamentos = documento.lancamentos.select_related('tipo').prefetch_related(
                'pessoas__pessoa'
            ).order_by('id')
            
            # Verificar se tem múltiplas origens
            origens_disponiveis = self._obter_origens_documento(documento, lancamentos)
            tem_multiplas_origens = len(origens_disponiveis) > 1
            
            # Verificar escolha atual da sessão
            escolha_atual = session.get(f'origem_documento_{documento.id}') if session else None
            
            # Formatar origens para o template (ordenadas do maior para o menor)
            origens_formatadas = []
            for origem in origens_disponiveis:
                origens_formatadas.append({
                    'numero': origem,
                    'escolhida': origem == escolha_atual
                })
            
            cadeia_processada.append({
                'documento': documento,
                'lancamentos': lancamentos,
                'origens_disponiveis': origens_formatadas,
                'tem_multiplas_origens': tem_multiplas_origens,
                'escolha_atual': escolha_atual
            })
        
        return {
            'tis': tis,
            'imovel': imovel,
            'cadeia': cadeia_processada,
            'tem_lancamentos': any(len(item['lancamentos']) > 0 for item in cadeia_processada)
        }
    
    def _obter_origens_documento(self, documento, lancamentos):
        """
        Obtém as origens disponíveis para um documento
        """
        origens = set()
        
        for lancamento in lancamentos:
            if lancamento.tipo.tipo == 'inicio_matricula' and lancamento.origem:
                # Extrair origens do campo origem
                origens_lancamento = self._extrair_origens(lancamento.origem)
                origens.update(origens_lancamento)
        
        # Ordenar do maior para o menor número
        origens_list = list(origens)
        return sorted(origens_list, key=lambda x: int(x.replace('M', '').replace('T', '')), reverse=True)
    
    def _extrair_origens(self, origem_string):
        """
        Extrai origens de uma string
        Ex: "M3212; M3211; M3210" -> ["M3212", "M3211", "M3210"]
        """
        if not origem_string:
            return []
        
        # Dividir por ponto e vírgula e limpar espaços
        partes = [parte.strip() for parte in origem_string.split(';') if parte.strip()]
        return partes
    
    def get_estatisticas_cadeia(self, cadeia):
        """
        Calcula estatísticas da cadeia dominial
        """
        total_documentos = len(cadeia)
        total_lancamentos = sum(len(item['lancamentos']) for item in cadeia)
        documentos_com_multiplas_origens = sum(1 for item in cadeia if item['tem_multiplas_origens'])
        
        return {
            'total_documentos': total_documentos,
            'total_lancamentos': total_lancamentos,
            'documentos_com_multiplas_origens': documentos_com_multiplas_origens,
            'percentual_multiplas_origens': (documentos_com_multiplas_origens / total_documentos * 100) if total_documentos > 0 else 0
        }

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