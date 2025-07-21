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
from django.views.decorators.csrf import csrf_exempt
from .cadeia_dominial_views import cadeia_dominial_tabela
from ..services.cadeia_dominial_tabela_service import CadeiaDominialTabelaService
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

@login_required
@csrf_exempt
@require_http_methods(["POST"])
def escolher_origem_documento(request):
    """
    API para escolher origem no nível do documento
    """
    try:
        data = json.loads(request.body)
        documento_id = data.get('documento_id')
        origem_numero = data.get('origem_numero')
        tis_id = data.get('tis_id')
        imovel_id = data.get('imovel_id')
        
        if not all([documento_id, origem_numero, tis_id, imovel_id]):
            return JsonResponse({
                'success': False,
                'error': 'Parâmetros obrigatórios não fornecidos'
            }, status=400)
        
        # Salvar escolha na sessão
        session_key = f'origem_documento_{documento_id}'
        request.session[session_key] = origem_numero
        
        # Não retornar cadeia_data para evitar erro de serialização
        return JsonResponse({
            'success': True,
            'message': f'Origem {origem_numero} escolhida para documento {documento_id}'
        })
        
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'JSON inválido'
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)



@login_required
@csrf_exempt
@require_http_methods(["POST"])
def escolher_origem_lancamento(request):
    """
    API para escolher origem no nível do lançamento
    """
    try:
        data = json.loads(request.body)
        lancamento_id = data.get('lancamento_id')
        origem_numero = data.get('origem_numero')
        tis_id = data.get('tis_id')
        imovel_id = data.get('imovel_id')
        
        if not all([lancamento_id, origem_numero, tis_id, imovel_id]):
            return JsonResponse({
                'success': False,
                'error': 'Parâmetros obrigatórios não fornecidos'
            }, status=400)
        
        # Salvar escolha na sessão
        session_key = f'origem_lancamento_{lancamento_id}'
        request.session[session_key] = origem_numero
        
        # Recarregar dados da cadeia dominial com a nova escolha
        service = CadeiaDominialTabelaService()
        cadeia_data = service.get_cadeia_dominial_tabela(tis_id, imovel_id, request.session)
        
        return JsonResponse({
            'success': True,
            'message': f'Origem {origem_numero} escolhida para lançamento {lancamento_id}',
            'cadeia_data': cadeia_data
        })
        
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'JSON inválido'
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)

@login_required
@require_http_methods(["GET"])
def get_cadeia_dominial_atualizada(request, tis_id, imovel_id):
    """
    API para obter cadeia dominial atualizada com escolhas da sessão
    """
    try:
        service = CadeiaDominialTabelaService()
        cadeia_data = service.get_cadeia_dominial_tabela(tis_id, imovel_id, request.session)
        
        # Serializar dados para JSON
        cadeia_serializada = []
        for item in cadeia_data['cadeia']:
            documento = item['documento']
            
            # Verificar se o documento tem todos os campos necessários
            try:
                documento_serializado = {
                    'id': documento.id,
                    'numero': documento.numero,
                    'data': documento.data.strftime('%d/%m/%Y') if documento.data else '',
                    'tipo_display': documento.tipo.get_tipo_display() if documento.tipo else '',
                    'cartorio_nome': documento.cartorio.nome if documento.cartorio else '',
                    'livro': documento.livro,
                    'folha': documento.folha,
                    'is_importado': item.get('is_importado', False),
                    'grupo_importacao': item.get('grupo_importacao') is not None,
                    'is_primeiro_grupo': item.get('is_primeiro_grupo', False)
                }
            except Exception as e:
                # Se houver erro ao serializar o documento, pular
                continue
            
            lancamentos_serializados = []
            try:
                for lancamento in item['lancamentos']:
                    lancamento_serializado = {
                        'id': lancamento.id,
                        'tipo': lancamento.tipo.tipo if lancamento.tipo else '',
                        'tipo_tipo': lancamento.tipo.tipo if lancamento.tipo else '',  # Adicionar para compatibilidade
                        'tipo_display': lancamento.tipo.get_tipo_display() if lancamento.tipo else '',
                        'numero_lancamento': lancamento.numero_lancamento,
                        'data': lancamento.data.strftime('%d/%m/%Y') if lancamento.data else '',
                        'forma': lancamento.forma,
                        'titulo': lancamento.titulo,
                        'descricao': lancamento.descricao,
                        'area': lancamento.area,
                        'origem': lancamento.origem,
                        'observacoes': lancamento.observacoes,
                        'cartorio_transmissao_nome': lancamento.cartorio_transmissao_compat.nome if lancamento.cartorio_transmissao_compat else None,
                        'livro_transacao': lancamento.livro_transacao,
                        'folha_transacao': lancamento.folha_transacao,
                        'data_transacao': lancamento.data_transacao.strftime('%d/%m/%Y') if lancamento.data_transacao else None,
                        'pessoas': []
                    }
                    
                    # Serializar pessoas
                    try:
                        for lancamento_pessoa in lancamento.pessoas.all():
                            lancamento_serializado['pessoas'].append({
                                'pessoa_nome': lancamento_pessoa.pessoa.nome,
                                'tipo': lancamento_pessoa.tipo
                            })
                    except Exception as e:
                        # Se houver erro ao serializar pessoas, continuar sem pessoas
                        pass
                    
                    lancamentos_serializados.append(lancamento_serializado)
            except Exception as e:
                # Se houver erro ao serializar lançamentos, continuar sem lançamentos
                pass
            
            item_serializado = {
                'documento': documento_serializado,
                'lancamentos': lancamentos_serializados,
                'origens_disponiveis': item.get('origens_disponiveis', []),
                'tem_multiplas_origens': item.get('tem_multiplas_origens', False),
                'escolha_atual': item.get('escolha_atual'),
                'is_importado': item.get('is_importado', False),
                'grupo_importacao': item.get('grupo_importacao'),
                'is_primeiro_grupo': item.get('is_primeiro_grupo', False)
            }
            
            cadeia_serializada.append(item_serializado)
        
        return JsonResponse({
            'success': True,
            'cadeia': cadeia_serializada
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)

@login_required
@csrf_exempt
@require_http_methods(["POST"])
def limpar_escolhas_origem(request):
    """
    API para limpar todas as escolhas de origem da sessão
    """
    try:
        # Limpar todas as chaves de origem da sessão
        keys_to_remove = []
        for key in request.session.keys():
            if key.startswith('origem_documento_'):
                keys_to_remove.append(key)
        
        for key in keys_to_remove:
            del request.session[key]
        
        # Salvar a sessão
        request.session.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Escolhas de origem limpas com sucesso'
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)