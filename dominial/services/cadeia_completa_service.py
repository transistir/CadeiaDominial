"""
Service para gerar a cadeia dominial completa
"""

import re
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
    
    @staticmethod
    def _extrair_numero_simples(numero_lancamento):
        """
        Extrai o número simples do numero_lancamento para ordenação
        Ex: "R4M235" -> 4, "AV12M235" -> 12, "AV4 M2725" -> 4, "M235" -> 0 (início de matrícula)
        """
        if not numero_lancamento:
            return 0
        
        # Para início de matrícula, retornar 0 para ficar por último
        if not numero_lancamento.startswith(('R', 'AV')):
            return 0
        
        # Extrair número após R ou AV (com ou sem espaço)
        match = re.search(r'^(R|AV)(\d+)', numero_lancamento)
        if match:
            return int(match.group(2))
        
        return 0
    
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
            
            # Ordenar por número simples em Python
            lancamentos_list = list(lancamentos)
            lancamentos_list.sort(key=lambda x: (
                -self._extrair_numero_simples(x.numero_lancamento),
                x.id
            ))
            lancamentos = lancamentos_list
            
            # Verificar se é importado
            is_importado = documento.imovel != self.imovel_atual
            
            documentos_processados.append({
                'documento': documento,
                'lancamentos': lancamentos,
                'is_importado': is_importado,
                'origens_disponiveis': self._obter_origens_documento(documento)
            })
        
        return documentos_processados
    
    def _processar_documento_para_template(self, documento):
        """
        Processa um único documento para o formato do template
        """
        # Carregar lançamentos
        lancamentos = documento.lancamentos.select_related('tipo').prefetch_related(
            'pessoas__pessoa'
        ).order_by('id')
        
        # Ordenar por número simples em Python
        lancamentos_list = list(lancamentos)
        lancamentos_list.sort(key=lambda x: (
            -CadeiaCompletaService._extrair_numero_simples(x.numero_lancamento),
            x.id
        ))
        lancamentos = lancamentos_list
        
        # Verificar se é importado
        is_importado = documento.imovel != self.imovel_atual if self.imovel_atual else False
        
        return {
            'documento': documento,
            'lancamentos': lancamentos,
            'is_importado': is_importado,
            'origens_disponiveis': self._obter_origens_documento(documento)
        }
    
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
        
        # Ordenar: matrículas primeiro (maior número), depois transcrições (maior número)
        origens_list = list(origens)
        if origens_list:
            try:
                def origem_sort_key(origem):
                    if origem.startswith('M'):
                        # Matrículas: prioridade 0 (maior prioridade), número negativo para ordem decrescente
                        return (0, -int(origem[1:]))
                    elif origem.startswith('T'):
                        # Transcrições: prioridade 1 (menor prioridade), número negativo para ordem decrescente
                        return (1, -int(origem[1:]))
                    else:
                        # Outros: prioridade 2, ordem alfabética reversa
                        return (2, -ord(origem[0]) if origem else 0)
                
                return sorted(origens_list, key=origem_sort_key)
            except (ValueError, AttributeError):
                # Fallback: ordenação alfabética com matrículas primeiro
                def fallback_sort_key(origem):
                    if origem.startswith('M'):
                        return (0, origem)
                    elif origem.startswith('T'):
                        return (1, origem)
                    else:
                        return (2, origem)
                
                return sorted(origens_list, key=fallback_sort_key)
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
    
    def _calcular_estatisticas_completas(self, cadeia_completa):
        """Calcula estatísticas da cadeia completa"""
        total_documentos = 0
        total_lancamentos = 0
        documentos_importados = 0
        
        # Verificar se é lista (formato antigo) ou dicionário (formato novo)
        if isinstance(cadeia_completa, list):
            # Formato antigo: lista de troncos
            for tronco in cadeia_completa:
                if isinstance(tronco, dict) and 'documentos' in tronco:
                    total_documentos += len(tronco['documentos'])
                    for doc in tronco['documentos']:
                        if isinstance(doc, dict):
                            total_lancamentos += len(doc.get('lancamentos', []))
                            if doc.get('is_importado'):
                                documentos_importados += 1
        else:
            # Formato novo: dicionário com tronco_principal e troncos_secundarios
            # Contar documentos do tronco principal
            if cadeia_completa.get('tronco_principal'):
                total_documentos += len(cadeia_completa['tronco_principal'])
                for doc in cadeia_completa['tronco_principal']:
                    total_lancamentos += len(doc.get('lancamentos', []))
                    if doc.get('is_importado'):
                        documentos_importados += 1
            
            # Contar documentos dos troncos secundários
            if cadeia_completa.get('troncos_secundarios'):
                for tronco in cadeia_completa['troncos_secundarios']:
                    total_documentos += len(tronco.get('documentos', []))
                    for doc in tronco.get('documentos', []):
                        total_lancamentos += len(doc.get('lancamentos', []))
                        if doc.get('is_importado'):
                            documentos_importados += 1
        
        return {
            'total_documentos': total_documentos,
            'total_lancamentos': total_lancamentos,
            'documentos_importados': documentos_importados
        }

    def get_cadeia_completa_com_sequencia_personalizada(self, tis_id, imovel_id, sequencia_ids):
        """
        Obtém a cadeia completa com sequência personalizada de documentos
        
        Args:
            tis_id: ID da Terra Indígena
            imovel_id: ID do Imóvel
            sequencia_ids: String com IDs dos documentos separados por vírgula
        """
        try:
            # Obter imóvel
            imovel = Imovel.objects.get(id=imovel_id, terra_indigena_id=tis_id)
            
            # Converter sequência de IDs em lista
            ids_documentos = [int(id.strip()) for id in sequencia_ids.split(',') if id.strip().isdigit()]
            
            if not ids_documentos:
                # Se não há IDs válidos, usar sequência padrão
                return self.get_cadeia_completa(tis_id, imovel_id)
            
            # Buscar documentos na ordem especificada
            documentos_ordenados = []
            documentos_por_id = {}
            
            # Primeiro, buscar todos os documentos
            documentos = Documento.objects.filter(id__in=ids_documentos)\
                .select_related('cartorio', 'tipo', 'imovel')\
                .prefetch_related('lancamentos', 'lancamentos__tipo')
            
            for doc in documentos:
                documentos_por_id[doc.id] = doc
            
            # Ordenar conforme a sequência especificada
            for doc_id in ids_documentos:
                if doc_id in documentos_por_id:
                    doc = documentos_por_id[doc_id]
                    documentos_ordenados.append(doc)
            
            # Definir imovel_atual para o processamento
            self.imovel_atual = imovel
            
            # Processar documentos para o template
            documentos_processados = []
            for doc in documentos_ordenados:
                doc_processado = self._processar_documento_para_template(doc)
                documentos_processados.append(doc_processado)
            
            # Organizar em estrutura hierárquica para o template (formato esperado pelo cadeia_completa_pdf.html)
            cadeia_completa = [
                {
                    'tipo': 'tronco_principal',
                    'titulo': '🌳 TRONCO PRINCIPAL',
                    'documentos': documentos_processados
                }
            ]
            
            # Calcular estatísticas
            estatisticas = self._calcular_estatisticas_completas(cadeia_completa)
            
            return {
                'tis': imovel.terra_indigena_id,
                'imovel': imovel,
                'cadeia_completa': cadeia_completa,
                'estatisticas': estatisticas,
                'sequencia_personalizada': True
            }
            
        except Exception as e:
            # Em caso de erro, usar sequência padrão
            return self.get_cadeia_completa(tis_id, imovel_id)
    
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
    

