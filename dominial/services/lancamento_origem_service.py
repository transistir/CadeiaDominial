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
from ..managers import identidade_existe_fora_do_escopo
from ..utils.segregacao_utils import MENSAGEM_ORIGEM_RESTRITA
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


class OrigemRestritaError(Exception):
    """D1 (#132): a origem existe, mas em TI fora do escopo. Mensagem fixa."""
    def __init__(self):
        super().__init__(MENSAGEM_ORIGEM_RESTRITA)


class LancamentoOrigemService:
    # Mapeamento origem→cartório/livro/folha do POST corrente, como atributo
    # TEMPORÁRIO da instância (#144 fase 2, D4): vive exatamente uma
    # requisição/um save na memória do objeto. O LocMem anterior vazava por
    # TTL de 1h para POSTs seguintes e era um por processo (gunicorn com
    # workers sync), como o do tronco que o #210 já tinha desligado.
    ATRIBUTO_MAPEAMENTO = '_mapeamento_origens_post'

    @staticmethod
    def _origem_restrita(tipo, numero, cartorio, documentos_queryset):
        """True quando (tipo, número, cartório) existe só fora do escopo (D1)."""
        if not tipo or not cartorio:
            return False
        try:
            identidade = DocumentoIdentidade(tipo, numero, cartorio.pk)
        except (TypeError, ValueError):
            return False
        return identidade_existe_fora_do_escopo(
            documentos_queryset, tipo=identidade.tipo,
            numero_normalizado=identidade.numero_normalizado,
            cartorio_id=identidade.cartorio_id,
        )

    @staticmethod
    def definir_mapeamento(lancamento, mapeamento):
        """Grava o mapeamento do POST corrente na instância.

        Lista vazia limpa: um POST sem cartório resolvido não pode deixar
        o mapeamento de um POST anterior na mesma instância.
        """
        if mapeamento:
            setattr(
                lancamento,
                LancamentoOrigemService.ATRIBUTO_MAPEAMENTO,
                mapeamento,
            )
        else:
            LancamentoOrigemService.limpar_mapeamento(lancamento)

    @staticmethod
    def obter_mapeamento(lancamento):
        """O mapeamento do POST corrente, ou None (instância nova, já limpa)."""
        return getattr(
            lancamento, LancamentoOrigemService.ATRIBUTO_MAPEAMENTO, None
        )

    @staticmethod
    def limpar_mapeamento(lancamento):
        """Remove o atributo da instância (chamado no finally dos services)."""
        lancamento.__dict__.pop(
            LancamentoOrigemService.ATRIBUTO_MAPEAMENTO, None
        )

    @staticmethod
    def item_do_mapeamento(
        mapeamento, origem_individual, indice_origem=None, total_origens=None
    ):
        """
        Seleciona a entrada do mapeamento para UMA origem (D2, fase 2).

        Formato novo (pelo menos uma entrada tem ``indice``): vale só o valor
        de ``indice`` — a ordem física da lista e ``total_origens`` são
        ignorados. Entrada sem ``indice`` ou com ``indice`` não-int (inclui
        ``bool``) é descartada; um mapeamento misto NUNCA cai na regra legada.

        Formato legado (nenhuma entrada tem ``indice``, como as listas que o
        pré-fase-2 gravava): regra da fase 1 — acesso posicional quando a
        lista cobre todas as origens e o texto na posição bate; senão fallback
        por texto, que só vale com UM candidato.

        Devolve ``(item | None, ambiguo)``.
        """
        if not mapeamento:
            return None, False

        entradas = [
            item for item in mapeamento if isinstance(item, dict)
        ]
        if any('indice' in item for item in entradas):
            if indice_origem is None:
                return None, False
            na_posicao = [
                item for item in entradas
                if isinstance(item.get('indice'), int)
                and not isinstance(item.get('indice'), bool)
                and item['indice'] == indice_origem
            ]
            if len(na_posicao) > 1:
                return None, True
            if na_posicao:
                item = na_posicao[0]
                if item.get('origem') == origem_individual:
                    return item, False
                # Entrada na posição com texto divergente: é de outra origem,
                # e a busca segue para a linha persistida.
                return None, False
            return None, False

        # Legado (fase 1): posicional quando cobre todas as origens.
        if (
            indice_origem is not None
            and total_origens is not None
            and len(entradas) == total_origens
            and 0 <= indice_origem < len(entradas)
            and entradas[indice_origem].get('origem') == origem_individual
        ):
            return entradas[indice_origem], False
        por_texto = [
            item for item in entradas
            if item.get('origem') == origem_individual
        ]
        if len(por_texto) > 1:
            return None, True
        return (por_texto[0] if por_texto else None), False

    @staticmethod
    def chaves_homonimas(origens):
        """Chaves de identidade (tipo + número normalizado) que aparecem 2 ou
        mais vezes na lista de origens."""
        contagem = {}
        for origem in origens:
            chave = LancamentoOrigemService._chave_identidade_texto(origem)
            if chave:
                contagem[chave] = contagem.get(chave, 0) + 1
        return {
            chave for chave, total in contagem.items() if total > 1
        }

    @staticmethod
    def processar_origens_automaticas(
        lancamento,
        origem,
        imovel,
        documentos_queryset=None,
    ):
        """
        Processa origens para criar documentos automáticos
        NOVO: Fim de cadeia não cria documentos, apenas formata a origem
        """
        # Chamadas originadas de requests passam documentos_for_user(user).
        # O fallback existe para signals/rotinas internas sem usuário e fica
        # deliberadamente restrito ao imóvel do lançamento.
        if documentos_queryset is None:
            documentos_queryset = Documento.objects.filter(imovel=imovel)

        if not origem:
            LancamentoOrigemService._sincronizar_origens_estruturadas(
                lancamento,
                [],
                imovel,
                documentos_queryset,
            )
            return None
        
        # Separar origens normais de fim de cadeia
        origens_individuals = [o.strip() for o in origem.split(';') if o.strip()]
        origens_normais = []
        origens_fim_cadeia = []

        for indice_origem, origem_individual in enumerate(origens_individuals):
            if LancamentoOrigemService._is_fim_cadeia(origem_individual):
                origens_fim_cadeia.append(origem_individual)
            else:
                # (índice no texto COMPLETO, texto): a posição é a chave que
                # diferencia origens homônimas ("T366; T366") em cartórios
                # distintos — o índice acompanha a origem até o lookup.
                origens_normais.append((indice_origem, origem_individual))

        # Escrita dupla da transição: mantém Lancamento.origem intocado e
        # reconcilia somente as origens documentais que possuem identidade.
        LancamentoOrigemService._sincronizar_origens_estruturadas(
            lancamento,
            origens_individuals,
            imovel,
            documentos_queryset,
        )

        # Processar apenas origens normais (que criam documentos)
        if origens_normais:
            return LancamentoOrigemService._processar_origens_normais(
                lancamento, origens_normais, imovel, len(origens_individuals),
                origens_atuais=origens_individuals,
                documentos_queryset=documentos_queryset,
            )
        
        # Se só tem fim de cadeia, retornar mensagem informativa
        if origens_fim_cadeia:
            return "Origem de fim de cadeia processada (sem criação de documento)"
        
        return None

    @staticmethod
    def _extrair_identidade_origem(origem_individual, imovel, lancamento, cartorio, documentos_queryset):
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
            documentos_queryset=documentos_queryset,
        )
        if len(processadas) != 1:
            return None
        return processadas[0]['tipo'], processadas[0]['numero']

    @staticmethod
    def _sincronizar_origens_estruturadas(
        lancamento,
        origens,
        imovel,
        documentos_queryset,
    ):
        """
        Reconcilia o conjunto estruturado preservando IDs e o texto legado.

        Os índices existentes são movidos temporariamente para permitir troca
        de ordem sem colisão na constraint ``(lancamento, indice_origem)``.
        """
        desejadas = []
        identidades_vistas = {}

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
                origens_atuais=origens,
            )
            cartorio = dados_origem['cartorio']
            identidade = LancamentoOrigemService._extrair_identidade_origem(
                origem_individual,
                imovel,
                lancamento,
                cartorio,
                documentos_queryset=documentos_queryset,
            )
            if not identidade:
                continue

            tipo_documento, numero = identidade
            if not cartorio:
                if dados_origem['ambiguo']:
                    # Homônima sem posição confiável: a mensagem explica o
                    # motivo e cita o número, para o usuário saber qual
                    # linha do formulário selecionar (D6).
                    # F2-21: Se a ambiguidade vem de linhas legadas/persistidas
                    # no banco (não da lista atual do usuário), a mensagem
                    # distingue dizendo "registrada".
                    origem_termo = (
                        'origem registrada' if dados_origem.get('ambiguo_registrada')
                        else 'origem'
                    )
                    raise ValidationError(
                        f'Cartório obrigatório para a origem '
                        f'{indice_origem + 1} ({origem_individual}): há mais '
                        f'de uma {origem_termo} com esse número e não foi possível '
                        'identificar o cartório desta posição. Selecione o '
                        'cartório.'
                    )
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
                # A mensagem cita a posição colidente para o usuário
                # entender qual das linhas é a repetida (D6).
                raise ValidationError(
                    f'Origem documental duplicada na posição '
                    f'{indice_origem + 1}: corresponde à origem da posição '
                    f'{identidades_vistas[chave_identidade] + 1}, com o mesmo '
                    'tipo, número e cartório.'
                )
            identidades_vistas[chave_identidade] = indice_origem

            documento_origem = LancamentoOrigemService._resolver_documento(
                tipo_documento,
                numero,
                cartorio,
                documentos_queryset,
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

            # Reaproveitamento por identidade (tipo + número normalizado +
            # cartório) com preferência pela MESMA posição (#144 rodada 3):
            # homônimos em cartórios distintos são chaves distintas (nunca
            # "Origem documental duplicada"), e cada chave reaproveita a linha
            # que já ocupa a sua posição antes de qualquer outra — preserva
            # id/livro/folha na troca de ordem das origens.
            existentes_por_identidade = {}
            for origem in existentes:
                existentes_por_identidade.setdefault(
                    (
                        origem.tipo_documento,
                        origem.numero_normalizado,
                        origem.cartorio_id,
                    ),
                    [],
                ).append(origem)
            ids_mantidos = []

            for item in desejadas:
                chave = (
                    item['tipo_documento'],
                    item['numero_normalizado'],
                    item['cartorio'].pk,
                )
                origem = None
                for candidata in existentes_por_identidade.get(chave, []):
                    if candidata.indice_origem == item['indice_origem']:
                        origem = candidata
                        break
                if origem is None:
                    candidatas = existentes_por_identidade.get(chave) or []
                    origem = candidatas[0] if candidatas else None
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
    def _processar_origens_normais(
        lancamento, origens_normais, imovel, total_origens, origens_atuais=None, *, documentos_queryset
    ):
        """
        Processa origens normais (que criam documentos).

        ``origens_normais`` carrega ``(indice_no_texto_completo, texto)`` —
        índices do texto COMPLETO (fins de cadeia incluídos), os mesmos usados
        pelas linhas persistidas e pelo mapeamento do formulário (#144 rodada 3).
        """
        # Múltiplas origens: cada uma é validada e criada com o cartório
        # específico dela (#144) - nunca pré-validar o texto todo com o
        # cartório da primeira origem.
        if len(origens_normais) > 1:
            return LancamentoOrigemService._processar_multiplas_origens(
                lancamento, origens_normais, imovel, total_origens,
                origens_atuais=origens_atuais, documentos_queryset=documentos_queryset,
            )

        indice_unico, origem_unica = origens_normais[0]
        dados_origem = LancamentoOrigemService._buscar_dados_origem(
            lancamento,
            origem_unica,
            indice_origem=indice_unico,
            total_origens=total_origens,
            origens_atuais=origens_atuais,
        )
        
        # D1 (#132): pré-check de origem restrita antes de processar
        restritas = []
        chave = LancamentoOrigemService._chave_identidade_texto(origem_unica)
        if chave and LancamentoOrigemService._origem_restrita(
            chave[0], origem_unica, dados_origem['cartorio'], documentos_queryset,
        ):
            logger.info(
                "Origem %s do lançamento %s em TI fora do escopo; não vinculada",
                indice_unico + 1, lancamento.pk,
            )
            return LancamentoOrigemService._montar_mensagem_origens(
                1, 0, 0, 'da origem identificada', restritas=[indice_unico]
            )
        
        origens_processadas = processar_origens_para_documentos(
            origem_unica, imovel, lancamento, dados_origem['cartorio'],
            documentos_queryset=documentos_queryset,
        )

        if not origens_processadas:
            if LancamentoOrigemService._origem_ambigua(
                origem_unica, dados_origem['cartorio'], documentos_queryset
            ):
                logger.warning(
                    "Origem %r do lançamento %s é ambígua no cartório %s; não vinculada",
                    origem_unica, lancamento.pk,
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
                        imovel, lancamento, origem_info, dados_origem['cartorio'],
                        documentos_queryset=documentos_queryset,
                    )
            except OrigemRestritaError:
                restritas.append(indice_unico)
                continue
            except Exception:
                LancamentoOrigemService._registrar_falha_origem(lancamento, origem_info)
                falhas += 1
                continue
            if documento_criado:
                documentos_criados.append(documento_criado)

        return LancamentoOrigemService._montar_mensagem_origens(
            len(origens_processadas), len(documentos_criados), falhas,
            'das origens identificadas', restritas=restritas,
        )

    @staticmethod
    def _origem_ambigua(origem_individual, cartorio, documentos_queryset):
        """True quando a identidade da origem casa com mais de um documento."""
        chave = LancamentoOrigemService._chave_identidade_texto(origem_individual)
        if not chave or not cartorio:
            return False
        try:
            LancamentoOrigemService._resolver_documento_estrito(
                chave[0], origem_individual, cartorio, documentos_queryset
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
    def _montar_mensagem_origens(identificadas, criados, falhas, complemento, *, restritas=()):
        """Mensagem ao usuário que reflete criações, reaproveitamentos e falhas."""
        # D1 (#132): aviso de origens restritas com posições
        aviso = ''
        if restritas:
            posicoes = ', '.join(str(i + 1) for i in sorted(set(restritas)))
            aviso = f'Origem(ns) na(s) posição(ões) {posicoes} não vinculada(s): {MENSAGEM_ORIGEM_RESTRITA}.'
            identificadas -= len(restritas)
        
        if identificadas <= 0:
            return aviso
        
        if falhas:
            partes = []
            if criados:
                partes.append(f'{criados} documento(s) criado(s) automaticamente')
            partes.append(
                f'{falhas} não puderam ser vinculadas — verifique os avisos na árvore'
            )
            base = (
                f'Foram identificadas {identificadas} origem(ns): '
                + '; '.join(partes) + '.'
            )
            return f'{base} {aviso}'.strip()
        if criados:
            base = f'Foram criados {criados} documento(s) automaticamente a partir {complemento}.'
            return f'{base} {aviso}'.strip()
        base = (
            f'Foram identificadas {identificadas} origem(ns); '
            'os documentos já existiam e foram reaproveitados.'
        )
        return f'{base} {aviso}'.strip()

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
    def _processar_multiplas_origens(
        lancamento, origens_normais, imovel, total_origens, origens_atuais=None, *, documentos_queryset
    ):
        """
        Processa múltiplas origens com seus respectivos cartórios.

        ``origens_normais`` carrega ``(indice_no_texto_completo, texto)``: o
        índice viaja com a origem para que homônimos ("T366; T366") em
        cartórios distintos sejam diferenciados pela POSIÇÃO (#144 rodada 3).
        """
        documentos_criados = []
        identificadas = 0
        falhas = 0
        restritas = []

        # Para cada origem individual, criar documento com cartório específico
        for indice_origem, origem_individual in origens_normais:
            # Buscar cartório e metadados específicos desta origem.
            dados_origem = LancamentoOrigemService._buscar_dados_origem(
                lancamento,
                origem_individual,
                indice_origem=indice_origem,
                total_origens=total_origens,
                origens_atuais=origens_atuais,
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

            # D1 (#132): pré-check de origem restrita antes de processar
            chave = LancamentoOrigemService._chave_identidade_texto(origem_individual)
            if chave and LancamentoOrigemService._origem_restrita(
                chave[0], origem_individual, cartorio, documentos_queryset,
            ):
                logger.info(
                    "Origem %s do lançamento %s em TI fora do escopo; não vinculada",
                    indice_origem + 1, lancamento.pk,
                )
                identificadas += 1
                restritas.append(indice_origem)
                continue

            # Validar com o cartório DESTA origem (#144), não o da primeira.
            origens_processadas = processar_origens_para_documentos(
                origem_individual, imovel, lancamento, cartorio,
                documentos_queryset=documentos_queryset,
            )

            if not origens_processadas and LancamentoOrigemService._origem_ambigua(
                origem_individual, cartorio, documentos_queryset=documentos_queryset,
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
                                documentos_queryset=documentos_queryset,
                            )
                        )
                except OrigemRestritaError:
                    restritas.append(indice_origem)
                    continue
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
            'das múltiplas origens identificadas', restritas=restritas,
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
    def resolver_linha_por_posicao(
        linhas, origem_individual, indice_origem, origens_atuais
    ):
        """
        Lógica pura de ``resolver_origem_persistida`` (D3, fase 2), sem tocar
        o banco: ``linhas`` já vem carregada pelo chamador.

        Devolve ``(linha | None, ambiguo, ambiguo_registrada)``:

        1. Linha com ``indice_origem`` igual ao da origem sendo processada E
           identidade (tipo + número normalizado) igual ao texto — o caso
           normal de re-save, em que cada posição continua sendo a mesma
           origem. É a única forma de diferenciar "T366; T366" em cartórios
           distintos: o texto sozinho não distingue.
        2. Origem HOMÔNIMA (a chave aparece 2+ vezes em ``origens_atuais``)
           sem linha na posição → ``(None, True, False)``: SEM fallback por texto
           (P1-1) — o texto não distingue qual linha é desta posição, e
           gravar em silêncio a 1ª candidata troca o cartório da origem.
        3. Origem não homônima → fallback por texto: exatamente 1 candidato
           → a linha; 2 ou mais → ``(None, True, True)`` (ambiguidade no banco,
           mensagem distingue dizendo 'origem registrada'); nenhum → ``(None, False, False)``.
           Cobrem a edição que trocou o texto da posição e o legado com
           índices reordenados.
        """
        chave = LancamentoOrigemService._chave_identidade_texto(origem_individual)
        if not chave:
            return None, False, False
        if indice_origem is not None:
            na_posicao = next(
                (origem for origem in linhas if origem.indice_origem == indice_origem),
                None,
            )
            # F2-21: Mesmo com match na posição, se o banco tem múltiplas
            # linhas para a mesma chave E a lista atual não as reconhece
            # (não é homônima), é ambiguidade no banco (caso B).
            if na_posicao and (
                na_posicao.tipo_documento,
                na_posicao.numero_normalizado,
            ) == chave:
                if chave not in LancamentoOrigemService.chaves_homonimas(origens_atuais):
                    candidatos = [
                        origem for origem in linhas
                        if (origem.tipo_documento, origem.numero_normalizado) == chave
                    ]
                    if len(candidatos) > 1:
                        return None, True, True
                return na_posicao, False, False
        if chave in LancamentoOrigemService.chaves_homonimas(origens_atuais):
            return None, True, False
        candidatos = [
            origem for origem in linhas
            if (origem.tipo_documento, origem.numero_normalizado) == chave
        ]
        if len(candidatos) > 1:
            return None, True, True
        if candidatos:
            return candidatos[0], False, False
        return None, False, False

    @staticmethod
    def resolver_origem_persistida(
        lancamento, origem_individual, indice_origem=None, origens_atuais=None
    ):
        """
        Localiza a ``LancamentoOrigem`` persistida da origem (D3, fase 2).

        Wrapper de ``resolver_linha_por_posicao``: mantém as guardas que
        evitam a consulta ao banco quando o lançamento não está salvo ou o
        texto não tem identidade (tipo + número), carrega as linhas e delega
        a lógica pura.
        """
        if not lancamento.pk:
            return None, False, False
        chave = LancamentoOrigemService._chave_identidade_texto(origem_individual)
        if not chave:
            return None, False, False
        linhas = list(
            lancamento.origens_estruturadas.select_related('cartorio')
            .order_by('indice_origem')
        )
        if origens_atuais is None:
            origens_atuais = [
                o for o in (lancamento.origem or '').split(';') if o.strip()
            ]
        return LancamentoOrigemService.resolver_linha_por_posicao(
            linhas, origem_individual, indice_origem, origens_atuais
        )

    @staticmethod
    def encontrar_origem_persistida(
        lancamento, origem_individual, indice_origem=None, origens_atuais=None
    ):
        """
        Wrapper de ``resolver_origem_persistida`` que devolve só a linha
        (compatibilidade com os chamadores da fase 1).
        """
        linha, _, _ = LancamentoOrigemService.resolver_origem_persistida(
            lancamento, origem_individual, indice_origem, origens_atuais
        )
        return linha

    @staticmethod
    def _buscar_dados_origem(
        lancamento,
        origem_individual,
        indice_origem=None,
        total_origens=None,
        origens_atuais=None,
    ):
        """
        Busca cartório, livro e folha específicos para uma origem individual.

        A ``LancamentoOrigem`` persistida é a fonte durável (#144); o
        mapeamento do POST corrente — atributo temporário da instância gravado
        pelo writer do formulário (fase 2, D4), não mais o cache LocMem — só
        otimiza o save corrente. Ordem: mapeamento → linha persistida →
        (criação nova) cartório da primeira origem, único caso em que ele é
        o cartório correto. Com linhas persistidas e nenhuma casando, devolve
        ``cartorio=None`` para o chamador falhar de forma visível em vez de
        regravar a origem com a identidade de outra.

        A POSIÇÃO (``indice_origem``) é a chave primária do lookup em ambas
        as fontes (#144 rodada 3): origens textualmente idênticas em cartórios
        distintos ("T366; T366") só são diferenciadas pela posição. O match
        por texto é o fallback para mapeamento parcial/legado e só vale com
        UM candidato compatível; homônimos sem posição confiável são
        ambíguos (P1 Codex r3) e caem no caminho de falha visível — o dict
        devolve ``'ambiguo': True`` e o chamador cita a posição (D3, P1-1).
        A ambiguidade no mapeamento ou na linha persistida devolve
        ``cartorio=None`` na hora, sem consultar as fontes seguintes nem o
        cartório do lançamento (P1 Opus r4).
        """
        dados = {
            'cartorio': None, 'livro': None, 'folha': None, 'ambiguo': False,
            'ambiguo_registrada': False,
        }

        # 1. Mapeamento do POST corrente (atributo da instância). O seletor
        # (D2) concentra as regras: formato novo pelo 'indice' de cada
        # entrada; legado posicional/fallback por texto da fase 1.
        mapeamento = LancamentoOrigemService.obter_mapeamento(lancamento)
        item, ambiguo = LancamentoOrigemService.item_do_mapeamento(
            mapeamento, origem_individual, indice_origem, total_origens
        )
        if ambiguo:
            # Sem posição confiável não há como saber a qual origem cada
            # entrada pertence. A ambiguidade encerra o lookup (P1 Opus r4):
            # cair nas fontes seguintes gravaria o cartório da 1ª ocorrência
            # nas duas posições.
            dados['ambiguo'] = True
            return dados
        if item:
            cartorio = Cartorios.objects.filter(id=item.get('cartorio_id')).first()
            if cartorio is None and item.get('cartorio_nome'):
                cartorio = Cartorios.objects.filter(
                    nome__iexact=item['cartorio_nome']
                ).first()
            if cartorio is not None:
                dados['livro'] = item.get('livro')
                dados['folha'] = item.get('folha')
                dados['cartorio'] = cartorio
                return dados

        # 2. Linha persistida desta origem (D3): posição primeiro; homônima
        # sem linha na posição é ambígua e NÃO cai no fallback por texto.
        persistida, ambiguo, ambiguo_registrada = LancamentoOrigemService.resolver_origem_persistida(
            lancamento, origem_individual, indice_origem, origens_atuais
        )
        if persistida:
            dados.update(
                cartorio=persistida.cartorio,
                livro=persistida.livro,
                folha=persistida.folha,
            )
            return dados
        if ambiguo:
            dados['ambiguo'] = True
            # Ambiguidade vem de linhas legadas/persistidas no banco (não da
            # lista atual do usuário): a mensagem distingue dizendo registrada.
            dados['ambiguo_registrada'] = ambiguo_registrada
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
    def _criar_documento_automatico(imovel, lancamento, origem_info, cartorio_origem=None, *, documentos_queryset):
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
            documentos_queryset=documentos_queryset,
        )

    @staticmethod
    def _resolver_documento(
        tipo,
        numero,
        cartorio,
        documentos_queryset,
    ):
        """
        Resolve um documento pela identidade completa (tipo, número
        normalizado e cartório), nunca por número isolado.
        """
        if not cartorio or documentos_queryset is None:
            return None
        try:
            identidade = DocumentoIdentidade(tipo, numero, cartorio.pk)
        except (TypeError, ValueError):
            return None
        resultado = DocumentoIdentidadeService.resolver(
            identidade,
            queryset=documentos_queryset,
        )
        return resultado.documento if resultado.status == 'encontrado' else None

    @staticmethod
    def _resolver_documento_estrito(tipo, numero, cartorio, documentos_queryset):
        """
        Como ``_resolver_documento``, mas identidade ambígua levanta erro:
        criar mais um homônimo só aprofundaria a duplicidade (#144).
        """
        if documentos_queryset is None:
            raise TypeError('_resolver_documento_estrito exige documentos_queryset explícito')
        if not cartorio:
            return None
        try:
            identidade = DocumentoIdentidade(tipo, numero, cartorio.pk)
        except (TypeError, ValueError):
            return None
        resultado = DocumentoIdentidadeService.resolver(identidade, queryset=documentos_queryset)
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
        *,
        documentos_queryset,
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
            documentos_queryset=documentos_queryset,
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
        *,
        documentos_queryset,
    ):
        """Núcleo comum: resolve pela identidade completa e cria se não existir."""
        # Obter tipo de documento
        tipo_doc = DocumentoTipo.objects.get(tipo=origem_info['tipo'])

        # Buscar o documento de origem pela identidade completa (tipo,
        # número normalizado e cartório) - nunca por número isolado
        documento_origem = LancamentoOrigemService._resolver_documento_estrito(
            origem_info['tipo'], origem_info['numero'], cartorio_origem,
            documentos_queryset=documentos_queryset,
        )

        # D1 (#132): se não resolveu no escopo mas existe em outra TI, aborta
        # a criação sem IntegrityError — a LancamentoOrigem já foi gravada.
        if documento_origem is None and LancamentoOrigemService._origem_restrita(
            origem_info['tipo'], origem_info['numero'], cartorio_origem, documentos_queryset,
        ):
            raise OrigemRestritaError()

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
