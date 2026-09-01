from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.http import require_http_methods, require_POST
from django.http import Http404, JsonResponse
from django.db.models import Prefetch
from ..models import TIs, Imovel, Lancamento, Pessoas, Cartorios, Documento, LancamentoPessoa, FimCadeia
from ..services.lancamento_service import LancamentoService
from ..utils.hierarquia_utils import processar_origens_para_documentos
from datetime import date
import unicodedata
import uuid
from ..services.lancamento_heranca_service import LancamentoHerancaService
from ..services.lancamento_duplicata_service import LancamentoDuplicataService
from ..services.documento_service import DocumentoService
from ..services.lancamento_consulta_service import LancamentoConsultaService


def _build_fim_cadeia_opcoes():
    """Siglas de destacamento do patrimônio público oferecidas no select do
       formulário de fim de cadeia (issue #104).

       A sigla é o valor gravado no lançamento, então cadastros sem sigla ficam
       de fora — não teriam valor para selecionar."""
    return list(
        FimCadeia.objects
        .filter(tipo='destacamento_publico', ativo=True)
        .exclude(sigla__isnull=True)
        .exclude(sigla='')
        .order_by('nome')
        .values('nome', 'sigla')
    )


def _build_documento_lancamentos(documento, current_lancamento_id=None):
    """Constrói lista de lançamentos do documento para o sidebar de navegação.
       Ordem: do maior número simples para o menor (igual à tabela detalhada)."""
    lancamentos = list(
        Lancamento.objects
        .filter(documento=documento)
        .select_related('tipo')
    )
    # Mesma ordenação do documento_detalhado:
    # número extraído decrescente, depois id crescente
    lancamentos.sort(key=lambda x: (
        -LancamentoConsultaService._extrair_numero_simples(x.numero_lancamento),
        x.id
    ))
    return [
        {
            'id': lanc.id,
            'display': lanc.numero_lancamento or f'#{lanc.id}',
            'is_current': current_lancamento_id is not None and lanc.id == current_lancamento_id,
        }
        for lanc in lancamentos
    ]


class LancamentoForaDaCadeiaError(Exception):
    """O lançamento existe, mas o documento dele não é referenciado — direta
       nem indiretamente — na cadeia dominial deste imóvel."""
    def __init__(self, lancamento):
        self.lancamento = lancamento
        super().__init__(f'Lançamento {lancamento.id} fora da cadeia do imóvel')


def _resolver_lancamento_no_contexto_do_imovel(imovel, lancamento_id):
    """Resolve um lançamento visto pela URL de `imovel`, aceitando documentos
       compartilhados (importados) — o mesmo cenário que o `documento_detalhado`
       já suporta (issue #152).

       Retorna (lancamento, is_lancamento_do_imovel).
       Levanta Http404 se o lançamento não existe.
       Levanta LancamentoForaDaCadeiaError se existe mas o documento dele não é
       referenciado nesta cadeia (protege contra exclusão/edição de homônimo em
       outra cadeia — ver test_divida_edicao_lancamento_homonimo.py)."""
    try:
        return Lancamento.objects.get(id=lancamento_id, documento__imovel=imovel), True
    except Lancamento.DoesNotExist:
        pass

    try:
        lancamento = Lancamento.objects.get(id=lancamento_id)
    except Lancamento.DoesNotExist:
        raise Http404("Lançamento não encontrado")

    # imports locais: preservar como estão hoje para não alterar o grafo de
    # imports do módulo
    from ..models import Lancamento as LancamentoModel
    from ..services.hierarquia_arvore_service import HierarquiaArvoreService
    from ..services.lancamento_origem_leitura_service import LancamentoOrigemLeituraService

    # Verificar referência direta pela identidade completa (tipo +
    # número normalizado + cartório), nunca por número isolado: um
    # texto de origem que apenas contenha o mesmo número não prova
    # que é o mesmo documento - pode ser um homônimo em outro
    # cartório que não pertence à cadeia deste imóvel.
    documento_referenciado = lancamento.documento
    lancamentos_referenciando_direta = False
    for lanc_do_imovel in LancamentoModel.objects.filter(documento__imovel=imovel):
        for origem_info in LancamentoOrigemLeituraService.obter_origens(lanc_do_imovel):
            if (
                origem_info.tipo_documento == documento_referenciado.tipo.tipo
                and origem_info.numero_normalizado == documento_referenciado.numero_normalizado
                and origem_info.cartorio_id == documento_referenciado.cartorio_id
            ):
                lancamentos_referenciando_direta = True
                break
        if lancamentos_referenciando_direta:
            break

    # Verificar referência indireta (através da cadeia dominial)
    lancamentos_referenciando_indireta = False
    if not lancamentos_referenciando_direta:
        # Usar o HierarquiaArvoreService para verificar se o documento aparece na cadeia dominial
        arvore = HierarquiaArvoreService.construir_arvore_cadeia_dominial(imovel)
        documento_na_arvore = any(
            doc['id'] == lancamento.documento.id and doc['is_compartilhado']
            for doc in arvore['documentos']
        )
        lancamentos_referenciando_indireta = documento_na_arvore

    if not lancamentos_referenciando_direta and not lancamentos_referenciando_indireta:
        raise LancamentoForaDaCadeiaError(lancamento)

    return lancamento, False


def _form_data_do_post(request):
    """Reconstrói o estado do formulário de lançamento a partir do POST para
       re-renderizar o formulário sem perder o que o usuário digitou depois de
       um erro de validação ou do fluxo de duplicata (issue #157).

       Inclui os 7 campos do bloco Transmissão (`*_transacao`), que antes eram
       lidos por nomes fantasmas (`forma`/`titulo`) e nunca sobreviviam."""
    return {
        'tipo_lancamento': request.POST.get('tipo_lancamento'),
        'numero_lancamento': request.POST.get('numero_lancamento'),
        'numero_lancamento_simples': request.POST.get('numero_lancamento_simples'),
        'data': request.POST.get('data'),
        'observacoes': request.POST.get('observacoes'),
        'transmitente_ids': request.POST.getlist('transmitente[]'),
        'transmitente_nomes': request.POST.getlist('transmitente_nome[]'),
        'adquirente_ids': request.POST.getlist('adquirente[]'),
        'adquirente_nomes': request.POST.getlist('adquirente_nome[]'),
        'area': request.POST.get('area'),
        'descricao': request.POST.get('descricao'),
        # Campos específicos por tipo
        'forma_averbacao': request.POST.get('forma_averbacao'),
        # Bloco Transmissão (issue #157) — `registro`/`inicio_matricula` também
        # leem `forma_transacao` (os nomes `forma_registro`/`forma_inicio` eram
        # fantasmas, sem emitter em template).
        'forma_transacao': request.POST.get('forma_transacao'),
        'titulo_transacao': request.POST.get('titulo_transacao'),
        'cartorio_transmissao': request.POST.get('cartorio_transmissao'),
        'cartorio_transmissao_nome': request.POST.get('cartorio_transmissao_nome'),
        'livro_transacao': request.POST.get('livro_transacao'),
        'folha_transacao': request.POST.get('folha_transacao'),
        'data_transacao': request.POST.get('data_transacao'),
    }


def _build_novo_lancamento_context(request, tis, imovel, documento_ativo, pessoas,
                                   cartorios, tipos_lancamento, emitir_avisos=True):
    """Contexto base do formulário de novo lançamento — fonte única de verdade.

       Reúne os metadados do documento e a lógica de herança de cartório
       (`is_primeiro_lancamento` / `lancamento` herdado / `cartorio_matricula`).

       Tanto o branch GET quanto o re-render de erro
       (`_render_erro_novo_lancamento`) chamam esta função. Antes, o caminho de
       erro caía no fluxo GET e essa metadata de cartório/herança se perdia
       (issue #157).

       `emitir_avisos=False` no re-render de erro para não duplicar o aviso de
       cartório indefinido."""
    context = {
        'tis': tis,
        'imovel': imovel,
        'documento': documento_ativo,
        'pessoas': pessoas,
        'cartorios': cartorios,
        'tipos_lancamento': tipos_lancamento,
        'transmitentes': [],
        'adquirentes': [],
        'is_documento_importado': getattr(documento_ativo, 'is_importado', False),  # Usar flag do service
        'cartorio_origem_correto': documento_ativo.cartorio,  # SEMPRE passar o cartório correto
        'documento_lancamentos': _build_documento_lancamentos(documento_ativo, current_lancamento_id=None),
        'is_novo_lancamento': True,
        'fim_cadeia_opcoes': _build_fim_cadeia_opcoes(),
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
            if not imovel.cartorio and emitir_avisos:
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

        context['lancamento'] = lancamento_herdado
        context['modo_edicao'] = True  # Para usar os dados herdados no template

        # CORREÇÃO: Adicionar cartorio_origem_correto para o template usar
        context['cartorio_origem_correto'] = documento_ativo.cartorio

    return context


def _render_erro_novo_lancamento(request, tis, imovel, documento_ativo, pessoas,
                                 cartorios, tipos_lancamento,
                                 numero_lancamento_error=False):
    """Re-renderiza o formulário de novo lançamento preservando o POST.

       Usado tanto pelo branch de falha de validação (`sucesso is None`) quanto
       pelo `except` — antes só o `except` re-renderizava e o branch de falha
       caía no fluxo GET, perdendo TODOS os campos digitados (issue #157)."""
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

    # Buscar lançamentos anteriores (para painel lateral mesmo em caso de erro)
    lancamentos_anteriores = (
        Lancamento.objects
        .filter(documento=documento_ativo)
        .select_related('tipo', 'documento')
        .prefetch_related(
            Prefetch('pessoas', queryset=LancamentoPessoa.objects.select_related('pessoa'))
        )
        .order_by('-data', '-id')[:20]
    )
    lancamentos_com_pessoas = []
    for lanc in lancamentos_anteriores:
        relacoes = lanc.pessoas.all()
        transmitentes = [lp.pessoa for lp in relacoes if lp.tipo == 'transmitente']
        adquirentes = [lp.pessoa for lp in relacoes if lp.tipo == 'adquirente']
        lancamentos_com_pessoas.append({
            'lancamento': lanc,
            'transmitentes': transmitentes,
            'adquirentes': adquirentes,
        })

    # Partir do contexto base (mesma fonte do branch GET): herança de cartório,
    # is_primeiro_lancamento, cartorio_matricula, fim_cadeia_opcoes, etc.
    context = _build_novo_lancamento_context(
        request, tis, imovel, documento_ativo, pessoas, cartorios, tipos_lancamento,
        emitir_avisos=False,
    )

    # O `modo_edicao` fica exatamente como o builder o definiu — igual ao branch
    # GET (herança → True + `lancamento` herdado; primeiro lançamento da cadeia →
    # `is_primeiro_lancamento`). Não forçamos `modo_edicao=False`: o `lancamento`
    # herdado é um `Lancamento()` vazio (só `cartorio_origem`), então todo guard
    # `modo_edicao and lancamento.X` do bloco Transmissão
    # (lancamento_form.html:124-160) já é False e o `form_data` do POST vence.
    # Forçar False zerava os hidden `cartorio`/`cartorio_nome` que o GET preenche
    # (issue #157, revisão Codex round-2).

    context.update({
        'form_data': _form_data_do_post(request),
        'numero_lancamento_error': numero_lancamento_error,
        'lancamentos_com_pessoas': lancamentos_com_pessoas,
        'transmitentes': transmitentes_data,
        'adquirentes': adquirentes_data,
    })

    return render(request, 'dominial/lancamento_form.html', context)


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
        # Primeiro, tentar encontrar no imóvel atual
        try:
            documento_ativo = Documento.objects.get(id=documento_id, imovel=imovel)
        except Documento.DoesNotExist:
            # Se não encontrou no imóvel atual, pode ser um documento importado
            try:
                documento_ativo = Documento.objects.get(id=documento_id)
                # Redirecionar para o imóvel correto
                messages.info(request, '📄 Documento importado — redirecionado para o imóvel de origem.')
                return redirect(
                    'novo_lancamento_documento',
                    tis_id=documento_ativo.imovel.terra_indigena_id_id,
                    imovel_id=documento_ativo.imovel.id,
                    documento_id=documento_id,
                )
            except Documento.DoesNotExist:
                raise Http404("Documento não encontrado")
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
                        'descricao': request.POST.get('descricao'),
                        # Bloco Transmissão (issue #157): antes lia os nomes
                        # fantasmas 'forma'/'titulo' e não repassava os hidden
                        # fields, perdendo o bloco no fluxo de duplicata.
                        'forma_transacao': request.POST.get('forma_transacao'),
                        'titulo_transacao': request.POST.get('titulo_transacao'),
                        'cartorio_transmissao': request.POST.get('cartorio_transmissao'),
                        'cartorio_transmissao_nome': request.POST.get('cartorio_transmissao_nome'),
                        'livro_transacao': request.POST.get('livro_transacao'),
                        'folha_transacao': request.POST.get('folha_transacao'),
                        'data_transacao': request.POST.get('data_transacao'),
                        'origem_completa': request.POST.getlist('origem_completa[]'),
                        'cartorio_origem': request.POST.getlist('cartorio_origem[]'),
                        'cartorio_origem_nome': request.POST.getlist('cartorio_origem_nome[]'),
                        'livro_origem': request.POST.getlist('livro_origem[]'),
                        'folha_origem': request.POST.getlist('folha_origem[]'),
                        'transmitente': request.POST.getlist('transmitente[]'),
                        'transmitente_nome': request.POST.getlist('transmitente_nome[]'),
                        'adquirente': request.POST.getlist('adquirente[]'),
                        'adquirente_nome': request.POST.getlist('adquirente_nome[]'),
                        # Preservar campos de fim de cadeia
                        'fim_cadeia': request.POST.getlist('fim_cadeia[]'),
                        'tipo_fim_cadeia': request.POST.getlist('tipo_fim_cadeia[]'),
                        'classificacao_fim_cadeia': request.POST.getlist('classificacao_fim_cadeia[]'),
                        'sigla_patrimonio_publico': request.POST.getlist('sigla_patrimonio_publico[]'),
                        'info_adicional_fim_cadeia': request.POST.getlist('info_adicional_fim_cadeia[]'),
                        'especificacao_fim_cadeia': request.POST.getlist('especificacao_fim_cadeia[]'),
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
                    # Redirecionar para a página do documento detalhado
                    return redirect('documento_detalhado', tis_id=tis.id, imovel_id=imovel.id, documento_id=documento_ativo.id)
            else:
                # Falha de validação (ex.: número de lançamento duplicado):
                # o service retorna (None, mensagem). Antes NÃO havia return
                # aqui e o fluxo caía no branch GET, re-renderizando o
                # formulário sem `form_data` — perdendo TODOS os campos
                # digitados, inclusive o bloco Transmissão (issue #157).
                messages.error(request, mensagem_origens)
                numero_lancamento_error = (
                    'Já existe um lançamento com o número' in (mensagem_origens or '')
                )
                return _render_erro_novo_lancamento(
                    request, tis, imovel, documento_ativo, pessoas, cartorios,
                    tipos_lancamento, numero_lancamento_error=numero_lancamento_error,
                )

        except Exception as e:
            # Capturar exceções para debug
            import traceback
            error_msg = f'Erro inesperado: {str(e)}\n{traceback.format_exc()}'
            messages.error(request, f'❌ {error_msg}')
            print(f"ERRO NA CRIAÇÃO DE LANÇAMENTO: {error_msg}")

            # Verificar se é erro de número duplicado para destacar o campo
            numero_lancamento_error = 'Já existe um lançamento com o número' in str(e)

            return _render_erro_novo_lancamento(
                request, tis, imovel, documento_ativo, pessoas, cartorios,
                tipos_lancamento, numero_lancamento_error=numero_lancamento_error,
            )

    # GET - mostrar formulário
    # Limpar dados de duplicata cancelada da sessão sempre
    request.session.pop('duplicata_cancelada', None)
    request.session.pop('duplicata_origem', None)
    request.session.pop('duplicata_cartorio', None)
    
    duplicata_cancelada = False
    duplicata_origem = ''
    duplicata_cartorio = ''
    
    # Buscar lançamentos anteriores deste documento (para painel lateral)
    lancamentos_anteriores = (
        Lancamento.objects
        .filter(documento=documento_ativo)
        .select_related('tipo', 'documento')
        .prefetch_related(
            Prefetch('pessoas', queryset=LancamentoPessoa.objects.select_related('pessoa'))
        )
        .order_by('-data', '-id')[:20]
    )
    lancamentos_com_pessoas = []
    for lanc in lancamentos_anteriores:
        relacoes = lanc.pessoas.all()
        transmitentes = [lp.pessoa for lp in relacoes if lp.tipo == 'transmitente']
        adquirentes = [lp.pessoa for lp in relacoes if lp.tipo == 'adquirente']
        lancamentos_com_pessoas.append({
            'lancamento': lanc,
            'transmitentes': transmitentes,
            'adquirentes': adquirentes,
        })

    context = _build_novo_lancamento_context(
        request, tis, imovel, documento_ativo, pessoas, cartorios, tipos_lancamento
    )
    context['duplicata_cancelada'] = duplicata_cancelada
    context['duplicata_origem'] = duplicata_origem
    context['duplicata_cartorio'] = duplicata_cartorio
    context['lancamentos_com_pessoas'] = lancamentos_com_pessoas

    return render(request, 'dominial/lancamento_form.html', context)

@login_required
def editar_lancamento(request, tis_id, imovel_id, lancamento_id):
    """
    View para editar um lançamento existente
    """
    # Obter objetos básicos
    tis = get_object_or_404(TIs, id=tis_id)
    imovel = get_object_or_404(Imovel, id=imovel_id, terra_indigena_id=tis)
    
    # Permitir edição de lançamentos de documentos compartilhados (issue #152)
    try:
        lancamento, is_lancamento_do_imovel = _resolver_lancamento_no_contexto_do_imovel(
            imovel, lancamento_id
        )
    except LancamentoForaDaCadeiaError as erro:
        messages.error(
            request,
            f'Lançamento {erro.lancamento.numero_lancamento} não pode ser editado '
            f'pois não é referenciado como origem neste imóvel.'
        )
        return redirect('cadeia_dominial', tis_id=tis.id, imovel_id=imovel.id)

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
                # Redirecionar para a página do documento detalhado
                return redirect('documento_detalhado', tis_id=tis.id, imovel_id=imovel.id, documento_id=lancamento.documento.id)
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
        'cartorio_origem_correto': cartorio_origem_correto,
        'is_lancamento_do_imovel': is_lancamento_do_imovel,
        'is_lancamento_compartilhado': not is_lancamento_do_imovel,
        'documento_lancamentos': _build_documento_lancamentos(lancamento.documento, current_lancamento_id=lancamento.id),
        'fim_cadeia_opcoes': _build_fim_cadeia_opcoes(),
    }
    
    # Preparar dados para o template
    if context['modo_edicao'] and lancamento.origem:
        # Separar múltiplas origens para o template
        origens_separadas = []
        
        # Carregar dados de fim de cadeia do novo modelo
        origens_fim_cadeia = lancamento.origens_fim_cadeia.all()
        fim_cadeia_por_indice = {origem.indice_origem: origem for origem in origens_fim_cadeia}
        
        # Verificar se é fim de cadeia (formato antigo, novo formato ou tem dados no modelo)
        padroes_fim_cadeia = ['FIM_CADEIA', 'Destacamento Público:', 'Outra:', 'Sem Origem:']
        tem_fim_cadeia = any(padrao in lancamento.origem for padrao in padroes_fim_cadeia) or origens_fim_cadeia.exists()
        
        if tem_fim_cadeia:
            # Processar origem de fim de cadeia
            if origens_fim_cadeia.exists():
                # Usar dados do novo modelo
                origem_fim_cadeia = origens_fim_cadeia.first()
                # Extrair sigla do patrimônio público da string de origem se disponível
                sigla_patrimonio_publico = ''
                if 'FIM_CADEIA' in lancamento.origem:
                    # Formato antigo: FIM_CADEIA:tipo_origem:numero:tipo_fim_cadeia:classificacao:sigla_patrimonio
                    origem_parts = lancamento.origem.split(':')
                    if len(origem_parts) >= 6:
                        sigla_patrimonio_publico = origem_parts[5]
                
                origens_separadas.append({
                    'texto': lancamento.origem,
                    'index': 0,
                    'cartorio_nome': lancamento.cartorio_origem.nome if lancamento.cartorio_origem else '',
                    'cartorio_id': lancamento.cartorio_origem.id if lancamento.cartorio_origem else '',
                    'livro': lancamento.livro_origem,
                    'folha': lancamento.folha_origem,
                    'fim_cadeia': True,
                    'tipo_origem': '',
                    'numero_origem': '',
                    'tipo_fim_cadeia': origem_fim_cadeia.tipo_fim_cadeia,
                    'classificacao_fim_cadeia': origem_fim_cadeia.classificacao_fim_cadeia,
                    'sigla_patrimonio_publico': sigla_patrimonio_publico,
                    'especificacao_fim_cadeia': origem_fim_cadeia.especificacao_fim_cadeia,
                    'info_adicional_fim_cadeia': origem_fim_cadeia.info_adicional_fim_cadeia
                })
            else:
                # Processar formato antigo FIM_CADEIA ou novo formato
                if 'FIM_CADEIA' in lancamento.origem:
                    # Formato antigo FIM_CADEIA
                    origem_parts = lancamento.origem.split(':')
                    if len(origem_parts) >= 2:
                        tipo_origem = origem_parts[1] if origem_parts[1] else ''
                        numero_origem = origem_parts[2] if len(origem_parts) > 2 else ''
                        
                        if len(origem_parts) == 4:  # Formato sem tipo de origem (formato antigo)
                            tipo_fim_cadeia = origem_parts[2] if len(origem_parts) > 2 else 'sem_origem'
                            classificacao = origem_parts[3] if len(origem_parts) > 3 else 'sem_origem'
                            sigla_patrimonio = ''
                        elif len(origem_parts) == 5:  # Formato sem tipo de origem (com sigla patrimônio)
                            tipo_fim_cadeia = origem_parts[2] if len(origem_parts) > 2 else 'sem_origem'
                            classificacao = origem_parts[3] if len(origem_parts) > 3 else 'sem_origem'
                            sigla_patrimonio = origem_parts[4] if len(origem_parts) > 4 else ''
                        else:  # Formato com tipo de origem
                            tipo_fim_cadeia = origem_parts[3] if len(origem_parts) > 3 else 'sem_origem'
                            classificacao = origem_parts[4] if len(origem_parts) > 4 else 'sem_origem'
                            sigla_patrimonio = origem_parts[5] if len(origem_parts) > 5 else ''
                        
                        origens_separadas.append({
                            'texto': lancamento.origem,
                            'index': 0,
                            'cartorio_nome': lancamento.cartorio_origem.nome if lancamento.cartorio_origem else '',
                            'cartorio_id': lancamento.cartorio_origem.id if lancamento.cartorio_origem else '',
                            'livro': lancamento.livro_origem,
                            'folha': lancamento.folha_origem,
                            'fim_cadeia': True,
                            'tipo_origem': tipo_origem,
                            'numero_origem': numero_origem,
                            'tipo_fim_cadeia': tipo_fim_cadeia,
                            'classificacao_fim_cadeia': classificacao,
                            'sigla_patrimonio_publico': sigla_patrimonio,
                            'especificacao_fim_cadeia': ''
                        })
                else:
                    # Novo formato: Destacamento Público:Sigla:Classificação
                    origem_parts = lancamento.origem.split(':')
                    if len(origem_parts) >= 3:
                        # Mapear os tipos para os valores corretos do template
                        tipo_mapping = {
                            'destacamento_público': 'destacamento_publico',
                            'outra': 'outra',
                            'sem_origem': 'sem_origem'
                        }
                        tipo_raw = origem_parts[0].lower().replace(' ', '_')
                        tipo_fim_cadeia = tipo_mapping.get(tipo_raw, tipo_raw)
                        
                        sigla_patrimonio = origem_parts[1]
                        
                        # Mapear as classificações para os valores corretos do template
                        classificacao_mapping = {
                            'origem_identificada': 'origem_lidima',
                            'origem_lidima': 'origem_lidima',
                            'origem_lídima': 'origem_lidima',
                            'sem_origem': 'sem_origem',
                            'situacao_inconclusa': 'inconclusa'
                        }
                        classificacao_raw = origem_parts[2].lower().replace(' ', '_')
                        classificacao_raw = ''.join(
                            caractere
                            for caractere in unicodedata.normalize('NFD', classificacao_raw)
                            if unicodedata.category(caractere) != 'Mn'
                        )
                        classificacao = classificacao_mapping.get(classificacao_raw, classificacao_raw)
                        
                        origens_separadas.append({
                            'texto': lancamento.origem,
                            'index': 0,
                            'cartorio_nome': lancamento.cartorio_origem.nome if lancamento.cartorio_origem else '',
                            'cartorio_id': lancamento.cartorio_origem.id if lancamento.cartorio_origem else '',
                            'livro': lancamento.livro_origem,
                            'folha': lancamento.folha_origem,
                            'fim_cadeia': True,
                            'tipo_origem': '',
                            'numero_origem': '',
                            'tipo_fim_cadeia': tipo_fim_cadeia,
                            'classificacao_fim_cadeia': classificacao,
                            'sigla_patrimonio_publico': sigla_patrimonio,
                            'especificacao_fim_cadeia': ''
                        })
        else:
            # Processar origens normais
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
                        origem_fim_cadeia = fim_cadeia_por_indice.get(i)
                        
                        origens_separadas.append({
                            'texto': origem,
                            'index': i,
                            'cartorio_nome': mapeamento.get('cartorio_nome', ''),
                            'cartorio_id': mapeamento.get('cartorio_id', ''),
                            'livro': mapeamento.get('livro', ''),
                            'folha': mapeamento.get('folha', ''),
                            'fim_cadeia': origem_fim_cadeia.fim_cadeia if origem_fim_cadeia else False,
                            'tipo_fim_cadeia': origem_fim_cadeia.tipo_fim_cadeia if origem_fim_cadeia else '',
                            'classificacao_fim_cadeia': origem_fim_cadeia.classificacao_fim_cadeia if origem_fim_cadeia else '',
                            'sigla_patrimonio_publico': '',
                            'especificacao_fim_cadeia': origem_fim_cadeia.especificacao_fim_cadeia if origem_fim_cadeia else ''
                        })
                else:
                    # Fallback: usar cartório geral do lançamento para todas as origens
                    for i, origem in enumerate(origens_list):
                        origem_fim_cadeia = fim_cadeia_por_indice.get(i)
                        
                        origens_separadas.append({
                            'texto': origem,
                            'index': i,
                            'cartorio_nome': lancamento.cartorio_origem.nome if lancamento.cartorio_origem else '',
                            'cartorio_id': lancamento.cartorio_origem.id if lancamento.cartorio_origem else '',
                            'livro': lancamento.livro_origem,
                            'folha': lancamento.folha_origem,
                            'fim_cadeia': origem_fim_cadeia.fim_cadeia if origem_fim_cadeia else False,
                            'tipo_fim_cadeia': origem_fim_cadeia.tipo_fim_cadeia if origem_fim_cadeia else '',
                            'classificacao_fim_cadeia': origem_fim_cadeia.classificacao_fim_cadeia if origem_fim_cadeia else '',
                            'sigla_patrimonio_publico': '',
                            'especificacao_fim_cadeia': origem_fim_cadeia.especificacao_fim_cadeia if origem_fim_cadeia else ''
                        })
            else:
                # Uma única origem
                origem_fim_cadeia = fim_cadeia_por_indice.get(0)
                
                origens_separadas.append({
                    'texto': lancamento.origem,
                    'index': 0,
                    'cartorio_nome': lancamento.cartorio_origem.nome if lancamento.cartorio_origem else '',
                    'cartorio_id': lancamento.cartorio_origem.id if lancamento.cartorio_origem else '',
                    'livro': lancamento.livro_origem,
                    'folha': lancamento.folha_origem,
                    'fim_cadeia': origem_fim_cadeia.fim_cadeia if origem_fim_cadeia else False,
                    'tipo_fim_cadeia': origem_fim_cadeia.tipo_fim_cadeia if origem_fim_cadeia else '',
                    'classificacao_fim_cadeia': origem_fim_cadeia.classificacao_fim_cadeia if origem_fim_cadeia else '',
                    'sigla_patrimonio_publico': '',
                    'especificacao_fim_cadeia': origem_fim_cadeia.especificacao_fim_cadeia if origem_fim_cadeia else ''
                })
    else:
        origens_separadas = []

    # Normaliza chaves usadas pelo bloco de destacamento do patrimônio público (issue #104)
    for origem_separada in origens_separadas:
        origem_separada.setdefault('info_adicional_fim_cadeia', '')
        origem_separada['is_destacamento_publico'] = (
            origem_separada.get('tipo_fim_cadeia') == 'destacamento_publico'
        )

    context['origens_separadas'] = origens_separadas
    
    return render(request, 'dominial/lancamento_form.html', context)

@login_required
def excluir_lancamento(request, tis_id, imovel_id, lancamento_id):
    """View para excluir um lançamento"""
    tis = get_object_or_404(TIs, id=tis_id)
    imovel = get_object_or_404(Imovel, id=imovel_id, terra_indigena_id=tis)

    # Permitir exclusão de lançamentos de documentos compartilhados (issue #152)
    try:
        lancamento, is_lancamento_do_imovel = _resolver_lancamento_no_contexto_do_imovel(
            imovel, lancamento_id
        )
    except LancamentoForaDaCadeiaError as erro:
        messages.error(
            request,
            f'Lançamento {erro.lancamento.numero_lancamento} não pode ser excluído '
            f'pois não é referenciado como origem neste imóvel.'
        )
        return redirect('cadeia_dominial', tis_id=tis.id, imovel_id=imovel.id)

    if request.method == 'POST':
        try:
            documento_id = lancamento.documento.id
            numero_lancamento = lancamento.numero_lancamento or f"Lançamento {lancamento.id}"
            lancamento.delete()
            messages.success(request, f'Lançamento "{numero_lancamento}" excluído com sucesso!')
            return redirect('documento_detalhado', tis_id=tis_id, imovel_id=imovel_id, documento_id=documento_id)
        except Exception as e:
            messages.error(request, f'Erro ao excluir lançamento: {str(e)}')

    # Alinha com documento_detalhado: o aviso também vale quando o imóvel é o
    # DONO de um documento que outras cadeias importaram (issue #152, AC#3).
    from ..models import DocumentoImportado
    documento_compartilhado = (not is_lancamento_do_imovel) or DocumentoImportado.objects.filter(
        documento=lancamento.documento
    ).exists()

    return render(request, 'dominial/lancamento_confirm_delete.html', {
        'tis': tis,
        'imovel': imovel,
        'lancamento': lancamento,
        'documento': lancamento.documento,
        'is_lancamento_do_imovel': is_lancamento_do_imovel,
        'documento_compartilhado': documento_compartilhado,
    })

@login_required
def lancamento_resumo_partial(request, tis_id, imovel_id, lancamento_id):
    """Retorna HTML parcial com o resumo de um lançamento (para sidebar AJAX)."""
    tis = get_object_or_404(TIs, id=tis_id)
    imovel = get_object_or_404(Imovel, id=imovel_id, terra_indigena_id=tis)
    lancamento = get_object_or_404(
        Lancamento.objects.select_related('documento', 'tipo').prefetch_related(
            Prefetch('pessoas', queryset=LancamentoPessoa.objects.select_related('pessoa'))
        ),
        id=lancamento_id, documento__imovel=imovel
    )
    transmitentes = lancamento.pessoas.filter(tipo='transmitente')
    adquirentes = lancamento.pessoas.filter(tipo='adquirente')
    return render(request, 'dominial/components/_lancamento_resumo_card.html', {
        'lancamento': lancamento,
        'documento': lancamento.documento,
        'transmitentes': transmitentes,
        'adquirentes': adquirentes,
        'tis': tis,
        'imovel': imovel,
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
        'adquirentes': adquirentes,
        'documento_lancamentos': _build_documento_lancamentos(lancamento.documento, current_lancamento_id=lancamento.id),
    }
    
    return render(request, 'dominial/lancamento_detail.html', context)
