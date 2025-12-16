"""
Versão melhorada do HierarquiaArvoreService para resolver problemas de conexão
Especificamente para o caso T1004 -> T2822
"""

from ..models import Documento, Lancamento
from .hierarquia_origem_service import HierarquiaOrigemService
from .documento_service import DocumentoService
import re
import logging
from collections import deque

logger = logging.getLogger(__name__)


class HierarquiaArvoreServiceMelhorado:
    """
    Versão melhorada do serviço para construir árvore da cadeia dominial
    Resolve problemas de conexão entre documentos citados
    """
    
    @staticmethod
    def extrair_origens_robusto(origem_texto):
        """
        Extrai origens com múltiplos padrões para capturar mais casos
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
        
        # Padrão 4: Busca por texto livre (último recurso)
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
    
    @staticmethod
    def buscar_documento_origem_robusto(origem_numero, cartorio_origem=None, lancamento=None):
        """
        Busca documento de origem APENAS no cartório de origem especificado
        CORREÇÃO: Não busca em outros cartórios para evitar conexões incorretas
        """
        logger.info(f"🔍 Buscando documento origem: {origem_numero}")
        
        # REGRA: Buscar APENAS no cartório de origem especificado
        if cartorio_origem:
            # Estratégia 1: Buscar exatamente como especificado
            doc = Documento.objects.filter(
                numero=origem_numero,
                cartorio=cartorio_origem
            ).first()
            
            if doc:
                logger.info(f"✅ Documento {origem_numero} encontrado no cartório de origem {cartorio_origem.nome}")
                return doc
            
            # Estratégia 2: Buscar por variações do número no MESMO cartório
            numero_limpo = re.sub(r'^[MT]', '', origem_numero)
            if numero_limpo.isdigit():
                # Buscar com prefixo M no mesmo cartório
                doc_m = Documento.objects.filter(
                    numero=f'M{numero_limpo}',
                    cartorio=cartorio_origem
                ).first()
                if doc_m:
                    logger.info(f"✅ Documento encontrado como M{numero_limpo} no cartório {cartorio_origem.nome}")
                    return doc_m
                
                # Buscar com prefixo T no mesmo cartório
                doc_t = Documento.objects.filter(
                    numero=f'T{numero_limpo}',
                    cartorio=cartorio_origem
                ).first()
                if doc_t:
                    logger.info(f"✅ Documento encontrado como T{numero_limpo} no cartório {cartorio_origem.nome}")
                    return doc_t
            
            logger.warning(f"❌ Documento {origem_numero} não encontrado no cartório de origem {cartorio_origem.nome}")
            return None
        
        # Se não tem cartório de origem especificado, não buscar em lugar nenhum
        logger.warning(f"❌ Cartório de origem não especificado para {origem_numero} - não buscando")
        return None
    
    @staticmethod
    def criar_documento_automatico_seguro(origem_numero, cartorio_origem, imovel_atual, lancamento):
        """
        Cria documento automaticamente de forma segura
        """
        logger.info(f"🔧 Tentando criar documento automático: {origem_numero}")
        
        # Verificar se já existe
        if Documento.objects.filter(numero=origem_numero).exists():
            logger.info(f"✅ Documento {origem_numero} já existe, não criando")
            return Documento.objects.filter(numero=origem_numero).first()
        
        # Determinar tipo do documento
        from ..models import DocumentoTipo
        if origem_numero.startswith('M'):
            tipo_documento = DocumentoTipo.objects.filter(tipo='matricula').first()
        elif origem_numero.startswith('T'):
            tipo_documento = DocumentoTipo.objects.filter(tipo='transcricao').first()
        else:
            # Assumir matrícula por padrão
            tipo_documento = DocumentoTipo.objects.filter(tipo='matricula').first()
        
        if not tipo_documento:
            logger.error(f"❌ Tipo de documento não encontrado para {origem_numero}")
            return None
        
        # Criar documento
        try:
            from datetime import date
            documento = Documento.objects.create(
                numero=origem_numero,
                imovel=imovel_atual,  # Temporariamente associado ao imóvel atual
                cartorio=cartorio_origem,
                tipo=tipo_documento,
                data=date.today(),
                livro='',
                folha='',
                origem=f'Documento criado automaticamente para origem {origem_numero}',
                observacoes=f'Criado automaticamente a partir de lançamento {lancamento.id} do documento {lancamento.documento.numero}'
            )
            
            logger.info(f"✅ Documento {origem_numero} criado automaticamente com ID {documento.id}")
            return documento
            
        except Exception as e:
            logger.error(f"❌ Erro ao criar documento {origem_numero}: {e}")
            return None
    
    @staticmethod
    def buscar_documentos_pais_melhorado(documento, imovel, criar_documentos_automaticos=False):
        """
        Versão melhorada para buscar documentos pais (origens)
        Resolve o problema T1004 -> T2822
        """
        documentos_pais = []
        documentos_processados = set()
        
        logger.info(f"🔍 Buscando documentos pais para {documento.numero}")
        
        # Buscar lançamentos com origens
        lancamentos = documento.lancamentos.filter(
            origem__isnull=False
        ).exclude(origem='')
        
        logger.info(f"📋 Encontrados {lancamentos.count()} lançamentos com origens")
        
        for lancamento in lancamentos:
            logger.info(f"📝 Processando lançamento {lancamento.id}: {lancamento.origem}")
            
            # Extrair origens com método robusto
            origens = HierarquiaArvoreServiceMelhorado.extrair_origens_robusto(lancamento.origem)
            
            logger.info(f"🎯 Origens extraídas: {origens}")
            
            for origem_numero in origens:
                if origem_numero in documentos_processados:
                    logger.info(f"⏭️ Origem {origem_numero} já processada, pulando")
                    continue
                
                documentos_processados.add(origem_numero)
                
                # Buscar documento com método robusto
                doc_pai = HierarquiaArvoreServiceMelhorado.buscar_documento_origem_robusto(
                    origem_numero, 
                    lancamento.cartorio_origem, 
                    lancamento
                )
                
                if doc_pai:
                    logger.info(f"✅ Documento pai encontrado: {doc_pai.numero} (ID: {doc_pai.id})")
                    documentos_pais.append(doc_pai)
                else:
                    # Tentar criar documento automaticamente se habilitado
                    if criar_documentos_automaticos and lancamento.cartorio_origem:
                        logger.info(f"🔧 Tentando criar documento automático para {origem_numero}")
                        doc_pai = HierarquiaArvoreServiceMelhorado.criar_documento_automatico_seguro(
                            origem_numero, 
                            lancamento.cartorio_origem, 
                            imovel, 
                            lancamento
                        )
                        
                        if doc_pai:
                            logger.info(f"✅ Documento criado automaticamente: {doc_pai.numero}")
                            documentos_pais.append(doc_pai)
                        else:
                            logger.warning(f"❌ Falha ao criar documento automático para {origem_numero}")
                    else:
                        logger.warning(f"❌ Documento {origem_numero} não encontrado e criação automática desabilitada")
        
        logger.info(f"📊 Total de documentos pais encontrados: {len(documentos_pais)}")
        return documentos_pais
    
    @staticmethod
    def construir_arvore_cadeia_dominial_melhorada(imovel, criar_documentos_automaticos=True):
        """
        Versão melhorada para construir a árvore da cadeia dominial
        """
        logger.info(f"🌳 Construindo árvore melhorada para imóvel {imovel.matricula}")
        
        # Identificar documento principal
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
        
        logger.info(f"📄 Documento principal identificado: {documento_principal.numero}")
        
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
            
            # Buscar documentos pais com método melhorado
            documentos_pais = HierarquiaArvoreServiceMelhorado.buscar_documentos_pais_melhorado(
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
                    logger.info(f"🔗 Conexão criada: {documento_atual.numero} -> {doc_pai.numero}")
                
                # Adicionar à fila se não foi processado
                if doc_pai.id not in documentos_processados:
                    fila.append((doc_pai, nivel + 1))
        
        # Recalcular níveis baseado na hierarquia real
        HierarquiaArvoreService._recalcular_niveis(arvore, documento_principal.numero)
        
        logger.info(f"✅ Árvore construída com {len(arvore['documentos'])} documentos e {len(arvore['conexoes'])} conexões")
        return arvore
