"""
Service para gerar a cadeia dominial completa
"""

from django.shortcuts import get_object_or_404
from ..models import TIs, Imovel, Documento, Lancamento
from ..services.hierarquia_service import HierarquiaService


class CadeiaCompletaService:
    """
    Service para gerar a cadeia dominial completa
    """
    
    def __init__(self):
        self.hierarquia_service = HierarquiaService()
        self.imovel_atual = None
    
    def get_cadeia_completa(self, tis_id, imovel_id):
        """
        Obtém a cadeia dominial completa organizada hierarquicamente
        """
        tis = get_object_or_404(TIs, id=tis_id)
        imovel = get_object_or_404(Imovel, id=imovel_id)
        self.imovel_atual = imovel
        
        # 1. Obter tronco principal completo
        tronco_principal = self._obter_tronco_principal_completo(imovel)
        
        # 2. Obter troncos secundários completos
        troncos_secundarios = self._obter_troncos_secundarios_completos(imovel)
        
        # 3. Organizar hierarquicamente
        cadeia_organizada = self._organizar_cadeia_hierarquica(
            tronco_principal, troncos_secundarios
        )
        
        return {
            'tis': tis,
            'imovel': imovel,
            'cadeia_completa': cadeia_organizada,
            'estatisticas': self._calcular_estatisticas_completas(cadeia_organizada)
        }
    
    def _obter_tronco_principal_completo(self, imovel):
        """
        Obtém o tronco principal expandindo TODAS as origens
        Usa a mesma lógica da página ver-cadeia-dominial para garantir a sequência correta
        """
        # 1. Obter o tronco principal na sequência correta (como na página ver-cadeia-dominial)
        tronco_principal = self.hierarquia_service.obter_tronco_principal(imovel)
        
        # 2. Usar HierarquiaArvoreService para obter TODOS os documentos da cadeia
        from .hierarquia_arvore_service import HierarquiaArvoreService
        arvore = HierarquiaArvoreService.construir_arvore_cadeia_dominial(imovel)
        
        # 3. Extrair todos os documentos da árvore
        todos_documentos = []
        for doc_node in arvore['documentos']:
            documento = Documento.objects.get(id=doc_node['id'])
            todos_documentos.append(documento)
        
        # 4. Organizar: tronco principal primeiro, depois todos os outros documentos
        documentos_organizados = []
        documentos_processados = set()
        
        # Primeiro, adicionar o tronco principal na ordem correta
        for documento in tronco_principal:
            if documento.id not in documentos_processados:
                documentos_organizados.append(documento)
                documentos_processados.add(documento.id)
        
        # Depois, adicionar todos os outros documentos que não estão no tronco principal
        # Ordenar por tipo e número para manter hierarquia
        outros_documentos = []
        for documento in todos_documentos:
            if documento.id not in documentos_processados:
                outros_documentos.append(documento)
        
        # Ordenar outros documentos hierarquicamente
        outros_documentos_ordenados = self._ordenar_documentos_hierarquicamente(outros_documentos)
        
        for documento in outros_documentos_ordenados:
            documentos_organizados.append(documento)
        
        return documentos_organizados
    
    def _obter_troncos_secundarios_completos(self, imovel):
        """
        Obtém todos os troncos secundários expandindo TODAS as origens
        """
        # Por enquanto, retornar lista vazia
        # TODO: Implementar lógica de troncos secundários
        return []
    
    def _expandir_todas_origens_documento(self, documento, documentos_processados=None):
        """
        Expande TODAS as origens de um documento (não apenas uma)
        """
        if documentos_processados is None:
            documentos_processados = set()
            
        documentos_origem = []
        
        # Buscar lançamentos com origens
        lancamentos = documento.lancamentos.filter(
            origem__isnull=False
        ).exclude(origem='')
        
        for lancamento in lancamentos:
            if lancamento.origem:
                # Extrair todas as origens (separadas por ';')
                origens = [o.strip() for o in lancamento.origem.split(';') if o.strip()]
                
                for origem_numero in origens:
                    # Buscar documento de origem
                    doc_origem = Documento.objects.filter(
                        numero=origem_numero
                    ).select_related('cartorio', 'tipo').first()
                    
                    if doc_origem and doc_origem.id not in documentos_processados:
                        documentos_origem.append(doc_origem)
                        documentos_processados.add(doc_origem.id)
                        
                        # Recursivamente expandir origens deste documento
                        sub_origens = self._expandir_todas_origens_documento(doc_origem, documentos_processados)
                        for sub_origem in sub_origens:
                            if sub_origem.id not in documentos_processados:
                                documentos_origem.append(sub_origem)
                                documentos_processados.add(sub_origem.id)
        
        return documentos_origem
    

    
    def _organizar_cadeia_hierarquica(self, tronco_principal, troncos_secundarios):
        """
        Organiza a cadeia em estrutura hierárquica para o template
        """
        cadeia_organizada = []
        
        # 1. Tronco Principal
        if tronco_principal:
            cadeia_organizada.append({
                'tipo': 'tronco_principal',
                'titulo': '🌳 TRONCO PRINCIPAL',
                'documentos': self._processar_documentos_para_template(tronco_principal)
            })
        
        # 2. Troncos Secundários
        for i, tronco in enumerate(troncos_secundarios, 1):
            if tronco:
                cadeia_organizada.append({
                    'tipo': 'tronco_secundario',
                    'titulo': f'🌿 TRONCO SECUNDÁRIO {i}',
                    'documentos': self._processar_documentos_para_template(tronco)
                })
        
        return cadeia_organizada
    
    def _processar_documentos_para_template(self, documentos):
        """
        Processa documentos para o formato do template
        """
        documentos_processados = []
        
        for documento in documentos:
            # Carregar lançamentos
            lancamentos = documento.lancamentos.select_related('tipo').prefetch_related(
                'pessoas__pessoa'
            ).order_by('id')
            
            # Verificar se é importado
            is_importado = documento.imovel != self.imovel_atual
            
            documentos_processados.append({
                'documento': documento,
                'lancamentos': lancamentos,
                'is_importado': is_importado,
                'origens_disponiveis': self._obter_origens_documento(documento)
            })
        
        return documentos_processados
    
    def _obter_origens_documento(self, documento):
        """
        Obtém as origens disponíveis para um documento
        """
        origens = set()
        
        for lancamento in documento.lancamentos.all():
            if lancamento.tipo.tipo == 'inicio_matricula' and lancamento.origem:
                # Extrair origens do campo origem
                origens_lancamento = self._extrair_origens(lancamento.origem)
                origens.update(origens_lancamento)
        
        # Ordenar do maior para o menor número
        origens_list = list(origens)
        if origens_list:
            # Ordenar numericamente removendo M/T e convertendo para int
            try:
                return sorted(origens_list, key=lambda x: int(str(x).replace('M', '').replace('T', '')), reverse=True)
            except (ValueError, AttributeError):
                # Se falhar, ordenar alfabeticamente reverso
                return sorted(origens_list, reverse=True)
        return []
    
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
    
    def _calcular_estatisticas_completas(self, cadeia_organizada):
        """
        Calcula estatísticas da cadeia completa
        """
        total_documentos = 0
        total_lancamentos = 0
        total_troncos = len(cadeia_organizada)
        documentos_importados = 0
        
        for tronco in cadeia_organizada:
            for item in tronco['documentos']:
                total_documentos += 1
                total_lancamentos += len(item['lancamentos'])
                if item['is_importado']:
                    documentos_importados += 1
        
        return {
            'total_documentos': total_documentos,
            'total_lancamentos': total_lancamentos,
            'total_troncos': total_troncos,
            'documentos_importados': documentos_importados,
            'percentual_importados': (documentos_importados / total_documentos * 100) if total_documentos > 0 else 0
        }
    
    def _ordenar_documentos_hierarquicamente(self, documentos):
        """
        Ordena documentos hierarquicamente:
        1. Matrículas (maior número primeiro)
        2. Transcrições (maior número primeiro)
        3. Outros tipos (ordem alfabética)
        """
        def extrair_numero_documento(documento):
            """Extrai o número numérico do documento para ordenação"""
            try:
                # Remove M ou T e converte para int
                numero_limpo = str(documento.numero).replace('M', '').replace('T', '')
                return int(numero_limpo)
            except (ValueError, AttributeError):
                return 0
        
        def tipo_prioridade(documento):
            """Define prioridade do tipo de documento"""
            tipo = documento.tipo.tipo if documento.tipo else ''
            if tipo == 'matricula':
                return 1  # Maior prioridade
            elif tipo == 'transcricao':
                return 2  # Segunda prioridade
            else:
                return 3  # Menor prioridade
        
        # Ordenar por tipo (matrícula -> transcrição -> outros) e depois por número (maior primeiro)
        documentos_ordenados = sorted(
            documentos,
            key=lambda x: (tipo_prioridade(x), -extrair_numero_documento(x))
        )
        
        return documentos_ordenados
    

