"""
Service especializado para criação e atualização de lançamentos
"""

import logging
from ..models import Lancamento, LancamentoTipo
from .lancamento_form_service import LancamentoFormService
from .lancamento_validacao_service import LancamentoValidacaoService
from .lancamento_origem_service import LancamentoOrigemService
from .lancamento_campos_service import LancamentoCamposService
from .regra_petrea_service import RegraPetreaService
from .lancamento_duplicata_service import LancamentoDuplicataService
from .lancamento_pessoa_service import LancamentoPessoaService

logger = logging.getLogger(__name__)


class LancamentoCriacaoService:
    """
    Service para criar e atualizar lançamentos completos
    """
    
    @staticmethod
    def criar_lancamento_completo(request, tis, imovel, documento_ativo):
        """
        Cria um lançamento completo com todas as validações e processamentos
        """
        logger.debug(f"Iniciando criação de lançamento para documento {documento_ativo.id}")
        
        # Obter dados do formulário
        tipo_id = request.POST.get('tipo_lancamento')
        logger.debug(f"Tipo de lançamento ID: {tipo_id}")
        
        if not tipo_id:
            logger.debug("Erro - tipo_lancamento não fornecido")
            return None, "Tipo de lançamento é obrigatório"
        
        try:
            tipo_lanc = LancamentoTipo.objects.get(id=tipo_id)
            logger.debug(f"Tipo de lançamento encontrado: {tipo_lanc.tipo}")
        except LancamentoTipo.DoesNotExist:
            logger.debug(f"Erro - tipo de lançamento {tipo_id} não encontrado")
            return None, f"Tipo de lançamento {tipo_id} não encontrado"
        
        # Validar se o número simples foi fornecido para registro e averbação
        numero_simples = request.POST.get('numero_lancamento_simples', '').strip()
        if (tipo_lanc.tipo == 'registro' or tipo_lanc.tipo == 'averbacao') and not numero_simples:
            logger.debug(f"Erro - número simples obrigatório para {tipo_lanc.tipo}")
            return None, f"Para lançamentos do tipo '{tipo_lanc.get_tipo_display()}', é obrigatório preencher o campo 'Número' (ex: 1, 5, etc.)"
        
        # Processar dados do lançamento
        logger.debug("Processando dados do lançamento...")
        dados_lancamento = LancamentoFormService.processar_dados_lancamento(request, tipo_lanc)
        logger.debug(f"Dados processados: {dados_lancamento}")
        
        # Verificar duplicatas antes de criar o lançamento (pular se após importação)
        apos_importacao = request.POST.get('apos_importacao') == 'true'
        
        if not apos_importacao:
            logger.debug("Verificando duplicatas...")
            logger.debug("Importando LancamentoDuplicataService...")
            try:
                duplicata_resultado = LancamentoDuplicataService.verificar_duplicata_antes_criacao(
                    request, documento_ativo
                )
                logger.debug("Verificação de duplicata executada com sucesso")
            except Exception as e:
                logger.error(f"Erro na verificação de duplicata: {e}", exc_info=True)
                # Return error instead of proceeding - prevents potential duplicate creation
                return None, f'Erro na verificação de duplicatas: {str(e)}. Tente novamente.'
            logger.debug(f"Resultado verificação duplicata: {duplicata_resultado}")
            
            if duplicata_resultado['tem_duplicata']:
                logger.debug(f"Duplicata encontrada: {duplicata_resultado['mensagem']}")
                return {
                    'tipo': 'duplicata_encontrada',
                    'duplicata_info': duplicata_resultado
                }, duplicata_resultado['mensagem']
        else:
            logger.debug("Pulando verificação de duplicatas (após importação)")
        
        # Validar número do lançamento
        logger.debug("Validando número do lançamento...")
        is_valid, error_message = LancamentoValidacaoService.validar_numero_lancamento(
            dados_lancamento['numero_lancamento'], documento_ativo
        )
        logger.debug(f"Validação do número: {is_valid}, mensagem: {error_message}")
        
        if not is_valid:
            logger.debug(f"Erro na validação: {error_message}")
            return None, error_message
        
        # CORREÇÃO: Validar cartórios das origens
        logger.debug("Validando cartórios das origens...")
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
                    logger.debug(f"Cartório inválido na origem {i+1}: '{cartorio_nome}'")
                    return None, f"❌ Cartório inválido na origem {i+1}: '{cartorio_nome}'. Selecione um cartório da lista. Não é possível criar novos cartórios."
                
                # Verificar se o cartório realmente existe
                try:
                    cartorio = Cartorios.objects.get(id=cartorio_id)
                    if cartorio.nome != cartorio_nome:
                        logger.debug(f"Nome do cartório não confere: '{cartorio_nome}' vs '{cartorio.nome}'")
                        return None, f"❌ Cartório inválido na origem {i+1}: '{cartorio_nome}'. Selecione um cartório da lista."
                except Cartorios.DoesNotExist:
                    logger.debug(f"Cartório não encontrado: ID {cartorio_id}")
                    return None, f"❌ Cartório inválido na origem {i+1}: '{cartorio_nome}'. Selecione um cartório da lista."
        
        logger.debug("Validação de cartórios das origens aprovada")
        
        try:
            logger.debug("Criando lançamento básico...")
            # Criar o lançamento
            lancamento = LancamentoCriacaoService._criar_lancamento_basico(documento_ativo, dados_lancamento, tipo_lanc)
            logger.debug(f"Lançamento criado com ID: {lancamento.id}")
            
            # Processar cartório de origem
            logger.debug("Processando cartório de origem...")
            # Cartório de origem processado no service consolidado
            
            # Processar campos específicos por tipo de lançamento
            logger.debug("Processando campos específicos...")
            LancamentoCamposService.processar_campos_por_tipo(request, lancamento)
            
            logger.debug("Salvando lançamento...")
            lancamento.save()
            logger.debug(f"Lançamento salvo com sucesso: {lancamento.id}")
            
            # APLICAR CAMPOS DO DOCUMENTO: aplicar livro e folha ao documento
            logger.debug("Aplicando campos do documento...")
            documento_atualizado = LancamentoCriacaoService._aplicar_campos_documento(
                lancamento, dados_lancamento
            )
            if documento_atualizado:
                logger.debug("Campos do documento aplicados com sucesso")
            else:
                logger.debug("Campos do documento não aplicados")
                
            # VALIDAR CAMPOS OBRIGATÓRIOS NO PRIMEIRO LANÇAMENTO
            logger.debug("Validando campos obrigatórios no primeiro lançamento...")
            is_primeiro_lancamento = lancamento.documento.lancamentos.count() == 1
            
            if is_primeiro_lancamento:
                # Se é o primeiro lançamento, verificar se livro e folha foram definidos
                if not lancamento.documento.livro or lancamento.documento.livro == '0':
                    logger.debug("AVISO - Primeiro lançamento sem livro definido")
                if not lancamento.documento.folha or lancamento.documento.folha == '0':
                    logger.debug("AVISO - Primeiro lançamento sem folha definida")
            
            # APLICAR REGRA PÉTREA: primeiro lançamento define livro e folha do documento (se não aplicado acima)
            logger.debug("Aplicando regra pétrea...")
            regra_aplicada = RegraPetreaService.aplicar_regra_petrea(lancamento)
            if regra_aplicada:
                logger.debug("Regra pétrea aplicada - livro e folha definidos no documento")
            else:
                logger.debug("Regra pétrea não aplicada - não é o primeiro lançamento")
            
            # Processar origens para criar documentos automáticos
            logger.debug("Processando origens...")
            mensagem_origens = LancamentoOrigemService.processar_origens_automaticas(
                lancamento, dados_lancamento['origem'], imovel
            )
            
            # Processar transmitentes
            logger.debug("Processando transmitentes...")
            transmitentes_data = request.POST.getlist('transmitente_nome[]')
            transmitente_ids = request.POST.getlist('transmitente[]')
            
            # Pessoas processadas no service consolidado
            LancamentoPessoaService.processar_pessoas_lancamento(
                lancamento, transmitentes_data, transmitente_ids, 'transmitente'
            )
            
            # Processar adquirentes
            logger.debug("Processando adquirentes...")
            adquirentes_data = request.POST.getlist('adquirente_nome[]')
            adquirente_ids = request.POST.getlist('adquirente[]')
            
            # Pessoas processadas no service consolidado
            LancamentoPessoaService.processar_pessoas_lancamento(
                lancamento, adquirentes_data, adquirente_ids, 'adquirente'
            )
            
            logger.debug("Lançamento criado com sucesso!")
            return lancamento, mensagem_origens
            
        except Exception as e:
            logger.error(f"Erro durante criação de lançamento: {e}", exc_info=True)
            return None, f'Erro ao criar lançamento: {str(e)}'
    
    @staticmethod
    def atualizar_lancamento_completo(request, lancamento, imovel):
        """
        Atualiza um lançamento completo com todas as validações e processamentos
        """
        try:
            logger.debug(f"Iniciando atualização do lançamento {lancamento.id}")
            
            # Obter e processar o tipo de lançamento
            tipo_id = request.POST.get('tipo_lancamento')
            logger.debug(f"Tipo de lançamento ID recebido: {tipo_id}")
            
            if not tipo_id:
                logger.debug("Erro - tipo_lancamento não fornecido")
                return False, "Tipo de lançamento é obrigatório"
            
            try:
                tipo_lanc = LancamentoTipo.objects.get(id=tipo_id)
                logger.debug(f"Tipo de lançamento encontrado: {tipo_lanc.tipo}")
                
                # Atualizar o tipo do lançamento
                lancamento.tipo = tipo_lanc
                logger.debug(f"Tipo do lançamento atualizado para: {tipo_lanc.tipo}")
                
            except LancamentoTipo.DoesNotExist:
                logger.debug(f"Erro - tipo de lançamento {tipo_id} não encontrado")
                return False, f"Tipo de lançamento {tipo_id} não encontrado"
            
            # Validar se o número simples foi fornecido para registro e averbação
            numero_simples = request.POST.get('numero_lancamento_simples', '').strip()
            if (tipo_lanc.tipo == 'registro' or tipo_lanc.tipo == 'averbacao') and not numero_simples:
                logger.debug(f"Erro - número simples obrigatório para {tipo_lanc.tipo}")
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
            
            # Processar campos específicos por tipo de lançamento
            logger.debug("Processando campos específicos por tipo...")
            LancamentoCamposService.processar_campos_por_tipo(request, lancamento)
            
            # Salvar o lançamento
            logger.debug("Salvando lançamento...")
            lancamento.save()
            logger.debug(f"Lançamento salvo com sucesso: {lancamento.id}")
            
            # APLICAR REGRA PÉTREA: primeiro lançamento define livro e folha do documento
            logger.debug("Aplicando regra pétrea...")
            regra_aplicada = RegraPetreaService.aplicar_regra_petrea(lancamento)
            if regra_aplicada:
                logger.debug("Regra pétrea aplicada - livro e folha definidos no documento")
            else:
                logger.debug("Regra pétrea não aplicada - não é o primeiro lançamento")
            
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
                lancamento, origem, imovel
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
            
            logger.debug("Lançamento atualizado com sucesso!")
            return True, mensagem_origens
            
        except Exception as e:
            logger.error(f"Erro durante atualização de lançamento: {e}", exc_info=True)
            return False, f'Erro ao atualizar lançamento: {str(e)}'
    
    @staticmethod
    def _aplicar_campos_documento(lancamento, dados_lancamento):
        """
        Aplica os campos livro e folha do documento baseado nos dados do formulário
        HERANÇA: Se os campos livro_origem e folha_origem estiverem preenchidos,
        eles são convertidos em livro e folha do documento
        
        Args:
            lancamento: Objeto Lancamento
            dados_lancamento: Dict com dados do formulário
            
        Returns:
            bool: True se foi aplicado, False se não foi possível
        """
        documento = lancamento.documento
        
        # Obter livro e folha do documento dos dados do formulário
        livro_documento = dados_lancamento.get('livro_documento')
        folha_documento = dados_lancamento.get('folha_documento')
        
        # HERANÇA: Se os campos de origem estiverem preenchidos, usar eles
        livro_origem = dados_lancamento.get('livro_origem')
        folha_origem = dados_lancamento.get('folha_origem')
        
        # Priorizar campos do formulário, depois campos de origem
        livro_final = None
        folha_final = None
        
        # Se os campos do documento foram fornecidos no formulário, usar eles
        if livro_documento and livro_documento.strip():
            livro_final = livro_documento.strip()
        elif livro_origem and livro_origem.strip():
            # Herdar do campo de origem
            livro_final = livro_origem.strip()
        
        if folha_documento and folha_documento.strip():
            folha_final = folha_documento.strip()
        elif folha_origem and folha_origem.strip():
            # Herdar do campo de origem
            folha_final = folha_origem.strip()
        
        # Atualizar documento se algum campo foi definido
        documento_atualizado = False
        
        if livro_final:
            documento.livro = livro_final
            documento_atualizado = True
        
        if folha_final:
            documento.folha = folha_final
            documento_atualizado = True
        
        if documento_atualizado:
            documento.save()
            logger.debug(f"Campos do documento aplicados - Livro: {livro_final}, Folha: {folha_final}")
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