from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods, require_POST
from django.http import JsonResponse
from django.core.paginator import Paginator
from django.core.management import call_command
from django.db.models import Q
from ..models import Cartorios, Pessoas, Alteracoes, Imovel, TIs, Documento, Lancamento, DocumentoTipo, LancamentoTipo
import json

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
    
    # Filtrar apenas cartórios de imóveis (que tenham palavras relacionadas a imóveis)
    cartorios = Cartorios.objects.filter(
        estado=estado, 
        cidade=cidade
    ).filter(
        Q(nome__icontains='imovel') | 
        Q(nome__icontains='imoveis') | 
        Q(nome__icontains='imóveis') |
        Q(nome__icontains='imobiliario') |
        Q(nome__icontains='imobiliária') |
        Q(nome__icontains='Registro de Imóveis')
    ).order_by('nome')
    
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

@require_POST
def criar_cartorio(request):
    """View para criar um novo cartório via AJAX"""
    try:
        data = json.loads(request.body)
        
        # Validar campos obrigatórios
        nome = data.get('nome', '').strip()
        cns = data.get('cns', '').strip()
        estado = data.get('estado', '').strip()
        cidade = data.get('cidade', '').strip()
        
        if not nome or not cns or not estado or not cidade:
            return JsonResponse({
                'success': False,
                'error': 'Nome, CNS, Estado e Cidade são obrigatórios.'
            }, status=400)
        
        # Verificar se já existe um cartório com este CNS
        if Cartorios.objects.filter(cns=cns).exists():
            return JsonResponse({
                'success': False,
                'error': 'Já existe um cartório com este CNS.'
            }, status=400)
        
        # Criar o cartório
        cartorio = Cartorios.objects.create(
            nome=nome,
            cns=cns,
            endereco=data.get('endereco', '').strip(),
            telefone=data.get('telefone', '').strip(),
            email=data.get('email', '').strip(),
            estado=estado,
            cidade=cidade
        )
        
        # Retornar dados do cartório criado
        return JsonResponse({
            'success': True,
            'message': 'Cartório criado com sucesso!',
            'cartorio': {
                'id': cartorio.id,
                'nome': cartorio.nome,
                'cns': cartorio.cns,
                'endereco': cartorio.endereco,
                'telefone': cartorio.telefone,
                'email': cartorio.email,
                'estado': cartorio.estado,
                'cidade': cartorio.cidade
            }
        })
        
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Dados inválidos.'
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Erro ao criar cartório: {str(e)}'
        }, status=500)

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
    documentos = Documento.objects.all().order_by('-data')
    return render(request, 'dominial/alteracoes.html', {'documentos': documentos})

@login_required
def lancamentos(request):
    # Obter parâmetros de filtro
    tipo_documento = request.GET.get('tipo_documento')
    tipo_lancamento = request.GET.get('tipo_lancamento')
    busca = request.GET.get('busca')

    # Iniciar queryset
    lancamentos = Lancamento.objects.all()

    # Aplicar filtros
    if tipo_documento:
        lancamentos = lancamentos.filter(documento__tipo_id=tipo_documento)
    if tipo_lancamento:
        lancamentos = lancamentos.filter(tipo_id=tipo_lancamento)
    if busca:
        lancamentos = lancamentos.filter(documento__numero__icontains=busca)

    # Ordenar por ordem de inserção (ID crescente)
    lancamentos = lancamentos.order_by('id')

    # Paginação
    paginator = Paginator(lancamentos, 10)  # 10 itens por página
    page = request.GET.get('page')
    lancamentos = paginator.get_page(page)

    # Obter tipos para os filtros
    tipos_documento = DocumentoTipo.objects.all()
    tipos_lancamento = LancamentoTipo.objects.all()

    return render(request, 'dominial/lancamentos.html', {
        'lancamentos': lancamentos,
        'tipos_documento': tipos_documento,
        'tipos_lancamento': tipos_lancamento,
    }) 