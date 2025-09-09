"""
Service para visualização de tabela da cadeia dominial
"""

import re
from django.shortcuts import get_object_or_404
from ..models import TIs, Imovel, Documento, Lancamento, DocumentoImportado
from ..services.hierarquia_service import HierarquiaService


class CadeiaDominialTabelaService:
    """
    Service para gerenciar a visualização de tabela da cadeia dominial
    """
    
    def __init__(self):
        self.hierarquia_service = HierarquiaService()
    
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
    
    def get_cadeia_dominial_tabela(self, tis_id, imovel_id, session=None):
        """
        Obtém dados da cadeia dominial em formato de tabela
        """
        tis = get_object_or_404(TIs, id=tis_id)
        imovel = get_object_or_404(Imovel, id=imovel_id)
        
        # Extrair escolhas de origem da sessão
        escolhas_origem = {}
        if session:
            for key, value in session.items():
                if key.startswith('origem_documento_'):
                    documento_id = key.replace('origem_documento_', '')
                    escolhas_origem[documento_id] = value
        
        # Obter tronco principal considerando escolhas
        tronco_principal = self.hierarquia_service.obter_tronco_principal(imovel, escolhas_origem)
        
        # Expandir tronco principal com documentos importados referenciados
        tronco_expandido = self._expandir_tronco_com_importados(imovel, tronco_principal, escolhas_origem)
        
        # Processar cada documento (manter ordem hierárquica)
        cadeia_processada = []
        documentos_ordenados = tronco_expandido
        for documento in documentos_ordenados:
            # Carregar lançamentos e ordenar por número simples (decrescente)
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
            
            # Verificar se tem múltiplas origens
            origens_disponiveis = self._obter_origens_documento(documento, lancamentos)
            tem_multiplas_origens = len(origens_disponiveis) > 1
            
            # Verificar escolha atual da sessão
            escolha_atual = session.get(f'origem_documento_{documento.id}') if session else None
            
            # Se não há escolha na sessão E há origens disponíveis, usar a origem de número maior como padrão
            if not escolha_atual and origens_disponiveis:
                # A lista já está ordenada do maior para o menor, então pegamos o primeiro
                escolha_atual = origens_disponiveis[0]
            
            # Formatar origens para o template (ordenadas do maior para o menor)
            origens_formatadas = []
            for i, origem in enumerate(origens_disponiveis):
                # Sempre usar a primeira origem (maior número) como padrão se não há escolha na sessão
                is_escolhida = (origem == escolha_atual) if escolha_atual else (i == 0)
                origens_formatadas.append({
                    'numero': origem,
                    'escolhida': is_escolhida
                })
            
            # Verificar se documento foi importado (está em outro imóvel)
            is_importado = documento.imovel != imovel
            
            cadeia_processada.append({
                'documento': documento,
                'lancamentos': lancamentos,
                'origens_disponiveis': origens_formatadas,
                'tem_multiplas_origens': tem_multiplas_origens,
                'escolha_atual': escolha_atual,
                'is_importado': is_importado
            })
        
        result = {
            'tis': tis,
            'imovel': imovel,
            'cadeia': cadeia_processada,
            'tem_lancamentos': any(len(item['lancamentos']) > 0 for item in cadeia_processada)
        }
        return result
    

    
    def _obter_origens_documento(self, documento, lancamentos):
        """
        Obtém as origens disponíveis para um documento
        """
        origens = set()
        
        for lancamento in lancamentos:
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
    
    def get_estatisticas_cadeia(self, cadeia):
        """
        Calcula estatísticas da cadeia dominial
        """
        total_documentos = len(cadeia)
        total_lancamentos = sum(len(item['lancamentos']) for item in cadeia)
        documentos_com_multiplas_origens = sum(1 for item in cadeia if item['tem_multiplas_origens'])
        
        return {
            'total_documentos': total_documentos,
            'total_lancamentos': total_lancamentos,
            'documentos_com_multiplas_origens': documentos_com_multiplas_origens,
            'percentual_multiplas_origens': (documentos_com_multiplas_origens / total_documentos * 100) if total_documentos > 0 else 0
        }

    @staticmethod
    def obter_cadeia_tabela(imovel, escolhas_origem=None):
        """
        Retorna a cadeia dominial em formato de tabela com lançamentos expandíveis
        
        Args:
            imovel: Objeto Imovel
            escolhas_origem: Dict com escolhas de origem do usuário
            
        Returns:
            list: Lista de documentos com dados para tabela
        """
        if escolhas_origem is None:
            escolhas_origem = {}
        
        # Usar o HierarquiaService para obter apenas o TRONCO PRINCIPAL
        from .hierarquia_service import HierarquiaService
        todos_documentos = HierarquiaService.obter_tronco_principal(imovel, escolhas_origem)
        
        # Ordenar documentos por data para manter a ordem cronológica
        todos_documentos.sort(key=lambda x: x.data)
        
        cadeia_completa = []
        for documento in todos_documentos:
            # Carregar lançamentos com pessoas
            lancamentos = documento.lancamentos.select_related('tipo').prefetch_related(
                'pessoas__pessoa'
            ).order_by('id')
            
            # Ordenar por número simples em Python
            lancamentos_list = list(lancamentos)
            lancamentos_list.sort(key=lambda x: (
                -CadeiaDominialTabelaService._extrair_numero_simples(x.numero_lancamento),
                x.id
            ))
            lancamentos = lancamentos_list
            
            # Verificar se tem múltiplas origens
            tem_multiplas_origens = False
            origens_disponiveis = []
            
            for lancamento in lancamentos:
                if lancamento.tipo.tipo == 'inicio_matricula' and lancamento.origem:
                    origens = CadeiaDominialTabelaService.extrair_origens_disponiveis(
                        lancamento.origem, imovel
                    )
                    if len(origens) > 1:
                        tem_multiplas_origens = True
                        origens_disponiveis = origens
                        break
            
            # Verificar escolha atual
            escolha_atual = escolhas_origem.get(str(documento.id))
            
            # Se não há escolha e há origens disponíveis, usar a primeira (maior número)
            if not escolha_atual and origens_disponiveis:
                escolha_atual = origens_disponiveis[0]['numero']
            
            # Formatar origens para o template
            origens_formatadas = []
            for i, origem in enumerate(origens_disponiveis):
                is_escolhida = (origem['numero'] == escolha_atual) if escolha_atual else (i == 0)
                origens_formatadas.append({
                    'numero': origem['numero'],
                    'escolhida': is_escolhida
                })
            
            cadeia_completa.append({
                'documento': documento,
                'lancamentos': lancamentos,
                'tem_multiplas_origens': tem_multiplas_origens,
                'origens_disponiveis': origens_formatadas,
                'escolha_atual': escolha_atual
            })
        
        return cadeia_completa
    
    @staticmethod
    def extrair_origens_disponiveis(origem_texto, imovel):
        """
        Extrai as origens disponíveis de um texto de origem
        
        Args:
            origem_texto: Texto contendo as origens
            imovel: Objeto Imovel
            
        Returns:
            list: Lista de origens disponíveis
        """
        if not origem_texto:
            return []
        
        origens = []
        # Dividir por ponto e vírgula se houver múltiplas origens
        origens_split = [o.strip() for o in origem_texto.split(';') if o.strip()]
        
        for origem in origens_split:
            # Extrair códigos de matrícula/transcrição
            codigos = re.findall(r'[MT]\d+', origem)
            
            for codigo in codigos:
                doc_existente = Documento.objects.filter(
                    imovel=imovel, numero=codigo
                ).first()
                if doc_existente:
                    origens.append({
                        'numero': codigo,
                        'documento': doc_existente,
                        'escolhida': False  # Será definida pelo contexto
                    })
        
        # Ordenar do maior para o menor número
        if origens:
            try:
                return sorted(origens, key=lambda x: int(str(x['numero']).replace('M', '').replace('T', '')), reverse=True)
            except (ValueError, AttributeError):
                return sorted(origens, key=lambda x: x['numero'], reverse=True)
        
        return origens 
    
    def _expandir_tronco_com_importados(self, imovel, tronco_principal, escolhas_origem=None):
        """
        Expande o tronco principal incluindo documentos importados na posição correta
        """
        tronco_expandido = []
        documentos_processados = set()
        
        for documento in tronco_principal:
            # Adicionar o documento atual
            if documento.id not in documentos_processados:
                tronco_expandido.append(documento)
                documentos_processados.add(documento.id)
            
            # Verificar se este documento tem lançamentos com origens importadas
            lancamentos = documento.lancamentos.filter(
                origem__isnull=False
            ).exclude(origem='')
            
            # Lista temporária para documentos importados deste documento
            docs_importados_temp = []
            
            for lancamento in lancamentos:
                origens = [o.strip() for o in lancamento.origem.split(';') if o.strip()]
                
                for origem_numero in origens:
                    # Buscar documento importado com este número
                    doc_importado = Documento.objects.filter(
                        numero=origem_numero
                    ).exclude(
                        imovel=imovel
                    ).select_related('cartorio', 'tipo').first()
                    
                    if doc_importado and doc_importado.id not in documentos_processados:
                        docs_importados_temp.append(doc_importado)
                        documentos_processados.add(doc_importado.id)
            
            # Adicionar documentos importados após o documento atual
            tronco_expandido.extend(docs_importados_temp)
            
            # Expandir recursivamente a cadeia de cada documento importado
            for doc_importado in docs_importados_temp:
                # Verificar se há uma escolha específica para este documento
                escolha_especifica = None
                if escolhas_origem:
                    escolha_especifica = escolhas_origem.get(str(doc_importado.id))
                
                if escolha_especifica:
                    # Usar a escolha específica da sessão
                    doc_origem_escolhido = Documento.objects.filter(
                        numero=escolha_especifica
                    ).select_related('cartorio', 'tipo').first()
                    
                    if doc_origem_escolhido and doc_origem_escolhido.id not in documentos_processados:
                        tronco_expandido.append(doc_origem_escolhido)
                        documentos_processados.add(doc_origem_escolhido.id)
                        
                        # Expandir recursivamente a cadeia completa abaixo da origem escolhida
                        cadeia_abaixo = self._expandir_cadeia_recursiva(doc_origem_escolhido, documentos_processados, escolhas_origem, 0)
                        tronco_expandido.extend(cadeia_abaixo)
                else:
                    # Usar o documento de origem de nível mais alto (comportamento padrão)
                    doc_origem_mais_alto = self._obter_documento_origem_mais_alto(doc_importado)
                    
                    if doc_origem_mais_alto and doc_origem_mais_alto.id not in documentos_processados:
                        tronco_expandido.append(doc_origem_mais_alto)
                        documentos_processados.add(doc_origem_mais_alto.id)
                        
                        # Expandir recursivamente a cadeia completa abaixo da origem mais alta
                        cadeia_abaixo = self._expandir_cadeia_recursiva(doc_origem_mais_alto, documentos_processados, escolhas_origem, 0)
                        tronco_expandido.extend(cadeia_abaixo)
        
        return tronco_expandido
    
    def _obter_documento_origem_mais_alto(self, documento):
        """
        Obtém o documento de origem de nível mais alto (maior número) de um documento
        """
        # Buscar lançamentos com origens
        lancamentos = documento.lancamentos.filter(
            origem__isnull=False
        ).exclude(origem='')
        
        origens_encontradas = []
        
        for lancamento in lancamentos:
            origens = [o.strip() for o in lancamento.origem.split(';') if o.strip()]
            
            for origem_numero in origens:
                # Buscar documento de origem
                doc_origem = Documento.objects.filter(
                    numero=origem_numero
                ).select_related('cartorio', 'tipo').first()
                
                if doc_origem:
                    origens_encontradas.append(doc_origem)
        
        # Retornar o documento com maior número (nível mais alto)
        if origens_encontradas:
            try:
                return max(origens_encontradas, key=lambda x: int(str(x.numero).replace('M', '').replace('T', '')))
            except (ValueError, AttributeError) as e:
                print(f"⚠️ Erro ao ordenar documentos por número: {str(e)}")
                # Em caso de erro, retornar o primeiro documento encontrado
                return origens_encontradas[0] if origens_encontradas else None
        
        return None
    
    def _expandir_cadeia_recursiva(self, documento, documentos_processados, escolhas_origem=None, profundidade=0):
        """
        Expande recursivamente apenas a subcadeia da origem escolhida (ou padrão) de um documento,
        seguindo a ordem: matrículas maiores, depois transcrições maiores, ambos do maior para o menor.
        """
        # Proteção contra recursão infinita
        if profundidade > 50:  # Limite máximo de profundidade
            print(f"⚠️ Limite de profundidade atingido para documento {documento.numero}")
            return []
            
        cadeia_expandida = []
        
        # Buscar lançamentos com origens
        lancamentos = documento.lancamentos.filter(
            origem__isnull=False
        ).exclude(origem='')
        
        # Coletar todas as origens possíveis
        origens = set()
        for lancamento in lancamentos:
            origens_lanc = [o.strip() for o in lancamento.origem.split(';') if o.strip()]
            origens.update(origens_lanc)
        origens = list(origens)

        # Função de ordenação: matrículas maiores primeiro, depois transcrições maiores
        def origem_sort_key(origem):
            try:
                if origem.startswith('M'):
                    numero_part = origem.replace('M', '')
                    if numero_part.isdigit():
                        return (0, -int(numero_part))
                    else:
                        return (2, origem)  # Não é um número válido
                if origem.startswith('T'):
                    numero_part = origem.replace('T', '')
                    if numero_part.isdigit():
                        return (1, -int(numero_part))
                    else:
                        return (2, origem)  # Não é um número válido
                return (2, origem)
            except (ValueError, AttributeError):
                # Se houver qualquer erro na conversão, tratar como string normal
                return (2, origem)
        
        # Filtrar origens válidas antes de ordenar
        origens_validas = []
        for origem in origens:
            try:
                if origem.startswith(('M', 'T')):
                    numero_part = origem[1:]  # Remove M ou T
                    if numero_part.isdigit():
                        origens_validas.append(origem)
                    else:
                        print(f"⚠️ Origem ignorada (não é número válido): '{origem}'")
                else:
                    origens_validas.append(origem)
            except Exception as e:
                print(f"⚠️ Origem ignorada (erro): '{origem}' - {str(e)}")
        
        origens_validas.sort(key=origem_sort_key)
        origens = origens_validas

        # Determinar origem escolhida
        escolha_especifica = None
        if escolhas_origem:
            escolha_especifica = escolhas_origem.get(str(documento.id))
        if escolha_especifica and escolha_especifica in origens:
            origem_escolhida = escolha_especifica
        elif origens:
            origem_escolhida = origens[0]  # padrão: maior matrícula, depois maior transcrição
        else:
            origem_escolhida = None

        # Só expandir a subcadeia da origem escolhida
        if origem_escolhida:
            doc_origem = Documento.objects.filter(
                numero=origem_escolhida
            ).select_related('cartorio', 'tipo').first()
            if doc_origem and doc_origem.id not in documentos_processados:
                cadeia_expandida.append(doc_origem)
                documentos_processados.add(doc_origem.id)
                # Recursão: expandir apenas a subcadeia da origem escolhida
                sub_cadeia = self._expandir_cadeia_recursiva(doc_origem, documentos_processados, escolhas_origem, profundidade + 1)
                cadeia_expandida.extend(sub_cadeia)
        return cadeia_expandida