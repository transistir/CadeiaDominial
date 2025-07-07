from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.http import require_http_methods, require_POST
from django.http import JsonResponse
from ..models import Lancamento, LancamentoTipo, Imovel, Documento, TIs, Pessoas, Cartorios, DocumentoTipo, LancamentoPessoa
from ..services.lancamento_service import LancamentoService
from ..utils.hierarquia_utils import processar_origens_para_documentos
from datetime import date
import uuid

@login_required
def novo_lancamento(request, tis_id, imovel_id, documento_id=None):
    """
    View para criar um novo lançamento
    """
    # Obter objetos básicos
    tis = get_object_or_404(TIs, id=tis_id)
    imovel = get_object_or_404(Imovel, id=imovel_id, terra_indigena_id=tis)
    

    
    # Obter documento ativo usando o service
    documento_ativo = LancamentoService.obter_documento_ativo(imovel, documento_id)
    
    # Se não há documento ativo, criar automaticamente um documento de matrícula
    if not documento_ativo:
        try:
            documento_ativo, mensagem = LancamentoService.criar_documento_matricula_automatico(imovel)
            messages.info(request, mensagem)
        except Exception as e:
            messages.error(request, str(e))
            return redirect('novo_documento', tis_id=tis.id, imovel_id=imovel.id)
    
    # Obter dados para o formulário
    pessoas = Pessoas.objects.all().order_by('nome')
    cartorios = Cartorios.objects.all().order_by('nome')
    tipos_lancamento = LancamentoService.obter_tipos_lancamento_por_documento(documento_ativo)
    
    # Processar POST
    if request.method == 'POST':
        try:
            # Usar o service para criar o lançamento completo
            lancamento, mensagem_origens = LancamentoService.criar_lancamento_completo(
                request, tis, imovel, documento_ativo
            )
            
            if lancamento:
                messages.success(request, f'Lançamento "{lancamento.numero_lancamento}" criado com sucesso!')
                if mensagem_origens:
                    messages.info(request, mensagem_origens)
                return redirect('documento_lancamentos', documento_id=documento_ativo.id, tis_id=tis.id, imovel_id=imovel.id)
            else:
                # Erro na criação - preparar contexto com dados do formulário
                messages.error(request, f'❌ Erro ao criar lançamento: {mensagem_origens}')
                
                # Verificar se é erro de número duplicado para destacar o campo
                numero_lancamento_error = 'Já existe um lançamento com o número' in mensagem_origens
                
                # Adicionar dados das pessoas para preservação
                transmitentes_data = []
                for i, nome in enumerate(request.POST.getlist('transmitente_nome[]')):
                    if nome.strip():
                        transmitentes_data.append({
                            'nome': nome.strip(),
                            'id': request.POST.getlist('transmitente[]')[i] if i < len(request.POST.getlist('transmitente[]')) else ''
                        })
                
                adquirentes_data = []
                for i, nome in enumerate(request.POST.getlist('adquirente_nome[]')):
                    if nome.strip():
                        adquirentes_data.append({
                            'nome': nome.strip(),
                            'id': request.POST.getlist('adquirente[]')[i] if i < len(request.POST.getlist('adquirente[]')) else ''
                        })
                
                context = {
                    'tis': tis,
                    'imovel': imovel,
                    'documento': documento_ativo,
                    'pessoas': pessoas,
                    'cartorios': cartorios,
                    'tipos_lancamento': tipos_lancamento,
                    'form_data': {
                        'tipo_lancamento': request.POST.get('tipo_lancamento'),
                        'numero_lancamento': request.POST.get('numero_lancamento'),
                        'numero_lancamento_simples': request.POST.get('numero_lancamento_simples'),
                        'data': request.POST.get('data'),
                        'observacoes': request.POST.get('observacoes'),
                        'livro': request.POST.get('livro'),
                        'folha': request.POST.get('folha'),
                        'cartorio': request.POST.get('cartorio'),
                        'cartorio_nome': request.POST.get('cartorio_nome'),
                        'transmitente_ids': request.POST.getlist('transmitente[]'),
                        'transmitente_nomes': request.POST.getlist('transmitente_nome[]'),
                        'adquirente_ids': request.POST.getlist('adquirente[]'),
                        'adquirente_nomes': request.POST.getlist('adquirente_nome[]'),
                        'area': request.POST.get('area'),
                        'origem': request.POST.get('origem_completa') or request.POST.get('origem'),
                        'forma': request.POST.get('forma'),
                        'descricao': request.POST.get('descricao'),
                        'titulo': request.POST.get('titulo'),
                        'cartorio_origem': request.POST.get('cartorio_origem'),
                        'livro_origem': request.POST.get('livro_origem'),
                        'folha_origem': request.POST.get('folha_origem'),
                        'data_origem': request.POST.get('data_origem'),
                        # Campos específicos por tipo
                        'forma_averbacao': request.POST.get('forma_averbacao'),
                        'forma_registro': request.POST.get('forma_registro'),
                        'forma_inicio': request.POST.get('forma_inicio'),
                    },
                    'numero_lancamento_error': numero_lancamento_error,
                }
                
                context['transmitentes'] = transmitentes_data
                context['adquirentes'] = adquirentes_data
                
                return render(request, 'dominial/lancamento_form.html', context)
                
        except Exception as e:
            # Capturar exceções para debug
            import traceback
            error_msg = f'Erro inesperado: {str(e)}\n{traceback.format_exc()}'
            messages.error(request, f'❌ {error_msg}')
            print(f"ERRO NA CRIAÇÃO DE LANÇAMENTO: {error_msg}")
            
            # Verificar se é erro de número duplicado para destacar o campo
            numero_lancamento_error = 'Já existe um lançamento com o número' in str(e)
            
            # Adicionar dados das pessoas para preservação
            transmitentes_data = []
            for i, nome in enumerate(request.POST.getlist('transmitente_nome[]')):
                if nome.strip():
                    transmitentes_data.append({
                        'nome': nome.strip(),
                        'id': request.POST.getlist('transmitente[]')[i] if i < len(request.POST.getlist('transmitente[]')) else ''
                    })
            
            adquirentes_data = []
            for i, nome in enumerate(request.POST.getlist('adquirente_nome[]')):
                if nome.strip():
                    adquirentes_data.append({
                        'nome': nome.strip(),
                        'id': request.POST.getlist('adquirente[]')[i] if i < len(request.POST.getlist('adquirente[]')) else ''
                    })
            
            context = {
                'tis': tis,
                'imovel': imovel,
                'documento': documento_ativo,
                'pessoas': pessoas,
                'cartorios': cartorios,
                'tipos_lancamento': tipos_lancamento,
                'form_data': {
                    'tipo_lancamento': request.POST.get('tipo_lancamento'),
                    'numero_lancamento': request.POST.get('numero_lancamento'),
                    'numero_lancamento_simples': request.POST.get('numero_lancamento_simples'),
                    'data': request.POST.get('data'),
                    'observacoes': request.POST.get('observacoes'),
                    'livro': request.POST.get('livro'),
                    'folha': request.POST.get('folha'),
                    'cartorio': request.POST.get('cartorio'),
                    'cartorio_nome': request.POST.get('cartorio_nome'),
                    'transmitente_ids': request.POST.getlist('transmitente[]'),
                    'transmitente_nomes': request.POST.getlist('transmitente_nome[]'),
                    'adquirente_ids': request.POST.getlist('adquirente[]'),
                    'adquirente_nomes': request.POST.getlist('adquirente_nome[]'),
                    'area': request.POST.get('area'),
                    'origem': request.POST.get('origem_completa') or request.POST.get('origem'),
                    'forma': request.POST.get('forma'),
                    'descricao': request.POST.get('descricao'),
                    'titulo': request.POST.get('titulo'),
                    'cartorio_origem': request.POST.get('cartorio_origem'),
                    'livro_origem': request.POST.get('livro_origem'),
                    'folha_origem': request.POST.get('folha_origem'),
                    'data_origem': request.POST.get('data_origem'),
                    # Campos específicos por tipo
                    'forma_averbacao': request.POST.get('forma_averbacao'),
                    'forma_registro': request.POST.get('forma_registro'),
                    'forma_inicio': request.POST.get('forma_inicio'),
                },
                'numero_lancamento_error': numero_lancamento_error,
            }
            
            context['transmitentes'] = transmitentes_data
            context['adquirentes'] = adquirentes_data
            
            return render(request, 'dominial/lancamento_form.html', context)
    
    # GET - mostrar formulário
    context = {
        'tis': tis,
        'imovel': imovel,
        'documento': documento_ativo,
        'pessoas': pessoas,
        'cartorios': cartorios,
        'tipos_lancamento': tipos_lancamento,
    }
    return render(request, 'dominial/lancamento_form.html', context)

@login_required
def editar_lancamento(request, tis_id, imovel_id, lancamento_id):
    """
    View para editar um lançamento existente
    """
    # Obter objetos básicos
    tis = get_object_or_404(TIs, id=tis_id)
    imovel = get_object_or_404(Imovel, id=imovel_id, terra_indigena_id=tis)
    lancamento = get_object_or_404(Lancamento, id=lancamento_id, documento__imovel=imovel)
    
    # Obter dados para o formulário
    pessoas = Pessoas.objects.all().order_by('nome')
    cartorios = Cartorios.objects.all().order_by('nome')
    tipos_lancamento = LancamentoService.obter_tipos_lancamento_por_documento(lancamento.documento)
    
    # Processar POST
    if request.method == 'POST':
        # Usar o service para atualizar o lançamento completo
        sucesso, mensagem_origens = LancamentoService.atualizar_lancamento_completo(
            request, lancamento, imovel
        )
        
        if sucesso:
            messages.success(request, f'Lançamento "{lancamento.numero_lancamento}" atualizado com sucesso!')
            if mensagem_origens:
                messages.info(request, mensagem_origens)
            
            # Verificar se o usuário marcou "finalizar"
            finalizar = request.POST.get('finalizar') == 'on'
            
            if finalizar:
                # Redirecionar para a visualização dos lançamentos do documento
                return redirect('documento_lancamentos', tis_id=tis.id, imovel_id=imovel.id, documento_id=lancamento.documento.id)
            else:
                # Redirecionar para criar um novo lançamento no mesmo documento
                return redirect('novo_lancamento_documento', tis_id=tis.id, imovel_id=imovel.id, documento_id=lancamento.documento.id)
        else:
            messages.error(request, mensagem_origens)
    
    # Obter pessoas do lançamento para exibição no formulário
    transmitentes = lancamento.pessoas.filter(tipo='transmitente')
    adquirentes = lancamento.pessoas.filter(tipo='adquirente')
    
    context = {
        'tis': tis,
        'imovel': imovel,
        'lancamento': lancamento,
        'documento': lancamento.documento,
        'pessoas': pessoas,
        'cartorios': cartorios,
        'tipos_lancamento': tipos_lancamento,
        'transmitentes': transmitentes,
        'adquirentes': adquirentes,
        'modo_edicao': True
    }
    
    return render(request, 'dominial/lancamento_form.html', context)

@login_required
def excluir_lancamento(request, tis_id, imovel_id, lancamento_id):
    """View para excluir um lançamento"""
    tis = get_object_or_404(TIs, id=tis_id)
    imovel = get_object_or_404(Imovel, id=imovel_id, terra_indigena_id=tis)
    lancamento = get_object_or_404(Lancamento, id=lancamento_id, documento__imovel=imovel)
    
    if request.method == 'POST':
        try:
            documento_id = lancamento.documento.id
            numero_lancamento = lancamento.numero_lancamento or f"Lançamento {lancamento.id}"
            lancamento.delete()
            messages.success(request, f'Lançamento "{numero_lancamento}" excluído com sucesso!')
            return redirect('documento_lancamentos', tis_id=tis_id, imovel_id=imovel_id, documento_id=documento_id)
        except Exception as e:
            messages.error(request, f'Erro ao excluir lançamento: {str(e)}')
    
    return render(request, 'dominial/lancamento_confirm_delete.html', {
        'tis': tis,
        'imovel': imovel,
        'lancamento': lancamento,
        'documento': lancamento.documento
    })

@login_required
def lancamento_detail(request, tis_id, imovel_id, lancamento_id):
    """View para visualizar detalhes de um lançamento"""
    tis = get_object_or_404(TIs, id=tis_id)
    imovel = get_object_or_404(Imovel, id=imovel_id, terra_indigena_id=tis)
    lancamento = get_object_or_404(Lancamento, id=lancamento_id, documento__imovel=imovel)
    
    # Obter pessoas do lançamento
    transmitentes = lancamento.pessoas.filter(tipo='transmitente')
    adquirentes = lancamento.pessoas.filter(tipo='adquirente')
    
    context = {
        'tis': tis,
        'imovel': imovel,
        'lancamento': lancamento,
        'documento': lancamento.documento,
        'transmitentes': transmitentes,
        'adquirentes': adquirentes
    }
    
    return render(request, 'dominial/lancamento_detail.html', context) 