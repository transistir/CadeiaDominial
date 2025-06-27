"""
Service especializado para construção da árvore de hierarquia
"""

from ..models import Documento, Lancamento
from .hierarquia_origem_service import HierarquiaOrigemService
import re


class HierarquiaArvoreService:
    """
    Service para construir e gerenciar a árvore de hierarquia da cadeia dominial
    """
    
    @staticmethod
    def construir_arvore_cadeia_dominial(imovel):
        """
        Constrói a estrutura de árvore da cadeia dominial para visualização
        """
        # Otimização: usar select_related e prefetch_related para reduzir queries
        documentos = Documento.objects.filter(imovel=imovel)\
            .select_related('cartorio', 'tipo')\
            .prefetch_related('lancamentos', 'lancamentos__tipo')\
            .order_by('data')
        
        # Processar origens identificadas de lançamentos
        origens_identificadas = HierarquiaOrigemService.processar_origens_identificadas(imovel)
        
        # Estrutura para armazenar a árvore
        arvore = {
            'imovel': {
                'id': imovel.id,
                'matricula': imovel.matricula,
                'nome': imovel.nome,
                'proprietario': imovel.proprietario.nome if imovel.proprietario else ''
            },
            'documentos': [],
            'origens_identificadas': [],
            'conexoes': []
        }
        
        # Mapear documentos por número para facilitar busca
        documentos_por_numero = {}
        
        # Processar cada documento
        for documento in documentos:
            doc_node = HierarquiaArvoreService._criar_no_documento(documento)
            documentos_por_numero[documento.numero] = doc_node
            arvore['documentos'].append(doc_node)
        
        # Criar conexões baseadas nas origens dos documentos e lançamentos
        HierarquiaArvoreService._criar_conexoes_documentos(arvore, documentos, documentos_por_numero)
        
        # Calcular níveis da árvore de forma hierárquica
        HierarquiaArvoreService._calcular_niveis_hierarquicos(arvore)
        
        # Adicionar apenas origens que ainda não foram convertidas em documentos
        origens_finais = []
        for origem in origens_identificadas:
            if not origem['ja_criado']:
                origens_finais.append(origem)
        
        arvore['origens_identificadas'] = origens_finais
        
        return arvore
    
    @staticmethod
    def _criar_no_documento(documento):
        """
        Cria um nó de documento para a árvore
        """
        return {
            'id': documento.id,
            'numero': documento.numero,
            'tipo': documento.tipo.tipo,
            'tipo_display': documento.tipo.get_tipo_display(),
            'data': documento.data.strftime('%d/%m/%Y'),
            'cartorio': documento.cartorio.nome,
            'livro': documento.livro,
            'folha': documento.folha,
            'origem': documento.origem or '',
            'observacoes': documento.observacoes or '',
            'total_lancamentos': documento.lancamentos.count(),
            'x': 0,  # Posição X (será calculada pelo frontend)
            'y': 0,  # Posição Y (será calculada pelo frontend)
            'nivel': 0  # Nível na árvore (será calculado)
        }
    
    @staticmethod
    def _criar_conexoes_documentos(arvore, documentos, documentos_por_numero):
        """
        Cria conexões baseadas nas origens dos documentos e lançamentos
        """
        for documento in documentos:
            # Verificar origem do documento
            if documento.origem:
                HierarquiaArvoreService._processar_origem_documento(
                    arvore, documento, documentos_por_numero
                )
            
            # Verificar origens dos lançamentos do documento
            lancamentos = documento.lancamentos.all()
            for lancamento in lancamentos:
                if lancamento.origem:
                    HierarquiaArvoreService._processar_origem_lancamento(
                        arvore, documento, lancamento, documentos_por_numero
                    )
    
    @staticmethod
    def _processar_origem_documento(arvore, documento, documentos_por_numero):
        """
        Processa origem de um documento específico
        """
        # Extrair códigos de origem (M ou T seguidos de números)
        origens = re.findall(r'[MT]\d+', documento.origem)
        
        # Se não encontrou padrões M/T, tentar extrair números
        if not origens:
            numeros = re.findall(r'\d+', documento.origem)
            origens = numeros
        
        # Se ainda não encontrou, verificar se há referência a outros documentos
        if not origens and 'matrícula' in documento.origem.lower():
            # Procurar por documentos que podem ser a matrícula atual
            for outro_doc in documentos_por_numero.values():
                if outro_doc['tipo'] == 'matricula' and outro_doc['numero'] != documento.numero:
                    origens = [outro_doc['numero']]
                    break
        
        for origem in origens:
            # Evitar auto-referências
            if origem != documento.numero and origem in documentos_por_numero:
                conexao = {
                    'from': origem,  # Documento de origem
                    'to': documento.numero,  # Documento atual
                    'tipo': 'origem'
                }
                arvore['conexoes'].append(conexao)
    
    @staticmethod
    def _processar_origem_lancamento(arvore, documento, lancamento, documentos_por_numero):
        """
        Processa origem de um lançamento específico
        """
        # Extrair códigos de origem dos lançamentos
        origens_lancamento = re.findall(r'[MT]\d+', lancamento.origem)
        
        for origem in origens_lancamento:
            # Evitar auto-referências e verificar se existe um documento com esse número
            if origem != documento.numero and origem in documentos_por_numero:
                conexao = {
                    'from': origem,  # Documento de origem
                    'to': documento.numero,  # Documento atual
                    'tipo': 'origem_lancamento'
                }
                # Evitar duplicatas
                if not any(c['from'] == origem and c['to'] == documento.numero for c in arvore['conexoes']):
                    arvore['conexoes'].append(conexao)
    
    @staticmethod
    def _calcular_niveis_hierarquicos(arvore):
        """
        Calcula níveis da árvore de forma hierárquica correta
        """
        # Identificar a matrícula atual (documento principal)
        matricula_atual = HierarquiaArvoreService._identificar_matricula_atual(arvore)
        
        # Definir níveis de forma hierárquica
        niveis_hierarquicos = {}
        
        # Nível 0: Matrícula atual
        niveis_hierarquicos[matricula_atual] = 0
        
        # Calcular níveis para documentos conectados
        HierarquiaArvoreService._calcular_niveis_conectados(
            arvore, niveis_hierarquicos, matricula_atual
        )
        
        # Aplicar níveis aos documentos
        for doc_node in arvore['documentos']:
            doc_node['nivel'] = niveis_hierarquicos.get(doc_node['numero'], 0)
    
    @staticmethod
    def _identificar_matricula_atual(arvore):
        """
        Identifica a matrícula atual (documento principal)
        """
        for doc_node in arvore['documentos']:
            if not doc_node['origem'] or doc_node['origem'] == '' or 'Matrícula atual' in doc_node['origem'] or 'Criado automaticamente' not in doc_node['origem']:
                return doc_node['numero']
        
        # Se não encontrou matrícula atual, usar o primeiro documento
        if arvore['documentos']:
            return arvore['documentos'][0]['numero']
        
        return None
    
    @staticmethod
    def _calcular_niveis_conectados(arvore, niveis_hierarquicos, matricula_atual):
        """
        Calcula níveis para documentos conectados de forma recursiva
        """
        # Nível 1: Documentos que são referenciados pela matrícula atual
        documentos_nivel_1 = []
        for conexao in arvore['conexoes']:
            if conexao['to'] == matricula_atual:  # Se a matrícula atual referencia este documento
                documentos_nivel_1.append(conexao['from'])
                niveis_hierarquicos[conexao['from']] = 1
        
        # Nível 2: Documentos que são referenciados pelos documentos do nível 1
        documentos_nivel_2 = []
        for conexao in arvore['conexoes']:
            if conexao['to'] in documentos_nivel_1:  # Se um documento do nível 1 referencia este documento
                if conexao['from'] not in niveis_hierarquicos:  # Se ainda não foi definido
                    documentos_nivel_2.append(conexao['from'])
                    niveis_hierarquicos[conexao['from']] = 2
        
        # Nível 3+: Continuar para níveis mais profundos se necessário
        nivel_atual = 3
        documentos_nivel_anterior = documentos_nivel_2.copy()
        
        while documentos_nivel_anterior:
            documentos_nivel_atual = []
            for conexao in arvore['conexoes']:
                if conexao['to'] in documentos_nivel_anterior:  # Se um documento do nível anterior referencia este documento
                    if conexao['from'] not in niveis_hierarquicos:  # Se ainda não foi definido
                        documentos_nivel_atual.append(conexao['from'])
                        niveis_hierarquicos[conexao['from']] = nivel_atual
            
            documentos_nivel_anterior = documentos_nivel_atual
            nivel_atual += 1 