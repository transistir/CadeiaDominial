from django.http import JsonResponse
from ..models import Pessoas, Cartorios, Imovel
from django.db.models import Q

def pessoa_autocomplete(request):
    """View para autocomplete de pessoas"""
    query = request.GET.get('q', '').strip()
    
    if len(query) < 2:
        return JsonResponse([], safe=False)
    
    # Otimização: limitar resultados e usar select_related se necessário
    pessoas = Pessoas.objects.filter(nome__icontains=query)\
        .order_by('nome')\
        .values('id', 'nome', 'cpf')[:10]  # Usar values() para reduzir overhead
    
    results = []
    for pessoa in pessoas:
        results.append({
            'id': pessoa['id'],
            'nome': pessoa['nome'],
            'cpf': pessoa['cpf']
        })
    
    return JsonResponse(results, safe=False)

def cartorio_autocomplete(request):
    """View para autocomplete de cartórios"""
    query = request.GET.get('q', '').strip()
    
    if len(query) < 2:
        return JsonResponse([], safe=False)
    
    # Otimização: limitar resultados e usar select_related se necessário
    cartorios = Cartorios.objects.filter(nome__icontains=query)\
        .order_by('nome')\
        .values('id', 'nome', 'cidade', 'estado')[:10]  # Usar values() para reduzir overhead
    
    results = []
    for cartorio in cartorios:
        results.append({
            'id': cartorio['id'],
            'nome': cartorio['nome'],
            'cidade': cartorio['cidade'],
            'estado': cartorio['estado']
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

def imovel_autocomplete(request):
    """View para autocomplete de imóveis"""
    query = request.GET.get('q', '').strip()
    tis_id = request.GET.get('tis_id')
    
    if len(query) < 2:
        return JsonResponse([], safe=False)
    
    # Construir queryset base
    imoveis = Imovel.objects.all()
    
    # Filtrar por TI se especificado
    if tis_id:
        imoveis = imoveis.filter(terra_indigena_id_id=tis_id)
    
    # Buscar por matrícula ou nome
    imoveis = imoveis.filter(
        Q(matricula__icontains=query) | Q(nome__icontains=query)
    ).select_related('terra_indigena_id', 'proprietario')\
     .order_by('matricula')\
     .values('id', 'matricula', 'nome', 'terra_indigena_id__nome', 'proprietario__nome')[:10]
    
    results = []
    for imovel in imoveis:
        results.append({
            'id': imovel['id'],
            'matricula': imovel['matricula'],
            'nome': imovel['nome'],
            'terra_indigena': imovel['terra_indigena_id__nome'],
            'proprietario': imovel['proprietario__nome'] or 'Não informado'
        })
    
    return JsonResponse(results, safe=False) 