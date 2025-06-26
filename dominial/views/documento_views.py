from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from ..models import Documento, DocumentoTipo, Imovel, TIs, Cartorios
from ..forms import ImovelForm
from datetime import date

@login_required
def novo_documento(request, tis_id, imovel_id):
    """View para criar um novo documento"""
    tis = get_object_or_404(TIs, id=tis_id)
    imovel = get_object_or_404(Imovel, id=imovel_id, terra_indigena_id=tis)
    
    if request.method == 'POST':
        try:
            # Obter dados do formulário
            tipo_id = request.POST.get('tipo')
            numero = request.POST.get('numero', '').strip()
            data_doc = request.POST.get('data') if request.POST.get('data') else None
            origem = request.POST.get('origem', '').strip()
            observacoes = request.POST.get('observacoes', '').strip()
            livro = request.POST.get('livro', '').strip()
            folha = request.POST.get('folha', '').strip()
            
            # Validação básica
            if not numero:
                messages.error(request, 'O número do documento é obrigatório.')
                return render(request, 'dominial/documento_form.html', {
                    'tis': tis,
                    'imovel': imovel,
                    'tipos_documento': DocumentoTipo.objects.all()
                })
            
            # Verificar se já existe um documento com esse número
            if Documento.objects.filter(imovel=imovel, numero=numero).exists():
                messages.error(request, f'Já existe um documento com o número "{numero}" neste imóvel.')
                return render(request, 'dominial/documento_form.html', {
                    'tis': tis,
                    'imovel': imovel,
                    'tipos_documento': DocumentoTipo.objects.all()
                })
            
            # Obter o tipo de documento
            tipo_doc = DocumentoTipo.objects.get(id=tipo_id)
            
            # Criar o documento
            documento = Documento.objects.create(
                imovel=imovel,
                tipo=tipo_doc,
                numero=numero,
                data=data_doc,
                cartorio=imovel.cartorio if imovel.cartorio else Cartorios.objects.first(),
                livro=livro,
                folha=folha,
                origem=origem,
                observacoes=observacoes
            )
            
            messages.success(request, f'Documento "{numero}" criado com sucesso!')
            return redirect('documento_lancamentos', tis_id=tis.id, imovel_id=imovel.id, documento_id=documento.id)
            
        except Exception as e:
            messages.error(request, f'Erro ao criar documento: {str(e)}')
    
    context = {
        'tis': tis,
        'imovel': imovel,
        'tipos_documento': DocumentoTipo.objects.all()
    }
    return render(request, 'dominial/documento_form.html', context)

@login_required
def documento_lancamentos(request, tis_id, imovel_id, documento_id):
    """Visualiza os lançamentos de um documento específico"""
    tis = get_object_or_404(TIs, id=tis_id)
    imovel = get_object_or_404(Imovel, id=imovel_id, terra_indigena_id=tis)
    documento = get_object_or_404(Documento, id=documento_id, imovel=imovel)
    
    # Obter lançamentos ordenados por ordem de inserção
    lancamentos = documento.lancamentos.all().order_by('id')
    
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
    
    # Obter todos os documentos do imóvel ordenados por data
    documentos = Documento.objects.filter(imovel=imovel).order_by('-data')
    
    context = {
        'tis': tis,
        'imovel': imovel,
        'documentos': documentos,
    }
    
    return render(request, 'dominial/selecionar_documento_lancamento.html', context)

@login_required
def editar_documento(request, documento_id, tis_id, imovel_id):
    """View para editar um documento existente"""
    tis = get_object_or_404(TIs, id=tis_id)
    imovel = get_object_or_404(Imovel, id=imovel_id, terra_indigena_id=tis)
    documento = get_object_or_404(Documento, id=documento_id, imovel=imovel)
    
    if request.method == 'POST':
        try:
            # Atualizar dados do documento
            documento.numero = request.POST.get('numero', '').strip()
            documento.data = request.POST.get('data') if request.POST.get('data') else None
            documento.origem = request.POST.get('origem', '').strip()
            documento.observacoes = request.POST.get('observacoes', '').strip()
            documento.livro = request.POST.get('livro', '').strip()
            documento.folha = request.POST.get('folha', '').strip()
            
            # Atualizar cartório se fornecido
            cartorio_id = request.POST.get('cartorio_id')
            if cartorio_id:
                documento.cartorio = Cartorios.objects.get(id=cartorio_id)
            else:
                documento.cartorio = None
            
            documento.save()
            
            messages.success(request, f'Documento "{documento.numero}" atualizado com sucesso!')
            return redirect('documento_lancamentos', tis_id=tis_id, imovel_id=imovel_id, documento_id=documento.id)
            
        except Exception as e:
            messages.error(request, f'Erro ao atualizar documento: {str(e)}')
    
    context = {
        'tis': tis,
        'imovel': imovel,
        'documento': documento,
        'cartorios': Cartorios.objects.all().order_by('nome')
    }
    return render(request, 'dominial/documento_form.html', context)

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