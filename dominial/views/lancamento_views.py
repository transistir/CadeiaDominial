from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.http import require_http_methods, require_POST
from django.http import JsonResponse
from ..models import TIs, Imovel, Lancamento, Pessoas, Cartorios, Documento
from ..services.lancamento_service import LancamentoService
from ..utils.hierarquia_utils import processar_origens_para_documentos
from datetime import date
import uuid
from ..services.lancamento_heranca_service import LancamentoHerancaService
from ..services.lancamento_duplicata_service import LancamentoDuplicataService
from ..services.documento_compartilhado_service import DocumentoCompartilhadoService

@login_required
def novo_lancamento(request, tis_id, imovel_id, documento_id=None):
    """
    View para criar um novo lançamento
    """
    # Obter objetos básicos
    tis = get_object_or_404(TIs, id=tis_id)
    imovel = get_object_or_404(Imovel, id=imovel_id, terra_indigena_id=tis)
    
    # Determinar documento ativo - MODIFICAÇÃO PARA SUPORTAR DOCUMENTOS IMPORTADOS
    documento_ativo = None
    
    if documento_id:
        # Usar o novo service para verificar acesso ao documento
        documento_ativo = DocumentoCompartilhadoService.obter_documento_com_acesso(documento_id, imovel)
        
        if not documento_ativo:
            messages.error(request, '❌ Documento não encontrado ou não importado para este imóvel.')
            return redirect('imoveis', tis_id=tis.id)
    else:
        # Buscar documento ativo do imóvel (primeiro documento)
        documento_ativo = imovel.documentos.first()
        if not documento_ativo:
            messages.error(request, '❌ Nenhum documento encontrado para este imóvel.')
            return redirect('imoveis', tis_id=tis.id)
    
    # Obter dados para o formulário
    pessoas = Pessoas.objects.all().order_by('nome')
    cartorios = Cartorios.objects.all().order_by('nome')
    tipos_lancamento = LancamentoService.obter_tipos_lancamento_por_documento(documento_ativo)
    
    # Processar POST
    if request.method == 'POST':
        try:
            # Usar o service para criar o lançamento completo
            resultado = LancamentoService.criar_lancamento_completo(
                request, tis, imovel, documento_ativo
            )
            
            print(f"DEBUG VIEW: Resultado recebido: {resultado}")
            print(f"DEBUG VIEW: Tipo do resultado: {type(resultado)}")
            print(f"DEBUG VIEW: É tupla: {isinstance(resultado, tuple)}")
            if isinstance(resultado, tuple):
                print(f"DEBUG VIEW: Tamanho da tupla: {len(resultado)}")
            
            # Verificar se é resultado de duplicata
            if isinstance(resultado, tuple) and len(resultado) == 2:
                primeiro_elemento, segundo_elemento = resultado
                
                # Verificar se é resultado de duplicata (primeiro elemento é dict com 'tipo')
                if isinstance(primeiro_elemento, dict) and primeiro_elemento.get('tipo') == 'duplicata_encontrada':
                    # Resultado de duplicata encontrada
                    duplicata_info = primeiro_elemento
                    
                    # Preparar dados para o template de duplicata
                    dados_template = LancamentoDuplicataService.obter_dados_duplicata_para_template(
                        duplicata_info['duplicata_info']
                    )
                    
                    # Preparar dados do formulário para preservação
                    form_data = {
                        'tipo_lancamento': request.POST.get('tipo_lancamento'),
                        'numero_lancamento': request.POST.get('numero_lancamento'),
                        'numero_lancamento_simples': request.POST.get('numero_lancamento_simples'),
                        'data': request.POST.get('data'),
                        'observacoes': request.POST.get('observacoes'),
                        'livro_documento': request.POST.get('livro_documento'),
                        'folha_documento': request.POST.get('folha_documento'),
                        'cartorio': request.POST.get('cartorio'),
                        'cartorio_nome': request.POST.get('cartorio_nome'),
                        'area': request.POST.get('area'),
                        'forma': request.POST.get('forma'),
                        'descricao': request.POST.get('descricao'),
                        'titulo': request.POST.get('titulo'),
                        'origem_completa': request.POST.getlist('origem_completa[]'),
                        'cartorio_origem': request.POST.getlist('cartorio_origem[]'),
                        'cartorio_origem_nome': request.POST.getlist('cartorio_origem_nome[]'),
                        'livro_origem': request.POST.getlist('livro_origem[]'),
                        'folha_origem': request.POST.getlist('folha_origem[]'),
                        'transmitente': request.POST.getlist('transmitente[]'),
                        'transmitente_nome': request.POST.getlist('transmitente_nome[]'),
                        'adquirente': request.POST.getlist('adquirente[]'),
                        'adquirente_nome': request.POST.getlist('adquirente_nome[]'),
                    }
                    
                    # Renderizar template de duplicata
                    context = {
                        'tis': tis,
                        'imovel': imovel,
                        'documento': documento_ativo,
                        'duplicata_info': dados_template,
                        'form_data': form_data,
                        'modo_duplicata': True
                    }
                    
                    return render(request, 'dominial/duplicata_importacao.html', context)
                else:
                    # Resultado normal (sucesso, mensagem)
                    sucesso, mensagem_origens = resultado
            
            if sucesso:
                messages.success(request, '✅ Lançamento criado com sucesso!')
                if mensagem_origens:
                    messages.info(request, mensagem_origens)
                
                # Verificar se o usuário marcou "finalizar"
                finalizar = request.POST.get('finalizar') == 'on'
                
                if finalizar:
                    # Redirecionar para a visualização dos lançamentos do documento
                    return redirect('documento_lancamentos', tis_id=tis.id, imovel_id=imovel.id, documento_id=documento_ativo.id)
                else:
                    # Redirecionar para criar um novo lançamento no mesmo documento
                    return redirect('novo_lancamento_documento', tis_id=tis.id, imovel_id=imovel.id, documento_id=documento_ativo.id)
            else:
                messages.error(request, mensagem_origens)
                
        except Exception as e:
            # Capturar exceções para debug
            import traceback
            error_msg = f'Erro inesperado: {str(e)}\n{traceback.format_exc()}'
            messages.error(request, f'❌ {error_msg}')
            print(f"ERRO NA CRIAÇÃO DE LANÇAMENTO: {error_msg}")
            
            # Verificar se é erro de número duplicado para destacar o campo
            numero_lancamento_error = 'Já existe um lançamento com o número' in str(e)
            
            # Adicionar dados das pessoas para preservação
            transmitentes_data = []
            for i, nome in enumerate(request.POST.getlist('transmitente_nome[]')):
                if nome.strip():
                    transmitentes_data.append({
                        'nome': nome.strip(),
                        'id': request.POST.getlist('transmitente[]')[i] if i < len(request.POST.getlist('transmitente[]')) else ''
                    })
            
            adquirentes_data = []
            for i, nome in enumerate(request.POST.getlist('adquirente_nome[]')):
                if nome.strip():
                    adquirentes_data.append({
                        'nome': nome.strip(),
                        'id': request.POST.getlist('adquirente[]')[i] if i < len(request.POST.getlist('adquirente[]')) else ''
                    })
            
            context = {
                'tis': tis,
                'imovel': imovel,
                'documento': documento_ativo,
                'pessoas': pessoas,
                'cartorios': cartorios,
                'tipos_lancamento': tipos_lancamento,
                'form_data': {
                    'tipo_lancamento': request.POST.get('tipo_lancamento'),
                    'numero_lancamento': request.POST.get('numero_lancamento'),
                    'numero_lancamento_simples': request.POST.get('numero_lancamento_simples'),
                    'data': request.POST.get('data'),
                    'observacoes': request.POST.get('observacoes'),
                    'livro': request.POST.get('livro'),
                    'folha': request.POST.get('folha'),
                    'cartorio': request.POST.get('cartorio'),
                    'cartorio_nome': request.POST.get('cartorio_nome'),
                    'transmitente_ids': request.POST.getlist('transmitente[]'),
                    'transmitente_nomes': request.POST.getlist('transmitente_nome[]'),
                    'adquirente_ids': request.POST.getlist('adquirente[]'),
                    'adquirente_nomes': request.POST.getlist('adquirente_nome[]'),
                    'area': request.POST.get('area'),
                    'origem': request.POST.get('origem_completa') or request.POST.get('origem'),
                    'forma': request.POST.get('forma'),
                    'descricao': request.POST.get('descricao'),
                    'titulo': request.POST.get('titulo'),
                    'cartorio_origem': request.POST.get('cartorio_origem'),
                    'livro_origem': request.POST.get('livro_origem'),
                    'folha_origem': request.POST.get('folha_origem'),
                    'data_origem': request.POST.get('data_origem'),
                    # Campos específicos por tipo
                    'forma_averbacao': request.POST.get('forma_averbacao'),
                    'forma_registro': request.POST.get('forma_registro'),
                    'forma_inicio': request.POST.get('forma_inicio'),
                },
                'numero_lancamento_error': numero_lancamento_error,
            }
            
            context['transmitentes'] = transmitentes_data
            context['adquirentes'] = adquirentes_data
            
            return render(request, 'dominial/lancamento_form.html', context)
    
    # GET - mostrar formulário
    # Limpar dados de duplicata cancelada da sessão sempre
    request.session.pop('duplicata_cancelada', None)
    request.session.pop('duplicata_origem', None)
    request.session.pop('duplicata_cartorio', None)
    
    duplicata_cancelada = False
    duplicata_origem = ''
    duplicata_cartorio = ''
    
    context = {
        'tis': tis,
        'imovel': imovel,
        'documento': documento_ativo,
        'pessoas': pessoas,
        'cartorios': cartorios,
        'duplicata_cancelada': duplicata_cancelada,
        'duplicata_origem': duplicata_origem,
        'duplicata_cartorio': duplicata_cartorio,
        'tipos_lancamento': tipos_lancamento,
        'transmitentes': [],
        'adquirentes': [],
        'is_documento_importado': getattr(documento_ativo, 'is_importado', False),  # Usar flag do service
        'cartorio_origem_correto': documento_ativo.cartorio,  # SEMPRE passar o cartório correto
    }
    
    # Verificar se é o primeiro lançamento do documento
    total_lancamentos = Lancamento.objects.filter(documento=documento_ativo).count()
    is_primeiro_lancamento = total_lancamentos == 0
    
    # Verificar se é o primeiro documento da cadeia dominial (matrícula atual)
    is_primeiro_documento_cadeia = (documento_ativo.tipo.tipo == 'matricula' and 
                                   documento_ativo.numero == imovel.matricula)
    
    if is_primeiro_lancamento:
        # Para o primeiro lançamento, verificar se deve usar cartório da matrícula ou do documento
        if is_primeiro_documento_cadeia:
            # É o primeiro documento da cadeia (matrícula atual) - usar cartório da matrícula
            context['is_primeiro_lancamento'] = True
            context['cartorio_matricula'] = imovel.cartorio
            context['cartorio_matricula_nome'] = imovel.cartorio.nome if imovel.cartorio else 'Cartório não definido'
            
            # Se não há cartório definido, mostrar aviso
            if not imovel.cartorio:
                messages.warning(request, '⚠️ Atenção: O imóvel não possui cartório definido. Será necessário definir um cartório.')
        else:
            # É um documento criado automaticamente a partir de uma origem - usar cartório do documento
            context['is_primeiro_lancamento'] = False
            context['modo_edicao'] = True
            
            # Criar um lançamento temporário com o cartório do documento
            lancamento_herdado = Lancamento()
            lancamento_herdado.cartorio_origem = documento_ativo.cartorio
            context['lancamento'] = lancamento_herdado
    else:
        # Para lançamentos subsequentes, herdar dados do primeiro lançamento
        context['is_primeiro_lancamento'] = False
        
        # Obter dados do primeiro lançamento para herança
        dados_primeiro = LancamentoHerancaService.obter_dados_primeiro_lancamento(documento_ativo)
        
        # Para lançamentos subsequentes, usar o cartório do próprio documento
        lancamento_herdado = Lancamento()
        
        # CORREÇÃO: Usar o cartório do próprio documento (que foi definido quando ele foi criado)
        # O cartório do documento é o cartório que foi informado no lançamento de início de matrícula que criou este documento
        lancamento_herdado.cartorio_origem = documento_ativo.cartorio
        
        # Herdar livro e folha do primeiro lançamento se disponíveis
        if dados_primeiro:
            lancamento_herdado.livro_origem = dados_primeiro['livro_origem']
            lancamento_herdado.folha_origem = dados_primeiro['folha_origem']
        
        context['lancamento'] = lancamento_herdado
        context['modo_edicao'] = True  # Para usar os dados herdados no template
        
        # CORREÇÃO: Adicionar cartorio_origem_correto para o template usar
        context['cartorio_origem_correto'] = documento_ativo.cartorio
    
    return render(request, 'dominial/lancamento_form.html', context)

@login_required
def editar_lancamento(request, tis_id, imovel_id, lancamento_id):
    """
    View para editar um lançamento existente
    """
    # Obter objetos básicos
    tis = get_object_or_404(TIs, id=tis_id)
    imovel = get_object_or_404(Imovel, id=imovel_id, terra_indigena_id=tis)
    lancamento = get_object_or_404(Lancamento, id=lancamento_id, documento__imovel=imovel)
    
    # Obter dados para o formulário
    pessoas = Pessoas.objects.all().order_by('nome')
    cartorios = Cartorios.objects.all().order_by('nome')
    tipos_lancamento = LancamentoService.obter_tipos_lancamento_por_documento(lancamento.documento)
    
    # Processar POST
    if request.method == 'POST':
        # Usar o service para atualizar o lançamento completo
        sucesso, mensagem_origens = LancamentoService.atualizar_lancamento_completo(
            request, lancamento, imovel
        )
        
        if sucesso:
            messages.success(request, f'Lançamento "{lancamento.numero_lancamento}" atualizado com sucesso!')
            if mensagem_origens:
                messages.info(request, mensagem_origens)
            
            # Verificar se o usuário marcou "finalizar"
            finalizar = request.POST.get('finalizar') == 'on'
            
            if finalizar:
                # Redirecionar para a visualização detalhada do documento
                return redirect('documento_detalhado', tis_id=tis.id, imovel_id=imovel.id, documento_id=lancamento.documento.id)
            else:
                # Redirecionar para criar um novo lançamento no mesmo documento
                return redirect('novo_lancamento_documento', tis_id=tis.id, imovel_id=imovel.id, documento_id=lancamento.documento.id)
        else:
            messages.error(request, mensagem_origens)
    
    # Obter pessoas do lançamento para exibição no formulário
    transmitentes = lancamento.pessoas.filter(tipo='transmitente')
    adquirentes = lancamento.pessoas.filter(tipo='adquirente')
    
    # CORREÇÃO: Para o formulário de edição, usar o cartório do documento atual
    # O cartório de origem deve ser o cartório do próprio documento (que foi definido quando ele foi criado)
    cartorio_origem_correto = lancamento.documento.cartorio
    
    context = {
        'tis': tis,
        'imovel': imovel,
        'lancamento': lancamento,
        'documento': lancamento.documento,
        'pessoas': pessoas,
        'cartorios': cartorios,
        'tipos_lancamento': tipos_lancamento,
        'transmitentes': transmitentes,
        'adquirentes': adquirentes,
        'modo_edicao': True,
        'cartorio_origem_correto': cartorio_origem_correto
    }
    
    # Preparar dados para o template
    if context['modo_edicao'] and lancamento.origem:
        # Separar múltiplas origens para o template
        origens_separadas = []
        
        # Tentar recuperar mapeamento de origens e cartórios do cache
        from django.core.cache import cache
        cache_key = f"mapeamento_origens_lancamento_{lancamento.id}"
        mapeamento_origens = cache.get(cache_key)
        
        if ';' in lancamento.origem:
            origens_list = [o.strip() for o in lancamento.origem.split(';') if o.strip()]
            
            if mapeamento_origens and len(mapeamento_origens) == len(origens_list):
                # Usar mapeamento do cache se disponível
                for i, origem in enumerate(origens_list):
                    mapeamento = mapeamento_origens[i] if i < len(mapeamento_origens) else {}
                    origens_separadas.append({
                        'texto': origem,
                        'index': i,
                        'cartorio_nome': mapeamento.get('cartorio_nome', ''),
                        'cartorio_id': mapeamento.get('cartorio_id', ''),
                        'livro': mapeamento.get('livro', ''),
                        'folha': mapeamento.get('folha', '')
                    })
            else:
                # Fallback: usar cartório geral do lançamento para todas as origens
                for i, origem in enumerate(origens_list):
                    origens_separadas.append({
                        'texto': origem,
                        'index': i,
                        'cartorio_nome': lancamento.cartorio_origem.nome if lancamento.cartorio_origem else '',
                        'cartorio_id': lancamento.cartorio_origem.id if lancamento.cartorio_origem else '',
                        'livro': lancamento.livro_origem,
                        'folha': lancamento.folha_origem
                    })
        else:
            # Uma única origem
            origens_separadas.append({
                'texto': lancamento.origem,
                'index': 0,
                'cartorio_nome': lancamento.cartorio_origem.nome if lancamento.cartorio_origem else '',
                'cartorio_id': lancamento.cartorio_origem.id if lancamento.cartorio_origem else '',
                'livro': lancamento.livro_origem,
                'folha': lancamento.folha_origem
            })
    else:
        origens_separadas = []
    
    context['origens_separadas'] = origens_separadas
    
    return render(request, 'dominial/lancamento_form.html', context)

@login_required
def excluir_lancamento(request, tis_id, imovel_id, lancamento_id):
    """View para excluir um lançamento"""
    tis = get_object_or_404(TIs, id=tis_id)
    imovel = get_object_or_404(Imovel, id=imovel_id, terra_indigena_id=tis)
    lancamento = get_object_or_404(Lancamento, id=lancamento_id, documento__imovel=imovel)
    
    if request.method == 'POST':
        try:
            documento_id = lancamento.documento.id
            numero_lancamento = lancamento.numero_lancamento or f"Lançamento {lancamento.id}"
            lancamento.delete()
            messages.success(request, f'Lançamento "{numero_lancamento}" excluído com sucesso!')
            return redirect('documento_detalhado', tis_id=tis_id, imovel_id=imovel_id, documento_id=documento_id)
        except Exception as e:
            messages.error(request, f'Erro ao excluir lançamento: {str(e)}')
    
    return render(request, 'dominial/lancamento_confirm_delete.html', {
        'tis': tis,
        'imovel': imovel,
        'lancamento': lancamento,
        'documento': lancamento.documento
    })

@login_required
def lancamento_detail(request, tis_id, imovel_id, lancamento_id):
    """View para visualizar detalhes de um lançamento"""
    tis = get_object_or_404(TIs, id=tis_id)
    imovel = get_object_or_404(Imovel, id=imovel_id, terra_indigena_id=tis)
    lancamento = get_object_or_404(Lancamento, id=lancamento_id, documento__imovel=imovel)
    
    # Obter pessoas do lançamento
    transmitentes = lancamento.pessoas.filter(tipo='transmitente')
    adquirentes = lancamento.pessoas.filter(tipo='adquirente')
    
    context = {
        'tis': tis,
        'imovel': imovel,
        'lancamento': lancamento,
        'documento': lancamento.documento,
        'transmitentes': transmitentes,
        'adquirentes': adquirentes
    }
    
    return render(request, 'dominial/lancamento_detail.html', context) 