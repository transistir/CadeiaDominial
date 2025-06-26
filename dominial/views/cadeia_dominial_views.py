from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from ..models import Imovel, TIs, Documento, Lancamento, Cartorios, DocumentoTipo
from ..services import HierarquiaService
from datetime import date

@login_required
def cadeia_dominial(request, tis_id, imovel_id):
    tis = get_object_or_404(TIs, id=tis_id)
    imovel = get_object_or_404(Imovel, id=imovel_id, terra_indigena_id=tis)
    documentos = Documento.objects.filter(imovel=imovel).order_by('data')
    tem_documentos = documentos.exists()
    tem_apenas_matricula = documentos.count() == 1 and documentos.first().tipo.tipo == 'matricula' if tem_documentos else False
    tem_lancamentos = Lancamento.objects.filter(documento__imovel=imovel).exists() if tem_documentos else False
    mostrar_lancamentos = request.GET.get('lancamentos') == 'true'

    # Refatoração: delegar identificação de troncos para o service
    tronco_principal = []
    troncos_secundarios = []
    if tem_documentos:
        tronco_principal = HierarquiaService.obter_tronco_principal(imovel)
        troncos_secundarios = HierarquiaService.obter_troncos_secundarios(imovel)

    context = {
        'tis': tis,
        'imovel': imovel,
        'documentos': documentos,
        'tem_apenas_matricula': tem_apenas_matricula,
        'tem_lancamentos': tem_lancamentos,
        'mostrar_lancamentos': mostrar_lancamentos,
        'tronco_principal': tronco_principal,
        'troncos_secundarios': troncos_secundarios,
    }

    if mostrar_lancamentos:
        return render(request, 'dominial/cadeia_dominial.html', context)
    else:
        return render(request, 'dominial/cadeia_dominial_arvore.html', context)

@login_required
def cadeia_dominial_arvore(request, tis_id, imovel_id):
    """Retorna os dados da cadeia dominial em formato de árvore para o diagrama"""
    try:
        tis = get_object_or_404(TIs, id=tis_id)
        imovel = get_object_or_404(Imovel, id=imovel_id, terra_indigena_id=tis)
        # Delegar a construção da árvore para um service/utilitário
        arvore = HierarquiaService.construir_arvore_cadeia_dominial(imovel)
        return JsonResponse(arvore, safe=False)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({'error': str(e)}, status=500)

@login_required
def tronco_principal(request, tis_id, imovel_id):
    # ... (código da view tronco_principal)
    pass

@login_required
def cadeia_dominial_dados(request, tis_id, imovel_id):
    # ... (código da view cadeia_dominial_dados)
    pass 