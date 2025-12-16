"""
Service final corrigido para construção da árvore de hierarquia
Implementa a lógica correta: filho -> pai (esquerda -> direita)
Resolve todos os problemas identificados nos testes
"""

from ..models import Documento, Lancamento
from .hierarquia_origem_service import HierarquiaOrigemService
from .documento_service import DocumentoService
import re
import logging
from collections import deque

logger = logging.getLogger(__name__)


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
        # Primeiro, tentar encontrar documento com número igual à matrícula
        documento_principal = Documento.objects.filter(
            imovel=imovel,
            numero=imovel.matricula
        ).first()
        
        if documento_principal:
            return documento_principal
        
        # Se não encontrar, tentar encontrar documento com número que contenha a matrícula
        documento_principal = Documento.objects.filter(
            imovel=imovel,
            numero__icontains=imovel.matricula
        ).first()
        
        if documento_principal:
            return documento_principal
        
        # Se não encontrar, usar o primeiro documento do imóvel
        # Priorizar matrículas para documentos que começam com M
        if imovel.matricula.startswith('M'):
            documento_principal = Documento.objects.filter(
                imovel=imovel,
                tipo__tipo='matricula'
            ).first()
            if not documento_principal:
                documento_principal = Documento.objects.filter(imovel=imovel).first()
        else:
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
        documentos_por_numero = {}
        fila = deque([(documento_principal, 0)])  # (documento, nível)
        
        while fila:
            documento_atual, nivel = fila.popleft()
            
            if documento_atual.id in documentos_processados:
                continue
            
            documentos_processados.add(documento_atual.id)
            
            # Criar nó do documento
            doc_node = HierarquiaArvoreService._criar_no_documento(
                documento_atual, imovel, nivel, lancamento_origem=None
            )
            documentos_por_numero[documento_atual.numero] = doc_node
            arvore['documentos'].append(doc_node)
            
            # Buscar documentos pais (origens) deste documento
            documentos_pais = HierarquiaArvoreService._buscar_documentos_pais(
                documento_atual, imovel, criar_documentos_automaticos
            )
            
            # Adicionar conexões diretas e documentos pais à fila
            for doc_pai in documentos_pais:
                # Criar conexão direta: filho -> pai
                conexao = {
                    'from': documento_atual.numero,
                    'to': doc_pai.numero,
                    'tipo': 'origem_lancamento'
                }
                
                # Evitar duplicatas
                if not any(c['from'] == documento_atual.numero and c['to'] == doc_pai.numero 
                          for c in arvore['conexoes']):
                    arvore['conexoes'].append(conexao)
                
                # Adicionar à fila se não foi processado
                if doc_pai.id not in documentos_processados:
                    fila.append((doc_pai, nivel + 1))
        
        # Recalcular níveis baseado na hierarquia real
        HierarquiaArvoreService._recalcular_niveis(arvore, documento_principal.numero)
        
        return arvore
    
    @staticmethod
    def _buscar_documentos_pais(documento, imovel, criar_documentos_automaticos):
        """
        Busca documentos pais (origens) de um documento
        CORREÇÃO: Para o documento do imóvel atual, buscar apenas origens diretas
        """
        documentos_pais = []
        documentos_processados = set()
        
        # CORREÇÃO: Verificar se é o documento principal do imóvel atual
        is_documento_principal = (documento.imovel.id == imovel.id and 
                                 (documento.numero == imovel.matricula or 
                                  documento.numero.endswith(imovel.matricula)))
        
        # Buscar lançamentos com origens
        lancamentos = documento.lancamentos.filter(
            origem__isnull=False
        ).exclude(origem='')
        
        for lancamento in lancamentos:
            # Extrair origens do lançamento com método robusto
            origens = HierarquiaArvoreService._extrair_origens_robusto(lancamento.origem)
            
            # CORREÇÃO: Para documento principal, buscar apenas origens diretas
            if is_documento_principal:
                # Para o documento principal, buscar apenas documentos que são origens diretas
                # (documentos que estão no mesmo imóvel e são citados como origem)
                for origem_numero in origens:
                    if origem_numero in documentos_processados:
                        continue
                    
                    documentos_processados.add(origem_numero)
                    
                    # Buscar documento com este número
                    # REGRA: Se não existe no cartório de origem, criar novo documento
                    doc_pai = None
                    
                    if lancamento.cartorio_origem:
                        # CORREÇÃO: Buscar primeiro no cartório de origem especificado
                        doc_pai = Documento.objects.filter(
                            numero=origem_numero,
                            cartorio=lancamento.cartorio_origem
                        ).first()
                        
                        # Se não encontrou no cartório de origem, buscar em qualquer cartório
                        # para preservar documentos já existentes
                        if not doc_pai:
                            logger.warning(f"Documento {origem_numero} não encontrado no cartório de origem {lancamento.cartorio_origem.nome}. Buscando em outros cartórios...")
                            
                            # Buscar todos os documentos com este número
                            todos_docs = Documento.objects.filter(numero=origem_numero)
                            
                            if todos_docs.exists():
                                # PRIORIZAR: Documentos com lançamentos sobre documentos vazios
                                docs_com_lancamentos = [doc for doc in todos_docs if doc.lancamentos.count() > 0]
                                
                                if docs_com_lancamentos:
                                    # Se há documentos com lançamentos, usar o primeiro
                                    doc_pai = docs_com_lancamentos[0]
                                    logger.warning(f"Documento {origem_numero} encontrado com lançamentos no cartório {doc_pai.cartorio.nome} (priorizado sobre documentos vazios)")
                                else:
                                    # Se não há documentos com lançamentos, usar qualquer um
                                    doc_pai = todos_docs.first()
                                    logger.warning(f"Documento {origem_numero} encontrado no cartório {doc_pai.cartorio.nome} (nenhum com lançamentos)")
                            else:
                                doc_pai = None
                        
                        # Só criar automaticamente se REALMENTE não existir em lugar nenhum
                        if not doc_pai:
                            logger.warning(f"Documento {origem_numero} não encontrado em nenhum cartório - não criando automaticamente para evitar duplicatas")
                            # Não criar documento automático - apenas pular
                            continue
                    else:
                        # Se não tem cartório de origem, buscar qualquer documento
                        # Priorizar transcrições para documentos que começam com T
                        if origem_numero.startswith('T'):
                            doc_pai = Documento.objects.filter(
                                numero=origem_numero,
                                tipo__tipo='transcricao'
                            ).first()
                            if not doc_pai:
                                doc_pai = Documento.objects.filter(numero=origem_numero).first()
                        else:
                            doc_pai = Documento.objects.filter(numero=origem_numero).first()
                    
                    if doc_pai:
                        # Adicionar como origem direta do documento principal
                        documentos_pais.append(doc_pai)
            else:
                # Para outros documentos, usar lógica normal
                for origem_numero in origens:
                    if origem_numero in documentos_processados:
                        continue
                    
                    documentos_processados.add(origem_numero)
                    
                    # Buscar documento com este número
                    # REGRA: Se não existe no cartório de origem, criar novo documento
                    doc_pai = None
                    
                    if lancamento.cartorio_origem:
                        # CORREÇÃO: Buscar primeiro no cartório de origem especificado
                        doc_pai = Documento.objects.filter(
                            numero=origem_numero,
                            cartorio=lancamento.cartorio_origem
                        ).first()
                        
                        # Se não encontrou no cartório de origem, buscar em qualquer cartório
                        # para preservar documentos já existentes
                        if not doc_pai:
                            logger.warning(f"Documento {origem_numero} não encontrado no cartório de origem {lancamento.cartorio_origem.nome}. Buscando em outros cartórios...")
                            
                            # Buscar todos os documentos com este número
                            todos_docs = Documento.objects.filter(numero=origem_numero)
                            
                            if todos_docs.exists():
                                # PRIORIZAR: Documentos com lançamentos sobre documentos vazios
                                docs_com_lancamentos = [doc for doc in todos_docs if doc.lancamentos.count() > 0]
                                
                                if docs_com_lancamentos:
                                    # Se há documentos com lançamentos, usar o primeiro
                                    doc_pai = docs_com_lancamentos[0]
                                    logger.warning(f"Documento {origem_numero} encontrado com lançamentos no cartório {doc_pai.cartorio.nome} (priorizado sobre documentos vazios)")
                                else:
                                    # Se não há documentos com lançamentos, usar qualquer um
                                    doc_pai = todos_docs.first()
                                    logger.warning(f"Documento {origem_numero} encontrado no cartório {doc_pai.cartorio.nome} (nenhum com lançamentos)")
                            else:
                                doc_pai = None
                        
                        # Só criar automaticamente se REALMENTE não existir em lugar nenhum
                        if not doc_pai:
                            logger.warning(f"Documento {origem_numero} não encontrado em nenhum cartório - não criando automaticamente para evitar duplicatas")
                            # Não criar documento automático - apenas pular
                            continue
                    else:
                        # Se não tem cartório de origem, buscar qualquer documento
                        # Priorizar transcrições para documentos que começam com T
                        if origem_numero.startswith('T'):
                            doc_pai = Documento.objects.filter(
                                numero=origem_numero,
                                tipo__tipo='transcricao'
                            ).first()
                            if not doc_pai:
                                doc_pai = Documento.objects.filter(numero=origem_numero).first()
                        else:
                            doc_pai = Documento.objects.filter(numero=origem_numero).first()
                    
                    if doc_pai:
                        documentos_pais.append(doc_pai)
                    else:
                        # CORREÇÃO: NÃO criar documentos automaticamente para evitar duplicatas
                        logger.warning(f"Documento {origem_numero} não encontrado - não criando automaticamente para evitar duplicatas")
        
        return documentos_pais
    
    @staticmethod
    def _criar_documento_automatico(numero_documento, cartorio, imovel):
        """
        Cria um documento automaticamente para uma origem identificada
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
            logger.error(f"Erro ao criar documento automático {numero_documento}: {e}")
            return None
    
    @staticmethod
    def _criar_no_documento(documento, imovel_atual, nivel, lancamento_origem=None):
        """
        Cria um nó de documento para a árvore
        """
        # Verificar se é documento do imóvel atual
        is_documento_atual = documento.imovel.id == imovel_atual.id
        
        # Verificar se é compartilhado
        # NOTA: Considerar cartório de origem se disponível
        is_compartilhado = not is_documento_atual
        
        # Se o documento foi marcado como "cartório diferente", não marcar como compartilhado
        # para evitar borda tracejada verde incorreta
        if hasattr(documento, '_cartorio_diferente') and documento._cartorio_diferente:
            is_compartilhado = False
        
        # Verificar se é o documento principal do imóvel atual
        # Pode ser igual à matrícula ou conter a matrícula (ex: M6700 para matrícula 6700)
        is_documento_principal = (is_documento_atual and 
                                 (documento.numero == imovel_atual.matricula or 
                                  documento.numero.endswith(imovel_atual.matricula)))
        
        # Corrigir tipo_documento baseado no número do documento
        tipo_correto = documento.tipo.tipo
        if documento.numero.startswith('T') and documento.tipo.tipo == 'matricula':
            tipo_correto = 'transcricao'
        elif documento.numero.startswith('M') and documento.tipo.tipo == 'transcricao':
            tipo_correto = 'matricula'
        
        return {
            'id': documento.id,
            'numero': documento.numero,
            'tipo': documento.tipo.tipo,
            'tipo_display': documento.tipo.get_tipo_display(),
            'tipo_documento': tipo_correto,
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
    def _recalcular_niveis(arvore, documento_principal_numero):
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
        fila = deque([(documento_principal_numero, 0)])
        visitados = set()
        
        while fila:
            doc_numero, nivel = fila.popleft()
            
            if doc_numero in visitados:
                continue
            visitados.add(doc_numero)
            
            niveis[doc_numero] = nivel
            
            # Adicionar pais diretos à fila (nível + 1)
            if doc_numero in pais_por_filho:
                for pai in pais_por_filho[doc_numero]:
                    if pai not in visitados:
                        fila.append((pai, nivel + 1))
        
        # Aplicar níveis aos documentos
        for doc_node in arvore['documentos']:
            nivel_calculado = niveis.get(doc_node['numero'], 0)
            doc_node['nivel'] = doc_node['nivel_manual'] if doc_node['nivel_manual'] is not None else nivel_calculado
        
        # Calcular nível do fim de cadeia (nível máximo + 1)
        if arvore['documentos']:
            nivel_maximo = max(doc['nivel'] for doc in arvore['documentos'])
            nivel_fim_cadeia = nivel_maximo + 1
            
            # Aplicar nível do fim de cadeia aos nós de fim de cadeia
            for doc_node in arvore['documentos']:
                if doc_node.get('is_fim_cadeia'):
                    doc_node['nivel'] = nivel_fim_cadeia
    
    @staticmethod
    def _criar_documento_automatico_para_origem(numero_documento, cartorio_origem, imovel_atual):
        """
        Cria um documento automaticamente para uma origem que não existe no cartório especificado
        """
        from ..models import Documento, DocumentoTipo
        from django.utils import timezone
        
        # Verificar se já existe documento com este número e cartório
        documento_existente = Documento.objects.filter(
            numero=numero_documento,
            cartorio=cartorio_origem
        ).first()
        
        if documento_existente:
            return documento_existente
        
        # Determinar tipo do documento
        tipo_documento = DocumentoTipo.objects.filter(tipo='matricula').first()
        if not tipo_documento:
            return None
        
        # Criar novo documento
        try:
            novo_documento = Documento.objects.create(
                numero=numero_documento,
                cartorio=cartorio_origem,
                tipo=tipo_documento,
                imovel=imovel_atual,  # Temporariamente associado ao imóvel atual
                data=timezone.now().date(),
                observacoes=f'Documento criado automaticamente para origem {numero_documento} do cartório {cartorio_origem.nome}'
            )
            
            logger.info(f"Documento criado automaticamente: {numero_documento} - {cartorio_origem.nome}")
            return novo_documento
            
        except Exception as e:
            logger.error(f"Erro ao criar documento {numero_documento}: {e}")
            return None
    
    @staticmethod
    def _extrair_origens_robusto(origem_texto):
        """
        Extrai origens com múltiplos padrões para capturar mais casos
        Resolve o problema T1004 -> T2822
        """
        if not origem_texto:
            return []
        
        origens = []
        
        # Padrão 1: M/T seguido de números (padrão atual)
        padrao1 = re.findall(r'[MT]\d+', origem_texto)
        origens.extend(padrao1)
        
        # Padrão 2: M/T com separadores (espaços, hífens, pontos)
        padrao2 = re.findall(r'[MT]\s*[-.]?\s*\d+', origem_texto)
        for match in padrao2:
            # Limpar e normalizar
            limpo = re.sub(r'\s*[-.]?\s*', '', match)
            if limpo not in origens:
                origens.append(limpo)
        
        # Padrão 3: Números simples (assumir como matrícula se >= 3 dígitos)
        padrao3 = re.findall(r'\b\d{3,}\b', origem_texto)
        for num in padrao3:
            # Verificar se não está já capturado em outros padrões
            if not any(f'M{num}' in origem_texto or f'T{num}' in origem_texto for _ in [1]):
                # Assumir como matrícula por padrão
                if f'M{num}' not in origens:
                    origens.append(f'M{num}')
        
        # Padrão 4: Busca por texto livre
        # Procurar por "transcrição" + número
        padrao4 = re.findall(r'transcri[çc][ãa]o\s*(\d+)', origem_texto, re.IGNORECASE)
        for num in padrao4:
            if f'T{num}' not in origens:
                origens.append(f'T{num}')
        
        # Procurar por "matrícula" + número
        padrao5 = re.findall(r'matr[íi]cula\s*(\d+)', origem_texto, re.IGNORECASE)
        for num in padrao5:
            if f'M{num}' not in origens:
                origens.append(f'M{num}')
        
        # Remover duplicatas e retornar
        return list(set(origens))