"""
Service especializado para criação e atualização de lançamentos
"""

import logging

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import transaction

from ..models import Lancamento, LancamentoTipo
from .lancamento_form_service import LancamentoFormService
from .lancamento_validacao_service import LancamentoValidacaoService
from .lancamento_origem_service import LancamentoOrigemService
from .lancamento_campos_service import LancamentoCamposService
from .regra_petrea_service import RegraPetreaService
from .lancamento_duplicata_service import LancamentoDuplicataService
from .lancamento_pessoa_service import LancamentoPessoaService
from ..managers import documentos_for_user, lancamentos_for_user

logger = logging.getLogger(__name__)

# Mensagens fixas em vez do `str(e)` cru: o texto da exceção vaza número de
# documento, matrícula e nome de tabela direto na tela do usuário (#132).
ERRO_CRIACAO = 'Criação cancelada por erro inesperado. Nenhum lançamento foi salvo.'
ERRO_ATUALIZACAO = 'Atualização cancelada por erro inesperado. Nenhuma alteração foi salva.'
ERRO_DUPLICATA = 'Não foi possível verificar duplicatas. Tente novamente.'
NAO_AUTORIZADO_DOCUMENTO = 'Documento não encontrado ou não atribuído ao seu usuário.'
NAO_AUTORIZADO_LANCAMENTO = 'Lançamento não encontrado ou não atribuído ao seu usuário.'


class LancamentoCriacaoService:
    """
    Service para criar e atualizar lançamentos completos
    """
    
    @staticmethod
    def criar_lancamento_completo(
        request,
        tis,
        imovel,
        documento_ativo,
        *,
        apos_importacao=False,
    ):
        """
        Cria um lançamento completo com todas as validações e processamentos
        """
        # `documento_ativo` chega pronto do caller. Sem revalidar aqui, o service
        # grava em documento de outro usuário assim que qualquer view a montante
        # esquecer o guard (#132).
        documentos_autorizados = documentos_for_user(request.user)
        if not documentos_autorizados.filter(pk=documento_ativo.pk).exists():
            return None, NAO_AUTORIZADO_DOCUMENTO

        print(f"DEBUG: Iniciando criação de lançamento para documento {documento_ativo.id}")

        # Obter dados do formulário
        tipo_id = request.POST.get('tipo_lancamento')
        print(f"DEBUG: Tipo de lançamento ID: {tipo_id}")
        
        if not tipo_id:
            print("DEBUG: Erro - tipo_lancamento não fornecido")
            return None, "Tipo de lançamento é obrigatório"
        
        try:
            tipo_lanc = LancamentoTipo.objects.get(id=tipo_id)
            print(f"DEBUG: Tipo de lançamento encontrado: {tipo_lanc.tipo}")
        except LancamentoTipo.DoesNotExist:
            print(f"DEBUG: Erro - tipo de lançamento {tipo_id} não encontrado")
            return None, f"Tipo de lançamento {tipo_id} não encontrado"
        
        # Validar se o número simples foi fornecido para registro e averbação
        numero_simples = request.POST.get('numero_lancamento_simples', '').strip()
        if (tipo_lanc.tipo == 'registro' or tipo_lanc.tipo == 'averbacao') and not numero_simples:
            print(f"DEBUG: Erro - número simples obrigatório para {tipo_lanc.tipo}")
            return None, f"Para lançamentos do tipo '{tipo_lanc.get_tipo_display()}', é obrigatório preencher o campo 'Número' (ex: 1, 5, etc.)"
        
        # Processar dados do lançamento
        print("DEBUG: Processando dados do lançamento...")
        dados_lancamento = LancamentoFormService.processar_dados_lancamento(request, tipo_lanc)

        # Esta flag é um argumento interno confiável. Dados enviados pelo
        # cliente nunca podem desativar a verificação de duplicatas.
        if not apos_importacao:
            print("DEBUG: Verificando duplicatas...")
            try:
                duplicata_resultado = LancamentoDuplicataService.verificar_duplicata_antes_criacao(
                    request, documento_ativo
                )
                print("DEBUG: Verificação de duplicata executada com sucesso")
            except Exception:
                # Falhar aberto aqui deixava passar exatamente a duplicata que a
                # verificação existe para barrar: aborta em vez de assumir "sem
                # duplicata".
                logger.exception(
                    'Falha ao verificar duplicatas do documento %s', documento_ativo.pk
                )
                return None, ERRO_DUPLICATA

            if duplicata_resultado['tem_duplicata']:
                print(f"DEBUG: Duplicata encontrada: {duplicata_resultado['mensagem']}")
                return {
                    'tipo': 'duplicata_encontrada',
                    'duplicata_info': duplicata_resultado
                }, duplicata_resultado['mensagem']
        else:
            print("DEBUG: Pulando verificação de duplicatas (após importação)")
        
        # Validar número do lançamento
        print("DEBUG: Validando número do lançamento...")
        is_valid, error_message = LancamentoValidacaoService.validar_numero_lancamento(
            dados_lancamento['numero_lancamento'], documento_ativo
        )
        print(f"DEBUG: Validação do número: {is_valid}, mensagem: {error_message}")
        
        if not is_valid:
            print(f"DEBUG: Erro na validação: {error_message}")
            return None, error_message
        
        # CORREÇÃO: Validar cartórios das origens
        print("DEBUG: Validando cartórios das origens...")
        cartorios_origem_ids = request.POST.getlist('cartorio_origem[]')
        cartorios_origem_nomes = request.POST.getlist('cartorio_origem_nome[]')
        origens_completas = request.POST.getlist('origem_completa[]')
        
        from ..models import Cartorios
        
        for i, (cartorio_id, cartorio_nome) in enumerate(zip(cartorios_origem_ids, cartorios_origem_nomes)):
            # Verificar se esta origem é fim de cadeia
            origem_atual = origens_completas[i] if i < len(origens_completas) else ''
            is_fim_cadeia = any(padrao in origem_atual for padrao in [
                'Destacamento Público:', 'Outra:', 'Sem Origem:', 'FIM_CADEIA'
            ])
            
            # Só validar cartório se NÃO for fim de cadeia
            if not is_fim_cadeia and cartorio_nome.strip():  # Se foi digitado um nome
                if not cartorio_id.strip():  # Mas não foi selecionado da lista
                    print(f"DEBUG: Cartório inválido na origem {i+1}: '{cartorio_nome}'")
                    return None, f"❌ Cartório inválido na origem {i+1}: '{cartorio_nome}'. Selecione um cartório da lista. Não é possível criar novos cartórios."
                
                # Verificar se o cartório realmente existe
                try:
                    cartorio = Cartorios.objects.get(id=cartorio_id)
                    if cartorio.nome != cartorio_nome:
                        print(f"DEBUG: Nome do cartório não confere: '{cartorio_nome}' vs '{cartorio.nome}'")
                        return None, f"❌ Cartório inválido na origem {i+1}: '{cartorio_nome}'. Selecione um cartório da lista."
                except Cartorios.DoesNotExist:
                    print(f"DEBUG: Cartório não encontrado: ID {cartorio_id}")
                    return None, f"❌ Cartório inválido na origem {i+1}: '{cartorio_nome}'. Selecione um cartório da lista."
        
        print("DEBUG: Validação de cartórios das origens aprovada")
        
        # O mapeamento do POST vive só durante a requisição (D4): o finally
        # limpa da instância mesmo quando a criação falha no meio. Iniciado
        # como None porque a falha pode acontecer ANTES da atribuição abaixo
        # (o finally não pode mascarar o erro original com UnboundLocalError).
        lancamento = None
        try:
            print("DEBUG: Criando lançamento básico...")
            
            # ATOMICIDADE (#241): espelha atualizar_lancamento_completo (:305).
            # Qualquer erro após o lançamento básico (cartório de origem,
            # processar_origens_automaticas, pessoas) desfaz TUDO — nada de
            # órfão persistido. O except fica FORA do atomic para capturar
            # o erro do lado de fora e devolver a mensagem genérica
            # (nunca `str(e)` — vazaria documento/matrícula do usuário).
            # O `return` dentro do `with` comita o atomic normalmente.
            with transaction.atomic():
                lancamento = LancamentoCriacaoService._criar_lancamento_basico(
                    documento_ativo, dados_lancamento, tipo_lanc
                )
                print(f"DEBUG: Lançamento criado com ID: {lancamento.id}")

                # Processar cartório de origem
                print("DEBUG: Processando cartório de origem...")
                LancamentoOrigemService.processar_cartorio_origem(lancamento, request.POST)

                # Processar campos específicos por tipo de lançamento
                print("DEBUG: Processando campos específicos...")
                LancamentoCamposService.processar_campos_por_tipo(
                    request, lancamento, documentos_queryset=documentos_autorizados
                )

                print("DEBUG: Salvando lançamento...")
                lancamento.save()
                print(f"DEBUG: Lançamento salvo com sucesso: {lancamento.id}")

                # Aplicar livro e folha ao documento
                print("DEBUG: Aplicando campos do documento...")
                documento_atualizado = LancamentoCriacaoService._aplicar_campos_documento(
                    lancamento, dados_lancamento
                )
                if documento_atualizado:
                    print("DEBUG: Campos do documento aplicados com sucesso")
                else:
                    print("DEBUG: Campos do documento não aplicados")

                # VALIDAR CAMPOS OBRIGATÓRIOS NO PRIMEIRO LANÇAMENTO
                print("DEBUG: Validando campos obrigatórios no primeiro lançamento...")
                is_primeiro_lancamento = lancamento.documento.lancamentos.count() == 1
                if is_primeiro_lancamento:
                    # Se é o primeiro lançamento, verificar se livro e folha foram definidos
                    if not lancamento.documento.livro or lancamento.documento.livro == '0':
                        print("DEBUG: AVISO - Primeiro lançamento sem livro definido")
                    if not lancamento.documento.folha or lancamento.documento.folha == '0':
                        print("DEBUG: AVISO - Primeiro lançamento sem folha definida")
                # APLICAR REGRA PÉTREA: primeiro lançamento define livro e folha do documento (se não aplicado acima)
                print("DEBUG: Aplicando regra pétrea...")
                regra_aplicada = RegraPetreaService.aplicar_regra_petrea(lancamento)
                if regra_aplicada:
                    print("DEBUG: Regra pétrea aplicada - livro e folha definidos no documento")
                else:
                    print("DEBUG: Regra pétrea não aplicada - não é o primeiro lançamento")
                
                # Processar origens para criar documentos automáticos
                print("DEBUG: Processando origens automáticas...")
                mensagem_origens = LancamentoOrigemService.processar_origens_automaticas(
                    lancamento, dados_lancamento.get('origem', ''), imovel,
                    documentos_queryset=documentos_autorizados
                )
                # Processar transmitentes
                print("DEBUG: Processando transmitentes...")
                transmitentes_data = request.POST.getlist('transmitente_nome[]')
                transmitente_ids = request.POST.getlist('transmitente[]')
                # Pessoas processadas no service consolidado
                LancamentoPessoaService.processar_pessoas_lancamento(
                    lancamento, transmitentes_data, transmitente_ids, 'transmitente'
                )
                # Processar adquirentes
                print("DEBUG: Processando adquirentes...")
                adquirentes_data = request.POST.getlist('adquirente_nome[]')
                adquirente_ids = request.POST.getlist('adquirente[]')
                # Pessoas processadas no service consolidado
                LancamentoPessoaService.processar_pessoas_lancamento(
                    lancamento, adquirentes_data, adquirente_ids, 'adquirente'
                )
                
                print("DEBUG: Lançamento criado com sucesso!")
                return lancamento, mensagem_origens
            
        except ValidationError as e:
            print(f"DEBUG: Criação cancelada por validação: {str(e)}")
            # Espelha atualizar_lancamento_completo (:376-386): mensagens de
            # validação já terminam com ponto; o rstrip evita ponto duplo na
            # frase final ("origem 2.. Nenhuma…"). O sufixo deixa explícito
            # para o usuário que nada foi persistido (o atomic faz rollback
            # automático, mas a view precisa comunicar isso).
            motivo = (
                '; '.join(m.rstrip('.') for m in e.messages)
                if hasattr(e, 'messages') else str(e).rstrip('.')
            )
            # BLOCKER (Opus review): o atomic desfaz o banco, mas a instância
            # ``documento_ativo`` passada pelo caller continua com livro/folha
            # SUJOS em memória (escritos por ``_aplicar_campos_documento`` e
            # ``RegraPetreaService.aplicar_regra_petrea`` ANTES da falha).
            # A view re-renderiza com essa instância → ``doc_livro_definido=
            # True`` → campo Livro disabled com valor não salvo → no reenvio
            # o campo disabled não vai no POST e o livro se perde em
            # silêncio. ``refresh_from_db`` restaura os valores do banco
            # (rollback) na instância em memória.
            try:
                documento_ativo.refresh_from_db(fields=['livro', 'folha'])
            except Exception:
                # Se o documento foi criado DENTRO do atomic e rollback
                # apagou, refresh_from_db pode falhar — não mascarar o
                # erro original.
                pass
            return None, (
                f'Criação cancelada: {motivo}. Nenhum lançamento foi salvo.'
            )
        except Exception:
            # Qualquer outro erro é genérico: logger.exception captura o
            # traceback completo, mas a mensagem ao usuário é fixa (#132).
            logger.exception(
                'Erro inesperado ao criar lançamento do documento %s',
                documento_ativo.pk,
            )
            try:
                documento_ativo.refresh_from_db(fields=['livro', 'folha'])
            except Exception:
                # O rollback pode ter apagado documento criado dentro do
                # atomic — não mascarar o erro original.
                pass
            return None, ERRO_CRIACAO
        finally:
            # O mapeamento do POST vive só durante a requisição (D4): limpar
            # mesmo quando a criação falha, para o re-render não herdar
            # dados de um POST que não foi salvo (P1-2).
            LancamentoOrigemService.limpar_mapeamento(lancamento)
    @staticmethod
    def atualizar_lancamento_completo(request, lancamento, imovel):
        """
        Atualiza um lançamento completo com todas as validações e processamentos
        """
        # Igual à criação: o lançamento vem pronto do caller, e mais abaixo este
        # método apaga `lancamento.pessoas` — escrita destrutiva que não pode
        # depender do guard da view (#132).
        if not lancamentos_for_user(request.user).filter(pk=lancamento.pk).exists():
            return False, NAO_AUTORIZADO_LANCAMENTO

        try:
            documentos_autorizados = documentos_for_user(request.user)
            print(f"DEBUG: Iniciando atualização do lançamento {lancamento.id}")

            # Obter e processar o tipo de lançamento
            tipo_id = request.POST.get('tipo_lancamento')
            print(f"DEBUG: Tipo de lançamento ID recebido: {tipo_id}")

            if not tipo_id:
                print("DEBUG: Erro - tipo_lancamento não fornecido")
                return False, "Tipo de lançamento é obrigatório"

            try:
                tipo_lanc = LancamentoTipo.objects.get(id=tipo_id)
                print(f"DEBUG: Tipo de lançamento encontrado: {tipo_lanc.tipo}")

                # Atualizar o tipo do lançamento
                lancamento.tipo = tipo_lanc
                print(f"DEBUG: Tipo do lançamento atualizado para: {tipo_lanc.tipo}")

            except LancamentoTipo.DoesNotExist:
                print(f"DEBUG: Erro - tipo de lançamento {tipo_id} não encontrado")
                return False, f"Tipo de lançamento {tipo_id} não encontrado"

            # Validar se o número simples foi fornecido para registro e averbação
            numero_simples = request.POST.get('numero_lancamento_simples', '').strip()
            if (tipo_lanc.tipo == 'registro' or tipo_lanc.tipo == 'averbacao') and not numero_simples:
                print(f"DEBUG: Erro - número simples obrigatório para {tipo_lanc.tipo}")
                return False, f"Para lançamentos do tipo '{tipo_lanc.get_tipo_display()}', é obrigatório preencher o campo 'Número' (ex: 1, 5, etc.)"

            # Obter dados do formulário
            numero_lancamento = request.POST.get('numero_lancamento')
            data = request.POST.get('data')
            observacoes = request.POST.get('observacoes')

            # Validar número do lançamento (exceto se for o mesmo)
            if numero_lancamento != lancamento.numero_lancamento:
                is_valid, error_message = LancamentoValidacaoService.validar_numero_lancamento(
                    numero_lancamento, lancamento.documento, lancamento.id
                )
                if not is_valid:
                    return False, error_message

            # Atualizar campos básicos
            lancamento.numero_lancamento = numero_lancamento

            # Processar data principal com validação
            if data and data.strip():
                data_value = data.strip()
                # Validar formato da data (YYYY-MM-DD)
                if len(data_value) == 10 and data_value.count('-') == 2:
                    try:
                        # Tentar converter para validar o formato
                        from datetime import datetime
                        datetime.strptime(data_value, '%Y-%m-%d')
                        lancamento.data = data_value
                    except ValueError:
                        # Se a data for inválida, definir como None
                        lancamento.data = None
                else:
                    lancamento.data = None
            else:
                lancamento.data = None

            lancamento.observacoes = observacoes

            # ATOMICIDADE (#144 rodada 3 e fase 2 — D7): o writer de campos
            # por tipo (cartórios criados por nome, OrigemFimCadeia apagada e
            # recriada), o texto de `lancamento.origem` e as origens
            # estruturadas são gravados na MESMA transação. Sem isso, uma
            # falha na sincronização (ex.: origem nova sem cartório mapeado)
            # deixava o texto novo persistido apontando origens que as linhas
            # estruturadas não confirmam, e o writer, que rodava antes do
            # atomic, deixava para trás o fim de cadeia recriado e os
            # cartórios novos. O signal post_save roda dentro do atomic
            # (savepoint) e também é coberto pelo rollback; `messages` não é
            # transacional e fica como está. A falha de CRIAÇÃO de documento
            # de origem segue contada na mensagem (capturada dentro de
            # processar_origens_automaticas), sem derrubar a transação.
            with transaction.atomic():
                # Processar campos específicos por tipo de lançamento
                print("DEBUG: Processando campos específicos por tipo...")
                LancamentoCamposService.processar_campos_por_tipo(
                    request, lancamento, documentos_queryset=documentos_autorizados
                )

                # Salvar o lançamento
                print("DEBUG: Salvando lançamento...")
                lancamento.save()
                print(f"DEBUG: Lançamento salvo com sucesso: {lancamento.id}")

                # #218: o update nunca grava livro/folha do documento; se o POST
                # trouxe valor divergente (aba stale), avisar em vez de descartar.
                LancamentoCriacaoService._avisar_divergencias(
                    request,
                    LancamentoCriacaoService._divergencias_livro_folha(
                        lancamento.documento, request.POST),
                )

                # APLICAR REGRA PÉTREA: primeiro lançamento define livro e folha do documento
                print("DEBUG: Aplicando regra pétrea...")
                regra_aplicada = RegraPetreaService.aplicar_regra_petrea(lancamento)
                if regra_aplicada:
                    print("DEBUG: Regra pétrea aplicada - livro e folha definidos no documento")
                else:
                    print("DEBUG: Regra pétrea não aplicada - não é o primeiro lançamento")

                # Processar origens para criar documentos automáticos
                origens_completas = request.POST.getlist('origem_completa[]')
                if origens_completas:
                    # Filtrar origens vazias e concatenar
                    origens_validas = [origem.strip() for origem in origens_completas if origem.strip()]
                    origem = '; '.join(origens_validas) if origens_validas else ''
                else:
                    # Fallback para campo único
                    origem = request.POST.get('origem_completa', '').strip()

                mensagem_origens = LancamentoOrigemService.processar_origens_automaticas(
                    lancamento, origem, imovel,
                    documentos_queryset=documentos_autorizados,
                )

                # Limpar pessoas existentes do lançamento
                lancamento.pessoas.all().delete()

                # Processar transmitentes
                transmitentes_data = request.POST.getlist('transmitente_nome[]')
                transmitente_ids = request.POST.getlist('transmitente[]')

                # Pessoas processadas no service consolidado
                LancamentoPessoaService.processar_pessoas_lancamento(
                    lancamento, transmitentes_data, transmitente_ids, 'transmitente'
                )

                # Processar adquirentes
                adquirentes_data = request.POST.getlist('adquirente_nome[]')
                adquirente_ids = request.POST.getlist('adquirente[]')

                # Pessoas processadas no service consolidado
                LancamentoPessoaService.processar_pessoas_lancamento(
                    lancamento, adquirentes_data, adquirente_ids, 'adquirente'
                )

            print("DEBUG: Lançamento atualizado com sucesso!")
            return True, mensagem_origens

        except ValidationError as e:
            print(f"DEBUG: Atualização cancelada por validação: {str(e)}")
            # As mensagens de validação já terminam com ponto; sem o rstrip a
            # frase final nasceria com ponto duplo ("origem 2.. Nenhuma…").
            motivo = (
                '; '.join(m.rstrip('.') for m in e.messages)
                if hasattr(e, 'messages') else str(e).rstrip('.')
            )
            return False, (
                f'Atualização cancelada: {motivo}. Nenhuma alteração foi salva.'
            )
        except Exception:
            # Qualquer outro erro é genérico: logger.exception captura o
            # traceback completo, mas a mensagem ao usuário é fixa (#132).
            logger.exception(
                'Erro inesperado ao atualizar lançamento %s', lancamento.pk
            )
            return False, ERRO_ATUALIZACAO
        finally:
            # O mapeamento do POST vive só durante a requisição (D4): limpar
            # mesmo quando a atualização falha, para o re-render não herdar
            # dados de um POST que não foi salvo (P1-2).
            LancamentoOrigemService.limpar_mapeamento(lancamento)

    @staticmethod
    def _avisar_divergencias(request, divergencias):
        """Emite o aviso de correção de livro/folha não gravada (#218).

        O valor divergente segue descartado (regra pétrea #138), mas o usuário
        precisa saber que a correção não foi gravada.
        """
        if divergencias:
            messages.warning(
                request,
                '⚠️ Livro/Folha do documento não foram alterados: ' +
                '; '.join(divergencias) +
                '. Para corrigir Livro/Folha do documento use "Editar Documento".',
                fail_silently=True,
            )

    @staticmethod
    def _divergencias_livro_folha(documento, dados_lancamento):
        """Lista os campos livro/folha em que o formulário diverge do valor
        já definido no documento (#218).

        Só considera divergência quando o documento JÁ tem o valor definido
        (vazio/'0' contam como não definido) e o formulário traz outro valor.
        """
        def _definido(valor):
            return bool(valor) and valor != '0'

        divergencias = []
        campos = [('Livro gravado', 'livro', 'livro_documento')]
        if documento.tipo.tipo != 'matricula':
            campos.append(('Folha gravada', 'folha', 'folha_documento'))
        for rotulo, attr, chave in campos:
            atual = getattr(documento, attr)
            digitado = (dados_lancamento.get(chave) or '').strip()
            if _definido(atual) and digitado and digitado != atual.strip():
                divergencias.append(
                    f'{rotulo} "{atual}", informado "{digitado}"')
        return divergencias

    @staticmethod
    def _aplicar_campos_documento(lancamento, dados_lancamento):
        """
        Aplica os campos livro e folha do documento ATUAL baseado nos dados do
        formulário.

        IMPORTANTE (#118): o documento atual só recebe livro/folha explícitos do
        formulário (``livro_documento``/``folha_documento``). Os campos
        ``livro_origem``/``folha_origem`` pertencem ao documento de ORIGEM e são
        tratados em ``lancamento_origem_service`` (``_obter_livro_folha_origem``
        → ``_criar_documento_automatico_com_cartorio``); nunca devem chegar ao
        documento atual.

        Args:
            lancamento: Objeto Lancamento
            dados_lancamento: Dict com dados do formulário

        Returns:
            bool: True se foi aplicado, False se não foi possível
        """
        documento = lancamento.documento
        is_matricula = documento.tipo.tipo == 'matricula'

        # Obter livro e folha do documento ATUAL dos dados do formulário.
        # IMPORTANTE (#118): não herdar de livro_origem/folha_origem — esses
        # campos pertencem ao documento de origem, não ao documento atual.
        livro_documento = dados_lancamento.get('livro_documento')
        folha_documento = dados_lancamento.get('folha_documento')

        livro_final = livro_documento.strip() if livro_documento and livro_documento.strip() else None
        folha_final = folha_documento.strip() if folha_documento and folha_documento.strip() else None

        # REGRA PÉTREA (#138): livro e folha são definidos uma vez.
        # Só preencher se o campo no documento estiver vazio — depois de
        # definido, nenhum lançamento sobrescreve.
        documento_atualizado = False

        if livro_final and (not documento.livro or documento.livro == '0'):
            documento.livro = livro_final
            documento_atualizado = True

        if folha_final and not is_matricula and (not documento.folha or documento.folha == '0'):
            documento.folha = folha_final
            documento_atualizado = True

        if documento_atualizado:
            documento.save()
            return True

        return False
    
    @staticmethod
    def _criar_lancamento_basico(documento_ativo, dados_lancamento, tipo_lanc):
        """
        Cria um novo lançamento básico
        """
        lancamento = Lancamento.objects.create(
            documento=documento_ativo,
            tipo=tipo_lanc,
            numero_lancamento=dados_lancamento['numero_lancamento'],
            data=dados_lancamento['data'],
            observacoes=dados_lancamento['observacoes'],
            forma=dados_lancamento['forma'],
            descricao=dados_lancamento['descricao'],
            titulo=dados_lancamento['titulo'],
            livro_origem=dados_lancamento['livro_origem'],
            folha_origem=dados_lancamento['folha_origem'],
            cartorio_origem=dados_lancamento['cartorio_origem'],
            cartorio_transacao=None,  # Legado - será preenchido pelo LancamentoCamposService se necessário
            cartorio_transmissao=None,  # Novo padrão - será preenchido pelo LancamentoCamposService se necessário
            data_origem=dados_lancamento['data'],
        )
        
        # Processar área e origem
        if dados_lancamento['area']:
            lancamento.area = float(dados_lancamento['area']) if dados_lancamento['area'] and dados_lancamento['area'].strip() else None
        if dados_lancamento['origem']:
            lancamento.origem = dados_lancamento['origem']
        
        return lancamento