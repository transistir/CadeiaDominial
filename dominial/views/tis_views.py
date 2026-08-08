from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from ..models import TIs, TerraIndigenaReferencia, Imovel
from ..forms import TIsForm, ImovelForm
from django.db.models import F, Max, Q
from django.db.models.functions import Coalesce
from django.http import Http404
from ..managers import tis_for_user, usuario_ve_tudo
from ..utils.segregacao_utils import MENSAGEM_SEM_IMOVEIS

@login_required
def home(request):
    busca = request.GET.get('busca', '').strip()
    tis_cadastradas = tis_for_user(request.user)
    terras_referencia = TerraIndigenaReferencia.objects.all()
    if busca:
        tis_cadastradas = tis_cadastradas.filter(
            Q(nome__icontains=busca) | Q(etnia__icontains=busca) | Q(codigo__icontains=busca)
        )
        terras_referencia = terras_referencia.filter(
            Q(nome__icontains=busca) | Q(etnia__icontains=busca) | Q(codigo__icontains=busca)
        )
    tis_com_imoveis = {
        tis.id: Imovel.objects.for_user(request.user).filter(terra_indigena_id=tis).count()
        for tis in tis_cadastradas
    }
    tis_ordenadas = sorted(
        tis_cadastradas,
        key=lambda x: (tis_com_imoveis.get(x.id, 0), x.nome),
        reverse=True
    )
    terras_referencia = terras_referencia.order_by('nome')
    codigos_tis_cadastradas = set(tis.codigo for tis in tis_cadastradas)
    terras_referencia_nao_cadastradas = [tr for tr in terras_referencia if tr.codigo not in codigos_tis_cadastradas]
    if not usuario_ve_tudo(request.user) and not Imovel.objects.for_user(request.user).exists():
        messages.info(request, MENSAGEM_SEM_IMOVEIS)
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
    
    # Obter status dos imóveis (ativos ou arquivados)
    status = request.GET.get('status', 'ativos')
    is_arquivado = status == 'arquivados'
    
    # Ordenar imóveis pela atividade mais recente na cadeia dominial:
    # documento mais recente, senão lançamento mais recente, senão o
    # próprio cadastro do imóvel; matrícula como desempate.
    imoveis_ordenados = (
        Imovel.objects.for_user(request.user)
        .filter(terra_indigena_id=tis, arquivado=is_arquivado)
        .annotate(
            ultimo_documento=Max('documentos__data_cadastro'),
            ultimo_lancamento=Max('documentos__lancamentos__data_cadastro'),
            atividade=Coalesce(
                Max('documentos__data_cadastro'),
                Max('documentos__lancamentos__data_cadastro'),
                F('data_cadastro'),
            ),
        )
        .order_by('-atividade', 'matricula')
    )

    return render(request, 'dominial/tis_detail.html', {
        'tis': tis,
        'imoveis': imoveis_ordenados,
        'status': status
    })

@login_required
def tis_delete(request, tis_id):
    tis = get_object_or_404(tis_for_user(request.user), id=tis_id)
    if not request.user.is_superuser:
        # Exclusão em cascata de uma TI é uma operação exclusiva de superuser.
        # Responder 404 mantém o padrão de não revelar objetos fora do escopo.
        raise Http404
    if request.method == 'POST':
        try:
            Imovel.objects.for_user(request.user).filter(
                terra_indigena_id=tis
            ).delete()
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
        imoveis = Imovel.objects.for_user(request.user).filter(terra_indigena_id=tis).order_by('matricula')
    else:
        imoveis = Imovel.objects.for_user(request.user).order_by('matricula')
    return render(request, 'dominial/imoveis.html', {'imoveis': imoveis})

@login_required
def imovel_detail(request, tis_id, imovel_id):
    tis = get_object_or_404(TIs, id=tis_id)
    imovel = get_object_or_404(Imovel.objects.for_user(request.user), id=imovel_id, terra_indigena_id=tis)
    
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
    imovel = get_object_or_404(Imovel.objects.for_user(request.user), id=imovel_id, terra_indigena_id=tis)
    
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
def arquivar_imovel(request, tis_id, imovel_id):
    """View para arquivar ou desarquivar um imóvel"""
    tis = get_object_or_404(TIs, id=tis_id)
    imovel = get_object_or_404(Imovel.objects.for_user(request.user), id=imovel_id, terra_indigena_id=tis)
    
    try:
        # Alternar status de arquivado
        imovel.arquivado = not imovel.arquivado
        imovel.save()
        
        if imovel.arquivado:
            messages.success(request, f'Imóvel "{imovel.nome}" arquivado com sucesso!')
            # Redirecionar para lista de ativos
            return redirect('tis_detail', tis_id=tis.id)
        else:
            messages.success(request, f'Imóvel "{imovel.nome}" desarquivado com sucesso!')
            # Redirecionar para lista de arquivados (onde estava antes)
            return redirect(f'/dominial/tis/{tis.id}/?status=arquivados')
    except Exception as e:
        messages.error(request, f'Erro ao alterar status do imóvel: {str(e)}')
        return redirect('tis_detail', tis_id=tis.id)
