from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.http import require_http_methods, require_POST
from django.http import JsonResponse
from ..models import Lancamento, LancamentoTipo, Imovel, Documento, TIs, Pessoas, Cartorios, DocumentoTipo, LancamentoPessoa
from ..utils.hierarquia_utils import processar_origens_para_documentos
from datetime import date
import uuid

@login_required
def novo_lancamento(request, tis_id, imovel_id, documento_id=None):
    tis = get_object_or_404(TIs, id=tis_id)
    imovel = get_object_or_404(Imovel, id=imovel_id, terra_indigena_id=tis)
    
    # Se documento_id foi fornecido, usar esse documento
    if documento_id:
        documento_ativo = get_object_or_404(Documento, id=documento_id, imovel=imovel)
    else:
        # Caso contrário, usar o documento mais recente
        documento_ativo = Documento.objects.filter(imovel=imovel).order_by('-data', '-id').first()
    
    # Se não há documento ativo, criar automaticamente um documento de matrícula
    if not documento_ativo:
        try:
            # Obter o tipo de documento "matricula"
            tipo_matricula = DocumentoTipo.objects.get(tipo='matricula')
            
            # Criar documento de matrícula automaticamente
            documento_ativo = Documento.objects.create(
                imovel=imovel,
                tipo=tipo_matricula,
                numero=imovel.matricula,  # Usar a matrícula do imóvel como número do documento
                data=imovel.data_cadastro,  # Usar a data de cadastro do imóvel
                cartorio=imovel.cartorio if imovel.cartorio else Cartorios.objects.first(),
                livro='1',  # Livro padrão
                folha='1',  # Folha padrão
                origem='Matrícula atual do imóvel',
                observacoes='Documento criado automaticamente ao iniciar a cadeia dominial'
            )
            
            messages.info(request, f'Documento de matrícula "{imovel.matricula}" criado automaticamente.')
            
        except Exception as e:
            messages.error(request, f'Erro ao criar documento de matrícula: {str(e)}')
            return redirect('novo_documento', tis_id=tis.id, imovel_id=imovel.id)
    
    pessoas = Pessoas.objects.all().order_by('nome')
    cartorios = Cartorios.objects.all().order_by('nome')
    
    # Filtrar tipos de lançamento baseado no tipo do documento
    if documento_ativo.tipo.tipo == 'matricula':
        # Para documentos do tipo matrícula: Averbação, Registro e Início de Matrícula
        tipos_lancamento = LancamentoTipo.objects.filter(
            tipo__in=['averbacao', 'registro', 'inicio_matricula']
        ).order_by('tipo')
    elif documento_ativo.tipo.tipo == 'transcricao':
        # Para documentos do tipo transcrição: Averbação e Início de Matrícula
        tipos_lancamento = LancamentoTipo.objects.filter(
            tipo__in=['averbacao', 'inicio_matricula']
        ).order_by('tipo')
    else:
        # Fallback: todos os tipos
        tipos_lancamento = LancamentoTipo.objects.all().order_by('tipo')
    
    if request.method == 'POST':
        tipo_id = request.POST.get('tipo_lancamento')
        numero_lancamento = request.POST.get('numero_lancamento')
        data = request.POST.get('data')
        observacoes = request.POST.get('observacoes')
        eh_inicio_matricula = request.POST.get('eh_inicio_matricula') == 'on'
        
        # Validação dos campos obrigatórios
        if not numero_lancamento or not numero_lancamento.strip():
            messages.error(request, 'O número do lançamento é obrigatório.')
            context = {
                'tis': tis,
                'imovel': imovel,
                'documento': documento_ativo,
                'pessoas': pessoas,
                'cartorios': cartorios,
                'tipos_lancamento': tipos_lancamento,
            }
            return render(request, 'dominial/lancamento_form.html', context)
        
        # Validar unicidade do número de lançamento
        if numero_lancamento.strip():
            lancamento_existente = Lancamento.objects.filter(
                documento=documento_ativo,
                numero_lancamento=numero_lancamento.strip()
            ).first()
            
            if lancamento_existente:
                messages.error(request, f'Já existe um lançamento com o número "{numero_lancamento.strip()}" neste documento.')
                context = {
                    'tis': tis,
                    'imovel': imovel,
                    'documento': documento_ativo,
                    'pessoas': pessoas,
                    'cartorios': cartorios,
                    'tipos_lancamento': tipos_lancamento,
                    # Preservar dados do formulário
                    'form_data': {
                        'tipo_lancamento': request.POST.get('tipo_lancamento'),
                        'numero_lancamento': numero_lancamento,
                        'data': request.POST.get('data'),
                        'observacoes': request.POST.get('observacoes'),
                        'eh_inicio_matricula': request.POST.get('eh_inicio_matricula') == 'on',
                        'transmitente_ids': request.POST.getlist('transmitente[]'),
                        'transmitente_nomes': request.POST.getlist('transmitente_nome[]'),
                        'transmitente_percentuais': request.POST.getlist('transmitente_percentual[]'),
                        'adquirente_ids': request.POST.getlist('adquirente[]'),
                        'adquirente_nomes': request.POST.getlist('adquirente_nome[]'),
                        'adquirente_percentuais': request.POST.getlist('adquirente_percentual[]'),
                        'area': request.POST.get('area'),
                        'origem': request.POST.get('origem_completa') or request.POST.get('origem'),
                        'forma': request.POST.get('forma'),
                        'descricao': request.POST.get('descricao'),
                        'titulo': request.POST.get('titulo'),
                        'cartorio_origem': request.POST.get('cartorio_origem'),
                        'livro_origem': request.POST.get('livro_origem'),
                        'folha_origem': request.POST.get('folha_origem'),
                        'data_origem': request.POST.get('data_origem'),
                    },
                    'numero_lancamento_error': True,  # Flag para destacar o campo em vermelho
                }
                return render(request, 'dominial/lancamento_form.html', context)
        
        try:
            # Criar o lançamento primeiro
            tipo_lanc = LancamentoTipo.objects.get(id=tipo_id)
            
            # Tratar campos vazios
            data_clean = data if data and data.strip() else None
            livro_origem_clean = request.POST.get('livro_origem') if request.POST.get('livro_origem') and request.POST.get('livro_origem').strip() else None
            folha_origem_clean = request.POST.get('folha_origem') if request.POST.get('folha_origem') and request.POST.get('folha_origem').strip() else None
            forma_value = request.POST.get('forma', '').strip()
            descricao_clean = observacoes if observacoes and observacoes.strip() else None
            titulo_clean = request.POST.get('titulo') if request.POST.get('titulo') and request.POST.get('titulo').strip() else None
            area = request.POST.get('area')
            origem = request.POST.get('origem_completa') or request.POST.get('origem')
            
            # Processar campo forma sempre (pode ser usado mesmo quando não é requerido)
            # Pegar o valor correto baseado no tipo de lançamento
            if tipo_lanc.tipo == 'averbacao':
                forma_value = request.POST.get('forma_averbacao', '').strip()
            elif tipo_lanc.tipo == 'registro':
                forma_value = request.POST.get('forma_registro', '').strip()
            elif tipo_lanc.tipo == 'inicio_matricula':
                forma_value = request.POST.get('forma_inicio', '').strip()
            else:
                # Fallback: tentar pegar qualquer campo forma
                forma_value = request.POST.get('forma', '').strip()
            
            # Sempre usar o valor enviado, independente do tipo
            lancamento = Lancamento.objects.create(
                documento=documento_ativo,
                tipo=tipo_lanc,
                numero_lancamento=numero_lancamento,
                data=data_clean,
                observacoes=observacoes,
                eh_inicio_matricula=eh_inicio_matricula,
                forma=forma_value if forma_value else None,
                descricao=descricao_clean,
                titulo=titulo_clean,
                livro_origem=livro_origem_clean,
                folha_origem=folha_origem_clean,
                data_origem=data_clean,
            )
            
            # Adicionar cartório de origem se fornecido
            cartorio_origem_id = request.POST.get('cartorio_origem')
            cartorio_origem_nome = request.POST.get('cartorio_origem_nome', '').strip()
            
            # Verificar se é averbação com campos de cartório adicionais
            if tipo_lanc.tipo == 'averbacao' and request.POST.get('incluir_cartorio_averbacao') == 'on':
                # Usar campos específicos da averbação
                cartorio_origem_id = request.POST.get('cartorio_origem_averbacao')
                cartorio_origem_nome = request.POST.get('cartorio_origem_nome_averbacao', '').strip()
                livro_origem_clean = request.POST.get('livro_origem_averbacao') if request.POST.get('livro_origem_averbacao') and request.POST.get('livro_origem_averbacao').strip() else None
                folha_origem_clean = request.POST.get('folha_origem_averbacao') if request.POST.get('folha_origem_averbacao') and request.POST.get('folha_origem_averbacao').strip() else None
                data_origem_clean = request.POST.get('data_origem_averbacao') if request.POST.get('data_origem_averbacao') else None
                titulo_clean = request.POST.get('titulo_averbacao') if request.POST.get('titulo_averbacao') and request.POST.get('titulo_averbacao').strip() else None
                
                # Atualizar o lançamento com os novos valores
                lancamento.livro_origem = livro_origem_clean
                lancamento.folha_origem = folha_origem_clean
                lancamento.data_origem = data_origem_clean
                lancamento.titulo = titulo_clean
            
            if cartorio_origem_id and cartorio_origem_id.strip():
                # Se tem ID, usar o cartório existente
                lancamento.cartorio_origem_id = cartorio_origem_id
            elif cartorio_origem_nome:
                # Se tem nome mas não tem ID, tentar encontrar ou criar o cartório
                try:
                    cartorio = Cartorios.objects.get(nome__iexact=cartorio_origem_nome)
                    lancamento.cartorio_origem = cartorio
                except Cartorios.DoesNotExist:
                    # Criar novo cartório com CNS único
                    cns_unico = f"CNS{str(uuid.uuid4().int)[:10]}"
                    cartorio = Cartorios.objects.create(
                        nome=cartorio_origem_nome,
                        cns=cns_unico,
                        cidade=Cartorios.objects.first().cidade if Cartorios.objects.exists() else None
                    )
                    lancamento.cartorio_origem = cartorio
            else:
                lancamento.cartorio_origem_id = None
            if area:
                lancamento.area = float(area) if area and area.strip() else None
            if origem:
                lancamento.origem = origem
            lancamento.save()
            
            # Processar origens para criar documentos automáticos
            if origem:
                origens_processadas = processar_origens_para_documentos(origem, imovel, lancamento)
                if origens_processadas:
                    messages.info(request, f'Foram identificadas {len(origens_processadas)} origem(ns) para criação automática de documentos.')
            
            # Processar transmitentes
            transmitentes_data = request.POST.getlist('transmitente_nome[]')
            transmitente_ids = request.POST.getlist('transmitente[]')
            transmitente_percentuais = request.POST.getlist('transmitente_percentual[]')
            
            processar_pessoas_lancamento(lancamento, transmitentes_data, transmitente_ids, transmitente_percentuais, 'transmitente')
            
            # Processar adquirentes
            adquirentes_data = request.POST.getlist('adquirente_nome[]')
            adquirente_ids = request.POST.getlist('adquirente[]')
            adquirente_percentuais = request.POST.getlist('adquirente_percentual[]')
            
            processar_pessoas_lancamento(lancamento, adquirentes_data, adquirente_ids, adquirente_percentuais, 'adquirente')
            
            messages.success(request, 'Lançamento criado com sucesso!')
            
            # Verificar se o usuário marcou "finalizar"
            finalizar = request.POST.get('finalizar') == 'on'
            
            if finalizar:
                # Redirecionar para a visualização dos lançamentos do documento
                return redirect('documento_lancamentos', tis_id=tis.id, imovel_id=imovel.id, documento_id=documento_ativo.id)
            else:
                # Redirecionar para criar um novo lançamento no mesmo documento
                return redirect('novo_lancamento_documento', tis_id=tis.id, imovel_id=imovel.id, documento_id=documento_ativo.id)
                    
        except Exception as e:
            messages.error(request, f'Erro ao criar lançamento: {str(e)}')
    
    context = {
        'tis': tis,
        'imovel': imovel,
        'documento': documento_ativo,
        'pessoas': pessoas,
        'cartorios': cartorios,
        'tipos_lancamento': tipos_lancamento,
    }
    return render(request, 'dominial/lancamento_form.html', context)

@login_required
def editar_lancamento(request, tis_id, imovel_id, lancamento_id):
    """View para editar um lançamento existente"""
    tis = get_object_or_404(TIs, id=tis_id)
    imovel = get_object_or_404(Imovel, id=imovel_id, terra_indigena_id=tis)
    lancamento = get_object_or_404(Lancamento, id=lancamento_id, documento__imovel=imovel)
    
    pessoas = Pessoas.objects.all().order_by('nome')
    cartorios = Cartorios.objects.all().order_by('nome')
    
    # Filtrar tipos de lançamento baseado no tipo do documento
    if lancamento.documento.tipo.tipo == 'matricula':
        # Para documentos do tipo matrícula: Averbação, Registro e Início de Matrícula
        tipos_lancamento = LancamentoTipo.objects.filter(
            tipo__in=['averbacao', 'registro', 'inicio_matricula']
        ).order_by('tipo')
    elif lancamento.documento.tipo.tipo == 'transcricao':
        # Para documentos do tipo transcrição: Averbação e Início de Matrícula
        tipos_lancamento = LancamentoTipo.objects.filter(
            tipo__in=['averbacao', 'inicio_matricula']
        ).order_by('tipo')
    else:
        # Fallback: todos os tipos
        tipos_lancamento = LancamentoTipo.objects.all().order_by('tipo')
    
    if request.method == 'POST':
        try:
            # Obter dados básicos do formulário
            lancamento.numero_lancamento = request.POST.get('numero_lancamento', '').strip()
            lancamento.data = request.POST.get('data') if request.POST.get('data') else None
            lancamento.observacoes = request.POST.get('observacoes', '').strip()
            lancamento.eh_inicio_matricula = request.POST.get('eh_inicio_matricula') == 'on'
            
            # Atualizar tipo de lançamento se fornecido
            tipo_id = request.POST.get('tipo_lancamento')
            if tipo_id:
                lancamento.tipo = LancamentoTipo.objects.get(id=tipo_id)
            
            # Tratar campos vazios
            data_clean = request.POST.get('data') if request.POST.get('data') and request.POST.get('data').strip() else None
            livro_origem_clean = request.POST.get('livro_origem') if request.POST.get('livro_origem') and request.POST.get('livro_origem').strip() else None
            folha_origem_clean = request.POST.get('folha_origem') if request.POST.get('folha_origem') and request.POST.get('folha_origem').strip() else None
            
            # Processar campo forma baseado no tipo de lançamento
            forma_value = ''
            if lancamento.tipo.tipo == 'averbacao':
                forma_value = request.POST.get('forma_averbacao', '').strip()
            elif lancamento.tipo.tipo == 'registro':
                forma_value = request.POST.get('forma_registro', '').strip()
            elif lancamento.tipo.tipo == 'inicio_matricula':
                forma_value = request.POST.get('forma_inicio', '').strip()
            
            # Definir forma no lançamento
            lancamento.forma = forma_value if forma_value else None
            
            # Processar campos específicos do tipo de lançamento
            if lancamento.tipo.tipo == 'averbacao':
                area_value = request.POST.get('area', '').strip() if request.POST.get('area') else None
                lancamento.area = float(area_value) if area_value else None
                lancamento.origem = request.POST.get('origem_completa', '').strip() if request.POST.get('origem_completa') else None
                lancamento.descricao = request.POST.get('descricao', '').strip() if request.POST.get('descricao') else None
                lancamento.titulo = request.POST.get('titulo', '').strip() if request.POST.get('titulo') else None
                
                # Verificar se é averbação com campos de cartório adicionais
                if request.POST.get('incluir_cartorio_averbacao') == 'on':
                    # Processar cartório de origem
                    cartorio_origem_id = request.POST.get('cartorio_origem_averbacao')
                    cartorio_origem_nome = request.POST.get('cartorio_origem_nome_averbacao', '').strip()
                    
                    if cartorio_origem_id and cartorio_origem_id.strip():
                        lancamento.cartorio_origem_id = cartorio_origem_id
                    elif cartorio_origem_nome:
                        try:
                            cartorio = Cartorios.objects.get(nome__iexact=cartorio_origem_nome)
                            lancamento.cartorio_origem = cartorio
                        except Cartorios.DoesNotExist:
                            # Criar novo cartório com CNS único
                            cns_unico = f"CNS{str(uuid.uuid4().int)[:10]}"
                            cartorio = Cartorios.objects.create(
                                nome=cartorio_origem_nome,
                                cns=cns_unico,
                                cidade=Cartorios.objects.first().cidade if Cartorios.objects.exists() else None
                            )
                            lancamento.cartorio_origem = cartorio
                    else:
                        lancamento.cartorio_origem_id = None
                    
                    # Processar outros campos de cartório
                    lancamento.livro_origem = request.POST.get('livro_origem_averbacao') if request.POST.get('livro_origem_averbacao') and request.POST.get('livro_origem_averbacao').strip() else None
                    lancamento.folha_origem = request.POST.get('folha_origem_averbacao') if request.POST.get('folha_origem_averbacao') and request.POST.get('folha_origem_averbacao').strip() else None
                    lancamento.data_origem = request.POST.get('data_origem_averbacao') if request.POST.get('data_origem_averbacao') else None
                    lancamento.titulo = request.POST.get('titulo_averbacao') if request.POST.get('titulo_averbacao') and request.POST.get('titulo_averbacao').strip() else None
                else:
                    # Limpar campos de cartório se o checkbox não estiver marcado
                    lancamento.cartorio_origem_id = None
                    lancamento.livro_origem = None
                    lancamento.folha_origem = None
                    lancamento.data_origem = None
                    
            elif lancamento.tipo.tipo == 'registro':
                # Processar cartório de origem
                cartorio_origem_id = request.POST.get('cartorio_origem')
                cartorio_origem_nome = request.POST.get('cartorio_origem_nome', '').strip()
                
                if cartorio_origem_id and cartorio_origem_id.strip():
                    lancamento.cartorio_origem_id = cartorio_origem_id
                elif cartorio_origem_nome:
                    try:
                        cartorio = Cartorios.objects.get(nome__iexact=cartorio_origem_nome)
                        lancamento.cartorio_origem = cartorio
                    except Cartorios.DoesNotExist:
                        # Criar novo cartório com CNS único
                        cns_unico = f"CNS{str(uuid.uuid4().int)[:10]}"
                        cartorio = Cartorios.objects.create(
                            nome=cartorio_origem_nome,
                            cns=cns_unico,
                            cidade=Cartorios.objects.first().cidade if Cartorios.objects.exists() else None
                        )
                        lancamento.cartorio_origem = cartorio
                else:
                    lancamento.cartorio_origem_id = None
                
                lancamento.livro_origem = livro_origem_clean
                lancamento.folha_origem = folha_origem_clean
                lancamento.data_origem = request.POST.get('data_origem') if request.POST.get('data_origem') else None
            elif lancamento.tipo.tipo == 'inicio_matricula':
                area_value = request.POST.get('area', '').strip() if request.POST.get('area') else None
                lancamento.area = float(area_value) if area_value else None
                lancamento.origem = request.POST.get('origem_completa', '').strip() if request.POST.get('origem_completa') else None
                lancamento.descricao = request.POST.get('descricao', '').strip() if request.POST.get('descricao') else None
                lancamento.titulo = request.POST.get('titulo', '').strip() if request.POST.get('titulo') else None
            
            # Salvar o lançamento
            lancamento.save()
            
            # Processar origens para criar documentos automáticos
            origem = request.POST.get('origem_completa', '').strip()
            if origem:
                origens_processadas = processar_origens_para_documentos(origem, imovel, lancamento)
                if origens_processadas:
                    messages.info(request, f'Foram identificadas {len(origens_processadas)} origem(ns) para criação automática de documentos.')
            
            # Limpar pessoas existentes do lançamento
            LancamentoPessoa.objects.filter(lancamento=lancamento).delete()
            
            # Processar transmitentes
            transmitentes_data = request.POST.getlist('transmitente_nome[]')
            transmitente_ids = request.POST.getlist('transmitente[]')
            transmitente_percentuais = request.POST.getlist('transmitente_percentual[]')
            
            processar_pessoas_lancamento(lancamento, transmitentes_data, transmitente_ids, transmitente_percentuais, 'transmitente')
            
            # Processar adquirentes
            adquirentes_data = request.POST.getlist('adquirente_nome[]')
            adquirente_ids = request.POST.getlist('adquirente[]')
            adquirente_percentuais = request.POST.getlist('adquirente_percentual[]')
            
            processar_pessoas_lancamento(lancamento, adquirentes_data, adquirente_ids, adquirente_percentuais, 'adquirente')
            
            messages.success(request, f'Lançamento "{lancamento.numero_lancamento}" atualizado com sucesso!')
            
            # Verificar se o usuário marcou "finalizar"
            finalizar = request.POST.get('finalizar') == 'on'
            
            if finalizar:
                # Redirecionar para a visualização dos lançamentos do documento
                return redirect('documento_lancamentos', tis_id=tis.id, imovel_id=imovel.id, documento_id=lancamento.documento.id)
            else:
                # Redirecionar para criar um novo lançamento no mesmo documento
                return redirect('novo_lancamento_documento', tis_id=tis.id, imovel_id=imovel.id, documento_id=lancamento.documento.id)
            
        except Exception as e:
            messages.error(request, f'Erro ao atualizar lançamento: {str(e)}')
    
    # Obter pessoas do lançamento para exibição no formulário
    transmitentes = lancamento.pessoas.filter(tipo='transmitente')
    adquirentes = lancamento.pessoas.filter(tipo='adquirente')
    
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
        'modo_edicao': True
    }
    
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
            return redirect('documento_lancamentos', tis_id=tis_id, imovel_id=imovel_id, documento_id=documento_id)
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

def processar_pessoas_lancamento(lancamento, pessoas_data, pessoas_ids, pessoas_percentuais, tipo_pessoa):
    """
    Processa as pessoas (transmitentes ou adquirentes) de um lançamento
    """
    for i, nome in enumerate(pessoas_data):
        if nome and nome.strip():
            pessoa_id = pessoas_ids[i] if i < len(pessoas_ids) and pessoas_ids[i] else None
            percentual = pessoas_percentuais[i] if i < len(pessoas_percentuais) and pessoas_percentuais[i] else None
            
            # Se tem ID, usar a pessoa existente
            if pessoa_id and pessoa_id.strip():
                try:
                    pessoa = Pessoas.objects.get(id=pessoa_id)
                    # Atualizar nome se necessário
                    if pessoa.nome != nome.strip():
                        pessoa.nome = nome.strip()
                        pessoa.save()
                except Pessoas.DoesNotExist:
                    # Criar nova pessoa
                    pessoa = Pessoas.objects.create(nome=nome.strip())
            else:
                # Criar nova pessoa
                pessoa = Pessoas.objects.create(nome=nome.strip())
            
            # Criar relação com o lançamento
            lancamento_pessoa = lancamento.lancamentopessoa_set.create(
                pessoa=pessoa,
                tipo=tipo_pessoa,
                percentual=float(percentual) if percentual and percentual.strip() else None
            ) 