"""
Service para operações relacionadas a lançamentos
"""

from django.contrib import messages
from django.shortcuts import get_object_or_404
from ..models import (
    Lancamento, LancamentoTipo, Documento, DocumentoTipo, 
    Pessoas, Cartorios, LancamentoPessoa
)
from ..utils.hierarquia_utils import processar_origens_para_documentos
import uuid
from .lancamento_documento_service import LancamentoDocumentoService
from .lancamento_tipo_service import LancamentoTipoService
from .lancamento_form_service import LancamentoFormService
from .lancamento_pessoa_service import LancamentoPessoaService
from .lancamento_cartorio_service import LancamentoCartorioService
from .lancamento_origem_service import LancamentoOrigemService


class LancamentoService:
    """
    Service para gerenciar operações de lançamentos
    """
    
    @staticmethod
    def obter_documento_ativo(imovel, documento_id=None):
        """
        Obtém o documento ativo para criação de lançamentos
        """
        return LancamentoDocumentoService.obter_documento_ativo(imovel, documento_id)
    
    @staticmethod
    def criar_documento_matricula_automatico(imovel):
        """
        Cria automaticamente um documento de matrícula se não existir
        """
        return LancamentoDocumentoService.criar_documento_matricula_automatico(imovel)
    
    @staticmethod
    def obter_tipos_lancamento_por_documento(documento):
        """
        Obtém os tipos de lançamento disponíveis baseado no tipo do documento
        """
        return LancamentoTipoService.obter_tipos_lancamento_por_documento(documento)
    
    @staticmethod
    def validar_numero_lancamento(numero_lancamento, documento):
        """
        Valida se o número do lançamento é válido e único
        """
        return LancamentoTipoService.validar_numero_lancamento(numero_lancamento, documento)
    
    @staticmethod
    def processar_dados_lancamento(request, tipo_lanc):
        """
        Processa os dados do formulário de lançamento
        """
        return LancamentoFormService.processar_dados_lancamento(request, tipo_lanc)
    
    @staticmethod
    def processar_cartorio_origem(request, tipo_lanc, lancamento):
        """
        Processa o cartório de origem do lançamento
        """
        return LancamentoCartorioService.processar_cartorio_origem(request, tipo_lanc, lancamento)
    
    @staticmethod
    def criar_lancamento(documento_ativo, dados_lancamento, tipo_lanc):
        """
        Cria um novo lançamento
        """
        lancamento = Lancamento.objects.create(
            documento=documento_ativo,
            tipo=tipo_lanc,
            numero_lancamento=dados_lancamento['numero_lancamento'],
            data=dados_lancamento['data'],
            observacoes=dados_lancamento['observacoes'],
            eh_inicio_matricula=dados_lancamento['eh_inicio_matricula'],
            forma=dados_lancamento['forma'],
            descricao=dados_lancamento['descricao'],
            titulo=dados_lancamento['titulo'],
            livro_origem=dados_lancamento['livro_origem'],
            folha_origem=dados_lancamento['folha_origem'],
            data_origem=dados_lancamento['data'],
        )
        
        # Processar área e origem
        if dados_lancamento['area']:
            lancamento.area = float(dados_lancamento['area']) if dados_lancamento['area'] and dados_lancamento['area'].strip() else None
        if dados_lancamento['origem']:
            lancamento.origem = dados_lancamento['origem']
        
        return lancamento
    
    @staticmethod
    def processar_origens_automaticas(lancamento, origem, imovel):
        return LancamentoOrigemService.processar_origens_automaticas(lancamento, origem, imovel)
    
    @staticmethod
    def processar_pessoas_lancamento(lancamento, pessoas_data, pessoas_ids, pessoas_percentuais, tipo_pessoa):
        return LancamentoPessoaService.processar_pessoas_lancamento(lancamento, pessoas_data, pessoas_ids, pessoas_percentuais, tipo_pessoa)
    
    @staticmethod
    def criar_lancamento_completo(request, tis, imovel, documento_ativo):
        """
        Cria um lançamento completo com todas as validações e processamentos
        """
        # Obter dados do formulário
        tipo_id = request.POST.get('tipo_lancamento')
        tipo_lanc = LancamentoTipo.objects.get(id=tipo_id)
        
        # Processar dados do lançamento
        dados_lancamento = LancamentoService.processar_dados_lancamento(request, tipo_lanc)
        
        # Validar número do lançamento
        is_valid, error_message = LancamentoService.validar_numero_lancamento(
            dados_lancamento['numero_lancamento'], documento_ativo
        )
        if not is_valid:
            return None, error_message
        
        try:
            # Criar o lançamento
            lancamento = LancamentoService.criar_lancamento(documento_ativo, dados_lancamento, tipo_lanc)
            
            # Processar cartório de origem
            LancamentoService.processar_cartorio_origem(request, tipo_lanc, lancamento)
            lancamento.save()
            
            # Processar origens para criar documentos automáticos
            mensagem_origens = LancamentoService.processar_origens_automaticas(
                lancamento, dados_lancamento['origem'], imovel
            )
            
            # Processar transmitentes
            transmitentes_data = request.POST.getlist('transmitente_nome[]')
            transmitente_ids = request.POST.getlist('transmitente[]')
            transmitente_percentuais = request.POST.getlist('transmitente_percentual[]')
            
            LancamentoService.processar_pessoas_lancamento(
                lancamento, transmitentes_data, transmitente_ids, transmitente_percentuais, 'transmitente'
            )
            
            # Processar adquirentes
            adquirentes_data = request.POST.getlist('adquirente_nome[]')
            adquirente_ids = request.POST.getlist('adquirente[]')
            adquirente_percentuais = request.POST.getlist('adquirente_percentual[]')
            
            LancamentoService.processar_pessoas_lancamento(
                lancamento, adquirentes_data, adquirente_ids, adquirente_percentuais, 'adquirente'
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
            eh_inicio_matricula = request.POST.get('eh_inicio_matricula') == 'on'
            
            # Validar número do lançamento (exceto se for o mesmo)
            if numero_lancamento != lancamento.numero_lancamento:
                is_valid, error_message = LancamentoService.validar_numero_lancamento(
                    numero_lancamento, lancamento.documento
                )
                if not is_valid:
                    return False, error_message
            
            # Atualizar campos básicos
            lancamento.numero_lancamento = numero_lancamento
            lancamento.data = data if data and data.strip() else None
            lancamento.observacoes = observacoes
            lancamento.eh_inicio_matricula = eh_inicio_matricula
            
            # Processar campos específicos por tipo de lançamento
            if lancamento.tipo.tipo == 'averbacao':
                LancamentoService._processar_campos_averbacao(request, lancamento)
            elif lancamento.tipo.tipo == 'registro':
                LancamentoService._processar_campos_registro(request, lancamento)
            elif lancamento.tipo.tipo == 'inicio_matricula':
                LancamentoService._processar_campos_inicio_matricula(request, lancamento)
            
            # Salvar o lançamento
            lancamento.save()
            
            # Processar origens para criar documentos automáticos
            origem = request.POST.get('origem_completa', '').strip()
            mensagem_origens = LancamentoService.processar_origens_automaticas(
                lancamento, origem, imovel
            )
            
            # Limpar pessoas existentes do lançamento
            lancamento.lancamentopessoa_set.all().delete()
            
            # Processar transmitentes
            transmitentes_data = request.POST.getlist('transmitente_nome[]')
            transmitente_ids = request.POST.getlist('transmitente[]')
            transmitente_percentuais = request.POST.getlist('transmitente_percentual[]')
            
            LancamentoService.processar_pessoas_lancamento(
                lancamento, transmitentes_data, transmitente_ids, transmitente_percentuais, 'transmitente'
            )
            
            # Processar adquirentes
            adquirentes_data = request.POST.getlist('adquirente_nome[]')
            adquirente_ids = request.POST.getlist('adquirente[]')
            adquirente_percentuais = request.POST.getlist('adquirente_percentual[]')
            
            LancamentoService.processar_pessoas_lancamento(
                lancamento, adquirentes_data, adquirente_ids, adquirente_percentuais, 'adquirente'
            )
            
            return True, mensagem_origens
            
        except Exception as e:
            return False, f'Erro ao atualizar lançamento: {str(e)}'
    
    @staticmethod
    def _processar_campos_averbacao(request, lancamento):
        """
        Processa campos específicos para lançamentos do tipo averbação
        """
        # Processar forma
        forma_value = request.POST.get('forma_averbacao', '').strip()
        lancamento.forma = forma_value if forma_value else None
        
        # Processar cartório de origem se checkbox estiver marcado
        if request.POST.get('incluir_cartorio_averbacao') == 'on':
            cartorio_origem_id = request.POST.get('cartorio_origem_averbacao')
            cartorio_origem_nome = request.POST.get('cartorio_origem_nome_averbacao', '').strip()
            
            if cartorio_origem_id and cartorio_origem_id.strip():
                lancamento.cartorio_origem_id = cartorio_origem_id
            elif cartorio_origem_nome:
                try:
                    cartorio = Cartorios.objects.get(nome__iexact=cartorio_origem_nome)
                    lancamento.cartorio_origem = cartorio
                except Cartorios.DoesNotExist:
                    # Criar novo cartório com CNS único
                    cns_unico = f"CNS{str(uuid.uuid4().int)[:10]}"
                    cartorio = Cartorios.objects.create(
                        nome=cartorio_origem_nome,
                        cns=cns_unico,
                        cidade=Cartorios.objects.first().cidade if Cartorios.objects.exists() else None
                    )
                    lancamento.cartorio_origem = cartorio
            
            # Processar outros campos de cartório
            lancamento.livro_origem = request.POST.get('livro_origem_averbacao') if request.POST.get('livro_origem_averbacao') and request.POST.get('livro_origem_averbacao').strip() else None
            lancamento.folha_origem = request.POST.get('folha_origem_averbacao') if request.POST.get('folha_origem_averbacao') and request.POST.get('folha_origem_averbacao').strip() else None
            lancamento.data_origem = request.POST.get('data_origem_averbacao') if request.POST.get('data_origem_averbacao') else None
            lancamento.titulo = request.POST.get('titulo_averbacao') if request.POST.get('titulo_averbacao') and request.POST.get('titulo_averbacao').strip() else None
        else:
            # Limpar campos de cartório se o checkbox não estiver marcado
            lancamento.cartorio_origem_id = None
            lancamento.livro_origem = None
            lancamento.folha_origem = None
            lancamento.data_origem = None
    
    @staticmethod
    def _processar_campos_registro(request, lancamento):
        """
        Processa campos específicos para lançamentos do tipo registro
        """
        # Processar forma
        forma_value = request.POST.get('forma_registro', '').strip()
        lancamento.forma = forma_value if forma_value else None
        
        # Processar cartório de origem
        cartorio_origem_id = request.POST.get('cartorio_origem')
        cartorio_origem_nome = request.POST.get('cartorio_origem_nome', '').strip()
        
        if cartorio_origem_id and cartorio_origem_id.strip():
            lancamento.cartorio_origem_id = cartorio_origem_id
        elif cartorio_origem_nome:
            try:
                cartorio = Cartorios.objects.get(nome__iexact=cartorio_origem_nome)
                lancamento.cartorio_origem = cartorio
            except Cartorios.DoesNotExist:
                # Criar novo cartório com CNS único
                cns_unico = f"CNS{str(uuid.uuid4().int)[:10]}"
                cartorio = Cartorios.objects.create(
                    nome=cartorio_origem_nome,
                    cns=cns_unico,
                    cidade=Cartorios.objects.first().cidade if Cartorios.objects.exists() else None
                )
                lancamento.cartorio_origem = cartorio
        else:
            lancamento.cartorio_origem_id = None
        
        # Processar outros campos
        livro_origem_clean = request.POST.get('livro_origem') if request.POST.get('livro_origem') and request.POST.get('livro_origem').strip() else None
        folha_origem_clean = request.POST.get('folha_origem') if request.POST.get('folha_origem') and request.POST.get('folha_origem').strip() else None
        
        lancamento.livro_origem = livro_origem_clean
        lancamento.folha_origem = folha_origem_clean
        lancamento.data_origem = request.POST.get('data_origem') if request.POST.get('data_origem') else None
    
    @staticmethod
    def _processar_campos_inicio_matricula(request, lancamento):
        """
        Processa campos específicos para lançamentos do tipo início de matrícula
        """
        # Processar forma
        forma_value = request.POST.get('forma_inicio', '').strip()
        lancamento.forma = forma_value if forma_value else None
        
        # Processar área e origem
        area_value = request.POST.get('area', '').strip() if request.POST.get('area') else None
        lancamento.area = float(area_value) if area_value else None
        lancamento.origem = request.POST.get('origem_completa', '').strip() if request.POST.get('origem_completa') else None
        lancamento.descricao = request.POST.get('descricao', '').strip() if request.POST.get('descricao') else None
        lancamento.titulo = request.POST.get('titulo', '').strip() if request.POST.get('titulo') else None 