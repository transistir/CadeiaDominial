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
import json

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
    CORREÇÃO: Não usar cartório da matrícula atual, mas determinar baseado no contexto
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
        
        # CORREÇÃO: Determinar cartório baseado na posição na cadeia dominial
        # Se é o primeiro documento (matrícula atual) → usar cartório do imóvel
        # Se não é o primeiro → buscar cartório de origem do lançamento do início da matrícula
        cartorio_documento = None
        
        # Verificar se é o primeiro documento da cadeia dominial (matrícula atual)
        if codigo_origem == imovel.matricula:
            # É o primeiro documento da cadeia dominial - usar cartório do imóvel
            cartorio_documento = imovel.cartorio if imovel.cartorio else Cartorios.objects.first()
        else:
            # Não é o primeiro documento - buscar cartório de origem do lançamento do início da matrícula
            from ..models import Lancamento, LancamentoTipo
            
            # Buscar o primeiro lançamento do tipo 'inicio_matricula' para obter o cartório de origem
            lancamento_inicio_matricula = Lancamento.objects.filter(
                documento__imovel=imovel,
                tipo__tipo='inicio_matricula'
            ).select_related('cartorio_origem').order_by('id').first()
            
            if lancamento_inicio_matricula and lancamento_inicio_matricula.cartorio_origem:
                # Usar o cartório de origem do primeiro lançamento do início da matrícula
                cartorio_documento = lancamento_inicio_matricula.cartorio_origem
            else:
                # Fallback: buscar em qualquer lançamento que tenha cartório de origem
                lancamento_com_origem = Lancamento.objects.filter(
                    documento__imovel=imovel,
                    cartorio_origem__isnull=False
                ).select_related('cartorio_origem').first()
                
                if lancamento_com_origem and lancamento_com_origem.cartorio_origem:
                    cartorio_documento = lancamento_com_origem.cartorio_origem
                else:
                    # Último fallback: usar cartório do imóvel ou primeiro cartório disponível
                    cartorio_documento = imovel.cartorio if imovel.cartorio else Cartorios.objects.first()
        
        # Criar o documento
        documento = Documento.objects.create(
            imovel=imovel,
            tipo=tipo_doc,
            numero=codigo_origem,
            data=date.today(),
            cartorio=cartorio_documento,
            livro='1',  # Livro padrão
            folha='1',  # Folha padrão
            origem=f'Criado automaticamente a partir de origem: {codigo_origem}',
            observacoes=f'Documento criado automaticamente ao clicar no card de origem "{codigo_origem}". Cartório determinado baseado na posição na cadeia dominial: {"primeiro documento (matrícula atual)" if codigo_origem == imovel.matricula else "documento subsequente (origem do início da matrícula)"}.'
        )
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'message': f'Documento "{codigo_origem}" criado com sucesso!',
                'documento_id': documento.id
            })
        
        messages.success(request, f'Documento "{codigo_origem}" criado com sucesso!')
        
        # Redirecionar para a visualização detalhada do novo documento
        return redirect('documento_detalhado', tis_id=tis_id, imovel_id=imovel_id, documento_id=documento.id)
        
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

@login_required
@require_POST
def ajustar_nivel_documento(request, documento_id):
    """
    Ajusta o nível manual de um documento via AJAX
    """
    try:
        documento = get_object_or_404(Documento, id=documento_id)
        
        # Verificar se o usuário tem permissão para editar este documento
        if not (request.user.is_staff or request.user.is_superuser):
            return JsonResponse({'error': 'Permissão negada'}, status=403)
        
        # Parsear dados JSON
        data = json.loads(request.body)
        nivel_manual = data.get('nivel_manual')
        
        # Validar nível
        if nivel_manual is not None:
            try:
                nivel_manual = int(nivel_manual)
                if nivel_manual < 0 or nivel_manual > 10:
                    return JsonResponse({'error': 'Nível deve estar entre 0 e 10'}, status=400)
            except (ValueError, TypeError):
                return JsonResponse({'error': 'Nível deve ser um número válido'}, status=400)
        
        # Salvar nível manual no documento
        documento.nivel_manual = nivel_manual
        documento.save()
        
        # Invalidar cache do imóvel
        CacheService.invalidate_documentos_imovel(documento.imovel.id)
        CacheService.invalidate_tronco_principal(documento.imovel.id)
        
        return JsonResponse({
            'success': True,
            'message': f'Nível do documento {documento.numero} ajustado para {nivel_manual if nivel_manual is not None else "automático"}'
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Dados JSON inválidos'}, status=400)
    except Exception as e:
        return JsonResponse({'error': f'Erro interno: {str(e)}'}, status=500) 