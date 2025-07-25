from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from ..models import TIs, TerraIndigenaReferencia, Imovel
from ..forms import TIsForm, ImovelForm
from django.db.models import Q

@login_required
def home(request):
    busca = request.GET.get('busca', '').strip()
    tis_cadastradas = TIs.objects.all()
    terras_referencia = TerraIndigenaReferencia.objects.all()
    if busca:
        tis_cadastradas = tis_cadastradas.filter(
            Q(nome__icontains=busca) | Q(etnia__icontains=busca) | Q(codigo__icontains=busca)
        )
        terras_referencia = terras_referencia.filter(
            Q(nome__icontains=busca) | Q(etnia__icontains=busca) | Q(codigo__icontains=busca)
        )
    tis_com_imoveis = {tis.id: Imovel.objects.filter(terra_indigena_id=tis).count() for tis in tis_cadastradas}
    tis_ordenadas = sorted(
        tis_cadastradas,
        key=lambda x: (tis_com_imoveis.get(x.id, 0), x.nome),
        reverse=True
    )
    terras_referencia = terras_referencia.order_by('nome')
    codigos_tis_cadastradas = set(tis.codigo for tis in tis_cadastradas)
    terras_referencia_nao_cadastradas = [tr for tr in terras_referencia if tr.codigo not in codigos_tis_cadastradas]
    return render(request, 'dominial/home.html', {
        'terras_indigenas': tis_ordenadas,
        'terras_referencia': terras_referencia_nao_cadastradas,
        'busca': busca,
        'total_tis_cadastradas': tis_cadastradas.count(),
        'total_terras_referencia': len(terras_referencia_nao_cadastradas),
        'tis_com_imoveis': tis_com_imoveis,
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
            Imovel.objects.filter(terra_indigena_id=tis).delete()
            nome = tis.nome
            tis.delete()
            messages.success(request, f'Terra Indígena "{nome}" excluída com sucesso!')
            return redirect('home')
        except Exception as e:
            messages.error(request, f'Erro ao excluir Terra Indígena: {str(e)}')
    return render(request, 'dominial/tis_confirm_delete.html', {'tis': tis})

@login_required
def imoveis(request, tis_id=None):
    if tis_id:
        tis = get_object_or_404(TIs, id=tis_id)
        imoveis = Imovel.objects.filter(terra_indigena_id=tis).order_by('matricula')
    else:
        imoveis = Imovel.objects.all().order_by('matricula')
    return render(request, 'dominial/imoveis.html', {'imoveis': imoveis})

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