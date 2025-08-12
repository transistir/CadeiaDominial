from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
from ..models import Imovel, TIs, Documento, Lancamento, Cartorios, DocumentoTipo
from ..services import HierarquiaService
from ..services.cache_service import CacheService
from ..services.cadeia_dominial_tabela_service import CadeiaDominialTabelaService
from datetime import date
import json
from weasyprint import HTML
from django.template.loader import render_to_string
from django.conf import settings
import os

@login_required
def cadeia_dominial(request, tis_id, imovel_id):
    # Otimização: usar select_related para reduzir queries
    tis = get_object_or_404(TIs, id=tis_id)
    imovel = get_object_or_404(Imovel, id=imovel_id, terra_indigena_id=tis)
    
    # Obter documentos seguindo a hierarquia correta (tronco principal)
    tronco_principal = HierarquiaService.obter_tronco_principal(imovel)
    documentos = list(tronco_principal)  # Usar a ordem do tronco principal
    
    tem_documentos = len(documentos) > 0
    tem_apenas_matricula = len(documentos) == 1 and documentos[0].tipo.tipo == 'matricula' if tem_documentos else False
    
    # Otimização: usar exists() em vez de count() para verificar lançamentos
    tem_lancamentos = Lancamento.objects.filter(documento__imovel=imovel).exists() if tem_documentos else False
    mostrar_lancamentos = request.GET.get('lancamentos') == 'true'

    # Refatoração: delegar identificação de troncos para o service
    troncos_secundarios = []
    if tem_documentos:
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
    
    # Obter documentos seguindo a hierarquia correta (tronco principal)
    tronco_principal = HierarquiaService.obter_tronco_principal(imovel)
    documentos = list(tronco_principal)  # Usar a ordem do tronco principal
    
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
    View para visualização de tabela da cadeia dominial
    """
    # NOVO: processar escolha de origem
    origem_escolhida = request.GET.get('origem')
    documento_id = request.GET.get('documento_id')
    if origem_escolhida and documento_id:
        request.session[f'origem_documento_{documento_id}'] = origem_escolhida

    service = CadeiaDominialTabelaService()
    context = service.get_cadeia_dominial_tabela(tis_id, imovel_id, request.session)

    # Adicionar estatísticas
    if context['cadeia']:
        context['estatisticas'] = service.get_estatisticas_cadeia(context['cadeia'])

    return render(request, 'dominial/cadeia_dominial_tabela.html', context)

@login_required
def cadeia_dominial_d3(request, tis_id, imovel_id):
    """Nova visualização D3.js da árvore da cadeia dominial"""
    tis = get_object_or_404(TIs, id=tis_id)
    imovel = get_object_or_404(Imovel, id=imovel_id, terra_indigena_id=tis)
    documentos = Documento.objects.filter(imovel=imovel)\
        .select_related('cartorio', 'tipo')\
        .prefetch_related('lancamentos', 'lancamentos__tipo')\
        .order_by('data')
    tem_documentos = documentos.exists()
    tem_apenas_matricula = documentos.count() == 1 and documentos.first().tipo.tipo == 'matricula' if tem_documentos else False
    tem_lancamentos = Lancamento.objects.filter(documento__imovel=imovel).exists() if tem_documentos else False
    context = {
        'tis': tis,
        'imovel': imovel,
        'documentos': documentos,
        'tem_apenas_matricula': tem_apenas_matricula,
        'tem_lancamentos': tem_lancamentos,
    }
    return render(request, 'dominial/cadeia_dominial_d3.html', context) 

@login_required
def documento_detalhado(request, tis_id, imovel_id, documento_id):
    """
    View para visualização detalhada de um documento específico
    Baseada na cadeia dominial tabela, mas mostra apenas um documento
    Suporta documentos importados de outras cadeias dominiais
    """
    tis = get_object_or_404(TIs, id=tis_id)
    imovel = get_object_or_404(Imovel, id=imovel_id, terra_indigena_id=tis)
    
    # Buscar o documento - pode estar em outro imóvel se for importado
    documento = None
    is_importado = False
    cadeias_dominiais = []
    
    # Primeiro, tentar encontrar no imóvel atual
    try:
        documento = Documento.objects.get(id=documento_id, imovel=imovel)
    except Documento.DoesNotExist:
        # Se não encontrou no imóvel atual, pode ser um documento importado
        try:
            documento = Documento.objects.get(id=documento_id)
            is_importado = True
            
            # Buscar informações de importação
            from ..models import DocumentoImportado
            importacoes = DocumentoImportado.objects.filter(documento=documento)
            for importacao in importacoes:
                cadeias_dominiais.append({
                    'imovel_id': importacao.imovel_origem.id,
                    'imovel_matricula': importacao.imovel_origem.matricula,
                    'imovel_nome': importacao.imovel_origem.nome,
                    'data_importacao': importacao.data_importacao.strftime('%d/%m/%Y'),
                    'importado_por': importacao.importado_por.username if importacao.importado_por else 'Sistema'
                })
        except Documento.DoesNotExist:
            # Documento não existe
            from django.http import Http404
            raise Http404("Documento não encontrado")
    
    # Carregar lançamentos do documento
    lancamentos = documento.lancamentos.select_related('tipo').prefetch_related(
        'pessoas__pessoa'
    ).order_by('id')
    
    context = {
        'tis': tis,
        'imovel': imovel,
        'documento': documento,
        'lancamentos': lancamentos,
        'tipo_visualizacao': 'documento_unico',
        'tem_lancamentos': lancamentos.exists(),
        'is_importado': is_importado,
        'cadeias_dominiais': cadeias_dominiais,
        'total_cadeias': len(cadeias_dominiais)
    }
    
    return render(request, 'dominial/documento_detalhado.html', context) 

@login_required
def exportar_cadeia_dominial_pdf(request, tis_id, imovel_id):
    """
    Exporta a cadeia dominial em formato PDF
    """
    try:
        tis = get_object_or_404(TIs, id=tis_id)
        imovel = get_object_or_404(Imovel, id=imovel_id, terra_indigena_id=tis)
        
        # Obter dados da cadeia dominial
        service = CadeiaDominialTabelaService()
        context = service.get_cadeia_dominial_tabela(tis_id, imovel_id, request.session)
        
        # Adicionar estatísticas
        if context['cadeia']:
            context['estatisticas'] = service.get_estatisticas_cadeia(context['cadeia'])
        
        # Renderizar template HTML para PDF
        html_string = render_to_string('dominial/cadeia_dominial_pdf.html', context)
        
        # Configurar CSS para PDF
        css_path = os.path.join(settings.STATIC_ROOT, 'dominial', 'css', 'cadeia_dominial_pdf.css')
        if not os.path.exists(css_path):
            css_path = os.path.join(settings.STATICFILES_DIRS[0], 'dominial', 'css', 'cadeia_dominial_pdf.css')
        
        # Gerar PDF
        pdf = HTML(string=html_string, base_url=request.build_absolute_uri('/')).write_pdf(
            stylesheets=[css_path] if os.path.exists(css_path) else None
        )
        
        # Configurar resposta HTTP
        response = HttpResponse(pdf, content_type='application/pdf')
        filename = f"cadeia_dominial_{imovel.matricula}_{date.today().strftime('%Y%m%d')}.pdf"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        return response
        
    except Exception as e:
        # Em caso de erro, retornar uma página de erro simples
        error_html = f"""
        <html>
        <head><title>Erro na Geração do PDF</title></head>
        <body>
            <h1>Erro na Geração do PDF</h1>
            <p>Ocorreu um erro ao gerar o PDF da cadeia dominial.</p>
            <p>Erro: {str(e)}</p>
            <p><a href="javascript:history.back()">Voltar</a></p>
        </body>
        </html>
        """
        return HttpResponse(error_html, content_type='text/html') 