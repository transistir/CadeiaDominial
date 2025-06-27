"""
Service para operações relacionadas à hierarquia de documentos
"""

from ..models import Documento, Lancamento, Cartorios, DocumentoTipo
from ..utils.hierarquia_utils import (
    calcular_niveis_hierarquicos_otimizada,
    identificar_tronco_principal,
    identificar_troncos_secundarios,
    processar_origens_para_documentos
)
from .cache_service import CacheService
from datetime import date
import re


class HierarquiaService:
    """
    Service para gerenciar a hierarquia de documentos e cadeia dominial
    """
    
    @staticmethod
    def calcular_hierarquia_documentos(imovel):
        """
        Calcula a hierarquia completa dos documentos de um imóvel
        """
        # Otimização: usar select_related para cartório e tipo
        documentos = Documento.objects.filter(imovel=imovel)\
            .select_related('cartorio', 'tipo')\
            .prefetch_related('lancamentos', 'lancamentos__tipo')\
            .order_by('data')
        
        conexoes = []
        
        # TODO: Implementar lógica de identificação de conexões
        # Esta será implementada na Fase 2
        
        return calcular_niveis_hierarquicos_otimizada(documentos, conexoes)
    
    @staticmethod
    def obter_tronco_principal(imovel):
        """
        Obtém o tronco principal da cadeia dominial com cache
        """
        # Tentar obter do cache primeiro
        cached_tronco = CacheService.get_cached_tronco_principal(imovel.id)
        if cached_tronco:
            return cached_tronco
        
        # Se não estiver em cache, calcular e armazenar
        tronco = identificar_tronco_principal(imovel)
        CacheService.set_cached_tronco_principal(imovel.id, tronco)
        
        return tronco
    
    @staticmethod
    def obter_troncos_secundarios(imovel):
        """
        Obtém os troncos secundários da cadeia dominial
        """
        tronco_principal = identificar_tronco_principal(imovel)
        return identificar_troncos_secundarios(imovel, tronco_principal)
    
    @staticmethod
    def validar_hierarquia(imovel):
        """
        Valida se a hierarquia de documentos está consistente
        """
        # TODO: Implementar validações de consistência
        # Esta será implementada na Fase 2
        return True

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
        origens_identificadas = HierarquiaService._processar_origens_identificadas(imovel)
        
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
            doc_node = {
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
            
            documentos_por_numero[documento.numero] = doc_node
            arvore['documentos'].append(doc_node)
        
        # Criar conexões baseadas nas origens dos documentos e lançamentos
        HierarquiaService._criar_conexoes_documentos(arvore, documentos, documentos_por_numero)
        
        # Calcular níveis da árvore de forma hierárquica
        HierarquiaService._calcular_niveis_hierarquicos(arvore)
        
        # Adicionar apenas origens que ainda não foram convertidas em documentos
        origens_finais = []
        for origem in origens_identificadas:
            if not origem['ja_criado']:
                origens_finais.append(origem)
        
        arvore['origens_identificadas'] = origens_finais
        
        return arvore

    @staticmethod
    def _processar_origens_identificadas(imovel):
        """
        Processa origens identificadas de lançamentos que ainda não foram convertidas em documentos
        """
        origens_identificadas = []
        
        # Otimização: usar select_related para reduzir queries
        lancamentos_com_origem = Lancamento.objects.filter(
            documento__imovel=imovel,
            origem__isnull=False
        ).exclude(origem='')\
         .select_related('documento', 'documento__cartorio', 'documento__tipo')
        
        for lancamento in lancamentos_com_origem:
            if lancamento.origem:
                origens_processadas = processar_origens_para_documentos(lancamento.origem, imovel, lancamento)
                
                for origem_info in origens_processadas:
                    # Verificar se já existe um documento com esse número
                    documento_existente = Documento.objects.filter(imovel=imovel, numero=origem_info['numero']).first()
                    
                    if not documento_existente:
                        # Criar o documento automaticamente
                        try:
                            tipo_doc = DocumentoTipo.objects.get(tipo=origem_info['tipo'])
                            documento_criado = Documento.objects.create(
                                imovel=imovel,
                                tipo=tipo_doc,
                                numero=origem_info['numero'],
                                data=date.today(),
                                cartorio=imovel.cartorio if imovel.cartorio else Cartorios.objects.first(),
                                livro='1',  # Livro padrão
                                folha='1',  # Folha padrão
                                origem=f'Criado automaticamente a partir de origem: {origem_info["numero"]}',
                                observacoes=f'Documento criado automaticamente ao identificar origem "{origem_info["numero"]}" no lançamento {lancamento.numero_lancamento}'
                            )
                            
                            # Invalidar cache do imóvel
                            CacheService.invalidate_documentos_imovel(imovel.id)
                            CacheService.invalidate_tronco_principal(imovel.id)
                            
                            # Adicionar à lista de origens identificadas (agora são documentos criados)
                            origens_identificadas.append({
                                'codigo': origem_info['numero'],
                                'tipo': origem_info['tipo'],
                                'tipo_display': 'Matrícula' if origem_info['tipo'] == 'matricula' else 'Transcrição',
                                'lancamento_origem': lancamento.numero_lancamento,
                                'documento_origem': lancamento.documento.numero,
                                'data_identificacao': lancamento.data.strftime('%d/%m/%Y'),
                                'cor': '#28a745' if origem_info['tipo'] == 'matricula' else '#6f42c1',
                                'documento_id': documento_criado.id,
                                'ja_criado': True
                            })
                        except DocumentoTipo.DoesNotExist:
                            # Se o tipo não existir, apenas listar como origem identificada
                            origens_identificadas.append({
                                'codigo': origem_info['numero'],
                                'tipo': origem_info['tipo'],
                                'tipo_display': 'Matrícula' if origem_info['tipo'] == 'matricula' else 'Transcrição',
                                'lancamento_origem': lancamento.numero_lancamento,
                                'documento_origem': lancamento.documento.numero,
                                'data_identificacao': lancamento.data.strftime('%d/%m/%Y'),
                                'cor': '#28a745' if origem_info['tipo'] == 'matricula' else '#6f42c1',
                                'ja_criado': False
                            })
                    else:
                        # Documento já existe, adicionar como origem identificada criada
                        origens_identificadas.append({
                            'codigo': origem_info['numero'],
                            'tipo': origem_info['tipo'],
                            'tipo_display': 'Matrícula' if origem_info['tipo'] == 'matricula' else 'Transcrição',
                            'lancamento_origem': lancamento.numero_lancamento,
                            'documento_origem': lancamento.documento.numero,
                            'data_identificacao': lancamento.data.strftime('%d/%m/%Y'),
                            'cor': '#28a745' if origem_info['tipo'] == 'matricula' else '#6f42c1',
                            'documento_id': documento_existente.id,
                            'ja_criado': True
                        })
        
        return origens_identificadas

    @staticmethod
    def _criar_conexoes_documentos(arvore, documentos, documentos_por_numero):
        """
        Cria conexões baseadas nas origens dos documentos e lançamentos
        """
        for documento in documentos:
            # Verificar origem do documento
            if documento.origem:
                # Extrair códigos de origem (M ou T seguidos de números)
                origens = re.findall(r'[MT]\d+', documento.origem)
                
                # Se não encontrou padrões M/T, tentar extrair números
                if not origens:
                    numeros = re.findall(r'\d+', documento.origem)
                    origens = numeros
                
                # Se ainda não encontrou, verificar se há referência a outros documentos
                if not origens and 'matrícula' in documento.origem.lower():
                    # Procurar por documentos que podem ser a matrícula atual
                    for outro_doc in documentos:
                        if outro_doc.tipo.tipo == 'matricula' and outro_doc != documento:
                            origens = [outro_doc.numero]
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
            
            # Verificar origens dos lançamentos do documento
            lancamentos = documento.lancamentos.all()
            for lancamento in lancamentos:
                if lancamento.origem:
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
        matricula_atual = None
        for doc_node in arvore['documentos']:
            if not doc_node['origem'] or doc_node['origem'] == '' or 'Matrícula atual' in doc_node['origem'] or 'Criado automaticamente' not in doc_node['origem']:
                matricula_atual = doc_node['numero']
                break
        
        # Se não encontrou matrícula atual, usar o primeiro documento
        if not matricula_atual and arvore['documentos']:
            matricula_atual = arvore['documentos'][0]['numero']
        
        # Definir níveis de forma hierárquica
        niveis_hierarquicos = {}
        
        # Nível 0: Matrícula atual
        niveis_hierarquicos[matricula_atual] = 0
        
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
        
        # Aplicar níveis aos documentos
        for doc_node in arvore['documentos']:
            doc_node['nivel'] = niveis_hierarquicos.get(doc_node['numero'], 0) 