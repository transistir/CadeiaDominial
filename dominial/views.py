from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from .models import TIs, Imovel, TerraIndigenaReferencia, Documento, Lancamento, DocumentoTipo, LancamentoTipo, LancamentoPessoa
from django.contrib import messages
from .models import Imovel, TIs, Cartorios, Pessoas, Alteracoes
from .forms import TIsForm, ImovelForm
import logging
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods, require_POST
import requests
import json
from django.core.paginator import Paginator
from django.urls import reverse
from django.db.models import Count
from django.utils import timezone
from django.core.management import call_command
from dal import autocomplete
from datetime import date
import uuid
from django.db.models import Q

logger = logging.getLogger(__name__)

# Create your views here.

@login_required
def home(request):
    terras_indigenas = TIs.objects.all().order_by('nome')
    terras_referencia = TerraIndigenaReferencia.objects.all().order_by('nome')
    return render(request, 'dominial/home.html', {
        'terras_indigenas': terras_indigenas,
        'terras_referencia': terras_referencia
    })

@login_required
def tis_form(request):
    if request.method == 'POST':
        form = TIsForm(request.POST)
        if form.is_valid():
            try:
                form.save()
                messages.success(request, 'Terra Indígena cadastrada com sucesso!')
                return redirect('home')
            except Exception as e:
                messages.error(request, f'Erro ao cadastrar Terra Indígena: {str(e)}')
    else:
        form = TIsForm()
    
    return render(request, 'dominial/tis_form.html', {'form': form})

@login_required
def tis_detail(request, tis_id):
    tis = get_object_or_404(TIs, id=tis_id)
    imoveis = Imovel.objects.filter(terra_indigena_id=tis)
    return render(request, 'dominial/tis_detail.html', {
        'tis': tis,
        'imoveis': imoveis
    })

@login_required
def tis_delete(request, tis_id):
    if not request.user.is_staff:
        messages.error(request, 'Você não tem permissão para excluir terras indígenas.')
        return redirect('home')
        
    tis = get_object_or_404(TIs, id=tis_id)
    
    if request.method == 'POST':
        try:
            # Primeiro, excluir todos os imóveis associados
            Imovel.objects.filter(terra_indigena_id=tis).delete()
            
            # Depois, excluir a TI
            nome = tis.nome
            tis.delete()
            
            messages.success(request, f'Terra Indígena "{nome}" excluída com sucesso!')
            return redirect('home')
        except Exception as e:
            logger.error(f'Erro ao excluir Terra Indígena: {str(e)}')
            messages.error(request, f'Erro ao excluir Terra Indígena: {str(e)}')
    
    return render(request, 'dominial/tis_confirm_delete.html', {
        'tis': tis
    })

@login_required
def imovel_form(request, tis_id, imovel_id=None):
    tis = get_object_or_404(TIs, pk=tis_id)
    imovel = None
    
    if imovel_id:
        imovel = get_object_or_404(Imovel, pk=imovel_id)
        
    if request.method == 'POST':
        form = ImovelForm(request.POST, instance=imovel)
        
        # Obter o ID do cartório do POST
        cartorio_id = request.POST.get('cartorio_id')
        if cartorio_id:
            try:
                cartorio = Cartorios.objects.get(pk=cartorio_id)
                form.instance.cartorio = cartorio
            except Cartorios.DoesNotExist:
                pass
        
        if form.is_valid():
            imovel = form.save(commit=False)
            imovel.terra_indigena_id = tis

            proprietario_id = form.cleaned_data.get('proprietario')
            nome = form.cleaned_data.get('proprietario_nome')

            if proprietario_id:
                try:
                    imovel.proprietario = Pessoas.objects.get(id=proprietario_id)
                except Pessoas.DoesNotExist:
                    messages.error(request, 'O proprietário selecionado não foi encontrado.')
                    return render(request, 'dominial/imovel_form.html', {'form': form, 'tis': tis, 'imovel': imovel})
            else:
                # Criar novo proprietário
                cpf = request.POST.get('cpf')
                rg = request.POST.get('rg')
                data_nascimento = request.POST.get('data_nascimento')
                email = request.POST.get('email')
                telefone = request.POST.get('telefone')

                if nome and cpf:
                    nova_pessoa = Pessoas.objects.create(
                        nome=nome,
                        cpf=cpf,
                        rg=rg,
                        email=email,
                        telefone=telefone,
                        data_nascimento=data_nascimento if data_nascimento else None
                    )
                    imovel.proprietario = nova_pessoa
                else:
                    messages.error(request, "Para cadastrar novo proprietário, preencha pelo menos Nome e CPF.")
                    return render(request, 'dominial/imovel_form.html', {'form': form, 'tis': tis, 'imovel': imovel})

            imovel.save()
            messages.success(request, 'Imóvel cadastrado com sucesso!')
            return redirect('tis_detail', tis_id=tis_id)
        else:
            messages.error(request, 'Erro no formulário. Verifique os dados.')

    else:
        form = ImovelForm(instance=imovel)

    return render(request, 'dominial/imovel_form.html', {'form': form, 'tis': tis, 'imovel': imovel})

@login_required
def imovel_detail(request, tis_id, imovel_id):
    tis = get_object_or_404(TIs, id=tis_id)
    imovel = get_object_or_404(Imovel, id=imovel_id, terra_indigena_id=tis)
    
    if request.method == 'POST':
        form = ImovelForm(request.POST, instance=imovel)
        if form.is_valid():
            try:
                form.save()
                messages.success(request, 'Imóvel atualizado com sucesso!')
                return redirect('tis_detail', tis_id=tis.id)
            except Exception as e:
                messages.error(request, f'Erro ao atualizar imóvel: {str(e)}')
    else:
        form = ImovelForm(instance=imovel)
    
    return render(request, 'dominial/imovel_form.html', {
        'form': form,
        'tis': tis,
        'imovel': imovel
    })

@login_required
def imovel_delete(request, tis_id, imovel_id):
    tis = get_object_or_404(TIs, id=tis_id)
    imovel = get_object_or_404(Imovel, id=imovel_id, terra_indigena_id=tis)
    
    if request.method == 'POST':
        try:
            matricula = imovel.matricula
            imovel.delete()
            messages.success(request, f'Imóvel "{matricula}" excluído com sucesso!')
            return redirect('tis_detail', tis_id=tis.id)
        except Exception as e:
            messages.error(request, f'Erro ao excluir imóvel: {str(e)}')
    
    return render(request, 'dominial/imovel_confirm_delete.html', {
        'imovel': imovel,
        'tis': tis
    })

@login_required
def imoveis(request, tis_id=None):
    if tis_id:
        tis = get_object_or_404(TIs, id=tis_id)
        imoveis = Imovel.objects.filter(terra_indigena_id=tis).order_by('matricula')
    else:
        imoveis = Imovel.objects.all().order_by('matricula')
    return render(request, 'dominial/imoveis.html', {'imoveis': imoveis})

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

def pessoa_autocomplete(request):
    """View para autocomplete de pessoas"""
    query = request.GET.get('q', '').strip()
    
    if len(query) < 2:
        return JsonResponse([], safe=False)
    
    pessoas = Pessoas.objects.filter(nome__icontains=query).order_by('nome')[:10]
    
    results = []
    for pessoa in pessoas:
        results.append({
            'id': pessoa.id,
            'nome': pessoa.nome,
            'cpf': pessoa.cpf
        })
    
    return JsonResponse(results, safe=False)

def cartorio_autocomplete(request):
    """View para autocomplete de cartórios (qualquer cartório)"""
    query = request.GET.get('q', '').strip()
    
    if len(query) < 2:
        return JsonResponse([], safe=False)
    
    cartorios = Cartorios.objects.filter(nome__icontains=query).order_by('nome')[:10]
    
    results = []
    for cartorio in cartorios:
        results.append({
            'id': cartorio.id,
            'nome': cartorio.nome,
            'cidade': cartorio.cidade if cartorio.cidade else None
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

@login_required
def cadeia_dominial(request, tis_id, imovel_id):
    tis = get_object_or_404(TIs, id=tis_id)
    imovel = get_object_or_404(Imovel, id=imovel_id, terra_indigena_id=tis)
    
    # Verificar se há documentos
    documentos = Documento.objects.filter(imovel=imovel).order_by('data')
    tem_documentos = documentos.exists()
    
    # Verificar se há apenas matrícula (documento inicial)
    tem_apenas_matricula = documentos.count() == 1 and documentos.first().tipo.tipo == 'matricula'
    
    # Verificar se há lançamentos
    tem_lancamentos = False
    if tem_documentos:
        tem_lancamentos = Lancamento.objects.filter(documento__imovel=imovel).exists()
    
    # Verificar se deve mostrar a visualização de lançamentos (tronco principal)
    mostrar_lancamentos = request.GET.get('lancamentos') == 'true'
    
    context = {
        'tis': tis,
        'imovel': imovel,
        'documentos': documentos,
        'tem_apenas_matricula': tem_apenas_matricula,
        'tem_lancamentos': tem_lancamentos,
        'mostrar_lancamentos': mostrar_lancamentos,
    }
    
    if mostrar_lancamentos:
        return render(request, 'dominial/cadeia_dominial.html', context)
    else:
        return render(request, 'dominial/cadeia_dominial_arvore.html', context)

@login_required
def novo_documento(request, tis_id, imovel_id):
    tis = get_object_or_404(TIs, id=tis_id)
    imovel = get_object_or_404(Imovel, id=imovel_id, terra_indigena_id=tis)
    cartorios = Cartorios.objects.all().order_by('nome')
    
    # Buscar sugestões de matrículas/transcrições da origem do documento anterior
    sugestoes = []
    documento_anterior = Documento.objects.filter(imovel=imovel).order_by('-data', '-id').first()
    
    if documento_anterior:
        # Buscar lançamentos de início de matrícula no documento anterior
        lancamentos_inicio = Lancamento.objects.filter(
            documento=documento_anterior,
            eh_inicio_matricula=True
        )
        
        for lancamento in lancamentos_inicio:
            if lancamento.origem:
                # Extrair matrículas (M) e transcrições (T) da origem
                origens = lancamento.origem.split(';')
                for origem in origens:
                    origem = origem.strip()
                    if origem.startswith('M') or origem.startswith('T'):
                        sugestoes.append({
                            'valor': origem,
                            'tipo': 'Matrícula' if origem.startswith('M') else 'Transcrição',
                            'descricao': f"{'Matrícula' if origem.startswith('M') else 'Transcrição'} sugerida da origem do documento anterior"
                        })
    
    if request.method == 'POST':
        tipo = request.POST.get('tipo')
        numero = request.POST.get('numero')
        data = request.POST.get('data')
        cartorio_id = request.POST.get('cartorio_id')
        livro = request.POST.get('livro')
        folha = request.POST.get('folha')
        origem = request.POST.get('origem')
        observacoes = request.POST.get('observacoes')

        try:
            cartorio = None
            if cartorio_id:
                cartorio = Cartorios.objects.get(id=cartorio_id)
            tipo_doc = DocumentoTipo.objects.get(tipo=tipo)
            
            documento = Documento.objects.create(
                imovel=imovel,
                tipo=tipo_doc,
                numero=numero,
                data=data,
                cartorio=cartorio,
                livro=livro,
                folha=folha,
                origem=origem,
                observacoes=observacoes
            )
            
            messages.success(request, 'Documento criado com sucesso!')
            return redirect('cadeia_dominial', tis_id=tis.id, imovel_id=imovel.id)
            
        except Exception as e:
            messages.error(request, f'Erro ao criar documento: {str(e)}')
    
    context = {
        'tis': tis,
        'imovel': imovel,
        'cartorios': cartorios,
        'sugestoes': sugestoes,
    }
    return render(request, 'dominial/documento_form.html', context)

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
                'documento_ativo': documento_ativo,
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
                    'documento_ativo': documento_ativo,
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
            
            if cartorio_origem_id and cartorio_origem_id.strip():
                # Se tem ID, usar o cartório existente
                lancamento.cartorio_origem_id = cartorio_origem_id
            elif cartorio_origem_nome:
                # Se tem nome mas não tem ID, tentar encontrar ou criar o cartório
                try:
                    cartorio = Cartorios.objects.get(nome__iexact=cartorio_origem_nome)
                    lancamento.cartorio_origem = cartorio
                except Cartorios.DoesNotExist:
                    # Criar novo cartório (você pode adicionar mais campos se necessário)
                    cartorio = Cartorios.objects.create(
                        nome=cartorio_origem_nome,
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
            transmitentes_percentual = request.POST.getlist('transmitente_percentual[]')
            transmitente_ids = request.POST.getlist('transmitente[]')
            
            for i, nome in enumerate(transmitentes_data):
                nome = nome.strip()
                if not nome:  # Pular se o nome estiver vazio
                    continue
                    
                percentual = transmitentes_percentual[i] if i < len(transmitentes_percentual) else None
                pessoa_id = transmitente_ids[i] if i < len(transmitente_ids) else None
                
                # Validar se o ID não está vazio
                if pessoa_id and pessoa_id.strip():
                    try:
                        pessoa = Pessoas.objects.get(id=pessoa_id)
                    except (Pessoas.DoesNotExist, ValueError):
                        pessoa = None
                else:
                    pessoa = None
                    
                if not pessoa and nome:
                    # Tentar encontrar pessoa pelo nome primeiro
                    try:
                        pessoa = Pessoas.objects.get(nome__iexact=nome)
                    except Pessoas.DoesNotExist:
                        # Criar nova pessoa com CPF único
                        cpf_unico = f"000000000{str(uuid.uuid4().int)[:2]}"
                        pessoa = Pessoas.objects.create(
                            nome=nome,
                            cpf=cpf_unico
                        )
                if pessoa and percentual:
                    from .models import LancamentoPessoa
                    LancamentoPessoa.objects.create(
                        lancamento=lancamento,
                        pessoa=pessoa,
                        tipo='transmitente',
                        percentual=percentual if percentual else 100,
                        nome_digitado=nome.strip()
                    )
            
            # Processar adquirentes
            adquirentes_data = request.POST.getlist('adquirente_nome[]')
            adquirente_ids = request.POST.getlist('adquirente[]')
            adquirente_percentuais = request.POST.getlist('adquirente_percentual[]')
            
            for i in range(len(adquirente_ids)):
                nome = adquirentes_data[i].strip() if i < len(adquirentes_data) else None
                if not nome:  # Pular se o nome estiver vazio
                    continue
                    
                percentual = adquirente_percentuais[i].strip() if i < len(adquirente_percentuais) and adquirente_percentuais[i].strip() else None
                pessoa_id = adquirente_ids[i] if i < len(adquirente_ids) else None
                
                # Validar se o ID não está vazio
                if pessoa_id and pessoa_id.strip():
                    try:
                        pessoa = Pessoas.objects.get(id=pessoa_id)
                    except (Pessoas.DoesNotExist, ValueError):
                        pessoa = None
                else:
                    pessoa = None
                    
                if not pessoa and nome:
                    # Tentar encontrar pessoa pelo nome primeiro
                    try:
                        pessoa = Pessoas.objects.get(nome__iexact=nome)
                    except Pessoas.DoesNotExist:
                        # Criar nova pessoa com CPF único
                        cpf_unico = f"000000000{str(uuid.uuid4().int)[:2]}"
                        pessoa = Pessoas.objects.create(
                            nome=nome,
                            cpf=cpf_unico
                        )
                if pessoa and percentual:
                    from .models import LancamentoPessoa
                    LancamentoPessoa.objects.create(
                        lancamento=lancamento,
                        pessoa=pessoa,
                        tipo='adquirente',
                        percentual=percentual if percentual else 100,
                        nome_digitado=nome.strip()
                    )
            
            messages.success(request, 'Lançamento criado com sucesso!')
            
            # Sempre redirecionar para a cadeia dominial após salvar
            return redirect('cadeia_dominial', tis_id=tis.id, imovel_id=imovel.id)
                    
        except Exception as e:
            messages.error(request, f'Erro ao criar lançamento: {str(e)}')
    
    context = {
        'tis': tis,
        'imovel': imovel,
        'documento_ativo': documento_ativo,
        'pessoas': pessoas,
        'cartorios': cartorios,
        'tipos_lancamento': tipos_lancamento,
    }
    return render(request, 'dominial/lancamento_form.html', context)

@login_required
def cadeia_dominial_dados(request, tis_id, imovel_id):
    """Retorna os dados da cadeia dominial em formato JSON para o diagrama de árvore"""
    tis = get_object_or_404(TIs, id=tis_id)
    imovel = get_object_or_404(Imovel, id=imovel_id, terra_indigena_id=tis)
    
    documentos = Documento.objects.filter(imovel=imovel).prefetch_related('lancamentos', 'lancamentos__tipo').order_by('data')
    
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
        lancamentos = documento.lancamentos.order_by('id')
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
def cadeia_dominial_arvore(request, tis_id, imovel_id):
    """Retorna os dados da cadeia dominial em formato de árvore para o diagrama"""
    print(f"DEBUG: Iniciando cadeia_dominial_arvore - TIS: {tis_id}, Imóvel: {imovel_id}")
    
    try:
        tis = get_object_or_404(TIs, id=tis_id)
        print(f"DEBUG: TI encontrada: {tis.nome}")
        
        imovel = get_object_or_404(Imovel, id=imovel_id, terra_indigena_id=tis)
        print(f"DEBUG: Imóvel encontrado: {imovel.matricula}")
        
        # Obter todos os documentos do imóvel ordenados por data
        documentos = Documento.objects.filter(imovel=imovel).order_by('data')
        print(f"DEBUG: Documentos encontrados: {documentos.count()}")
        
        # Obter origens identificadas de lançamentos que ainda não foram convertidas em documentos
        origens_identificadas = []
        lancamentos_com_origem = Lancamento.objects.filter(
            documento__imovel=imovel,
            origem__isnull=False
        ).exclude(origem='')
        
        print(f"DEBUG: Lançamentos com origem: {lancamentos_com_origem.count()}")
        
        for lancamento in lancamentos_com_origem:
            if lancamento.origem:
                origens_processadas = processar_origens_para_documentos(lancamento.origem, imovel, lancamento)
                
                for origem_info in origens_processadas:
                    # Verificar se já existe um documento com esse número
                    documento_existente = Documento.objects.filter(imovel=imovel, numero=origem_info['numero']).first()
                    
                    if not documento_existente:
                        # Criar o documento automaticamente
                        try:
                            tipo_doc = DocumentoTipo.objects.get(tipo=origem_info['tipo'])
                            documento_criado = Documento.objects.create(
                                imovel=imovel,
                                tipo=tipo_doc,
                                numero=origem_info['numero'],
                                data=date.today(),
                                cartorio=imovel.cartorio if imovel.cartorio else Cartorios.objects.first(),
                                livro='1',  # Livro padrão
                                folha='1',  # Folha padrão
                                origem=f'Criado automaticamente a partir de origem: {origem_info["numero"]}',
                                observacoes=f'Documento criado automaticamente ao identificar origem "{origem_info["numero"]}" no lançamento {lancamento.numero_lancamento}'
                            )
                            
                            # Adicionar à lista de origens identificadas (agora são documentos criados)
                            origens_identificadas.append({
                                'codigo': origem_info['numero'],
                                'tipo': origem_info['tipo'],
                                'tipo_display': 'Matrícula' if origem_info['tipo'] == 'matricula' else 'Transcrição',
                                'lancamento_origem': lancamento.numero_lancamento,
                                'documento_origem': lancamento.documento.numero,
                                'data_identificacao': lancamento.data.strftime('%d/%m/%Y'),
                                'cor': '#28a745' if origem_info['tipo'] == 'matricula' else '#6f42c1',
                                'documento_id': documento_criado.id,
                                'ja_criado': True
                            })
                        except DocumentoTipo.DoesNotExist:
                            # Se o tipo não existir, apenas listar como origem identificada
                            origens_identificadas.append({
                                'codigo': origem_info['numero'],
                                'tipo': origem_info['tipo'],
                                'tipo_display': 'Matrícula' if origem_info['tipo'] == 'matricula' else 'Transcrição',
                                'lancamento_origem': lancamento.numero_lancamento,
                                'documento_origem': lancamento.documento.numero,
                                'data_identificacao': lancamento.data.strftime('%d/%m/%Y'),
                                'cor': '#28a745' if origem_info['tipo'] == 'matricula' else '#6f42c1',
                                'ja_criado': False
                            })
                    else:
                        # Documento já existe, adicionar como origem identificada criada
                        origens_identificadas.append({
                            'codigo': origem_info['numero'],
                            'tipo': origem_info['tipo'],
                            'tipo_display': 'Matrícula' if origem_info['tipo'] == 'matricula' else 'Transcrição',
                            'lancamento_origem': lancamento.numero_lancamento,
                            'documento_origem': lancamento.documento.numero,
                            'data_identificacao': lancamento.data.strftime('%d/%m/%Y'),
                            'cor': '#28a745' if origem_info['tipo'] == 'matricula' else '#6f42c1',
                            'documento_id': documento_existente.id,
                            'ja_criado': True
                        })
        
        print(f"DEBUG: Origens identificadas: {len(origens_identificadas)}")
        
        # Estrutura para armazenar a árvore
        arvore = {
            'imovel': {
                'id': imovel.id,
                'matricula': imovel.matricula,
                'nome': imovel.nome,
                'proprietario': imovel.proprietario.nome
            },
            'documentos': [],
            'origens_identificadas': [],
            'conexoes': []
        }
        
        # Mapear documentos por número para facilitar busca
        documentos_por_numero = {}
        
        # Processar cada documento
        for documento in documentos:
            doc_node = {
                'id': documento.id,
                'numero': documento.numero,
                'tipo': documento.tipo.tipo,
                'tipo_display': documento.tipo.get_tipo_display(),
                'data': documento.data.strftime('%d/%m/%Y'),
                'cartorio': documento.cartorio.nome,
                'livro': documento.livro,
                'folha': documento.folha,
                'origem': documento.origem or '',
                'observacoes': documento.observacoes or '',
                'total_lancamentos': documento.lancamentos.count(),
                'x': 0,  # Posição X (será calculada pelo frontend)
                'y': 0,  # Posição Y (será calculada pelo frontend)
                'nivel': 0  # Nível na árvore (será calculado)
            }
            
            documentos_por_numero[documento.numero] = doc_node
            arvore['documentos'].append(doc_node)
        
        print(f"DEBUG: Documentos processados: {len(arvore['documentos'])}")
        
        # Criar conexões baseadas nas origens dos documentos e lançamentos
        for documento in documentos:
            # Verificar origem do documento
            if documento.origem:
                # Extrair códigos de origem (M ou T seguidos de números)
                import re
                origens = re.findall(r'[MT]\d+', documento.origem)
                
                # Se não encontrou padrões M/T, tentar extrair números
                if not origens:
                    numeros = re.findall(r'\d+', documento.origem)
                    origens = numeros
                
                # Se ainda não encontrou, verificar se há referência a outros documentos
                if not origens and 'matrícula' in documento.origem.lower():
                    # Procurar por documentos que podem ser a matrícula atual
                    for outro_doc in documentos:
                        if outro_doc.tipo.tipo == 'matricula' and outro_doc != documento:
                            origens = [outro_doc.numero]
                            break
                
                for origem in origens:
                    # Evitar auto-referências
                    if origem != documento.numero and origem in documentos_por_numero:
                        conexao = {
                            'from': origem,  # Documento de origem
                            'to': documento.numero,  # Documento atual
                            'tipo': 'origem'
                        }
                        arvore['conexoes'].append(conexao)
            
            # Verificar origens dos lançamentos do documento
            lancamentos = documento.lancamentos.all()
            for lancamento in lancamentos:
                if lancamento.origem:
                    # Extrair códigos de origem dos lançamentos
                    import re
                    origens_lancamento = re.findall(r'[MT]\d+', lancamento.origem)
                    
                    for origem in origens_lancamento:
                        # Evitar auto-referências e verificar se existe um documento com esse número
                        if origem != documento.numero and origem in documentos_por_numero:
                            conexao = {
                                'from': origem,  # Documento de origem
                                'to': documento.numero,  # Documento atual
                                'tipo': 'origem_lancamento'
                            }
                            # Evitar duplicatas
                            if not any(c['from'] == origem and c['to'] == documento.numero for c in arvore['conexoes']):
                                arvore['conexoes'].append(conexao)
        
        print(f"DEBUG: Conexões criadas: {len(arvore['conexoes'])}")
        
        # Calcular níveis da árvore de forma hierárquica correta
        # Nível 0: Matrícula atual (documento principal)
        # Nível 1: Documentos que aparecem como origem na matrícula atual
        # Nível 2: Documentos que aparecem como origem nos documentos do nível 1
        # E assim por diante...
        
        # Identificar a matrícula atual (documento principal)
        matricula_atual = None
        for doc_node in arvore['documentos']:
            if not doc_node['origem'] or doc_node['origem'] == '' or 'Matrícula atual' in doc_node['origem'] or 'Criado automaticamente' not in doc_node['origem']:
                matricula_atual = doc_node['numero']
                break
        
        # Se não encontrou matrícula atual, usar o primeiro documento
        if not matricula_atual and arvore['documentos']:
            matricula_atual = arvore['documentos'][0]['numero']
        
        print(f"DEBUG: Matrícula atual identificada: {matricula_atual}")
        
        # Definir níveis de forma hierárquica
        niveis_hierarquicos = {}
        
        # Nível 0: Matrícula atual
        niveis_hierarquicos[matricula_atual] = 0
        
        # Nível 1: Documentos que são referenciados pela matrícula atual
        documentos_nivel_1 = []
        for conexao in arvore['conexoes']:
            if conexao['to'] == matricula_atual:  # Se a matrícula atual referencia este documento
                documentos_nivel_1.append(conexao['from'])
                niveis_hierarquicos[conexao['from']] = 1
                print(f"DEBUG: {conexao['from']} definido como nível 1 (referenciado por {matricula_atual})")
        
        # Nível 2: Documentos que são referenciados pelos documentos do nível 1
        documentos_nivel_2 = []
        for conexao in arvore['conexoes']:
            if conexao['to'] in documentos_nivel_1:  # Se um documento do nível 1 referencia este documento
                if conexao['from'] not in niveis_hierarquicos:  # Se ainda não foi definido
                    documentos_nivel_2.append(conexao['from'])
                    niveis_hierarquicos[conexao['from']] = 2
                    print(f"DEBUG: {conexao['from']} definido como nível 2 (referenciado por {conexao['to']})")
        
        # Nível 3+: Continuar para níveis mais profundos se necessário
        nivel_atual = 3
        documentos_nivel_anterior = documentos_nivel_2.copy()
        
        while documentos_nivel_anterior:
            documentos_nivel_atual = []
            for conexao in arvore['conexoes']:
                if conexao['to'] in documentos_nivel_anterior:  # Se um documento do nível anterior referencia este documento
                    if conexao['from'] not in niveis_hierarquicos:  # Se ainda não foi definido
                        documentos_nivel_atual.append(conexao['from'])
                        niveis_hierarquicos[conexao['from']] = nivel_atual
                        print(f"DEBUG: {conexao['from']} definido como nível {nivel_atual} (referenciado por {conexao['to']})")
            
            documentos_nivel_anterior = documentos_nivel_atual
            nivel_atual += 1
        
        # Aplicar níveis aos documentos
        for doc_node in arvore['documentos']:
            doc_node['nivel'] = niveis_hierarquicos.get(doc_node['numero'], 0)
        
        print(f"DEBUG: Níveis hierárquicos finais: {[(doc['numero'], doc['tipo'], doc['nivel']) for doc in arvore['documentos']]}")
        
        # Adicionar apenas origens que ainda não foram convertidas em documentos
        origens_finais = []
        for origem in origens_identificadas:
            if not origem['ja_criado']:
                origens_finais.append(origem)
        
        arvore['origens_identificadas'] = origens_finais
        
        print(f"DEBUG: Origens finais (não criadas): {len(origens_finais)}")
        
        return JsonResponse(arvore, safe=False)
        
    except Exception as e:
        print(f"DEBUG: Erro na view: {str(e)}")
        import traceback
        traceback.print_exc()
        return JsonResponse({'error': str(e)}, status=500)

@login_required
def documento_lancamentos(request, tis_id, imovel_id, documento_id):
    """Visualiza os lançamentos de um documento específico"""
    tis = get_object_or_404(TIs, id=tis_id)
    imovel = get_object_or_404(Imovel, id=imovel_id, terra_indigena_id=tis)
    documento = get_object_or_404(Documento, id=documento_id, imovel=imovel)
    
    # Obter lançamentos ordenados por ordem de inserção
    lancamentos = documento.lancamentos.all().order_by('id')
    
    # Verificar se o usuário é admin para permitir edição
    pode_editar = request.user.is_staff or request.user.is_superuser
    
    context = {
        'tis': tis,
        'imovel': imovel,
        'documento': documento,
        'lancamentos': lancamentos,
        'pode_editar': pode_editar,
    }
    
    return render(request, 'dominial/documento_lancamentos.html', context)

@login_required
def selecionar_documento_lancamento(request, tis_id, imovel_id):
    """Página para selecionar em qual documento adicionar um novo lançamento"""
    tis = get_object_or_404(TIs, id=tis_id)
    imovel = get_object_or_404(Imovel, id=imovel_id, terra_indigena_id=tis)
    
    # Obter todos os documentos do imóvel ordenados por data
    documentos = Documento.objects.filter(imovel=imovel).order_by('-data')
    
    context = {
        'tis': tis,
        'imovel': imovel,
        'documentos': documentos,
    }
    
    return render(request, 'dominial/selecionar_documento_lancamento.html', context)

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
                lancamento.area = request.POST.get('area', '').strip() if request.POST.get('area') else None
                lancamento.origem = request.POST.get('origem_completa', '').strip() if request.POST.get('origem_completa') else None
                lancamento.descricao = request.POST.get('descricao', '').strip() if request.POST.get('descricao') else None
                lancamento.titulo = request.POST.get('titulo', '').strip() if request.POST.get('titulo') else None
            elif lancamento.tipo.tipo == 'registro':
                lancamento.cartorio_origem = request.POST.get('cartorio_origem', '').strip() if request.POST.get('cartorio_origem') else None
                lancamento.livro_origem = livro_origem_clean
                lancamento.folha_origem = folha_origem_clean
                lancamento.data_origem = request.POST.get('data_origem') if request.POST.get('data_origem') else None
            elif lancamento.tipo.tipo == 'inicio_matricula':
                lancamento.area = request.POST.get('area', '').strip() if request.POST.get('area') else None
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
            from .models import LancamentoPessoa
            LancamentoPessoa.objects.filter(lancamento=lancamento).delete()
            
            # Processar transmitentes
            transmitentes_data = []
            transmitente_ids = request.POST.getlist('transmitente[]')
            transmitente_nomes = request.POST.getlist('transmitente_nome[]')
            transmitente_percentuais = request.POST.getlist('transmitente_percentual[]')
            
            for i in range(len(transmitente_ids)):
                if transmitente_ids[i] and transmitente_ids[i].strip():
                    transmitentes_data.append({
                        'id': transmitente_ids[i].strip(),
                        'percentual': transmitente_percentuais[i].strip() if i < len(transmitente_percentuais) and transmitente_percentuais[i].strip() else None
                    })
                elif transmitente_nomes[i] and transmitente_nomes[i].strip():
                    # Criar nova pessoa
                    pessoa = Pessoas.objects.create(nome=transmitente_nomes[i].strip())
                    transmitentes_data.append({
                        'id': pessoa.id,
                        'percentual': transmitente_percentuais[i].strip() if i < len(transmitente_percentuais) and transmitente_percentuais[i].strip() else None
                    })
            
            # Adicionar transmitentes ao lançamento
            for transmitente_data in transmitentes_data:
                pessoa = Pessoas.objects.get(id=transmitente_data['id'])
                lancamento.pessoas.add(pessoa, through_defaults={
                    'tipo': 'transmitente',
                    'percentual': transmitente_data['percentual']
                })
            
            # Processar adquirentes
            adquirentes_data = request.POST.getlist('adquirente_nome[]')
            adquirente_ids = request.POST.getlist('adquirente[]')
            adquirente_percentuais = request.POST.getlist('adquirente_percentual[]')
            
            for i in range(len(adquirente_ids)):
                if adquirente_ids[i] and adquirente_ids[i].strip():
                    adquirentes_data.append({
                        'id': adquirente_ids[i].strip(),
                        'percentual': adquirente_percentuais[i].strip() if i < len(adquirente_percentuais) and adquirente_percentuais[i].strip() else None
                    })
                elif adquirente_nomes[i] and adquirente_nomes[i].strip():
                    # Criar nova pessoa
                    pessoa = Pessoas.objects.create(nome=adquirente_nomes[i].strip())
                    adquirentes_data.append({
                        'id': pessoa.id,
                        'percentual': adquirente_percentuais[i].strip() if i < len(adquirente_percentuais) and adquirente_percentuais[i].strip() else None
                    })
            
            # Adicionar adquirentes ao lançamento
            for adquirente_data in adquirentes_data:
                pessoa = Pessoas.objects.get(id=adquirente_data['id'])
                lancamento.pessoas.add(pessoa, through_defaults={
                    'tipo': 'adquirente',
                    'percentual': adquirente_data['percentual']
                })
            
            messages.success(request, f'Lançamento "{lancamento.numero_lancamento}" atualizado com sucesso!')
            
            # Sempre redirecionar para a cadeia dominial após salvar
            return redirect('documento_lancamentos', tis_id=tis_id, imovel_id=imovel_id, documento_id=lancamento.documento.id)
            
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

def processar_origens_para_documentos(origem_texto, imovel, lancamento):
    """
    Processa o texto de origem e identifica códigos de documentos para criação automática.
    Retorna uma lista de dicionários com informações dos documentos identificados.
    """
    import re
    from datetime import date
    
    # Padrões para identificar códigos de documentos
    # M123456 = Matrícula, T123456 = Transcrição
    padrao_matricula = r'\bM\d+\b'
    padrao_transcricao = r'\bT\d+\b'
    
    documentos_identificados = []
    
    # Buscar matrículas
    matriculas = re.findall(padrao_matricula, origem_texto, re.IGNORECASE)
    for codigo in matriculas:
        # Sempre adicionar a origem identificada, independente se o documento existe
        documentos_identificados.append({
            'tipo': 'matricula',
            'numero': codigo,
            'codigo_origem': codigo,
            'lancamento_origem': lancamento
        })
    
    # Buscar transcrições
    transcricoes = re.findall(padrao_transcricao, origem_texto, re.IGNORECASE)
    for codigo in transcricoes:
        # Sempre adicionar a origem identificada, independente se o documento existe
        documentos_identificados.append({
            'tipo': 'transcricao',
            'numero': codigo,
            'codigo_origem': codigo,
            'lancamento_origem': lancamento
        })
    
    # Salvar as origens identificadas no lançamento para referência futura
    if documentos_identificados:
        lancamento.origem_processada = origem_texto
        lancamento.save()
    
    return documentos_identificados

def criar_documento_automatico(request, tis_id, imovel_id, codigo_origem):
    """
    Cria um documento automaticamente baseado no código de origem fornecido.
    """
    tis = get_object_or_404(TIs, id=tis_id)
    imovel = get_object_or_404(Imovel, id=imovel_id, terra_indigena_id=tis)
    
    # Determinar o tipo baseado no prefixo
    if codigo_origem.upper().startswith('M'):
        tipo_documento = 'matricula'
    elif codigo_origem.upper().startswith('T'):
        tipo_documento = 'transcricao'
    else:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'error': f'Código de origem "{codigo_origem}" não é válido.'}, status=400)
        messages.error(request, f'Código de origem "{codigo_origem}" não é válido.')
        return redirect('cadeia_dominial', tis_id=tis_id, imovel_id=imovel_id)
    
    try:
        # Verificar se já existe um documento com esse número
        if Documento.objects.filter(imovel=imovel, numero=codigo_origem).exists():
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'error': f'Documento "{codigo_origem}" já existe.'}, status=400)
            messages.warning(request, f'Documento "{codigo_origem}" já existe.')
            return redirect('cadeia_dominial', tis_id=tis_id, imovel_id=imovel_id)
        
        # Obter o tipo de documento
        tipo_doc = DocumentoTipo.objects.get(tipo=tipo_documento)
        
        # Criar o documento
        documento = Documento.objects.create(
            imovel=imovel,
            tipo=tipo_doc,
            numero=codigo_origem,
            data=date.today(),
            cartorio=imovel.cartorio if imovel.cartorio else Cartorios.objects.first(),
            livro='1',  # Livro padrão
            folha='1',  # Folha padrão
            origem=f'Criado automaticamente a partir de origem: {codigo_origem}',
            observacoes=f'Documento criado automaticamente ao clicar no card de origem "{codigo_origem}"'
        )
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'message': f'Documento "{codigo_origem}" criado com sucesso!',
                'documento_id': documento.id
            })
        
        messages.success(request, f'Documento "{codigo_origem}" criado com sucesso!')
        
        # Redirecionar para o novo documento
        return redirect('documento_lancamentos', tis_id=tis_id, imovel_id=imovel_id, documento_id=documento.id)
        
    except DocumentoTipo.DoesNotExist:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'error': f'Tipo de documento "{tipo_documento}" não encontrado.'}, status=400)
        messages.error(request, f'Tipo de documento "{tipo_documento}" não encontrado.')
        return redirect('cadeia_dominial', tis_id=tis_id, imovel_id=imovel_id)
    except Exception as e:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'error': f'Erro ao criar documento: {str(e)}'}, status=500)
        messages.error(request, f'Erro ao criar documento: {str(e)}')
        return redirect('cadeia_dominial', tis_id=tis_id, imovel_id=imovel_id)

@login_required
def editar_documento(request, documento_id, tis_id, imovel_id):
    """View para editar um documento existente"""
    tis = get_object_or_404(TIs, id=tis_id)
    imovel = get_object_or_404(Imovel, id=imovel_id, terra_indigena_id=tis)
    documento = get_object_or_404(Documento, id=documento_id, imovel=imovel)
    
    if request.method == 'POST':
        try:
            # Atualizar dados do documento
            documento.numero = request.POST.get('numero', '').strip()
            documento.data = request.POST.get('data') if request.POST.get('data') else None
            documento.origem = request.POST.get('origem', '').strip()
            documento.observacoes = request.POST.get('observacoes', '').strip()
            documento.livro = request.POST.get('livro', '').strip()
            documento.folha = request.POST.get('folha', '').strip()
            
            # Atualizar cartório se fornecido
            cartorio_id = request.POST.get('cartorio_id')
            if cartorio_id:
                documento.cartorio = Cartorios.objects.get(id=cartorio_id)
            else:
                documento.cartorio = None
            
            documento.save()
            
            messages.success(request, f'Documento "{documento.numero}" atualizado com sucesso!')
            return redirect('documento_lancamentos', tis_id=tis_id, imovel_id=imovel_id, documento_id=documento.id)
            
        except Exception as e:
            messages.error(request, f'Erro ao atualizar documento: {str(e)}')
    else:
        # Formulário de edição
        cartorios = Cartorios.objects.all().order_by('nome')
        tipos_documento = DocumentoTipo.objects.all().order_by('tipo')
        
        context = {
            'tis': tis,
            'imovel': imovel,
            'documento': documento,
            'cartorios': cartorios,
            'tipos_documento': tipos_documento,
            'modo': 'editar'
        }
        
        return render(request, 'dominial/documento_form.html', context)