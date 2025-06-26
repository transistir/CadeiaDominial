from django.http import JsonResponse
from ..models import Pessoas, Cartorios, Imovel
from django.db.models import Q

def pessoa_autocomplete(request):
    """View para autocomplete de pessoas"""
    query = request.GET.get('q', '').strip()
    
    if len(query) < 2:
        return JsonResponse([], safe=False)
    
    pessoas = Pessoas.objects.filter(nome__icontains=query).order_by('nome')[:10]
    
    results = []
    for pessoa in pessoas:
        results.append({
            'id': pessoa.id,
            'nome': pessoa.nome,
            'cpf': pessoa.cpf
        })
    
    return JsonResponse(results, safe=False)

def cartorio_autocomplete(request):
    """View para autocomplete de cartórios (qualquer cartório)"""
    query = request.GET.get('q', '').strip()
    
    if len(query) < 2:
        return JsonResponse([], safe=False)
    
    cartorios = Cartorios.objects.filter(nome__icontains=query).order_by('nome')[:10]
    
    results = []
    for cartorio in cartorios:
        results.append({
            'id': cartorio.id,
            'nome': cartorio.nome,
            'cidade': cartorio.cidade if cartorio.cidade else None
        })
    
    return JsonResponse(results, safe=False)

def cartorio_imoveis_autocomplete(request):
    """View para autocomplete de cartórios de imóveis (filtrados)"""
    query = request.GET.get('q', '').strip()
    
    if len(query) < 2:
        return JsonResponse([], safe=False)
    
    # Filtrar apenas cartórios que tenham palavras relacionadas a imóveis
    cartorios = Cartorios.objects.filter(
        Q(nome__icontains=query) &
        (Q(nome__icontains='imovel') | 
         Q(nome__icontains='imoveis') | 
         Q(nome__icontains='imóveis') |
         Q(nome__icontains='imobiliario') |
         Q(nome__icontains='imobiliária') |
         Q(nome__icontains='Registro de Imóveis'))
    ).order_by('nome')[:10]
    
    results = []
    for cartorio in cartorios:
        results.append({
            'id': cartorio.id,
            'nome': cartorio.nome,
            'cidade': cartorio.cidade if cartorio.cidade else None
        })
    
    return JsonResponse(results, safe=False) 