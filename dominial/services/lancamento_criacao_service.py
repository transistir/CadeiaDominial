"""
Service especializado para criação e atualização de lançamentos
"""

from ..models import Lancamento, LancamentoTipo
from .lancamento_form_service import LancamentoFormService
from .lancamento_validacao_service import LancamentoValidacaoService
from .lancamento_cartorio_service import LancamentoCartorioService
from .lancamento_origem_service import LancamentoOrigemService
from .lancamento_pessoa_service import LancamentoPessoaService
from .lancamento_campos_service import LancamentoCamposService


class LancamentoCriacaoService:
    """
    Service para criar e atualizar lançamentos completos
    """
    
    @staticmethod
    def criar_lancamento_completo(request, tis, imovel, documento_ativo):
        """
        Cria um lançamento completo com todas as validações e processamentos
        """
        # Obter dados do formulário
        tipo_id = request.POST.get('tipo_lancamento')
        tipo_lanc = LancamentoTipo.objects.get(id=tipo_id)
        
        # Processar dados do lançamento
        dados_lancamento = LancamentoFormService.processar_dados_lancamento(request, tipo_lanc)
        
        # Validar número do lançamento
        is_valid, error_message = LancamentoValidacaoService.validar_numero_lancamento(
            dados_lancamento['numero_lancamento'], documento_ativo
        )
        if not is_valid:
            return None, error_message
        
        try:
            # Criar o lançamento
            lancamento = LancamentoCriacaoService._criar_lancamento_basico(documento_ativo, dados_lancamento, tipo_lanc)
            
            # Processar cartório de origem
            LancamentoCartorioService.processar_cartorio_origem(request, tipo_lanc, lancamento)
            
            # Processar campos específicos por tipo de lançamento
            LancamentoCamposService.processar_campos_por_tipo(request, lancamento)
            
            lancamento.save()
            
            # Processar origens para criar documentos automáticos
            mensagem_origens = LancamentoOrigemService.processar_origens_automaticas(
                lancamento, dados_lancamento['origem'], imovel
            )
            
            # Processar transmitentes
            transmitentes_data = request.POST.getlist('transmitente_nome[]')
            transmitente_ids = request.POST.getlist('transmitente[]')
            
            LancamentoPessoaService.processar_pessoas_lancamento(
                lancamento, transmitentes_data, transmitente_ids, 'transmitente'
            )
            
            # Processar adquirentes
            adquirentes_data = request.POST.getlist('adquirente_nome[]')
            adquirente_ids = request.POST.getlist('adquirente[]')
            
            LancamentoPessoaService.processar_pessoas_lancamento(
                lancamento, adquirentes_data, adquirente_ids, 'adquirente'
            )
            
            return lancamento, mensagem_origens
            
        except Exception as e:
            return None, f'Erro ao criar lançamento: {str(e)}'
    
    @staticmethod
    def atualizar_lancamento_completo(request, lancamento, imovel):
        """
        Atualiza um lançamento completo com todas as validações e processamentos
        """
        try:
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
            LancamentoCamposService.processar_campos_por_tipo(request, lancamento)
            
            # Salvar o lançamento
            lancamento.save()
            
            # Processar origens para criar documentos automáticos
            origem = request.POST.get('origem_completa', '').strip()
            mensagem_origens = LancamentoOrigemService.processar_origens_automaticas(
                lancamento, origem, imovel
            )
            
            # Limpar pessoas existentes do lançamento
            lancamento.pessoas.all().delete()
            
            # Processar transmitentes
            transmitentes_data = request.POST.getlist('transmitente_nome[]')
            transmitente_ids = request.POST.getlist('transmitente[]')
            
            LancamentoPessoaService.processar_pessoas_lancamento(
                lancamento, transmitentes_data, transmitente_ids, 'transmitente'
            )
            
            # Processar adquirentes
            adquirentes_data = request.POST.getlist('adquirente_nome[]')
            adquirente_ids = request.POST.getlist('adquirente[]')
            
            LancamentoPessoaService.processar_pessoas_lancamento(
                lancamento, adquirentes_data, adquirente_ids, 'adquirente'
            )
            
            return True, mensagem_origens
            
        except Exception as e:
            return False, f'Erro ao atualizar lançamento: {str(e)}'
    
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
            data_origem=dados_lancamento['data'],
        )
        
        # Processar área e origem
        if dados_lancamento['area']:
            lancamento.area = float(dados_lancamento['area']) if dados_lancamento['area'] and dados_lancamento['area'].strip() else None
        if dados_lancamento['origem']:
            lancamento.origem = dados_lancamento['origem']
        
        return lancamento 