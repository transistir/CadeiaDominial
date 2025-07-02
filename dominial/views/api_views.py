from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods, require_POST
from django.http import JsonResponse
from django.core.paginator import Paginator
from django.core.management import call_command
from django.db.models import Q
from ..models import Cartorios, Pessoas, Alteracoes, Imovel, TIs, Documento, Lancamento, DocumentoTipo, LancamentoTipo
from ..services.lancamento_consulta_service import LancamentoConsultaService
from ..services.cartorio_verificacao_service import CartorioVerificacaoService
import json

@require_http_methods(["POST"])
@login_required
def buscar_cidades(request):
    estado = request.POST.get('estado', '')
    
    if not estado:
        return JsonResponse({'error': 'Estado deve ser fornecido'}, status=400)
    
    # Buscar cidades únicas que têm cartórios de imóveis
    cidades = Cartorios.objects.filter(
        estado=estado
    ).filter(
        Q(nome__icontains='imovel') | 
        Q(nome__icontains='imoveis') | 
        Q(nome__icontains='imóveis') |
        Q(nome__icontains='imobiliario') |
        Q(nome__icontains='imobiliária') |
        Q(nome__icontains='Registro de Imóveis')
    ).values_list('cidade', flat=True).distinct().order_by('cidade')
    
    cidades_list = []
    
    for cidade in cidades:
        if cidade:  # Filtrar valores vazios
            cidades_list.append({
                'value': cidade,
                'label': cidade
            })
    
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
    
    # Usar o serviço para verificar cartórios
    resultado = CartorioVerificacaoService.verificar_cartorios_estado(estado)
    
    if 'erro' in resultado:
        return JsonResponse(resultado, status=500)
    
    return JsonResponse(resultado)

@require_POST
def importar_cartorios_estado(request):
    estado = request.POST.get('estado')
    if not estado:
        return JsonResponse({'error': 'Estado não informado'}, status=400)
    
    # Usar o serviço para importar cartórios
    resultado = CartorioVerificacaoService.importar_cartorios_estado(estado)
    
    if not resultado['success']:
        return JsonResponse(resultado, status=500)
    
    return JsonResponse(resultado)

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
    filtros = {
        'tipo_documento': request.GET.get('tipo_documento'),
        'tipo_lancamento': request.GET.get('tipo_lancamento'),
        'busca': request.GET.get('busca'),
    }
    
    # Usar o service para filtrar lançamentos
    resultado = LancamentoConsultaService.filtrar_lancamentos(
        filtros=filtros,
        pagina=request.GET.get('page'),
        itens_por_pagina=10
    )
    
    # Obter tipos para os filtros
    tipos = LancamentoConsultaService.obter_tipos_para_filtros()
    
    return render(request, 'dominial/lancamentos.html', {
        'lancamentos': resultado['lancamentos'],
        'tipos_documento': tipos['tipos_documento'],
        'tipos_lancamento': tipos['tipos_lancamento'],
    }) 