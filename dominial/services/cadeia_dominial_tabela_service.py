"""
Service para visualização de tabela da cadeia dominial
"""

import re
from django.shortcuts import get_object_or_404
from ..models import TIs, Imovel, Documento, Lancamento, DocumentoImportado
from ..services.hierarquia_service import HierarquiaService
from ..services.documento_identidade_service import DocumentoIdentidadeService
from ..services.lancamento_origem_leitura_service import LancamentoOrigemLeituraService
from ..services.keyword_alerta_service import buscar_keyword
from ..utils.documento_identidade_utils import DocumentoIdentidade
from ..utils.ordenacao_cadeia import chave_ordem_cadeia, chave_ordem_origem, ordenar_cadeia


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

    @staticmethod
    def _tipo_do_codigo(codigo):
        """Deduz o tipo documental (matricula/transcricao) do prefixo M/T de um código."""
        if not codigo:
            return None
        primeiro = codigo.strip()[:1].upper()
        if primeiro == 'M':
            return 'matricula'
        if primeiro == 'T':
            return 'transcricao'
        return None

    @staticmethod
    def _resolver_documento_por_codigo(codigo, cartorio):
        """
        Resolve um documento de origem pela identidade completa (tipo, número
        normalizado e cartório), nunca por número isolado. Sem cartório, com
        tipo incompatível ou com identidade ambígua, não seleciona nenhum documento.
        """
        if not cartorio:
            return None
        tipo = CadeiaDominialTabelaService._tipo_do_codigo(codigo)
        if not tipo:
            return None
        try:
            identidade = DocumentoIdentidade(tipo, codigo, cartorio.pk)
        except (TypeError, ValueError):
            return None
        resultado = DocumentoIdentidadeService.resolver(identidade)
        return resultado.documento if resultado.status == 'encontrado' else None

    def get_cadeia_dominial_tabela(self, tis_id, imovel_id, session=None, escolhas_origem_param=None):
        """
        Obtém dados da cadeia dominial em formato de tabela
        """
        tis = get_object_or_404(TIs, id=tis_id)
        imovel = get_object_or_404(Imovel, id=imovel_id)
        
        # Extrair escolhas de origem da sessão ou usar as escolhas passadas
        escolhas_origem = {}
        if session:
            for key, value in session.items():
                if key.startswith('origem_documento_'):
                    documento_id = key.replace('origem_documento_', '')
                    escolhas_origem[documento_id] = value
        
        # Se escolhas foram passadas como parâmetro, usar elas em vez da sessão
        if escolhas_origem_param:
            escolhas_origem = escolhas_origem_param
        
        # Obter tronco principal considerando escolhas
        tronco_principal = self.hierarquia_service.obter_tronco_principal(imovel, escolhas_origem)
        
        # Expandir tronco principal com documentos importados referenciados
        tronco_expandido = self._expandir_tronco_com_importados(imovel, tronco_principal, escolhas_origem)
        
        # Garantir que todos os documentos referenciados como origem sejam incluídos
        # tronco_expandido = self._garantir_todos_documentos_incluidos(imovel, tronco_expandido)
        
        # Processar cada documento na ordem canônica da cadeia (a mesma da trilha
        # sem escolha): a expansão define quais documentos entram, não a ordem
        cadeia_processada = []
        documentos_ordenados = ordenar_cadeia(tronco_expandido, imovel)
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
            for lanc in lancamentos_list:
                lanc.keyword_encontrada = buscar_keyword(lanc.observacoes)
            lancamentos = lancamentos_list
            
            # Verificar se tem múltiplas origens
            origens_disponiveis = self._obter_origens_documento(documento, lancamentos)
            tem_multiplas_origens = len(origens_disponiveis) > 1
            
            # Verificar escolha atual das escolhas de origem
            escolha_atual = escolhas_origem.get(str(documento.id)) if escolhas_origem else None
            
            # Se não há escolha na sessão E há origens disponíveis, o padrão é a
            # primeira da lista (ordem canônica), a mesma origem que a cadeia segue
            if not escolha_atual and origens_disponiveis:
                escolha_atual = origens_disponiveis[0]
            
            # Formatar origens para o template (na ordem canônica)
            origens_formatadas = []
            for i, origem in enumerate(origens_disponiveis):
                # Sem escolha na sessão, a primeira origem é a escolhida
                is_escolhida = (origem == escolha_atual) if escolha_atual else (i == 0)
                origens_formatadas.append({
                    'numero': origem,
                    'escolhida': is_escolhida
                })
            
            # Verificar se documento é compartilhado (pertence a outro imóvel)
            is_compartilhado = documento.imovel != imovel
            
            cadeia_processada.append({
                'documento': documento,
                'lancamentos': lancamentos,
                'origens_disponiveis': origens_formatadas,
                'tem_multiplas_origens': tem_multiplas_origens,
                'escolha_atual': escolha_atual,
                'is_compartilhado': is_compartilhado
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
        Obtém as origens disponíveis para um documento (apenas origens válidas
        para navegação), na ordem canônica da cadeia
        """
        # dict.fromkeys deduplica mantendo a ordem de leitura: com um set,
        # códigos de chave idêntica ficariam na ordem arbitrária do hash
        codigos = dict.fromkeys(
            origem.codigo
            for lancamento in lancamentos
            if lancamento.tipo.tipo == 'inicio_matricula'
            for origem in LancamentoOrigemLeituraService.obter_origens(lancamento)
        )
        return sorted(codigos, key=chave_ordem_origem)
    
    def _extrair_origens(self, origem_string):
        """
        Extrai todas as origens de uma string
        Ex: "M3212; M3211; M3210" -> ["M3212", "M3211", "M3210"]
        """
        if not origem_string:
            return []
        
        # Dividir por ponto e vírgula e limpar espaços
        partes = [parte.strip() for parte in origem_string.split(';') if parte.strip()]
        return partes
    
    def _extrair_origens_validas(self, origem_string):
        """
        Extrai apenas origens válidas (documentos reais) de uma string
        Ex: "M3212; M3211; Destacamento Público:INCRA" -> ["M3212", "M3211"]
        """
        if not origem_string:
            return []
        
        # Dividir por ponto e vírgula e limpar espaços
        partes = [parte.strip() for parte in origem_string.split(';') if parte.strip()]
        
        # Filtrar apenas origens que são documentos reais (M ou T seguido de números)
        import re
        origens_validas = []
        for parte in partes:
            # Verificar se é um documento real (M ou T seguido de números)
            if re.match(r'^[MT]\d+$', parte):
                origens_validas.append(parte)
        
        return origens_validas
    
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

    def obter_cadeia_tabela(self, imovel, escolhas_origem=None):
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
        tronco_principal = HierarquiaService.obter_tronco_principal(imovel, escolhas_origem)

        # Ordem canônica da cadeia, nunca por data. `ordenar_cadeia` devolve uma
        # nova lista: a recebida vem do cache do tronco principal, em ordem
        # hierárquica, e não pode ser reordenada no lugar (D5 da issue #201)
        todos_documentos = ordenar_cadeia(tronco_principal, imovel)
        
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
            for lanc in lancamentos_list:
                lanc.keyword_encontrada = buscar_keyword(lanc.observacoes)
            lancamentos = lancamentos_list
            
            # Verificar se tem múltiplas origens
            tem_multiplas_origens = False
            origens_disponiveis = []
            
            for lancamento in lancamentos:
                if lancamento.tipo.tipo == 'inicio_matricula':
                    origens_lancamento = LancamentoOrigemLeituraService.obter_origens(
                        lancamento
                    )
                    if len(origens_lancamento) > 1:
                        tem_multiplas_origens = True
                        origens_disponiveis = self._origens_disponiveis_lancamento(
                            lancamento
                        )
                        break
            
            # Verificar escolha atual
            escolha_atual = escolhas_origem.get(str(documento.id))
            
            # Se não há escolha e há origens disponíveis, usar a primeira (ordem canônica)
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
            
            # Verificar se documento é compartilhado (pertence a outro imóvel)
            is_compartilhado = documento.imovel != imovel
            
            cadeia_completa.append({
                'documento': documento,
                'lancamentos': lancamentos,
                'tem_multiplas_origens': tem_multiplas_origens,
                'origens_disponiveis': origens_formatadas,
                'escolha_atual': escolha_atual,
                'is_compartilhado': is_compartilhado
            })
        
        return cadeia_completa

    @staticmethod
    def _origens_disponiveis_lancamento(lancamento):
        origens = []
        for origem in LancamentoOrigemLeituraService.obter_origens(lancamento):
            documento = CadeiaDominialTabelaService._resolver_documento_por_codigo(
                origem.codigo, origem.cartorio
            )
            if documento:
                origens.append({
                    'numero': origem.codigo,
                    'documento': documento,
                    'escolhida': False,
                })
        return sorted(origens, key=lambda item: chave_ordem_origem(item['numero']))
    
    @staticmethod
    def extrair_origens_disponiveis(origem_texto, imovel, cartorio_origem=None):
        """
        Extrai as origens disponíveis de um texto de origem

        Args:
            origem_texto: Texto contendo as origens
            imovel: Objeto Imovel
            cartorio_origem: Cartório do lançamento que informou a origem. A
                resolução nunca busca por número isolado: sem cartório, com
                tipo incompatível ou com identidade ambígua, a origem não é
                selecionada.

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
                doc_existente = CadeiaDominialTabelaService._resolver_documento_por_codigo(
                    codigo, cartorio_origem
                )
                if doc_existente:
                    origens.append({
                        'numero': codigo,
                        'documento': doc_existente,
                        'escolhida': False  # Será definida pelo contexto
                    })

        # Ordem canônica da cadeia
        return sorted(origens, key=lambda x: chave_ordem_origem(x['numero']))
    
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
            lancamentos = documento.lancamentos.all()

            # Lista temporária para documentos importados deste documento
            docs_importados_temp = []

            for lancamento in lancamentos:
                for origem in LancamentoOrigemLeituraService.obter_origens(lancamento):
                    # Resolver o documento importado pela identidade completa
                    # (tipo, número normalizado e cartório do lançamento)
                    doc_importado = self._resolver_documento_por_codigo(
                        origem.codigo, origem.cartorio
                    )

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
                    doc_origem_escolhido = self._obter_documento_origem_especifica(
                        doc_importado, escolha_especifica
                    )

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

    def _obter_documento_origem_especifica(self, documento, codigo_escolhido):
        """
        Resolve a origem escolhida explicitamente (sessão do usuário), usando o
        cartório do lançamento de `documento` que efetivamente referencia esse código.
        """
        lancamentos = documento.lancamentos.all()

        for lancamento in lancamentos:
            for origem in LancamentoOrigemLeituraService.obter_origens(lancamento):
                if codigo_escolhido != origem.codigo:
                    continue
                doc_origem = self._resolver_documento_por_codigo(
                    origem.codigo, origem.cartorio
                )
                if doc_origem:
                    return doc_origem
        return None

    def _obter_documento_origem_mais_alto(self, documento):
        """
        Obtém a origem padrão de um documento: a primeira na ordem canônica da
        cadeia, a mesma destacada como padrão nos botões de origem
        """
        # Buscar lançamentos com origens
        lancamentos = documento.lancamentos.all()

        origens_encontradas = []

        for lancamento in lancamentos:
            for origem in LancamentoOrigemLeituraService.obter_origens(lancamento):
                # Resolver documento de origem pela identidade completa
                doc_origem = self._resolver_documento_por_codigo(
                    origem.codigo, origem.cartorio
                )

                if doc_origem:
                    origens_encontradas.append(doc_origem)

        # A primeira na ordem canônica (a mesma destacada nos botões de origem)
        if origens_encontradas:
            return ordenar_cadeia(origens_encontradas)[0]

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
        lancamentos = documento.lancamentos.all()

        # Coletar todas as origens possíveis, associadas ao lançamento que as
        # informou (cada uma tem seu próprio cartório de origem)
        origem_para_contexto = {}
        for lancamento in lancamentos:
            for origem in LancamentoOrigemLeituraService.obter_origens(lancamento):
                origem_para_contexto.setdefault(origem.codigo, origem)
        origens = list(origem_para_contexto.keys())

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
        
        # Ordem canônica: matrículas maiores primeiro, depois transcrições maiores
        origens_validas.sort(key=chave_ordem_origem)
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
            contexto_origem = origem_para_contexto.get(origem_escolhida)
            cartorio_origem = contexto_origem.cartorio if contexto_origem else None
            doc_origem = self._resolver_documento_por_codigo(origem_escolhida, cartorio_origem)
            if doc_origem and doc_origem.id not in documentos_processados:
                cadeia_expandida.append(doc_origem)
                documentos_processados.add(doc_origem.id)
                # Recursão: expandir apenas a subcadeia da origem escolhida
                sub_cadeia = self._expandir_cadeia_recursiva(doc_origem, documentos_processados, escolhas_origem, profundidade + 1)
                cadeia_expandida.extend(sub_cadeia)
        return cadeia_expandida
    
    def _garantir_todos_documentos_incluidos(self, imovel, documentos_atuais):
        """
        Garante que todos os documentos referenciados como origem sejam incluídos na cadeia
        """
        documentos_incluidos = set(doc.id for doc in documentos_atuais)
        documentos_para_adicionar = []
        
        # Para cada documento atual, verificar suas origens
        for documento in documentos_atuais:
            lancamentos = documento.lancamentos.all()
            
            for lancamento in lancamentos:
                for origem in LancamentoOrigemLeituraService.obter_origens(lancamento):
                    # Resolver documento de origem pela identidade completa
                    doc_origem = self._resolver_documento_por_codigo(
                        origem.codigo, origem.cartorio
                    )

                    if doc_origem and doc_origem.id not in documentos_incluidos:
                        documentos_para_adicionar.append(doc_origem)
                        documentos_incluidos.add(doc_origem.id)
        
        # Adicionar documentos encontrados
        if documentos_para_adicionar:
            # Ordem canônica da cadeia
            documentos_para_adicionar.sort(key=chave_ordem_cadeia)
            documentos_atuais.extend(documentos_para_adicionar)
        
        return documentos_atuais
