from django.http import JsonResponse
from ..models import Pessoas, Cartorios, Imovel
from django.db.models import Q
from django.db import models
from ..utils.cartorio_utils import q_nome_cri


def _q_busca_insensivel(query):
    """
    Busca icontains insensível a acento: gera variantes com e sem acento
    para cada caractere acentado no query e faz OR. Também usa regex para
    casar acentos no banco (SQLite icontains é ASCII-only).
    """
    import unicodedata
    # Strip accents from query
    nfkd = unicodedata.normalize('NFKD', query)
    query_sem_acento = ''.join(
        c for c in nfkd if not unicodedata.combining(c)
    )
    q = Q(nome__icontains=query)
    if query_sem_acento != query:
        q |= Q(nome__icontains=query_sem_acento)
    
    # Regex pattern: cada vogal vira uma classe de caracteres com todas as variantes acentuadas
    # Isso cobre o caso onde o query não tem acento mas o banco tem (ex: "Imoveis" -> "Imóveis")
    vowel_variants = {
        'a': '[aáàâãäåAÁÀÂÃÄÅ]',
        'e': '[eéèêëEÉÈÊË]',
        'i': '[iíìîïIÍÌÎÏ]',
        'o': '[oóòôõöOÓÒÔÕÖ]',
        'u': '[uúùûüUÚÙÛÜ]',
    }
    # Escape special regex chars (exceto vogais que já tratamos)
    import re as _re
    pattern = ''
    for c in query_sem_acento:
        lower_c = c.lower()
        if lower_c in vowel_variants:
            pattern += vowel_variants[lower_c]
        else:
            pattern += _re.escape(c)
    
    # Adicionar busca por regex (case-insensitive)
    q |= Q(nome__iregex=pattern)
    return q


def pessoa_autocomplete(request):
    """View para autocomplete de pessoas"""
    query = request.GET.get('q', '').strip()
    
    if len(query) < 2:
        return JsonResponse({'results': []})
    
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
    
    return JsonResponse({'results': results})

def cartorio_autocomplete(request):
    """
    View para autocomplete de cartórios.

    Parâmetros GET:
    - q: termo de busca (mínimo 2 caracteres)
    - imovel_id: ID do imóvel (para sugestões de cartórios mais usados)
    - sugestoes: se 'true', retorna cartórios mais usados como origem
    - somente_cri: se 'true', filtra apenas CRI (Cartórios de Registro de Imóveis)
                   usando o helper q_nome_cri(). Usado pelos campos de origem
                   para evitar listar tabelionatos (issue #227).
    """
    query = request.GET.get('q', '').strip()
    imovel_id = request.GET.get('imovel_id')
    sugestoes = request.GET.get('sugestoes') == 'true'
    somente_cri = request.GET.get('somente_cri') == 'true'
    
    # Se for para mostrar sugestões (sem query) e há imovel_id
    if sugestoes and not query and imovel_id:
        try:
            from ..models import Imovel, Lancamento
            imovel = Imovel.objects.get(id=imovel_id)
            
            # Buscar cartórios mais usados nos lançamentos deste imóvel
            cartorios_origem = Lancamento.objects.filter(
                documento__imovel=imovel,
                cartorio_origem__isnull=False
            ).values('cartorio_origem__id', 'cartorio_origem__nome', 'cartorio_origem__cidade', 'cartorio_origem__estado').annotate(
                count=models.Count('id')
            ).order_by('-count')[:5]
            
            results = []
            for cartorio in cartorios_origem:
                results.append({
                    'id': cartorio['cartorio_origem__id'],
                    'nome': cartorio['cartorio_origem__nome'],
                    'cidade': cartorio['cartorio_origem__cidade'],
                    'estado': cartorio['cartorio_origem__estado']
                })
            
            return JsonResponse({'results': results})
        except Imovel.DoesNotExist:
            pass
    
    # Busca normal por query
    if len(query) < 2:
        return JsonResponse({'results': []})
    
    # Filtro base: nome insensível a acento
    qs = Cartorios.objects.filter(_q_busca_insensivel(query))
    
    # Se somente_cri, aplicar filtro CRI (issue #227)
    if somente_cri:
        qs = qs.filter(q_nome_cri())
    
    cartorios = qs.order_by('nome', 'id')\
        .values('id', 'nome', 'cidade', 'estado')[:10]
    
    results = []
    for cartorio in cartorios:
        results.append({
            'id': cartorio['id'],
            'nome': cartorio['nome'],
            'cidade': cartorio['cidade'],
            'estado': cartorio['estado']
        })
    
    return JsonResponse({'results': results})

def cartorio_imoveis_autocomplete(request):
    """
    View para autocomplete de cartórios de imóveis (filtrados por CRI).
    Usa o mesmo helper q_nome_cri() que cartorio_autocomplete com somente_cri=true
    para garantir o mesmo conjunto e ordem (issue #227).
    """
    query = request.GET.get('q', '').strip()
    
    if len(query) < 2:
        return JsonResponse([], safe=False)
    
    # Filtrar apenas cartórios CRI usando o helper compartilhado
    cartorios = Cartorios.objects.filter(
        _q_busca_insensivel(query) & q_nome_cri()
    ).order_by('nome', 'id')[:10]
    
    results = []
    for cartorio in cartorios:
        results.append({
            'id': cartorio.id,
            'nome': cartorio.nome,
            'cidade': cartorio.cidade if cartorio.cidade else None,
            'estado': cartorio.estado if cartorio.estado else None
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
