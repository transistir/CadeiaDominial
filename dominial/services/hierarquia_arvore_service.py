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
        for documento in documentos:
            doc_node = HierarquiaArvoreService._criar_no_documento(documento, imovel)
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
        # Verificar se documento foi importado (está na tabela DocumentoImportado)
        # Um documento só é "importado" no imóvel que o importou, não no imóvel de origem
        is_importado = False
        if imovel:
            # Verificar se este documento foi importado PARA este imóvel específico
            # Ou seja, se existe um registro onde este documento foi importado de outro imóvel para este imóvel
            from ..models import DocumentoImportado
            is_importado = DocumentoImportado.objects.filter(
                documento=documento,
                documento__imovel=imovel  # O documento pertence ao imóvel atual
            ).exists()
            
            # Se o documento não pertence ao imóvel atual mas aparece na árvore,
            # significa que foi importado por referência
            if not is_importado and documento.imovel != imovel:
                is_importado = True
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
        
        # Procurar por documento com número igual à matrícula do imóvel
        for doc_node in arvore['documentos']:
            if doc_node['numero'] == matricula_imovel and doc_node['tipo'] == 'matricula':
                return doc_node['numero']
        
        # Se não encontrou, procurar por documento de matrícula mais recente
        documentos_matricula = [doc for doc in arvore['documentos'] if doc['tipo'] == 'matricula']
        if documentos_matricula:
            # Ordenar por data (mais recente primeiro) e pegar o primeiro
            documentos_matricula.sort(key=lambda x: x['data'], reverse=True)
            return documentos_matricula[0]['numero']
        
        # Se não há matrículas, procurar por transcrições mais recentes
        documentos_transcricao = [doc for doc in arvore['documentos'] if doc['tipo'] == 'transcricao']
        if documentos_transcricao:
            documentos_transcricao.sort(key=lambda x: x['data'], reverse=True)
            return documentos_transcricao[0]['numero']
        
        # Último recurso: usar o primeiro documento disponível
        if arvore['documentos']:
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
        
        for conexao in arvore['conexoes']:
            origem = conexao['from']
            destino = conexao['to']
            
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
        
        # Calcular níveis usando algoritmo de ordenação topológica
        # Processar documentos em múltiplas iterações até estabilizar
        mudancas = True
        iteracao = 0
        max_iteracoes = 100  # Evitar loop infinito
        
        while mudancas and iteracao < max_iteracoes:
            mudancas = False
            iteracao += 1
            
            # Para cada documento, calcular seu nível
            for doc_node in arvore['documentos']:
                numero_doc = doc_node['numero']
                
                # Pular se já tem nível manual definido ou é a matrícula atual
                if numero_doc in niveis_hierarquicos and doc_node.get('nivel_manual') is not None:
                    continue
                if numero_doc == matricula_atual:
                    continue
                
                # Calcular nível baseado nas origens/referenciadores
                nivel_calculado = HierarquiaArvoreService._calcular_nivel_documento(
                    numero_doc, origens_por_documento, documentos_por_origem, niveis_hierarquicos
                )
                
                # Se o nível mudou, atualizar
                nivel_atual = niveis_hierarquicos.get(numero_doc, 0)
                if nivel_calculado != nivel_atual:
                    niveis_hierarquicos[numero_doc] = nivel_calculado
                    mudancas = True
        
        # Para documentos que não foram processados (isolados), atribuir nível 0
        for doc_node in arvore['documentos']:
            if doc_node['numero'] not in niveis_hierarquicos:
                niveis_hierarquicos[doc_node['numero']] = 0
        
        # Para documentos que não foram processados (isolados), atribuir nível 0
        for doc_node in arvore['documentos']:
            if doc_node['numero'] not in niveis_hierarquicos:
                niveis_hierarquicos[doc_node['numero']] = 0
    
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
            
            # Nível = maior nível dos referenciadores + 1
            return max_nivel_referenciadores + 1
        
        # Verificar se este documento tem origens
        elif numero_doc in origens_por_documento:
            # Este documento tem origens
            origens = origens_por_documento[numero_doc]
            
            # Encontrar o maior nível entre as origens
            max_nivel_origens = 0
            for origem in origens:
                nivel_origem = niveis_hierarquicos.get(origem, 0)
                max_nivel_origens = max(max_nivel_origens, nivel_origem)
            
            # Nível = maior nível das origens + 1
            return max_nivel_origens + 1
        
        # Documento isolado (sem origens nem referenciadores)
        return 0 