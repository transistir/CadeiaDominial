from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from .models import TIs, Imovel, TerraIndigenaReferencia
from django.contrib import messages
from .models import Imovel, TIs, Cartorios, Pessoas, Alteracoes
from .forms import TIsForm, ImovelForm
import logging
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods, require_POST
import requests
import json
from django.core.paginator import Paginator
from django.urls import reverse
from django.db.models import Count
from django.utils import timezone
from django.core.management import call_command
from dal import autocomplete

logger = logging.getLogger(__name__)

# Create your views here.

@login_required
def home(request):
    terras_indigenas = TIs.objects.all().order_by('nome')
    terras_referencia = TerraIndigenaReferencia.objects.all().order_by('nome')
    return render(request, 'dominial/home.html', {
        'terras_indigenas': terras_indigenas,
        'terras_referencia': terras_referencia
    })

@login_required
def tis_form(request):
    if request.method == 'POST':
        form = TIsForm(request.POST)
        if form.is_valid():
            try:
                form.save()
                messages.success(request, 'Terra Indígena cadastrada com sucesso!')
                return redirect('home')
            except Exception as e:
                messages.error(request, f'Erro ao cadastrar Terra Indígena: {str(e)}')
    else:
        form = TIsForm()
    
    return render(request, 'dominial/tis_form.html', {'form': form})

@login_required
def tis_detail(request, tis_id):
    tis = get_object_or_404(TIs, id=tis_id)
    imoveis = Imovel.objects.filter(terra_indigena_id=tis)
    return render(request, 'dominial/tis_detail.html', {
        'tis': tis,
        'imoveis': imoveis
    })

@login_required
def tis_delete(request, tis_id):
    if not request.user.is_staff:
        messages.error(request, 'Você não tem permissão para excluir terras indígenas.')
        return redirect('home')
        
    tis = get_object_or_404(TIs, id=tis_id)
    
    if request.method == 'POST':
        try:
            # Primeiro, excluir todos os imóveis associados
            Imovel.objects.filter(terra_indigena_id=tis).delete()
            
            # Depois, excluir a TI
            nome = tis.nome
            tis.delete()
            
            messages.success(request, f'Terra Indígena "{nome}" excluída com sucesso!')
            return redirect('home')
        except Exception as e:
            logger.error(f'Erro ao excluir Terra Indígena: {str(e)}')
            messages.error(request, f'Erro ao excluir Terra Indígena: {str(e)}')
    
    return render(request, 'dominial/tis_confirm_delete.html', {
        'tis': tis
    })

@login_required
def imovel_form(request, tis_id, imovel_id=None):
    tis = get_object_or_404(TIs, pk=tis_id)
    imovel = None
    
    if imovel_id:
        imovel = get_object_or_404(Imovel, pk=imovel_id)
        
    if request.method == 'POST':
        form = ImovelForm(request.POST, instance=imovel)
        
        # Obter o ID do cartório do POST
        cartorio_id = request.POST.get('cartorio_id')
        if cartorio_id:
            try:
                cartorio = Cartorios.objects.get(pk=cartorio_id)
                form.instance.cartorio = cartorio
            except Cartorios.DoesNotExist:
                pass
        
        if form.is_valid():
            imovel = form.save(commit=False)
            imovel.terra_indigena_id = tis

            proprietario_id = form.cleaned_data.get('proprietario')
            nome = form.cleaned_data.get('proprietario_nome')

            if proprietario_id:
                try:
                    imovel.proprietario = Pessoas.objects.get(id=proprietario_id)
                except Pessoas.DoesNotExist:
                    messages.error(request, 'O proprietário selecionado não foi encontrado.')
                    return render(request, 'dominial/imovel_form.html', {'form': form, 'tis': tis, 'imovel': imovel})
            else:
                # Criar novo proprietário
                cpf = request.POST.get('cpf')
                rg = request.POST.get('rg')
                data_nascimento = request.POST.get('data_nascimento')
                email = request.POST.get('email')
                telefone = request.POST.get('telefone')

                if nome and cpf:
                    nova_pessoa = Pessoas.objects.create(
                        nome=nome,
                        cpf=cpf,
                        rg=rg,
                        email=email,
                        telefone=telefone,
                        data_nascimento=data_nascimento if data_nascimento else None
                    )
                    imovel.proprietario = nova_pessoa
                else:
                    messages.error(request, "Para cadastrar novo proprietário, preencha pelo menos Nome e CPF.")
                    return render(request, 'dominial/imovel_form.html', {'form': form, 'tis': tis, 'imovel': imovel})

            imovel.save()
            messages.success(request, 'Imóvel cadastrado com sucesso!')
            return redirect('tis_detail', tis_id=tis_id)
        else:
            print("Erros de formulário:", form.errors)

    else:
        form = ImovelForm(instance=imovel)

    return render(request, 'dominial/imovel_form.html', {'form': form, 'tis': tis, 'imovel': imovel})

@login_required
def imovel_detail(request, tis_id, imovel_id):
    tis = get_object_or_404(TIs, id=tis_id)
    imovel = get_object_or_404(Imovel, id=imovel_id, terra_indigena_id=tis)
    
    if request.method == 'POST':
        form = ImovelForm(request.POST, instance=imovel)
        if form.is_valid():
            try:
                form.save()
                messages.success(request, 'Imóvel atualizado com sucesso!')
                return redirect('tis_detail', tis_id=tis.id)
            except Exception as e:
                messages.error(request, f'Erro ao atualizar imóvel: {str(e)}')
    else:
        form = ImovelForm(instance=imovel)
    
    return render(request, 'dominial/imovel_form.html', {
        'form': form,
        'tis': tis,
        'imovel': imovel
    })

@login_required
def imovel_delete(request, tis_id, imovel_id):
    tis = get_object_or_404(TIs, id=tis_id)
    imovel = get_object_or_404(Imovel, id=imovel_id, terra_indigena_id=tis)
    
    if request.method == 'POST':
        try:
            matricula = imovel.matricula
            imovel.delete()
            messages.success(request, f'Imóvel "{matricula}" excluído com sucesso!')
            return redirect('tis_detail', tis_id=tis.id)
        except Exception as e:
            messages.error(request, f'Erro ao excluir imóvel: {str(e)}')
    
    return render(request, 'dominial/imovel_confirm_delete.html', {
        'imovel': imovel,
        'tis': tis
    })

@login_required
def imoveis(request, tis_id=None):
    if tis_id:
        tis = get_object_or_404(TIs, id=tis_id)
        imoveis = Imovel.objects.filter(terra_indigena_id=tis).order_by('matricula')
    else:
        imoveis = Imovel.objects.all().order_by('matricula')
    return render(request, 'dominial/imoveis.html', {'imoveis': imoveis})

@login_required
def cartorios(request):
    cartorios = Cartorios.objects.all().order_by('nome')
    return render(request, 'dominial/cartorios.html', {'cartorios': cartorios})

@login_required
def pessoas(request):
    pessoas = Pessoas.objects.all().order_by('nome')
    return render(request, 'dominial/pessoas.html', {'pessoas': pessoas})

@login_required
def alteracoes(request):
    alteracoes = Alteracoes.objects.all().order_by('-data')
    return render(request, 'dominial/alteracoes.html', {'alteracoes': alteracoes})

@require_http_methods(["POST"])
@login_required
def buscar_cidades(request):
    estado = request.POST.get('estado', '')
    if not estado:
        return JsonResponse({'error': 'Estado não fornecido'}, status=400)
    
    cidades = Cartorios.objects.filter(estado=estado).values_list('cidade', flat=True).distinct().order_by('cidade')
    cidades_list = [{'value': cidade, 'label': cidade} for cidade in cidades]
    
    return JsonResponse(cidades_list, safe=False)

@require_http_methods(["POST"])
@login_required
def buscar_cartorios(request):
    estado = request.POST.get('estado', '')
    cidade = request.POST.get('cidade', '')
    
    if not estado or not cidade:
        return JsonResponse({'error': 'Estado e cidade devem ser fornecidos'}, status=400)
    
    cartorios = Cartorios.objects.filter(estado=estado, cidade=cidade).order_by('nome')
    cartorios_list = []
    
    for cartorio in cartorios:
        cartorios_list.append({
            'id': cartorio.id,
            'nome': cartorio.nome,
            'cns': cartorio.cns,
            'endereco': cartorio.endereco,
            'telefone': cartorio.telefone,
            'email': cartorio.email
        })
    
    return JsonResponse(cartorios_list, safe=False)

@require_POST
def verificar_cartorios_estado(request):
    estado = request.POST.get('estado')
    if not estado:
        return JsonResponse({'error': 'Estado não informado'}, status=400)
    
    # Verifica se existem cartórios para o estado
    cartorios_count = Cartorios.objects.filter(estado=estado).count()
    
    return JsonResponse({
        'existem_cartorios': cartorios_count > 0,
        'total_cartorios': cartorios_count
    })

@require_POST
def importar_cartorios_estado(request):
    estado = request.POST.get('estado')
    if not estado:
        return JsonResponse({'error': 'Estado não informado'}, status=400)
    
    try:
        # Executa o comando de importação
        call_command('importar_cartorios_estado', estado)
        
        # Conta quantos cartórios foram importados
        cartorios_count = Cartorios.objects.filter(estado=estado).count()
        
        return JsonResponse({
            'success': True,
            'message': f'Cartórios do estado {estado} importados com sucesso!',
            'total_cartorios': cartorios_count
        })
    except Exception as e:
        return JsonResponse({
            'error': f'Erro ao importar cartórios: {str(e)}'
        }, status=500)


def pessoa_autocomplete(request):
    term = request.GET.get('term', '')
    pessoas = Pessoas.objects.filter(nome__icontains=term)[:10]
    results = [{'id': p.id, 'label': p.nome, 'value': p.nome} for p in pessoas]
    return JsonResponse(results, safe=False)