"""
Service especializado para construção da árvore de hierarquia
"""

from ..models import Documento, Lancamento
from .hierarquia_origem_service import HierarquiaOrigemService
from .documento_importado_service import DocumentoImportadoService
import re
from collections import deque


class HierarquiaArvoreService:
    """
    Service para construir e gerenciar a árvore de hierarquia da cadeia dominial
    """
    
    @staticmethod
    def construir_arvore_cadeia_dominial(imovel, criar_documentos_automaticos=False):
        """
        Constrói a estrutura de árvore da cadeia dominial para visualização
        
        Args:
            imovel: Objeto Imovel
            criar_documentos_automaticos: Se True, cria documentos automaticamente para origens identificadas
        """
        # Otimização: usar select_related e prefetch_related para reduzir queries
        documentos = Documento.objects.filter(imovel=imovel)\
            .select_related('cartorio', 'tipo')\
            .prefetch_related('lancamentos', 'lancamentos__tipo')\
            .order_by('data')
        
        # Buscar documentos importados que são referenciados pelos lançamentos deste imóvel
        documentos_importados = HierarquiaArvoreService._buscar_documentos_importados(imovel)
        
        # Adicionar documentos importados à lista
        documentos = list(documentos) + documentos_importados
        
        # Processar origens identificadas de lançamentos (só criar documentos se solicitado)
        origens_identificadas = HierarquiaOrigemService.processar_origens_identificadas(imovel, criar_documentos_automaticos)
        
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
        fins_cadeia_processados = {}  # Para evitar duplicação de nós de fim de cadeia
        
        for documento in documentos:
            doc_node = HierarquiaArvoreService._criar_no_documento(documento, imovel)
            documentos_por_numero[documento.numero] = doc_node
            arvore['documentos'].append(doc_node)
            
            # Verificar se é um documento de início de matrícula com fim de cadeia
            if documento.tipo.tipo == 'matricula':
                from ..models import OrigemFimCadeia
                lancamentos_fim_cadeia = documento.lancamentos.filter(origens_fim_cadeia__isnull=False).distinct()
                if lancamentos_fim_cadeia.exists():
                    lancamento_fim_cadeia = lancamentos_fim_cadeia.first()
                    origem_fim_cadeia = lancamento_fim_cadeia.origens_fim_cadeia.first()
                    
                    # Criar nó especial de fim de cadeia
                    fim_cadeia_node = HierarquiaArvoreService._criar_no_fim_cadeia(documento, lancamento_fim_cadeia, origem_fim_cadeia)
                    
                    # Verificar se já existe um nó de fim de cadeia com o mesmo ID
                    fim_cadeia_id = fim_cadeia_node['fim_cadeia_id']
                    if fim_cadeia_id not in fins_cadeia_processados:
                        fins_cadeia_processados[fim_cadeia_id] = fim_cadeia_node
                        arvore['documentos'].append(fim_cadeia_node)
        
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
    def _buscar_documentos_importados(imovel):
        """
        Busca documentos importados que são referenciados pelos lançamentos deste imóvel
        E também toda a cadeia dominial desses documentos importados
        
        Args:
            imovel: Objeto Imovel
            
        Returns:
            List: Lista de documentos importados e sua cadeia dominial
        """
        documentos_importados = []
        documentos_processados = set()
        
        # Buscar todos os lançamentos deste imóvel
        from ..models import Lancamento
        lancamentos = Lancamento.objects.filter(
            documento__imovel=imovel,
            origem__isnull=False
        ).exclude(origem='')
        
        # Para cada lançamento, verificar se a origem é um documento importado
        for lancamento in lancamentos:
            origens = [o.strip() for o in lancamento.origem.split(';') if o.strip()]
            
            for origem_numero in origens:
                # Buscar documento com este número que está em outro imóvel
                from ..models import Documento
                doc_importado = Documento.objects.filter(
                    numero=origem_numero
                ).exclude(
                    imovel=imovel
                ).select_related('cartorio', 'tipo').first()
                
                if doc_importado and doc_importado.id not in documentos_processados:
                    documentos_importados.append(doc_importado)
                    documentos_processados.add(doc_importado.id)
                    
                    # Buscar toda a cadeia dominial deste documento importado
                    cadeia_dominial = HierarquiaArvoreService._buscar_cadeia_dominial_documento(doc_importado)
                    for doc_cadeia in cadeia_dominial:
                        if doc_cadeia.id not in documentos_processados:
                            documentos_importados.append(doc_cadeia)
                            documentos_processados.add(doc_cadeia.id)
        
        return documentos_importados
    
    @staticmethod
    def _buscar_cadeia_dominial_documento(documento):
        """
        Busca toda a cadeia dominial de um documento (documentos que são origem dele)
        
        Args:
            documento: Documento para buscar a cadeia dominial
            
        Returns:
            List: Lista de documentos da cadeia dominial
        """
        from ..models import Lancamento, Documento
        from ..services.hierarquia_service import HierarquiaService
        
        # Usar o service que busca toda a cadeia dominial
        try:
            # Buscar o imóvel do documento
            imovel_documento = documento.imovel
            
            # Buscar TODOS os documentos de QUALQUER imóvel (não apenas do mesmo imóvel)
            todos_documentos = Documento.objects.all()\
                .select_related('cartorio', 'tipo')\
                .prefetch_related('lancamentos')\
                .order_by('data')
            
            # Filtrar apenas documentos que são parte da cadeia deste documento específico
            cadeia_documento = []
            for doc_imovel in todos_documentos:
                # Verificar se este documento é parte da cadeia do documento original
                if HierarquiaArvoreService._documento_pertence_cadeia(doc_imovel, documento):
                    cadeia_documento.append(doc_imovel)
            
            return cadeia_documento
            
        except Exception as e:
            print(f"Erro ao buscar cadeia dominial do documento {documento.numero}: {str(e)}")
            return []
    
    @staticmethod
    def _documento_pertence_cadeia(documento_candidato, documento_origem, documentos_processados=None):
        """
        Verifica se um documento candidato pertence à cadeia dominial de um documento origem
        Faz busca recursiva para encontrar toda a cadeia
        
        Args:
            documento_candidato: Documento a verificar
            documento_origem: Documento origem da cadeia
            documentos_processados: Set de IDs já processados (para evitar loops)
            
        Returns:
            bool: True se pertence à cadeia
        """
        if documentos_processados is None:
            documentos_processados = set()
        
        # Se é o próprio documento origem, pertence
        if documento_candidato.id == documento_origem.id:
            return True
        
        # Evitar loops infinitos
        if documento_origem.id in documentos_processados:
            return False
        
        documentos_processados.add(documento_origem.id)
        
        # Verificar se o documento candidato é referenciado como origem do documento origem
        from ..models import Lancamento, Documento
        
        # Verificar origens dos lançamentos do documento origem
        lancamentos_origem = Lancamento.objects.filter(documento=documento_origem)
        for lancamento in lancamentos_origem:
            if lancamento.origem:
                origens = [o.strip() for o in lancamento.origem.split(';') if o.strip()]
                if documento_candidato.numero in origens:
                    return True
                
                # Buscar recursivamente nos documentos de origem
                for origem_numero in origens:
                    try:
                        # Usar filter().first() em vez de get() para evitar erro de múltiplos objetos
                        # Buscar em qualquer imóvel, não apenas no mesmo imóvel
                        doc_origem = Documento.objects.filter(
                            numero=origem_numero
                        ).first()
                        
                        if doc_origem and HierarquiaArvoreService._documento_pertence_cadeia(
                            documento_candidato, doc_origem, documentos_processados
                        ):
                            return True
                    except Exception as e:
                        print(f"Erro ao buscar documento origem {origem_numero}: {e}")
                        continue
        
        # Verificar origem do próprio documento origem
        if documento_origem.origem:
            origens = [o.strip() for o in documento_origem.origem.split(';') if o.strip()]
            if documento_candidato.numero in origens:
                return True
            
            # Buscar recursivamente nos documentos de origem
            for origem_numero in origens:
                try:
                    # Usar filter().first() em vez de get() para evitar erro de múltiplos objetos
                    # Buscar em qualquer imóvel, não apenas no mesmo imóvel
                    doc_origem = Documento.objects.filter(
                        numero=origem_numero
                    ).first()
                    
                    if doc_origem and HierarquiaArvoreService._documento_pertence_cadeia(
                        documento_candidato, doc_origem, documentos_processados
                    ):
                        return True
                except Exception as e:
                    print(f"Erro ao buscar documento origem {origem_numero}: {e}")
                    continue
        
        return False
    
    @staticmethod
    def _criar_no_documento(documento, imovel=None):
        """
        Cria um nó de documento para a árvore
        """
        # CORREÇÃO: Documentos referenciados devem ser compartilhados, não importados
        # Um documento só é "importado" se foi explicitamente importado via interface
        is_importado = False
        if imovel:
            # Verificar se este documento foi explicitamente importado PARA este imóvel
            from ..models import DocumentoImportado
            is_importado = DocumentoImportado.objects.filter(
                documento=documento,
                documento__imovel=imovel  # O documento pertence ao imóvel atual
            ).exists()
            
            # NÃO marcar como importado se o documento não pertence ao imóvel atual
            # Isso será tratado como compartilhado
        info_importacao = None
        tooltip_importacao = None
        cadeias_dominiais = []
        
        if is_importado:
            info_importacao = DocumentoImportadoService.get_info_importacao(documento)
            tooltip_importacao = DocumentoImportadoService.get_tooltip_importacao(documento)
            
            # Buscar todas as cadeias dominiais onde este documento aparece
            from ..models import DocumentoImportado
            importacoes = DocumentoImportado.objects.filter(documento=documento)
            for importacao in importacoes:
                cadeias_dominiais.append({
                    'imovel_id': importacao.imovel_origem.id,
                    'imovel_matricula': importacao.imovel_origem.matricula,
                    'imovel_nome': importacao.imovel_origem.nome,
                    'data_importacao': importacao.data_importacao.strftime('%d/%m/%Y'),
                    'importado_por': importacao.importado_por.username if importacao.importado_por else 'Sistema'
                })
        
        # Verificar se documento está sendo compartilhado (referenciado em outros imóveis)
        is_compartilhado = False
        imoveis_compartilhando = []
        
        if imovel:
            # Verificar se este documento está sendo referenciado em outros imóveis
            from ..models import Lancamento
            lancamentos_compartilhando = Lancamento.objects.filter(
                origem__icontains=documento.numero
            ).exclude(
                documento__imovel=documento.imovel
            ).select_related('documento__imovel')
            
            if lancamentos_compartilhando.exists():
                is_compartilhado = True
                imoveis_compartilhando = sorted(list(set(
                    lanc.documento.imovel.matricula for lanc in lancamentos_compartilhando
                )))
        
        return {
            'id': documento.id,
            'numero': documento.numero,
            'tipo': documento.tipo.tipo,
            'tipo_display': documento.tipo.get_tipo_display(),
            'tipo_documento': documento.tipo.tipo,  # Adicionar tipo do documento para cores
            'data': documento.data.strftime('%d/%m/%Y'),
            'cartorio': documento.cartorio.nome,
            'livro': documento.livro,
            'folha': documento.folha,
            'origem': documento.origem or '',
            'observacoes': documento.observacoes or '',
            'total_lancamentos': documento.lancamentos.count(),
            'x': 0,  # Posição X (será calculada pelo frontend)
            'y': 0,  # Posição Y (será calculada pelo frontend)
            'nivel': 0,  # Nível na árvore (será calculado)
            'nivel_manual': documento.nivel_manual,  # Nível manual definido pelo usuário
            'is_importado': is_importado,
            'is_compartilhado': is_compartilhado,
            'imoveis_compartilhando': imoveis_compartilhando,
            'info_importacao': info_importacao,
            'tooltip_importacao': tooltip_importacao,
            'cadeias_dominiais': cadeias_dominiais,
            'total_cadeias': len(cadeias_dominiais)
        }
    
    @staticmethod
    def _criar_no_fim_cadeia(documento, lancamento_fim_cadeia, origem_fim_cadeia):
        """
        Cria um nó especial para representar o fim de cadeia usando o modelo FimCadeia
        """
        from ..models import FimCadeia
        
        # Extrair informações da origem do lançamento
        sigla_patrimonio_publico = None
        nome_fim_cadeia = None
        
        if lancamento_fim_cadeia.origem:
            if 'FIM_CADEIA' in lancamento_fim_cadeia.origem:
                origem_parts = lancamento_fim_cadeia.origem.split(':')
                if len(origem_parts) >= 6:
                    sigla_patrimonio_publico = origem_parts[5]
                    nome_fim_cadeia = sigla_patrimonio_publico
            elif ':' in lancamento_fim_cadeia.origem:
                # Formato novo: Destacamento Público:Sigla:Classificação
                primeira_origem = lancamento_fim_cadeia.origem.split(';')[0].strip()
                origem_parts = primeira_origem.split(':')
                if len(origem_parts) >= 2:
                    sigla_patrimonio_publico = origem_parts[1].strip()
                    nome_fim_cadeia = sigla_patrimonio_publico
        
        # Determinar o tipo e classificação
        tipo_fim_cadeia = origem_fim_cadeia.tipo_fim_cadeia if origem_fim_cadeia else 'sem_origem'
        classificacao = origem_fim_cadeia.classificacao_fim_cadeia if origem_fim_cadeia else 'sem_origem'
        
        # Buscar ou criar o registro FimCadeia
        if nome_fim_cadeia:
            fim_cadeia_obj, created = FimCadeia.objects.get_or_create(
                nome=nome_fim_cadeia,
                defaults={
                    'tipo': tipo_fim_cadeia,
                    'classificacao': classificacao,
                    'sigla': sigla_patrimonio_publico,
                    'ativo': True
                }
            )
        else:
            # Para casos sem nome específico, usar um nome genérico
            nome_fim_cadeia = "Sem Origem"
            fim_cadeia_obj, created = FimCadeia.objects.get_or_create(
                nome=nome_fim_cadeia,
                defaults={
                    'tipo': 'sem_origem',
                    'classificacao': 'sem_origem',
                    'ativo': True
                }
            )
        
        # Criar título baseado no tipo
        if tipo_fim_cadeia == 'destacamento_publico' and sigla_patrimonio_publico:
            titulo = f"Destacamento Público\n{sigla_patrimonio_publico}"
        elif tipo_fim_cadeia == 'outra' and origem_fim_cadeia and origem_fim_cadeia.especificacao_fim_cadeia:
            titulo = f"Outra Origem\n{origem_fim_cadeia.especificacao_fim_cadeia}"
        else:
            titulo = "Sem Origem"
        
        return {
            'id': f"fim_cadeia_{fim_cadeia_obj.id}",
            'numero': fim_cadeia_obj.nome,
            'tipo': 'fim_cadeia',
            'tipo_display': 'Fim de Cadeia',
            'tipo_documento': 'fim_cadeia',
            'data': '',
            'cartorio': '',
            'livro': '',
            'folha': '',
            'origem': '',
            'observacoes': '',
            'total_lancamentos': 0,
            'x': 0,  # Posição X (será calculada pelo frontend)
            'y': 0,  # Posição Y (será calculada pelo frontend)
            'nivel': 0,  # Nível na árvore (será calculado)
            'nivel_manual': None,
            'is_importado': False,
            'is_compartilhado': False,
            'imoveis_compartilhando': [],
            'info_importacao': '',
            'tooltip_importacao': '',
            'cadeias_dominiais': [],
            'total_cadeias': 0,
            'is_fim_cadeia': True,  # Flag especial para identificar nós de fim de cadeia
            'tipo_fim_cadeia': fim_cadeia_obj.tipo,
            'classificacao_fim_cadeia': fim_cadeia_obj.classificacao,
            'sigla_patrimonio_publico': fim_cadeia_obj.sigla,
            'titulo_fim_cadeia': titulo,
            'fim_cadeia_id': fim_cadeia_obj.id,  # ID do registro FimCadeia
            'documento_origem_id': documento.id  # Referência ao documento que originou este fim de cadeia
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
        Lógica: documento referenciado como origem → documento atual
        """
        # Extrair códigos de origem (M ou T seguidos de números)
        origens = re.findall(r'[MT]\d+', documento.origem)
        
        # Se não encontrou padrões M/T, tentar extrair números
        if not origens:
            numeros = re.findall(r'\d+', documento.origem)
            origens = numeros
        
        # CORREÇÃO: Remover lógica problemática que criava conexões incorretas
        # A lógica anterior criava conexões baseadas apenas na presença da palavra "matrícula"
        # Isso causava conexões incorretas como M9712 → M19905
        
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
        Lógica: documento referenciado como origem → documento atual
        CORRIGIDO: Extrai origens normais mesmo quando há fim de cadeia na mesma string
        """
        # Extrair códigos de origem dos lançamentos (M ou T seguidos de números)
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
        if matricula_atual:
            niveis_hierarquicos[matricula_atual] = 0
        
        # Calcular níveis para documentos conectados
        HierarquiaArvoreService._calcular_niveis_conectados(
            arvore, niveis_hierarquicos, matricula_atual
        )
        
        # Aplicar níveis aos documentos
        for doc_node in arvore['documentos']:
            # Se há nível manual definido, usar ele; senão usar o calculado
            nivel_calculado = niveis_hierarquicos.get(doc_node['numero'], 0)
            doc_node['nivel'] = doc_node['nivel_manual'] if doc_node['nivel_manual'] is not None else nivel_calculado
    
    @staticmethod
    def _identificar_matricula_atual(arvore):
        """
        Identifica a matrícula atual (documento principal)
        Usa a matrícula do imóvel como ponto de partida
        """
        # Primeiro, tentar encontrar um documento que corresponda à matrícula do imóvel
        matricula_imovel = arvore['imovel']['matricula']
        # print(f"DEBUG MATRICULA: Procurando matrícula do imóvel: {matricula_imovel}")
        
        # Procurar por documento com número igual à matrícula do imóvel (sem restrição de tipo)
        # Também verificar se o número do documento corresponde à matrícula sem o prefixo "M"
        for doc_node in arvore['documentos']:
            if doc_node['numero'] == matricula_imovel:
                print(f"DEBUG MATRICULA: Encontrado documento com matrícula do imóvel: {doc_node['numero']} (tipo: {doc_node.get('tipo', 'N/A')}, importado: {doc_node.get('is_importado', False)})")
                return doc_node['numero']
            # Verificar se a matrícula do imóvel tem prefixo "M" e o documento não
            elif matricula_imovel.startswith('M') and doc_node['numero'] == matricula_imovel[1:]:
                print(f"DEBUG MATRICULA: Encontrado documento correspondente à matrícula do imóvel: {doc_node['numero']} (matrícula: {matricula_imovel}) (tipo: {doc_node.get('tipo', 'N/A')}, importado: {doc_node.get('is_importado', False)})")
                return doc_node['numero']
        
        # Se não encontrou, procurar por documento de matrícula mais recente (não importado)
        documentos_matricula = [doc for doc in arvore['documentos'] if doc['tipo'] == 'matricula' and not doc.get('is_importado', False) and not doc.get('is_compartilhado', False)]
        if documentos_matricula:
            # Ordenar por data (mais recente primeiro) e pegar o primeiro
            documentos_matricula.sort(key=lambda x: x['data'], reverse=True)
            print(f"DEBUG MATRICULA: Usando matrícula mais recente (não importada): {documentos_matricula[0]['numero']}")
            return documentos_matricula[0]['numero']
        
        # Se não há matrículas não importadas, procurar por transcrições mais recentes (não importadas)
        documentos_transcricao = [doc for doc in arvore['documentos'] if doc['tipo'] == 'transcricao' and not doc.get('is_importado', False) and not doc.get('is_compartilhado', False)]
        if documentos_transcricao:
            documentos_transcricao.sort(key=lambda x: x['data'], reverse=True)
            print(f"DEBUG MATRICULA: Usando transcrição mais recente (não importada): {documentos_transcricao[0]['numero']}")
            return documentos_transcricao[0]['numero']
        
        # Último recurso: usar o primeiro documento não importado e não compartilhado disponível
        documentos_nao_importados = [doc for doc in arvore['documentos'] if not doc.get('is_importado', False) and not doc.get('is_compartilhado', False)]
        if documentos_nao_importados:
            print(f"DEBUG MATRICULA: Usando primeiro documento não importado: {documentos_nao_importados[0]['numero']}")
            return documentos_nao_importados[0]['numero']
        
        # Se todos são importados, usar o primeiro disponível
        if arvore['documentos']:
            print(f"DEBUG MATRICULA: Todos são importados, usando primeiro: {arvore['documentos'][0]['numero']}")
            return arvore['documentos'][0]['numero']
        
        return None
    
    @staticmethod
    def _calcular_niveis_conectados(arvore, niveis_hierarquicos, matricula_atual):
        """
        Calcula níveis para documentos conectados seguindo a regra:
        - Documento origem sempre fica um nível acima do documento que o originou
        - Quando um documento é origem de múltiplos documentos, herda o nível maior + 1
        """
        if not matricula_atual:
            return
        
        # Mapear conexões
        origens_por_documento = {}  # documento -> [origens]
        documentos_por_origem = {}  # origem -> [documentos que a referenciam]
        
        # print(f"DEBUG CONEXOES: Processando {len(arvore['conexoes'])} conexões:")
        for conexao in arvore['conexoes']:
            origem = conexao['from']
            destino = conexao['to']
            # print(f"DEBUG CONEXOES: {origem} -> {destino}")
            
            # Adicionar origem ao documento destino
            if destino not in origens_por_documento:
                origens_por_documento[destino] = []
            origens_por_documento[destino].append(origem)
            
            # Adicionar documento destino à origem
            if origem not in documentos_por_origem:
                documentos_por_origem[origem] = []
            documentos_por_origem[origem].append(destino)
        
        # Começar com a matrícula atual no nível 0
        niveis_hierarquicos[matricula_atual] = 0
        
        # Aplicar níveis manuais primeiro
        for doc_node in arvore['documentos']:
            if doc_node.get('nivel_manual') is not None:
                niveis_hierarquicos[doc_node['numero']] = doc_node['nivel_manual']
        
        # LÓGICA CORRIGIDA: Calcular níveis baseado em quem referencia quem
        # print(f"DEBUG NIVEIS: Aplicando lógica corrigida de níveis...")
        # print(f"DEBUG NIVEIS: origens_por_documento: {origens_por_documento}")
        # print(f"DEBUG NIVEIS: documentos_por_origem: {documentos_por_origem}")
        
        # Primeiro, identificar documentos que são referenciados como origens
        documentos_referenciados = set()
        for origem, documentos in documentos_por_origem.items():
            # Incluir todos os documentos que são referenciados como origens
            documentos_referenciados.add(origem)
        
        # print(f"DEBUG NIVEIS: Documentos referenciados como origens: {documentos_referenciados}")
        
        # Iterar até todos os documentos terem nível definido
        mudancas = True
        iteracao = 0
        max_iteracoes = 5
        
        while mudancas and iteracao < max_iteracoes:
            mudancas = False
            iteracao += 1
            # print(f"DEBUG NIVEIS: Iteração {iteracao}")
            
            for doc_node in arvore['documentos']:
                numero_doc = doc_node['numero']
                
                # Pular se já tem nível definido ou é a matrícula atual
                if numero_doc in niveis_hierarquicos or numero_doc == matricula_atual:
                    continue
                
                # Verificar se este documento é referenciado como origem
                if numero_doc in documentos_referenciados:
                    # Encontrar o menor nível entre os documentos que o referenciam
                    min_nivel_referenciadores = float('inf')
                    referenciadores_com_nivel = 0
                    
                    if numero_doc in documentos_por_origem:
                        for referenciador in documentos_por_origem[numero_doc]:
                            if referenciador in niveis_hierarquicos:
                                min_nivel_referenciadores = min(min_nivel_referenciadores, niveis_hierarquicos[referenciador])
                                referenciadores_com_nivel += 1
                    
                    # Se todos os referenciadores têm nível definido, definir nível deste documento
                    if referenciadores_com_nivel > 0 and min_nivel_referenciadores != float('inf'):
                        novo_nivel = min_nivel_referenciadores + 1
                        niveis_hierarquicos[numero_doc] = novo_nivel
                        # print(f"DEBUG NIVEIS: {numero_doc} definido como nível {novo_nivel} (referenciado por documentos de nível {min_nivel_referenciadores})")
                        mudancas = True
                    else:
                        # print(f"DEBUG NIVEIS: {numero_doc} aguardando - {referenciadores_com_nivel} referenciadores têm nível")
                        pass
        
        # PULAR o algoritmo de ordenação topológica - usar apenas a lógica específica
        # print(f"DEBUG NIVEIS: Usando lógica específica de níveis (pulando algoritmo topológico)")
        # print(f"DEBUG NIVEIS: Matrícula atual: {matricula_atual}")
        # print(f"DEBUG NIVEIS: Conexões encontradas: {len(arvore['conexoes'])}")
        
        # Para documentos que não foram processados, verificar se são realmente isolados
        for doc_node in arvore['documentos']:
            if doc_node['numero'] not in niveis_hierarquicos:
                # Cards de fim de cadeia ficam no nível 4 (fixo para evitar árvore gigantesca)
                if doc_node.get('is_fim_cadeia'):
                    nivel_fim_cadeia = 4  # Nível fixo para fim de cadeia
                    niveis_hierarquicos[doc_node['numero']] = nivel_fim_cadeia
                    # print(f"DEBUG NIVEIS: {doc_node['numero']} (fim de cadeia) definido como nível {nivel_fim_cadeia}")
                else:
                    # Verificar se o documento tem origens (não é realmente isolado)
                    if doc_node['numero'] in origens_por_documento:
                        print(f"DEBUG NIVEIS: {doc_node['numero']} tem origens, não é isolado - aguardando processamento")
                        # Não definir nível ainda, será processado na segunda iteração
                    else:
                        # Documentos realmente isolados ficam no nível 1
                        niveis_hierarquicos[doc_node['numero']] = 1
                        print(f"DEBUG NIVEIS: {doc_node['numero']} (realmente isolado) definido como nível 1")
        
        # CORREÇÃO: Ajustar nível do INCRA após calcular todos os outros níveis
        # print(f"DEBUG NIVEIS: Ajustando nível do INCRA após calcular todos os outros níveis...")
        for doc_node in arvore['documentos']:
            if doc_node.get('is_fim_cadeia'):
                # Cards de fim de cadeia ficam no nível 4 (fixo para evitar árvore gigantesca)
                nivel_fim_cadeia = 4
                niveis_hierarquicos[doc_node['numero']] = nivel_fim_cadeia
                # print(f"DEBUG NIVEIS: {doc_node['numero']} (fim de cadeia) ajustado para nível {nivel_fim_cadeia}")
        
        # NOVA LÓGICA: Processar novamente após definir níveis dos isolados
        # print(f"DEBUG NIVEIS: Processando novamente após definir níveis dos isolados...")
        mudancas = True
        iteracao = 0
        max_iteracoes = 5
        
        while mudancas and iteracao < max_iteracoes:
            mudancas = False
            iteracao += 1
            # print(f"DEBUG NIVEIS: Segunda iteração {iteracao}")
            
            for doc_node in arvore['documentos']:
                numero_doc = doc_node['numero']
                
                # Pular se já tem nível definido ou é a matrícula atual
                if numero_doc in niveis_hierarquicos or numero_doc == matricula_atual:
                    continue
                
                # Verificar se este documento tem origens
                if numero_doc in origens_por_documento:
                    origens = origens_por_documento[numero_doc]
                    # print(f"DEBUG NIVEIS: {numero_doc} tem origens: {origens}")
                    
                    # Encontrar o maior nível entre as origens
                    max_nivel_origens = -1
                    origens_com_nivel = 0
                    for origem in origens:
                        if origem in niveis_hierarquicos:
                            max_nivel_origens = max(max_nivel_origens, niveis_hierarquicos[origem])
                            origens_com_nivel += 1
                    
                    # Se todas as origens têm nível definido, definir nível deste documento
                    if origens_com_nivel == len(origens) and max_nivel_origens >= 0:
                        novo_nivel = max_nivel_origens + 1
                        niveis_hierarquicos[numero_doc] = novo_nivel
                        # print(f"DEBUG NIVEIS: {numero_doc} definido como nível {novo_nivel} (todas as origens têm nível)")
                        mudancas = True
                    else:
                        print(f"DEBUG NIVEIS: {numero_doc} aguardando - {origens_com_nivel}/{len(origens)} origens têm nível")
        
        # Aplicar os níveis calculados aos nós
        # print(f"DEBUG NIVEIS: Resultado final dos níveis:")
        for doc_node in arvore['documentos']:
            nivel_final = niveis_hierarquicos.get(doc_node['numero'], 0)
            doc_node['nivel'] = nivel_final
            # print(f"DEBUG NIVEIS: {doc_node['numero']} -> nível {nivel_final} (importado: {doc_node.get('is_importado', False)})")
    
    @staticmethod
    def _calcular_nivel_documento(numero_doc, origens_por_documento, documentos_por_origem, niveis_hierarquicos):
        """
        Calcula o nível de um documento específico seguindo as regras:
        1. Se é origem de outros documentos, nível = max(níveis dos documentos que o referenciam) + 1
        2. Se não é origem, nível = max(níveis das suas origens) + 1
        """
        # Verificar se este documento é origem de outros
        if numero_doc in documentos_por_origem:
            # Este documento é origem de outros documentos
            documentos_referenciadores = documentos_por_origem[numero_doc]
            
            # Encontrar o maior nível entre os documentos que o referenciam
            max_nivel_referenciadores = 0
            for doc_ref in documentos_referenciadores:
                nivel_ref = niveis_hierarquicos.get(doc_ref, 0)
                max_nivel_referenciadores = max(max_nivel_referenciadores, nivel_ref)
            
            # Nível = maior nível dos referenciadores + 1 (limitado a 5)
            return min(max_nivel_referenciadores + 1, 5)
        
        # Verificar se este documento tem origens
        elif numero_doc in origens_por_documento:
            # Este documento tem origens
            origens = origens_por_documento[numero_doc]
            
            # Encontrar o maior nível entre as origens
            max_nivel_origens = 0
            for origem in origens:
                nivel_origem = niveis_hierarquicos.get(origem, 0)
                max_nivel_origens = max(max_nivel_origens, nivel_origem)
            
            # Nível = maior nível das origens + 1 (limitado a 5)
            return min(max_nivel_origens + 1, 5)
        
        # Documento isolado (sem origens nem referenciadores) - nível 1
        return 1 