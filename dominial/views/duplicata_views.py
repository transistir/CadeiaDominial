"""
Views para processamento de duplicatas na criação de lançamentos
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.http import require_http_methods, require_POST
from django.http import JsonResponse, Http404
from ..models import TIs, Imovel, Documento
from ..services.lancamento_duplicata_service import LancamentoDuplicataService


@login_required
@require_POST
def verificar_duplicata_ajax(request, tis_id, imovel_id, documento_id):
    """
    View AJAX para verificar duplicatas durante o preenchimento do formulário
    """
    try:
        # Obter objetos básicos
        tis = get_object_or_404(TIs, id=tis_id)
        imovel = get_object_or_404(Imovel, id=imovel_id, terra_indigena_id=tis)
        documento_ativo = get_object_or_404(Documento, id=documento_id, imovel=imovel)
        
        # Verificar duplicata
        resultado = LancamentoDuplicataService.verificar_duplicata_antes_criacao(
            request, documento_ativo
        )
        
        if resultado['tem_duplicata']:
            # Preparar dados para o template
            dados_template = LancamentoDuplicataService.obter_dados_duplicata_para_template(resultado)
            
            return JsonResponse({
                'tem_duplicata': True,
                'mensagem': resultado['mensagem'],
                'dados_template': dados_template
            })
        else:
            return JsonResponse({
                'tem_duplicata': False,
                'mensagem': resultado['mensagem']
            })
            
    except Exception as e:
        return JsonResponse({
            'tem_duplicata': False,
            'mensagem': f'Erro na verificação: {str(e)}'
        })


@login_required
@require_POST
def importar_duplicata(request, tis_id, imovel_id, documento_id):
    """
    View para processar a importação de uma cadeia dominial duplicada
    """
    try:
        # Obter objetos básicos
        tis = get_object_or_404(TIs, id=tis_id)
        imovel = get_object_or_404(Imovel, id=imovel_id, terra_indigena_id=tis)
        documento_ativo = get_object_or_404(Documento, id=documento_id, imovel=imovel)
        
        # Processar importação
        resultado = LancamentoDuplicataService.processar_importacao_duplicata(
            request, documento_ativo, request.user
        )
        
        if resultado['sucesso']:
            messages.success(request, f"✅ {resultado['mensagem']}")
            
            # APÓS IMPORTAÇÃO BEM-SUCEDIDA, CRIAR O LANÇAMENTO ORIGINAL
            try:
                from ..services.lancamento_criacao_service import LancamentoCriacaoService
                
                # Marcar que estamos criando após importação para pular verificação de duplicatas
                request.POST = request.POST.copy()
                request.POST['apos_importacao'] = 'true'
                
                # Criar o lançamento original usando os dados do POST
                lancamento_criado, mensagem = LancamentoCriacaoService.criar_lancamento_completo(
                    request=request,
                    tis=tis,
                    imovel=imovel,
                    documento_ativo=documento_ativo
                )
                
                if lancamento_criado:
                    messages.success(request, f"✅ Lançamento '{lancamento_criado.numero_lancamento}' criado com sucesso após importação!")
                else:
                    messages.warning(request, "⚠️ Importação realizada, mas houve um problema na criação do lançamento original.")
                    
            except Exception as e:
                messages.warning(request, f"⚠️ Importação realizada, mas erro na criação do lançamento: {str(e)}")
            
            # Redirecionar para a visualização de tabela da cadeia dominial
            return redirect('cadeia_dominial_tabela', 
                          tis_id=tis.id, 
                          imovel_id=imovel.id)
        else:
            messages.error(request, f"❌ {resultado['mensagem']}")
            
            # Redirecionar de volta para o formulário de lançamento
            return redirect('novo_lancamento_documento', 
                          tis_id=tis.id, 
                          imovel_id=imovel.id, 
                          documento_id=documento_ativo.id)
            
    except Http404:
        messages.error(request, "❌ Documento não encontrado.")
        return redirect('imoveis', tis_id=tis_id)
    except Exception as e:
        messages.error(request, f"❌ Erro inesperado: {str(e)}")
        # Verificar se documento_ativo foi definido antes de usar
        if 'documento_ativo' in locals():
            return redirect('novo_lancamento_documento', 
                          tis_id=tis.id, 
                          imovel_id=imovel.id, 
                          documento_id=documento_ativo.id)
        else:
            return redirect('imoveis', tis_id=tis_id)


@login_required
def cancelar_importacao_duplicata(request, tis_id, imovel_id, documento_id):
    """
    View para cancelar a importação e voltar ao formulário normal
    """
    try:
        # Obter objetos básicos
        tis = get_object_or_404(TIs, id=tis_id)
        imovel = get_object_or_404(Imovel, id=imovel_id, terra_indigena_id=tis)
        documento_ativo = get_object_or_404(Documento, id=documento_id, imovel=imovel)
        
        # Marcar na sessão que o usuário cancelou uma duplicata
        request.session['duplicata_cancelada'] = True
        request.session['duplicata_origem'] = request.GET.get('origem', '')
        request.session['duplicata_cartorio'] = request.GET.get('cartorio', '')
        
        messages.error(request, "❌ Origem/cartório já existe. Altere a origem ou o cartório para continuar.")
        
        # Redirecionar para o formulário de lançamento
        return redirect('novo_lancamento_documento', 
                      tis_id=tis.id, 
                      imovel_id=imovel.id, 
                      documento_id=documento_ativo.id)
        
    except Http404:
        messages.error(request, "❌ Documento não encontrado.")
        return redirect('imoveis', tis_id=tis_id)
    except Exception as e:
        messages.error(request, f"❌ Erro: {str(e)}")
        # Verificar se documento_ativo foi definido antes de usar
        if 'documento_ativo' in locals():
            return redirect('novo_lancamento_documento', 
                          tis_id=tis.id, 
                          imovel_id=imovel.id, 
                          documento_id=documento_ativo.id)
        else:
            return redirect('imoveis', tis_id=tis_id) 