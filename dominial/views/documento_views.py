from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods, require_POST
from ..models import Documento, DocumentoTipo, Imovel, TIs, Cartorios, Lancamento
from ..forms import ImovelForm
from datetime import date
from ..services.documento_service import DocumentoService
from ..services.cache_service import CacheService

@login_required
def documentos(request, tis_id, imovel_id):
    """Lista todos os documentos de um imóvel"""
    tis = get_object_or_404(TIs, id=tis_id)
    imovel = get_object_or_404(Imovel, id=imovel_id, terra_indigena_id=tis)
    
    # Otimização: usar select_related e prefetch_related
    documentos = Documento.objects.filter(imovel=imovel)\
        .select_related('cartorio', 'tipo')\
        .prefetch_related('lancamentos')\
        .order_by('-data')
    
    context = {
        'tis': tis,
        'imovel': imovel,
        'documentos': documentos,
    }
    
    return render(request, 'dominial/documentos.html', context)

@login_required
def novo_documento(request, tis_id, imovel_id):
    """Cria um novo documento"""
    tis = get_object_or_404(TIs, id=tis_id)
    imovel = get_object_or_404(Imovel, id=imovel_id, terra_indigena_id=tis)
    
    # Otimização: usar select_related para cartórios
    cartorios = Cartorios.objects.all().select_related().order_by('nome')
    tipos_documento = DocumentoTipo.objects.all().order_by('tipo')
    
    if request.method == 'POST':
        sucesso, mensagem = DocumentoService.criar_documento(request, imovel)
        
        if sucesso:
            messages.success(request, f'Documento "{mensagem}" criado com sucesso!')
            # Invalidar cache do imóvel
            CacheService.invalidate_documentos_imovel(imovel.id)
            CacheService.invalidate_tronco_principal(imovel.id)
            return redirect('documentos', tis_id=tis.id, imovel_id=imovel.id)
        else:
            messages.error(request, mensagem)
    
    context = {
        'tis': tis,
        'imovel': imovel,
        'cartorios': cartorios,
        'tipos_documento': tipos_documento,
    }
    
    return render(request, 'dominial/documento_form.html', context)

@login_required
def editar_documento(request, tis_id, imovel_id, documento_id):
    """Edita um documento existente"""
    tis = get_object_or_404(TIs, id=tis_id)
    imovel = get_object_or_404(Imovel, id=imovel_id, terra_indigena_id=tis)
    documento = get_object_or_404(Documento, id=documento_id, imovel=imovel)
    
    # Otimização: usar select_related para cartórios
    cartorios = Cartorios.objects.all().select_related().order_by('nome')
    tipos_documento = DocumentoTipo.objects.all().order_by('tipo')
    
    if request.method == 'POST':
        sucesso, mensagem = DocumentoService.atualizar_documento(request, documento)
        
        if sucesso:
            messages.success(request, f'Documento "{mensagem}" atualizado com sucesso!')
            # Invalidar cache do imóvel
            CacheService.invalidate_documentos_imovel(imovel.id)
            CacheService.invalidate_tronco_principal(imovel.id)
            return redirect('documentos', tis_id=tis.id, imovel_id=imovel.id)
        else:
            messages.error(request, mensagem)
    
    context = {
        'tis': tis,
        'imovel': imovel,
        'documento': documento,
        'cartorios': cartorios,
        'tipos_documento': tipos_documento,
        'modo_edicao': True
    }
    
    return render(request, 'dominial/documento_form.html', context)

@login_required
def excluir_documento(request, tis_id, imovel_id, documento_id):
    """Exclui um documento"""
    tis = get_object_or_404(TIs, id=tis_id)
    imovel = get_object_or_404(Imovel, id=imovel_id, terra_indigena_id=tis)
    documento = get_object_or_404(Documento, id=documento_id, imovel=imovel)
    
    if request.method == 'POST':
        try:
            numero_documento = documento.numero
            documento.delete()
            messages.success(request, f'Documento "{numero_documento}" excluído com sucesso!')
            # Invalidar cache do imóvel
            CacheService.invalidate_documentos_imovel(imovel.id)
            CacheService.invalidate_tronco_principal(imovel.id)
            return redirect('documentos', tis_id=tis.id, imovel_id=imovel.id)
        except Exception as e:
            messages.error(request, f'Erro ao excluir documento: {str(e)}')
    
    return render(request, 'dominial/documento_confirm_delete.html', {
        'tis': tis,
        'imovel': imovel,
        'documento': documento
    })

@login_required
def documento_lancamentos(request, tis_id, imovel_id, documento_id):
    """Visualiza os lançamentos de um documento específico"""
    tis = get_object_or_404(TIs, id=tis_id)
    imovel = get_object_or_404(Imovel, id=imovel_id, terra_indigena_id=tis)
    documento = get_object_or_404(Documento, id=documento_id, imovel=imovel)
    
    # Otimização: usar select_related e prefetch_related
    lancamentos = documento.lancamentos.all()\
        .select_related('tipo', 'transmitente', 'adquirente')\
        .prefetch_related('pessoas')\
        .order_by('id')
    
    # Verificar se o usuário é admin para permitir edição
    pode_editar = request.user.is_staff or request.user.is_superuser
    
    context = {
        'tis': tis,
        'imovel': imovel,
        'documento': documento,
        'lancamentos': lancamentos,
        'pode_editar': pode_editar,
    }
    
    return render(request, 'dominial/documento_lancamentos.html', context)

@login_required
def selecionar_documento_lancamento(request, tis_id, imovel_id):
    """Página para selecionar em qual documento adicionar um novo lançamento"""
    tis = get_object_or_404(TIs, id=tis_id)
    imovel = get_object_or_404(Imovel, id=imovel_id, terra_indigena_id=tis)
    
    # Otimização: usar select_related e prefetch_related
    documentos = Documento.objects.filter(imovel=imovel)\
        .select_related('cartorio', 'tipo')\
        .prefetch_related('lancamentos')\
        .order_by('-data')
    
    context = {
        'tis': tis,
        'imovel': imovel,
        'documentos': documentos,
    }
    
    return render(request, 'dominial/selecionar_documento_lancamento.html', context)

@login_required
def criar_documento_automatico(request, tis_id, imovel_id, codigo_origem):
    """
    Cria um documento automaticamente baseado no código de origem fornecido.
    """
    tis = get_object_or_404(TIs, id=tis_id)
    imovel = get_object_or_404(Imovel, id=imovel_id, terra_indigena_id=tis)
    
    # Determinar o tipo baseado no prefixo
    if codigo_origem.upper().startswith('M'):
        tipo_documento = 'matricula'
    elif codigo_origem.upper().startswith('T'):
        tipo_documento = 'transcricao'
    else:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'error': f'Código de origem "{codigo_origem}" não é válido.'}, status=400)
        messages.error(request, f'Código de origem "{codigo_origem}" não é válido.')
        return redirect('cadeia_dominial', tis_id=tis_id, imovel_id=imovel_id)
    
    try:
        # Verificar se já existe um documento com esse número
        if Documento.objects.filter(imovel=imovel, numero=codigo_origem).exists():
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'error': f'Documento "{codigo_origem}" já existe.'}, status=400)
            messages.warning(request, f'Documento "{codigo_origem}" já existe.')
            return redirect('cadeia_dominial', tis_id=tis_id, imovel_id=imovel_id)
        
        # Obter o tipo de documento
        tipo_doc = DocumentoTipo.objects.get(tipo=tipo_documento)
        
        # Criar o documento
        documento = Documento.objects.create(
            imovel=imovel,
            tipo=tipo_doc,
            numero=codigo_origem,
            data=date.today(),
            cartorio=imovel.cartorio if imovel.cartorio else Cartorios.objects.first(),
            livro='1',  # Livro padrão
            folha='1',  # Folha padrão
            origem=f'Criado automaticamente a partir de origem: {codigo_origem}',
            observacoes=f'Documento criado automaticamente ao clicar no card de origem "{codigo_origem}"'
        )
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'message': f'Documento "{codigo_origem}" criado com sucesso!',
                'documento_id': documento.id
            })
        
        messages.success(request, f'Documento "{codigo_origem}" criado com sucesso!')
        
        # Redirecionar para o novo documento
        return redirect('documento_lancamentos', tis_id=tis_id, imovel_id=imovel_id, documento_id=documento.id)
        
    except DocumentoTipo.DoesNotExist:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'error': f'Tipo de documento "{tipo_documento}" não encontrado.'}, status=400)
        messages.error(request, f'Tipo de documento "{tipo_documento}" não encontrado.')
        return redirect('cadeia_dominial', tis_id=tis_id, imovel_id=imovel_id)
    except Exception as e:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'error': f'Erro ao criar documento: {str(e)}'}, status=500)
        messages.error(request, f'Erro ao criar documento: {str(e)}')
        return redirect('cadeia_dominial', tis_id=tis_id, imovel_id=imovel_id) 