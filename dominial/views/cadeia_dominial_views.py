from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from ..models import Imovel, TIs, Documento, Lancamento, Cartorios, DocumentoTipo
from ..services import HierarquiaService
from ..services.cache_service import CacheService
from ..services.cadeia_dominial_tabela_service import CadeiaDominialTabelaService
from datetime import date
import json

@login_required
def cadeia_dominial(request, tis_id, imovel_id):
    # Otimização: usar select_related para reduzir queries
    tis = get_object_or_404(TIs, id=tis_id)
    imovel = get_object_or_404(Imovel, id=imovel_id, terra_indigena_id=tis)
    
    # Otimização: usar select_related e prefetch_related
    documentos = Documento.objects.filter(imovel=imovel)\
        .select_related('cartorio', 'tipo')\
        .prefetch_related('lancamentos', 'lancamentos__tipo')\
        .order_by('data')
    
    tem_documentos = documentos.exists()
    tem_apenas_matricula = documentos.count() == 1 and documentos.first().tipo.tipo == 'matricula' if tem_documentos else False
    
    # Otimização: usar exists() em vez de count() para verificar lançamentos
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
    """Exibe o tronco principal da cadeia dominial em formato de tabela"""
    tis = get_object_or_404(TIs, id=tis_id)
    imovel = get_object_or_404(Imovel, id=imovel_id, terra_indigena_id=tis)
    
    # Obter escolhas de origem da URL (se houver)
    escolhas_origem = {}
    escolhas_param = request.GET.get('escolhas')
    if escolhas_param:
        try:
            escolhas_origem = json.loads(escolhas_param)
        except json.JSONDecodeError:
            escolhas_origem = {}
    
    # Obter cadeia em formato de tabela
    cadeia = CadeiaDominialTabelaService.obter_cadeia_tabela(imovel, escolhas_origem)
    
    # Verificar se há lançamentos
    tem_lancamentos = False
    if cadeia:
        tem_lancamentos = any(len(item['lancamentos']) > 0 for item in cadeia)
    
    context = {
        'tis': tis,
        'imovel': imovel,
        'cadeia': cadeia,
        'tem_lancamentos': tem_lancamentos,
        'tipo_visualizacao': 'tabela',
    }
    
    return render(request, 'dominial/cadeia_dominial_tabela.html', context)

@login_required
def cadeia_dominial_dados(request, tis_id, imovel_id):
    """Retorna os dados da cadeia dominial em formato JSON para o diagrama de árvore"""
    tis = get_object_or_404(TIs, id=tis_id)
    imovel = get_object_or_404(Imovel, id=imovel_id, terra_indigena_id=tis)
    
    # Otimização: usar select_related e prefetch_related
    documentos = Documento.objects.filter(imovel=imovel)\
        .select_related('cartorio', 'tipo')\
        .prefetch_related('lancamentos', 'lancamentos__tipo')\
        .order_by('data')
    
    # Estrutura para o diagrama de árvore
    tree_data = {
        'name': f'Imóvel: {imovel.matricula}',
        'children': []
    }
    
    for documento in documentos:
        doc_node = {
            'name': f'{documento.tipo.get_tipo_display()}: {documento.numero}',
            'data': {
                'tipo': 'documento',
                'id': documento.id,
                'numero': documento.numero,
                'data': documento.data.strftime('%d/%m/%Y'),
                'cartorio': documento.cartorio.nome,
                'livro': documento.livro,
                'folha': documento.folha,
                'origem': documento.origem or ''
            },
            'children': []
        }
        
        # Adicionar lançamentos como filhos do documento
        # Otimização: usar a lista já pré-carregada
        lancamentos = list(documento.lancamentos.all())
        lancamentos.sort(key=lambda x: x.id)  # Ordenar por ID
        
        for lancamento in lancamentos:
            lanc_node = {
                'name': f'{lancamento.tipo.get_tipo_display()}: {lancamento.data.strftime("%d/%m/%Y")}',
                'data': {
                    'tipo': 'lancamento',
                    'id': lancamento.id,
                    'tipo_lancamento': lancamento.tipo.tipo,
                    'data': lancamento.data.strftime('%d/%m/%Y'),
                    'eh_inicio_matricula': lancamento.eh_inicio_matricula,
                    'forma': lancamento.forma or '',
                    'descricao': lancamento.descricao or '',
                    'titulo': lancamento.titulo or '',
                    'observacoes': lancamento.observacoes or ''
                }
            }
            doc_node['children'].append(lanc_node)
        
        tree_data['children'].append(doc_node)
    
    return JsonResponse(tree_data, safe=False)

@login_required
def cadeia_dominial_tabela(request, tis_id, imovel_id):
    """
    Exibe a cadeia dominial em formato de tabela com lançamentos expandíveis
    """
    tis = get_object_or_404(TIs, id=tis_id)
    imovel = get_object_or_404(Imovel, id=imovel_id, terra_indigena_id=tis)
    
    # Obter escolhas de origem da URL (se houver)
    escolhas_origem = {}
    escolhas_param = request.GET.get('escolhas')
    if escolhas_param:
        try:
            escolhas_origem = json.loads(escolhas_param)
        except json.JSONDecodeError:
            escolhas_origem = {}
    
    # Obter cadeia em formato de tabela
    cadeia = CadeiaDominialTabelaService.obter_cadeia_tabela(imovel, escolhas_origem)
    
    # Verificar se há lançamentos
    tem_lancamentos = False
    if cadeia:
        tem_lancamentos = any(len(item['lancamentos']) > 0 for item in cadeia)
    
    context = {
        'tis': tis,
        'imovel': imovel,
        'cadeia': cadeia,
        'tem_lancamentos': tem_lancamentos,
        'tipo_visualizacao': 'tabela',
    }
    
    return render(request, 'dominial/cadeia_dominial_tabela.html', context) 