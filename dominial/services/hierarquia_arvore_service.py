"""
Service final corrigido para construção da árvore de hierarquia
Implementa a lógica correta: filho -> pai (esquerda -> direita)
Resolve todos os problemas identificados nos testes
"""

from ..models import Documento, Lancamento
from .hierarquia_origem_service import HierarquiaOrigemService
from .documento_service import DocumentoService
from .documento_identidade_service import DocumentoIdentidadeService
from .lancamento_origem_leitura_service import LancamentoOrigemLeituraService
from ..utils.documento_identidade_utils import DocumentoIdentidade
import re
from collections import deque


class HierarquiaArvoreService:
    """
    Service final para construir e gerenciar a árvore de hierarquia da cadeia dominial
    Lógica: filho -> pai (esquerda -> direita)
    """
    
    @staticmethod
    def construir_arvore_cadeia_dominial(imovel, criar_documentos_automaticos=False):
        """
        Constrói a estrutura de árvore da cadeia dominial para visualização
        Lógica corrigida: filho -> pai (esquerda -> direita)
        
        Args:
            imovel: Objeto Imovel
            criar_documentos_automaticos: Se True, cria documentos automaticamente para origens identificadas
        """
        # 1. Identificar documento principal do imóvel
        documento_principal = HierarquiaArvoreService._identificar_documento_principal(imovel)
        
        if not documento_principal:
            return {
                'imovel': {
                    'id': imovel.id,
                    'matricula': imovel.matricula,
                    'nome': imovel.nome,
                    'proprietario': imovel.proprietario.nome if imovel.proprietario else ''
                },
                'documentos': [],
                'origens_identificadas': [],
                'conexoes': [],
                'erro': 'Nenhum documento principal encontrado para este imóvel'
            }
        
        # 2. Construir árvore a partir do documento principal
        arvore = HierarquiaArvoreService._construir_arvore_a_partir_documento(
            documento_principal, imovel, criar_documentos_automaticos
        )
        
        return arvore
    
    @staticmethod
    def _identificar_documento_principal(imovel):
        """
        Identifica o documento principal do imóvel
        Prioridade: 1) Documento com número igual à matrícula, 2) Primeiro documento do imóvel
        """
        # Primeiro, tentar encontrar a identidade registral exata do imóvel.
        documento_principal = Documento.objects.filter(
            imovel=imovel,
            tipo__tipo=imovel.tipo_documento_principal,
            numero_normalizado=imovel.matricula_normalizada,
            cartorio_id=imovel.cartorio_id,
        ).first()
        
        if documento_principal:
            return documento_principal
        
        # Se não encontrar, usar o primeiro documento do imóvel
        documento_principal = Documento.objects.filter(imovel=imovel).first()
        
        return documento_principal
    
    @staticmethod
    def _construir_arvore_a_partir_documento(documento_principal, imovel, criar_documentos_automaticos):
        """
        Constrói a árvore a partir do documento principal
        """
        # Inicializar estrutura da árvore
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
        
        # Usar busca em largura para construir a árvore
        documentos_processados = set()
        conexoes_processadas = set()
        fila = deque([(documento_principal, 0)])  # (documento, nível)

        while fila:
            documento_atual, nivel = fila.popleft()

            if documento_atual.id in documentos_processados:
                continue

            documentos_processados.add(documento_atual.id)

            # Criar nó do documento
            doc_node = HierarquiaArvoreService._criar_no_documento(
                documento_atual, imovel, nivel
            )
            arvore['documentos'].append(doc_node)
            
            # Buscar documentos pais (origens) deste documento
            documentos_pais = HierarquiaArvoreService._buscar_documentos_pais(
                documento_atual, imovel, criar_documentos_automaticos
            )
            
            # Adicionar conexões diretas e documentos pais à fila
            for doc_pai in documentos_pais:
                # Criar conexão direta: filho -> pai
                conexao = {
                    'from': documento_atual.id,
                    'to': doc_pai.id,
                    'from_numero': documento_atual.numero,
                    'to_numero': doc_pai.numero,
                    'tipo': 'origem_lancamento'
                }
                
                # Evitar apenas a repetição da mesma aresta entre os mesmos IDs.
                chave_conexao = (documento_atual.id, doc_pai.id)
                if chave_conexao not in conexoes_processadas:
                    arvore['conexoes'].append(conexao)
                    conexoes_processadas.add(chave_conexao)
                
                # Adicionar à fila se não foi processado
                if doc_pai.id not in documentos_processados:
                    fila.append((doc_pai, nivel + 1))
        
        # Recalcular níveis baseado na hierarquia real
        HierarquiaArvoreService._recalcular_niveis(arvore, documento_principal.id)
        
        return arvore
    
    @staticmethod
    def _resolver_documento_por_codigo(codigo, cartorio):
        """
        Resolve um documento pela identidade completa (tipo, número
        normalizado e cartório), nunca por número isolado. Sem cartório, com
        tipo incompatível ou com identidade ambígua, não seleciona documento.
        """
        if not cartorio or not codigo:
            return None
        primeiro = codigo.strip()[:1].upper()
        if primeiro == 'M':
            tipo = 'matricula'
        elif primeiro == 'T':
            tipo = 'transcricao'
        else:
            return None
        try:
            identidade = DocumentoIdentidade(tipo, codigo, cartorio.pk)
        except (TypeError, ValueError):
            return None
        resultado = DocumentoIdentidadeService.resolver(identidade)
        return resultado.documento if resultado.status == 'encontrado' else None

    @staticmethod
    def _buscar_documentos_pais(documento, imovel, criar_documentos_automaticos):
        """
        Busca documentos pais (origens) de um documento
        CORREÇÃO: Para o documento do imóvel atual, buscar apenas origens diretas
        """
        documentos_pais = []
        documentos_processados = set()

        # CORREÇÃO: Verificar se é o documento principal do imóvel atual
        is_documento_principal = (
            documento.imovel_id == imovel.id
            and documento.tipo.tipo == imovel.tipo_documento_principal
            and documento.numero_normalizado == imovel.matricula_normalizada
            and documento.cartorio_id == imovel.cartorio_id
        )

        # Buscar lançamentos com origens
        lancamentos = documento.lancamentos.all()

        for lancamento in lancamentos:
            # CORREÇÃO: Para documento principal, buscar apenas origens diretas
            if is_documento_principal:
                # Para o documento principal, buscar apenas documentos que são origens diretas
                # (documentos que estão no mesmo imóvel e são citados como origem)
                for origem in LancamentoOrigemLeituraService.obter_origens(lancamento):
                    chave = (origem.codigo, origem.cartorio_id)
                    if chave in documentos_processados:
                        continue

                    documentos_processados.add(chave)

                    # Resolver documento pela identidade completa
                    doc_pai = HierarquiaArvoreService._resolver_documento_por_codigo(
                        origem.codigo, origem.cartorio
                    )

                    if doc_pai:
                        # Adicionar como origem direta do documento principal
                        documentos_pais.append(doc_pai)
            else:
                # Para outros documentos, usar lógica normal
                for origem in LancamentoOrigemLeituraService.obter_origens(lancamento):
                    chave = (origem.codigo, origem.cartorio_id)
                    if chave in documentos_processados:
                        continue

                    documentos_processados.add(chave)

                    # Resolver documento pela identidade completa
                    doc_pai = HierarquiaArvoreService._resolver_documento_por_codigo(
                        origem.codigo, origem.cartorio
                    )

                    if doc_pai:
                        documentos_pais.append(doc_pai)
                    elif criar_documentos_automaticos:
                        # Criar documento automaticamente se solicitado, sempre
                        # com o cartório da própria origem (nunca um cartório
                        # arbitrário).
                        doc_pai = HierarquiaArvoreService._criar_documento_automatico(
                            origem.codigo, origem.cartorio, imovel
                        )
                        if doc_pai:
                            documentos_pais.append(doc_pai)

        return documentos_pais
    
    @staticmethod
    def _criar_documento_automatico(numero_documento, cartorio, imovel):
        """
        Cria um documento automaticamente para uma origem identificada.

        O cartório é sempre o da própria origem (`origem.cartorio`), nunca um
        cartório arbitrário: sem cartório, não cria o documento (mesma regra
        aplicada em T11/T12/R06 — nunca resolver ou criar identidade sem
        contexto completo de cartório).
        """
        try:
            # Determinar tipo do documento
            from ..models import DocumentoTipo
            if numero_documento.startswith('M'):
                tipo_documento = DocumentoTipo.objects.get(tipo='matricula')
            elif numero_documento.startswith('T'):
                tipo_documento = DocumentoTipo.objects.get(tipo='transcricao')
            else:
                return None

            if not cartorio:
                return None

            # Criar documento
            from datetime import date
            documento = Documento.objects.create(
                numero=numero_documento,
                imovel=imovel,
                cartorio=cartorio,
                tipo=tipo_documento,
                data=date.today(),  # Data padrão
                livro='',  # Campo obrigatório
                folha='',  # Campo obrigatório
                origem='',  # Será preenchido quando houver lançamentos
                observacoes='Documento criado automaticamente para origem identificada'
            )
            
            return documento
            
        except Exception as e:
            print(f"Erro ao criar documento automático {numero_documento}: {e}")
            return None
    
    @staticmethod
    def _criar_no_documento(documento, imovel_atual, nivel):
        """
        Cria um nó de documento para a árvore
        """
        # Verificar se é documento do imóvel atual
        is_documento_atual = documento.imovel.id == imovel_atual.id
        
        # Verificar se é compartilhado
        is_compartilhado = not is_documento_atual
        
        # Verificar a identidade registral completa do documento principal.
        is_documento_principal = (
            is_documento_atual
            and documento.tipo.tipo == imovel_atual.tipo_documento_principal
            and documento.numero_normalizado == imovel_atual.matricula_normalizada
            and documento.cartorio_id == imovel_atual.cartorio_id
        )
        
        return {
            'id': documento.id,
            'numero': documento.numero,
            'tipo': documento.tipo.tipo,
            'tipo_display': documento.tipo.get_tipo_display(),
            'tipo_documento': documento.tipo.tipo,
            'data': documento.data.strftime('%d/%m/%Y'),
            'cartorio': documento.cartorio.nome,
            'livro': documento.livro,
            'folha': documento.folha,
            'origem': documento.origem or '',
            'observacoes': documento.observacoes or '',
            'total_lancamentos': documento.lancamentos.count(),
            'x': 0,  # Posição X (será calculada pelo frontend)
            'y': 0,  # Posição Y (será calculada pelo frontend)
            'nivel': nivel,  # Nível na árvore
            'nivel_manual': documento.nivel_manual,
            'is_importado': False,
            'is_compartilhado': is_compartilhado,
            'is_documento_atual': is_documento_principal,
            'imoveis_compartilhando': [],
            'info_importacao': '',
            'tooltip_importacao': '',
            'cadeias_dominiais': [],
            'total_cadeias': 0
        }
    
    @staticmethod
    def _recalcular_niveis(arvore, documento_principal_id):
        """
        Recalcula níveis baseado na hierarquia real
        Mantém apenas conexões diretas pai-filho
        """
        # Mapear conexões diretas
        filhos_por_pai = {}  # pai -> [filhos]
        pais_por_filho = {}  # filho -> [pais]
        
        for conexao in arvore['conexoes']:
            filho = conexao['from']
            pai = conexao['to']
            
            if pai not in filhos_por_pai:
                filhos_por_pai[pai] = []
            filhos_por_pai[pai].append(filho)
            
            if filho not in pais_por_filho:
                pais_por_filho[filho] = []
            pais_por_filho[filho].append(pai)
        
        # Calcular níveis usando busca em largura a partir do documento principal
        niveis = {}
        fila = deque([(documento_principal_id, 0)])
        visitados = set()
        
        while fila:
            documento_id, nivel = fila.popleft()
            
            if documento_id in visitados:
                continue
            visitados.add(documento_id)
            
            niveis[documento_id] = nivel
            
            # Adicionar pais diretos à fila (nível + 1)
            if documento_id in pais_por_filho:
                for pai in pais_por_filho[documento_id]:
                    if pai not in visitados:
                        fila.append((pai, nivel + 1))
        
        # Aplicar níveis aos documentos
        for doc_node in arvore['documentos']:
            nivel_calculado = niveis.get(doc_node['id'], 0)
            doc_node['nivel'] = doc_node['nivel_manual'] if doc_node['nivel_manual'] is not None else nivel_calculado
        
        # Calcular nível do fim de cadeia (nível máximo + 1)
        if arvore['documentos']:
            nivel_maximo = max(doc['nivel'] for doc in arvore['documentos'])
            nivel_fim_cadeia = nivel_maximo + 1
            
            # Aplicar nível do fim de cadeia aos nós de fim de cadeia
            for doc_node in arvore['documentos']:
                if doc_node.get('is_fim_cadeia'):
                    doc_node['nivel'] = nivel_fim_cadeia
