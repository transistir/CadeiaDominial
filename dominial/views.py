from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from .models import TIs, Imovel, TerraIndigenaReferencia, Documento, Lancamento, DocumentoTipo, LancamentoTipo
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
            print("Erros de formulário:", form.errors)

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

    # Ordenar por data mais recente
    lancamentos = lancamentos.order_by('-data')

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
    
    cartorios = Cartorios.objects.filter(estado=estado, cidade=cidade).order_by('nome')
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
    term = request.GET.get('term', '')
    pessoas = Pessoas.objects.filter(nome__icontains=term)[:10]
    results = [{'id': p.id, 'label': p.nome, 'value': p.nome} for p in pessoas]
    return JsonResponse(results, safe=False)

@login_required
def cadeia_dominial(request, tis_id, imovel_id):
    tis = get_object_or_404(TIs, id=tis_id)
    imovel = get_object_or_404(Imovel, id=imovel_id, terra_indigena_id=tis)
    documentos = Documento.objects.filter(imovel=imovel).order_by('data')
    
    # Se não há documentos, criar automaticamente um documento de matrícula baseado no imóvel
    if not documentos.exists():
        try:
            # Criar documento de matrícula automaticamente
            tipo_matricula = DocumentoTipo.objects.get(tipo='matricula')
            documento_matricula = Documento.objects.create(
                imovel=imovel,
                tipo=tipo_matricula,
                numero=imovel.matricula,
                data=imovel.data_cadastro,
                cartorio=imovel.cartorio or Cartorios.objects.first(),
                livro='',
                folha='',
                origem='Matrícula atual do imóvel',
                observacoes='Documento criado automaticamente para iniciar a cadeia dominial'
            )
            documentos = Documento.objects.filter(imovel=imovel).order_by('data')
            messages.info(request, f'Documento de matrícula "{imovel.matricula}" criado automaticamente.')
        except Exception as e:
            messages.error(request, f'Erro ao criar documento de matrícula: {str(e)}')
    
    # Verifica se existe apenas a matrícula atual
    matricula = documentos.filter(tipo__tipo='matricula').first()
    tem_apenas_matricula = documentos.count() == 1 and matricula is not None
    
    # Se tiver apenas matrícula, verifica se tem lançamentos
    tem_lancamentos = False
    if tem_apenas_matricula:
        tem_lancamentos = matricula.lancamentos.exists()
    
    context = {
        'tis': tis,
        'imovel': imovel,
        'documentos': documentos,
        'tem_apenas_matricula': tem_apenas_matricula,
        'tem_lancamentos': tem_lancamentos,
    }
    return render(request, 'dominial/cadeia_dominial.html', context)

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
        cartorio_id = request.POST.get('cartorio')
        livro = request.POST.get('livro')
        folha = request.POST.get('folha')
        origem = request.POST.get('origem')
        observacoes = request.POST.get('observacoes')

        try:
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
def novo_lancamento(request, tis_id, imovel_id):
    tis = get_object_or_404(TIs, id=tis_id)
    imovel = get_object_or_404(Imovel, id=imovel_id, terra_indigena_id=tis)
    documento_ativo = Documento.objects.filter(imovel=imovel).order_by('-data', '-id').first()
    
    # Se não há documento ativo, redirecionar para criar o primeiro documento
    if not documento_ativo:
        messages.warning(request, 'É necessário criar um documento antes de adicionar lançamentos.')
        return redirect('novo_documento', tis_id=tis.id, imovel_id=imovel.id)
    
    pessoas = Pessoas.objects.all().order_by('nome')
    cartorios = Cartorios.objects.all().order_by('nome')
    tipos_lancamento = LancamentoTipo.objects.all().order_by('tipo')
    
    if request.method == 'POST':
        tipo_id = request.POST.get('tipo')
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
        
        # Campos específicos por tipo
        forma = request.POST.get('forma')
        descricao = request.POST.get('descricao')
        titulo = request.POST.get('titulo')
        cartorio_origem_id = request.POST.get('cartorio_origem')
        livro_origem = request.POST.get('livro_origem')
        folha_origem = request.POST.get('folha_origem')
        data_origem = request.POST.get('data_origem')
        
        # Campos opcionais
        transmitente_id = request.POST.get('transmitente')
        adquirente_id = request.POST.get('adquirente')
        area = request.POST.get('area')
        origem = request.POST.get('origem_completa') or request.POST.get('origem')

        try:
            tipo_lanc = LancamentoTipo.objects.get(id=tipo_id)
            
            # Tratar campos vazios
            data_origem_clean = data_origem if data_origem and data_origem.strip() else None
            livro_origem_clean = livro_origem if livro_origem and livro_origem.strip() else None
            folha_origem_clean = folha_origem if folha_origem and folha_origem.strip() else None
            forma_clean = forma if forma and forma.strip() else None
            descricao_clean = descricao if descricao and descricao.strip() else None
            titulo_clean = titulo if titulo and titulo.strip() else None
            
            # Criar o lançamento
            lancamento = Lancamento.objects.create(
                documento=documento_ativo,
                tipo=tipo_lanc,
                numero_lancamento=numero_lancamento,
                data=data,
                observacoes=observacoes,
                eh_inicio_matricula=eh_inicio_matricula,
                forma=forma_clean,
                descricao=descricao_clean,
                titulo=titulo_clean,
                livro_origem=livro_origem_clean,
                folha_origem=folha_origem_clean,
                data_origem=data_origem_clean,
            )
            
            # Adicionar cartório de origem se fornecido
            if cartorio_origem_id:
                lancamento.cartorio_origem_id = cartorio_origem_id
            
            # Adicionar campos opcionais se fornecidos
            if transmitente_id:
                lancamento.transmitente_id = transmitente_id
            if adquirente_id:
                lancamento.adquirente_id = adquirente_id
            if area:
                lancamento.area = area
            if origem:
                lancamento.origem = origem
                
            lancamento.save()
            
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
            'name': f'{documento.get_tipo_display()}: {documento.numero}',
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
        lancamentos = documento.lancamentos.order_by('-data')
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