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
from .hierarquia_arvore_niveis_helper import recalcular_niveis
from ..utils.documento_identidade_utils import DocumentoIdentidade
import re
from collections import deque

from django.utils import timezone


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
        
        # Otimização: prefetch_related para evitar N+1 queries (issue #93)
        documento_principal = Documento.objects.select_related(
            'tipo', 'cartorio'
        ).prefetch_related(
            'lancamentos__tipo',
            'lancamentos__origens_fim_cadeia'
        ).get(id=documento_principal.id)

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

            # Injetar nós de fim de cadeia (issue #85)
            for lanc_fc in documento_atual.lancamentos.filter(
                origens_fim_cadeia__fim_cadeia=True
            ).distinct():
                for origem_fc in lanc_fc.origens_fim_cadeia.filter(
                    fim_cadeia=True
                ).order_by('indice_origem'):
                    no_fc = HierarquiaArvoreService._criar_no_fim_cadeia(
                        documento_atual, lanc_fc, origem_fc)
                    arvore['documentos'].append(no_fc)
                    arvore['conexoes'].append({
                        'from': documento_atual.id,
                        'to': no_fc['id'],
                        'from_numero': documento_atual.numero,
                        'to_numero': 'Fim de Cadeia',
                        'tipo': 'fim_cadeia',
                    })

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

        # Issue #120: exibir "Análise iniciada em:" apenas no primeiro
        # documento da cadeia; ocultar a data nos demais.
        primeiro_doc_marcado = False
        for doc_node in arvore['documentos']:
            if doc_node.get('is_fim_cadeia'):
                continue
            if not primeiro_doc_marcado:
                doc_node['label_data'] = 'Análise iniciada em:'
                primeiro_doc_marcado = True
            else:
                doc_node['data'] = ''
                doc_node['label_data'] = ''

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
            documento = Documento.objects.create(
                numero=numero_documento,
                imovel=imovel,
                cartorio=cartorio,
                tipo=tipo_documento,
                data=timezone.localdate(),  # Data padrão
                data_presumida=True,
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
            'data': documento.data_exibicao.strftime('%d/%m/%Y'),
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
    def _criar_no_fim_cadeia(documento, lancamento_fc, origem_fc):
        """Cria um nó especial de fim de cadeia para a árvore D3 (issue #85)."""
        # Extrair sigla de patrimônio público do campo origem do lançamento
        # Trata múltiplas origens separadas por ';' e formato legado de 5 partes (issue #92)
        sigla = None
        if lancamento_fc.origem:
            origens_texto = [o.strip() for o in lancamento_fc.origem.split(';') if o.strip()]
            texto = None
            if 0 <= origem_fc.indice_origem < len(origens_texto):
                candidato = origens_texto[origem_fc.indice_origem]
                if 'FIM_CADEIA' in candidato:
                    texto = candidato
            if texto is None:
                texto = next((o for o in origens_texto if 'FIM_CADEIA' in o), None)
            if texto:
                parts = texto.split(':')
                if len(parts) >= 6:
                    sigla = parts[5]
                elif len(parts) == 5:
                    sigla = parts[4]
            elif ':' in lancamento_fc.origem:
                parts = lancamento_fc.origem.split(':')
                if len(parts) >= 2:
                    sigla = parts[1]

        tipo_fc = origem_fc.tipo_fim_cadeia or 'sem_origem'
        classificacao = origem_fc.classificacao_fim_cadeia or 'sem_origem'
        espec = origem_fc.especificacao_fim_cadeia

        if tipo_fc == 'destacamento_publico' and sigla:
            titulo, numero = f"Destacamento Público\n{sigla}", sigla
        elif tipo_fc == 'outra' and espec:
            titulo = f"Outra Origem\n{espec}"
            numero = espec[:10] + "..." if len(espec) > 10 else espec
        else:
            titulo, numero = "Sem Origem", "Sem Origem"

        return {
            'id': f"fim_cadeia_{documento.id}_{lancamento_fc.id}_{origem_fc.id}",
            'numero': numero, 'tipo': 'fim_cadeia',
            'tipo_display': 'Fim de Cadeia', 'tipo_documento': 'fim_cadeia',
            'data': '', 'cartorio': '', 'livro': '', 'folha': '',
            'origem': '', 'observacoes': '', 'total_lancamentos': 0,
            'x': 0, 'y': 0, 'nivel': 0, 'nivel_manual': None,
            'is_importado': False, 'is_compartilhado': False,
            'imoveis_compartilhando': [], 'info_importacao': '',
            'tooltip_importacao': '', 'cadeias_dominiais': [],
            'total_cadeias': 0, 'is_fim_cadeia': True,
            'tipo_fim_cadeia': tipo_fc, 'classificacao_fim_cadeia': classificacao,
            'sigla_patrimonio_publico': sigla, 'titulo_fim_cadeia': titulo,
            'info_adicional_fim_cadeia': origem_fc.info_adicional_fim_cadeia,
            'documento_origem_id': documento.id,
        }

    @staticmethod
    def _recalcular_niveis(arvore, documento_principal_id):
        """Recalcula níveis — delega para helper para manter arquivo ≤400 linhas."""
        recalcular_niveis(arvore, documento_principal_id)
