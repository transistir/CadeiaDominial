"""
Service para processamento de origens automáticas dos lançamentos
"""
import logging
import re
import uuid

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from ..utils.hierarquia_utils import processar_origens_para_documentos
from ..models import Cartorios, Documento, DocumentoTipo, LancamentoOrigem
from ..services.cri_service import CRIService
from ..services.cache_service import CacheService
from ..services.documento_identidade_service import DocumentoIdentidadeService
from ..utils.documento_identidade_utils import (
    DocumentoIdentidade,
    normalizar_numero_documento,
)

logger = logging.getLogger(__name__)


class OrigemAmbiguaError(Exception):
    """A identidade da origem casa com mais de um documento (#144)."""


class LancamentoOrigemService:
    @staticmethod
    def processar_origens_automaticas(lancamento, origem, imovel):
        """
        Processa origens para criar documentos automáticos
        NOVO: Fim de cadeia não cria documentos, apenas formata a origem
        """
        if not origem:
            LancamentoOrigemService._sincronizar_origens_estruturadas(
                lancamento,
                [],
                imovel,
            )
            return None
        
        # Separar origens normais de fim de cadeia
        origens_individuals = [o.strip() for o in origem.split(';') if o.strip()]
        origens_normais = []
        origens_fim_cadeia = []
        
        for origem_individual in origens_individuals:
            if LancamentoOrigemService._is_fim_cadeia(origem_individual):
                origens_fim_cadeia.append(origem_individual)
            else:
                origens_normais.append(origem_individual)

        # Escrita dupla da transição: mantém Lancamento.origem intocado e
        # reconcilia somente as origens documentais que possuem identidade.
        LancamentoOrigemService._sincronizar_origens_estruturadas(
            lancamento,
            origens_individuals,
            imovel,
        )
        
        # Processar apenas origens normais (que criam documentos)
        if origens_normais:
            origem_normais_texto = '; '.join(origens_normais)
            return LancamentoOrigemService._processar_origens_normais(
                lancamento, origem_normais_texto, imovel
            )
        
        # Se só tem fim de cadeia, retornar mensagem informativa
        if origens_fim_cadeia:
            return "Origem de fim de cadeia processada (sem criação de documento)"
        
        return None

    @staticmethod
    def _extrair_identidade_origem(origem_individual, imovel, lancamento, cartorio=None):
        """Extrai uma identidade documental sem converter fins de cadeia."""
        numero_informado = origem_individual.strip()
        prefixo_direto = re.match(r'^([MT])\s*\d', numero_informado, re.IGNORECASE)

        if prefixo_direto:
            prefixo = prefixo_direto.group(1).upper()
            tipo_documento = (
                'matricula' if prefixo == 'M' else 'transcricao'
            )
            try:
                normalizar_numero_documento(numero_informado, tipo_documento)
            except (TypeError, ValueError):
                return None
            return tipo_documento, numero_informado

        if re.fullmatch(r'\d+', numero_informado):
            return 'matricula', numero_informado

        # Compatibilidade com o texto aceito pelo fluxo antigo. Só grava quando
        # o parser funcional chegou a uma única identidade inequívoca.
        processadas = processar_origens_para_documentos(
            numero_informado,
            imovel,
            lancamento,
            cartorio,
        )
        if len(processadas) != 1:
            return None
        return processadas[0]['tipo'], processadas[0]['numero']

    @staticmethod
    def _sincronizar_origens_estruturadas(lancamento, origens, imovel):
        """
        Reconcilia o conjunto estruturado preservando IDs e o texto legado.

        Os índices existentes são movidos temporariamente para permitir troca
        de ordem sem colisão na constraint ``(lancamento, indice_origem)``.
        """
        desejadas = []
        identidades_vistas = set()

        for indice_origem, origem_individual in enumerate(origens):
            if LancamentoOrigemService._is_fim_cadeia(origem_individual):
                continue

            # Cartório da PRÓPRIA origem (#144): a validação de texto livre
            # nunca usa o cartório da primeira origem para as demais.
            dados_origem = LancamentoOrigemService._buscar_dados_origem(
                lancamento,
                origem_individual,
                indice_origem=indice_origem,
                total_origens=len(origens),
            )
            cartorio = dados_origem['cartorio']
            identidade = LancamentoOrigemService._extrair_identidade_origem(
                origem_individual,
                imovel,
                lancamento,
                cartorio,
            )
            if not identidade:
                continue

            tipo_documento, numero = identidade
            if not cartorio:
                raise ValidationError(
                    f'Cartório obrigatório para a origem {indice_origem + 1}.'
                )

            numero_normalizado = normalizar_numero_documento(
                numero,
                tipo_documento,
            )
            chave_identidade = (
                tipo_documento,
                numero_normalizado,
                cartorio.pk,
            )
            if chave_identidade in identidades_vistas:
                raise ValidationError(
                    f'Origem documental duplicada na posição {indice_origem + 1}.'
                )
            identidades_vistas.add(chave_identidade)

            documento_origem = LancamentoOrigemService._resolver_documento(
                tipo_documento,
                numero,
                cartorio,
            )
            livro, folha = LancamentoOrigemService._obter_livro_folha_origem(
                lancamento,
                documento_origem=documento_origem,
                livro_origem_informado=dados_origem['livro'],
                folha_origem_informada=dados_origem['folha'],
            )
            desejadas.append({
                'indice_origem': indice_origem,
                'tipo_documento': tipo_documento,
                'numero': numero,
                'numero_normalizado': numero_normalizado,
                'cartorio': cartorio,
                'livro': livro,
                'folha': folha,
            })

        with transaction.atomic():
            existentes = list(
                LancamentoOrigem.objects.select_for_update().filter(
                    lancamento=lancamento
                )
            )
            maior_indice = max(
                [item['indice_origem'] for item in desejadas]
                + [origem.indice_origem for origem in existentes]
                + [-1]
            )
            indice_temporario = maior_indice + len(existentes) + 1
            for deslocamento, origem in enumerate(existentes):
                LancamentoOrigem.objects.filter(pk=origem.pk).update(
                    indice_origem=indice_temporario + deslocamento
                )

            existentes_por_identidade = {
                (
                    origem.tipo_documento,
                    origem.numero_normalizado,
                    origem.cartorio_id,
                ): origem
                for origem in existentes
            }
            ids_mantidos = []

            for item in desejadas:
                chave = (
                    item['tipo_documento'],
                    item['numero_normalizado'],
                    item['cartorio'].pk,
                )
                origem = existentes_por_identidade.get(chave)
                if origem is None:
                    origem = LancamentoOrigem(lancamento=lancamento)

                origem.indice_origem = item['indice_origem']
                origem.tipo_documento = item['tipo_documento']
                origem.numero = item['numero']
                origem.cartorio = item['cartorio']
                origem.livro = item['livro']
                origem.folha = item['folha']
                origem.full_clean(exclude=['numero_normalizado'])
                origem.save()
                ids_mantidos.append(origem.pk)

            LancamentoOrigem.objects.filter(lancamento=lancamento).exclude(
                pk__in=ids_mantidos
            ).delete()
    
    @staticmethod
    def _is_fim_cadeia(origem_individual):
        """
        Verifica se uma origem individual é fim de cadeia
        """
        # Verificar se contém padrões de fim de cadeia
        padroes_fim_cadeia = [
            'Destacamento Público:',
            'Outra:',
            'Sem Origem:',
            'FIM_CADEIA'  # Para compatibilidade com formato antigo
        ]
        
        for padrao in padroes_fim_cadeia:
            if padrao in origem_individual:
                return True
        
        return False
    
    @staticmethod
    def _processar_origens_normais(lancamento, origem, imovel):
        """
        Processa origens normais (que criam documentos)
        """
        # Extrair origens individuais do texto concatenado
        origens_individuals = [o.strip() for o in origem.split(';') if o.strip()]

        # Múltiplas origens: cada uma é validada e criada com o cartório
        # específico dela (#144) - nunca pré-validar o texto todo com o
        # cartório da primeira origem.
        if len(origens_individuals) > 1:
            return LancamentoOrigemService._processar_multiplas_origens(
                lancamento, origens_individuals, imovel
            )

        dados_origem = LancamentoOrigemService._buscar_dados_origem(
            lancamento, origens_individuals[0]
        )
        origens_processadas = processar_origens_para_documentos(
            origem, imovel, lancamento, dados_origem['cartorio']
        )

        if not origens_processadas:
            if LancamentoOrigemService._origem_ambigua(
                origens_individuals[0], dados_origem['cartorio']
            ):
                logger.warning(
                    "Origem %r do lançamento %s é ambígua no cartório %s; não vinculada",
                    origens_individuals[0], lancamento.pk,
                    dados_origem['cartorio'].nome,
                )
                return LancamentoOrigemService._montar_mensagem_origens(
                    1, 0, 1, 'da origem identificada'
                )
            return None

        documentos_criados = []
        falhas = 0
        for origem_info in origens_processadas:
            try:
                with transaction.atomic():
                    documento_criado = LancamentoOrigemService._criar_documento_automatico(
                        imovel, lancamento, origem_info, dados_origem['cartorio']
                    )
            except Exception:
                LancamentoOrigemService._registrar_falha_origem(lancamento, origem_info)
                falhas += 1
                continue
            if documento_criado:
                documentos_criados.append(documento_criado)

        return LancamentoOrigemService._montar_mensagem_origens(
            len(origens_processadas), len(documentos_criados), falhas,
            'das origens identificadas',
        )

    @staticmethod
    def _origem_ambigua(origem_individual, cartorio):
        """True quando a identidade da origem casa com mais de um documento."""
        chave = LancamentoOrigemService._chave_identidade_texto(origem_individual)
        if not chave or not cartorio:
            return False
        try:
            LancamentoOrigemService._resolver_documento_estrito(
                chave[0], origem_individual, cartorio
            )
        except OrigemAmbiguaError:
            return True
        return False

    @staticmethod
    def _registrar_falha_origem(lancamento, origem_info):
        """Falha na criação automática nunca é silenciosa (#144)."""
        logger.exception(
            "Falha ao criar documento automático para a origem %s do lançamento %s",
            origem_info.get('numero'), lancamento.pk,
        )

    @staticmethod
    def _montar_mensagem_origens(identificadas, criados, falhas, complemento):
        """Mensagem ao usuário que reflete criações, reaproveitamentos e falhas."""
        if falhas:
            partes = []
            if criados:
                partes.append(f'{criados} documento(s) criado(s) automaticamente')
            partes.append(
                f'{falhas} não puderam ser vinculadas — verifique os avisos na árvore'
            )
            return (
                f'Foram identificadas {identificadas} origem(ns): '
                + '; '.join(partes) + '.'
            )
        if criados:
            return f'Foram criados {criados} documento(s) automaticamente a partir {complemento}.'
        return (
            f'Foram identificadas {identificadas} origem(ns); '
            'os documentos já existiam e foram reaproveitados.'
        )

    @staticmethod
    def _processar_fim_cadeia(lancamento, origem, imovel):
        """
        Processa lançamento de fim de cadeia e cria documento com classificação
        """
        # Extrair informações da origem
        # Formato 1: FIM_CADEIA:tipo_origem:numero:tipo_fim_cadeia:classificacao:sigla_patrimonio (quando usuário seleciona tipo)
        # Formato 2: FIM_CADEIA::tipo_fim_cadeia:classificacao:sigla_patrimonio (quando usuário não seleciona tipo)
        partes = origem.split(':')
        
        if len(partes) == 4:  # Formato 2: FIM_CADEIA::tipo_fim_cadeia:classificacao (formato antigo)
            tipo_origem = ''
            numero_origem = ''
            tipo_fim_cadeia = partes[2] if len(partes) > 2 else 'sem_origem'
            classificacao = partes[3] if len(partes) > 3 else 'sem_origem'
            sigla_patrimonio = ''
        elif len(partes) == 5:  # Formato 2: FIM_CADEIA::tipo_fim_cadeia:classificacao:sigla_patrimonio
            tipo_origem = ''
            numero_origem = ''
            tipo_fim_cadeia = partes[2] if len(partes) > 2 else 'sem_origem'
            classificacao = partes[3] if len(partes) > 3 else 'sem_origem'
            sigla_patrimonio = partes[4] if len(partes) > 4 else ''
        else:  # Formato 1: FIM_CADEIA:tipo_origem:numero:tipo_fim_cadeia:classificacao:sigla_patrimonio
            tipo_origem = partes[1] if len(partes) > 1 else ''  # M ou T
            numero_origem = partes[2] if len(partes) > 2 else ''  # Número digitado pelo usuário
            tipo_fim_cadeia = partes[3] if len(partes) > 3 else 'sem_origem'
            classificacao = partes[4] if len(partes) > 4 else 'sem_origem'
            sigla_patrimonio = partes[5] if len(partes) > 5 else ''
        
        
        # Determinar tipo de documento baseado no tipo de origem selecionado pelo usuário
        if tipo_origem == 'T':
            # Usuário selecionou transcrição
            tipo_doc = DocumentoTipo.objects.get(tipo='transcricao')
            numero_doc = f'T{numero_origem}' if numero_origem else 'T00'
        elif tipo_origem == 'M':
            # Usuário selecionou matrícula
            tipo_doc = DocumentoTipo.objects.get(tipo='matricula')
            numero_doc = f'M{numero_origem}' if numero_origem else 'M00'
        else:
            # Usuário não selecionou tipo de origem, usar tipo de fim de cadeia
            if tipo_fim_cadeia == 'destacamento_publico':
                # Para destacamento público, usar a sigla como número do documento
                tipo_doc = DocumentoTipo.objects.get(tipo='transcricao')
                numero_doc = sigla_patrimonio if sigla_patrimonio else 'T00'
            elif tipo_fim_cadeia == 'outra':
                # Para outra, criar como transcrição com número único
                tipo_doc = DocumentoTipo.objects.get(tipo='transcricao')
                from datetime import datetime
                timestamp = datetime.now().strftime('%y%m%d%H%M%S')
                numero_doc = f'T{timestamp}'
            else:
                # Para sem origem, criar como matrícula
                tipo_doc = DocumentoTipo.objects.get(tipo='matricula')
                from datetime import datetime
                timestamp = datetime.now().strftime('%y%m%d%H%M%S')
                numero_doc = f'M{timestamp}'
        
        # Usar cartório do lançamento atual
        cartorio_atual = lancamento.documento.cartorio
        
        # Criar documento de fim de cadeia
        dados_documento = {
            'imovel': imovel,
            'tipo': tipo_doc,
            'numero': numero_doc,
            'data': timezone.localdate(),
            'data_presumida': True,
            'cartorio': cartorio_atual,
            'livro': '0',
            'folha': '0',
            'origem': f'Documento de fim de cadeia - {tipo_fim_cadeia}',
            'observacoes': f'Documento criado automaticamente para fim de cadeia. Tipo: {tipo_fim_cadeia}, Classificação: {classificacao}',
            'classificacao_fim_cadeia': classificacao,
            'sigla_patrimonio_publico': sigla_patrimonio if tipo_fim_cadeia == 'destacamento_publico' else None
        }
        
        # Criar documento usando CRIService
        documento_criado = CRIService.criar_documento_com_cri(
            imovel, dados_documento, cri_origem=cartorio_atual
        )
        
        # Invalidar cache do imóvel
        CacheService.invalidate_documentos_imovel(imovel.id)
        CacheService.invalidate_tronco_principal(imovel.id)
        
        return f'Documento de fim de cadeia criado: {documento_criado.numero} ({documento_criado.tipo.get_tipo_display()}) com classificação "{classificacao}"'
    
    @staticmethod
    def _processar_multiplas_origens(lancamento, origens_individuals, imovel):
        """
        Processa múltiplas origens com seus respectivos cartórios
        """
        documentos_criados = []
        identificadas = 0
        falhas = 0

        # Para cada origem individual, criar documento com cartório específico
        for origem_individual in origens_individuals:
            # Buscar cartório e metadados específicos desta origem.
            dados_origem = LancamentoOrigemService._buscar_dados_origem(
                lancamento, origem_individual,
                total_origens=len(origens_individuals),
            )
            cartorio = dados_origem['cartorio']

            if not cartorio:
                # Sem cartório próprio a origem não pode ser validada nem
                # criada: nunca cair no da primeira origem (#144).
                logger.warning(
                    "Origem %r do lançamento %s sem cartório próprio; não vinculada",
                    origem_individual, lancamento.pk,
                )
                identificadas += 1
                falhas += 1
                continue

            # Validar com o cartório DESTA origem (#144), não o da primeira.
            origens_processadas = processar_origens_para_documentos(
                origem_individual, imovel, lancamento, cartorio
            )

            if not origens_processadas and LancamentoOrigemService._origem_ambigua(
                origem_individual, cartorio
            ):
                # A validação descarta origem ambígua em silêncio; aqui ela
                # entra na contagem para a mensagem não omitir a rejeição.
                logger.warning(
                    "Origem %r do lançamento %s é ambígua no cartório %s; não vinculada",
                    origem_individual, lancamento.pk, cartorio.nome,
                )
                identificadas += 1
                falhas += 1
                continue

            for origem_info in origens_processadas:
                identificadas += 1
                try:
                    with transaction.atomic():
                        documento_criado = (
                            LancamentoOrigemService._criar_documento_automatico_com_cartorio(
                                imovel,
                                lancamento,
                                origem_info,
                                cartorio,
                                livro_origem_informado=dados_origem['livro'],
                                folha_origem_informada=dados_origem['folha'],
                            )
                        )
                except Exception:
                    LancamentoOrigemService._registrar_falha_origem(
                        lancamento, origem_info
                    )
                    falhas += 1
                    continue
                if documento_criado:
                    documentos_criados.append(documento_criado)

        if not identificadas:
            return None

        return LancamentoOrigemService._montar_mensagem_origens(
            identificadas, len(documentos_criados), falhas,
            'das múltiplas origens identificadas',
        )
    
    @staticmethod
    def _chave_identidade_texto(origem_individual):
        """(tipo, número normalizado) inferido do texto M/T + dígitos, ou None."""
        texto = (origem_individual or '').strip()
        prefixo = re.match(r'^([MT])\s*\d', texto, re.IGNORECASE)
        if prefixo:
            tipo = 'matricula' if prefixo.group(1).upper() == 'M' else 'transcricao'
        elif re.fullmatch(r'\d+', texto):
            tipo = 'matricula'
        else:
            return None
        try:
            return tipo, normalizar_numero_documento(texto, tipo)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def encontrar_origem_persistida(lancamento, origem_individual, indice_origem=None):
        """
        Localiza a ``LancamentoOrigem`` persistida que casa com o texto da
        origem (tipo + número normalizado). Havendo homônimos no mesmo
        lançamento, prefere a de mesmo ``indice_origem``.
        """
        if not lancamento.pk:
            return None
        chave = LancamentoOrigemService._chave_identidade_texto(origem_individual)
        if not chave:
            return None
        candidatas = [
            origem
            for origem in lancamento.origens_estruturadas.select_related('cartorio')
            if (origem.tipo_documento, origem.numero_normalizado) == chave
        ]
        for origem in candidatas:
            if origem.indice_origem == indice_origem:
                return origem
        return candidatas[0] if candidatas else None

    @staticmethod
    def _buscar_dados_origem(
        lancamento, origem_individual, indice_origem=None, total_origens=None
    ):
        """
        Busca cartório, livro e folha específicos para uma origem individual.

        A ``LancamentoOrigem`` persistida é a fonte durável (#144); o cache do
        formulário só otimiza o POST corrente. Ordem: cache → linha persistida
        → (criação nova) cartório da primeira origem, único caso em que ele é
        o cartório correto. Com linhas persistidas e nenhuma casando, devolve
        ``cartorio=None`` para o chamador falhar de forma visível em vez de
        regravar a origem com a identidade de outra.
        """
        from django.core.cache import cache

        dados = {'cartorio': None, 'livro': None, 'folha': None}

        # 1. Mapeamento do POST corrente (cache)
        mapeamento = cache.get(f"mapeamento_origens_lancamento_{lancamento.id}")
        for item in mapeamento or []:
            if item['origem'] != origem_individual:
                continue
            dados['livro'] = item.get('livro')
            dados['folha'] = item.get('folha')
            cartorio = Cartorios.objects.filter(id=item['cartorio_id']).first()
            if cartorio is None and item.get('cartorio_nome'):
                cartorio = Cartorios.objects.filter(
                    nome__iexact=item['cartorio_nome']
                ).first()
            if cartorio is not None:
                dados['cartorio'] = cartorio
                return dados
            break

        # 2. Linha persistida desta origem
        persistida = LancamentoOrigemService.encontrar_origem_persistida(
            lancamento, origem_individual, indice_origem
        )
        if persistida:
            dados.update(
                cartorio=persistida.cartorio,
                livro=persistida.livro,
                folha=persistida.folha,
            )
            return dados

        if total_origens is None:
            total_origens = len([
                o for o in (lancamento.origem or '').split(';') if o.strip()
            ])
        origem_unica = total_origens <= 1

        # 3. Edição: há linhas persistidas e nenhuma casa com esta origem.
        if not origem_unica and lancamento.pk and (
            lancamento.origens_estruturadas.exists()
        ):
            return dados

        # 4. Criação nova. O cartório do lançamento é o da PRIMEIRA origem.
        if not origem_unica:
            logger.warning(
                "Lançamento %s com múltiplas origens sem mapeamento de cartório "
                "por origem; usando o cartório da primeira origem para %r",
                lancamento.pk, origem_individual,
            )
            dados['cartorio'] = lancamento.cartorio_origem
        else:
            dados['cartorio'] = (
                lancamento.cartorio_origem or lancamento.documento.cartorio
            )
        return dados

    @staticmethod
    def _normalizar_metadado_origem(valor):
        if isinstance(valor, str) and valor.strip() and valor.strip() != "None":
            return valor.strip()
        return None

    @staticmethod
    def _obter_livro_folha_origem(
        lancamento,
        documento_origem=None,
        livro_origem_informado=None,
        folha_origem_informada=None,
    ):
        """Aplica a mesma ordem de herança nos caminhos único e múltiplo."""
        livro_origem = None
        folha_origem = None

        if documento_origem:
            primeiro_lancamento = documento_origem.lancamentos.order_by('id').first()
            if primeiro_lancamento:
                livro_origem = LancamentoOrigemService._normalizar_metadado_origem(
                    primeiro_lancamento.livro_origem
                )
                folha_origem = LancamentoOrigemService._normalizar_metadado_origem(
                    primeiro_lancamento.folha_origem
                )

        if not livro_origem:
            livro_origem = LancamentoOrigemService._normalizar_metadado_origem(
                livro_origem_informado
            )
        if not folha_origem:
            folha_origem = LancamentoOrigemService._normalizar_metadado_origem(
                folha_origem_informada
            )
        if not livro_origem:
            livro_origem = LancamentoOrigemService._normalizar_metadado_origem(
                lancamento.livro_origem
            )
        if not folha_origem:
            folha_origem = LancamentoOrigemService._normalizar_metadado_origem(
                lancamento.folha_origem
            )

        return livro_origem, folha_origem
    
    @staticmethod
    def _criar_documento_automatico(imovel, lancamento, origem_info, cartorio_origem=None):
        """
        Cria um documento automaticamente a partir de uma origem
        CORREÇÃO: Usa o cartório da própria origem (#144); sem ele, o de origem
        do lançamento e, por fim, o do documento atual
        HERANÇA: Livro e folha são herdados do primeiro lançamento do documento criado pela origem

        Falhas propagam: o chamador registra (logger.exception) e contabiliza.
        Retorna None apenas quando o documento já existe (reaproveitado).
        """
        if not cartorio_origem:
            cartorio_origem = lancamento.cartorio_origem or lancamento.documento.cartorio

        return LancamentoOrigemService._criar_documento_origem(
            imovel, lancamento, origem_info, cartorio_origem,
            rotulo_cartorio='Cartório herdado da origem',
        )

    @staticmethod
    def _resolver_documento(tipo, numero, cartorio):
        """
        Resolve um documento pela identidade completa (tipo, número
        normalizado e cartório), nunca por número isolado.
        """
        if not cartorio:
            return None
        try:
            identidade = DocumentoIdentidade(tipo, numero, cartorio.pk)
        except (TypeError, ValueError):
            return None
        resultado = DocumentoIdentidadeService.resolver(identidade)
        return resultado.documento if resultado.status == 'encontrado' else None

    @staticmethod
    def _resolver_documento_estrito(tipo, numero, cartorio):
        """
        Como ``_resolver_documento``, mas identidade ambígua levanta erro:
        criar mais um homônimo só aprofundaria a duplicidade (#144).
        """
        if not cartorio:
            return None
        try:
            identidade = DocumentoIdentidade(tipo, numero, cartorio.pk)
        except (TypeError, ValueError):
            return None
        resultado = DocumentoIdentidadeService.resolver(identidade)
        if resultado.status == 'ambiguo':
            raise OrigemAmbiguaError(
                f'A origem {numero} tem {len(resultado.candidatos)} documentos '
                f'candidatos (ids {[d.pk for d in resultado.candidatos]}) no '
                f'cartório {cartorio.nome}.'
            )
        return resultado.documento if resultado.status == 'encontrado' else None

    @staticmethod
    def _criar_documento_automatico_com_cartorio(
        imovel,
        lancamento,
        origem_info,
        cartorio_origem,
        livro_origem_informado=None,
        folha_origem_informada=None,
    ):
        """
        Cria um documento automaticamente a partir de uma origem com cartório específico

        Falhas propagam: o chamador registra (logger.exception) e contabiliza.
        """
        return LancamentoOrigemService._criar_documento_origem(
            imovel, lancamento, origem_info, cartorio_origem,
            livro_origem_informado=livro_origem_informado,
            folha_origem_informada=folha_origem_informada,
            rotulo_cartorio='Cartório da origem',
        )

    @staticmethod
    def _criar_documento_origem(
        imovel,
        lancamento,
        origem_info,
        cartorio_origem,
        livro_origem_informado=None,
        folha_origem_informada=None,
        rotulo_cartorio='Cartório da origem',
    ):
        """Núcleo comum: resolve pela identidade completa e cria se não existir."""
        # Obter tipo de documento
        tipo_doc = DocumentoTipo.objects.get(tipo=origem_info['tipo'])

        # Buscar o documento de origem pela identidade completa (tipo,
        # número normalizado e cartório) - nunca por número isolado
        documento_origem = LancamentoOrigemService._resolver_documento_estrito(
            origem_info['tipo'], origem_info['numero'], cartorio_origem
        )

        livro_origem, folha_origem = (
            LancamentoOrigemService._obter_livro_folha_origem(
                lancamento,
                documento_origem=documento_origem,
                livro_origem_informado=livro_origem_informado,
                folha_origem_informada=folha_origem_informada,
            )
        )

        if documento_origem:
            # Documento já existe com esta identidade - reutilizar, nunca
            # tratar um homônimo de outro cartório como edição dele
            return None

        # Criar documento com o cartório da origem
        dados_documento = {
            'imovel': imovel,
            'tipo': tipo_doc,
            'numero': origem_info['numero'],
            'data': timezone.localdate(),
            'data_presumida': True,
            'cartorio': cartorio_origem,  # CARTÓRIO DA ORIGEM
            'livro': livro_origem if livro_origem else '0',  # LIVRO HERDADO DA ORIGEM
            'folha': folha_origem if folha_origem else '0',  # FOLHA HERDADA DA ORIGEM
            'origem': f'Criado automaticamente a partir de origem: {origem_info["numero"]}',
            'observacoes': f'Documento criado automaticamente ao identificar origem "{origem_info["numero"]}" no lançamento {lancamento.numero_lancamento}. {rotulo_cartorio}: {cartorio_origem.nome}. Livro: {livro_origem or "não informado"}, Folha: {folha_origem or "não informada"}'
        }

        # Criar documento usando CRIService com CRI da origem
        documento_criado = CRIService.criar_documento_com_cri(
            imovel, dados_documento, cri_origem=cartorio_origem
        )

        # Invalidar cache do imóvel
        CacheService.invalidate_documentos_imovel(imovel.id)
        CacheService.invalidate_tronco_principal(imovel.id)

        return documento_criado
