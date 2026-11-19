"""Gravação de um ato: lançamento, origem, cartórios, partes e resposta.

``_vincular`` é chamado VIA O PACOTE (``importacao._vincular``): os testes
fazem ``patch.object`` em ``ia_ocr.importacao`` e o patch só vale se o call
site resolver o nome no objeto do pacote, a cada chamada.
"""
from django.core.exceptions import ValidationError

from dominial.models import Lancamento, LancamentoPessoa
from dominial.services.lancamento_origem_service import LancamentoOrigemService
from dominial.utils.documento_identidade_utils import (
    normalizar_numero_documento,
)

from .. import destinos, importacao
from ..valores import MOTIVO_LIMITE
from .ato_documento import (
    PREFIXO_TIPO_DOCUMENTO, _existente, _lancamento_duplicado,
    _resolver_tipo_e_numero, _tipo_documento_da_origem,
)
from .avisos import _registro_homonimo, _texto_do_aviso_gravado, _texto_ou_none
from .cartorios import _avisos_livro_folha_da_origem, _resolver_cartorio
from .pessoas import _resolver_pessoa
from .resposta import _Erros, _linha_resposta, _rotulo


# ---------------------------------------------------------------------------
# Gravação de um ato
# ---------------------------------------------------------------------------

def _importar_ato(
    ato, rotulo, documento, imovel, usuario, job, linhas,
    cache_pessoas, documentos_usuario, lancamentos_importados,
    nomes_travados, *, avisos_gravados=None,
):
    """Grava um ato (lançamento + origem + partes) e devolve a linha resposta.

    Sempre devolve ``(resposta | None, erros)``: com erro, o chamador levanta
    ``_AtoInvalido`` DENTRO do savepoint, que desfaz na hora o que este ato
    criou (lançamento parcial, cartórios, pessoas, documento de origem).
    ``lancamentos_importados`` são os gravados pelos atos anteriores desta
    importação (duplicata contra eles é interna, sem ``existente``);
    ``nomes_travados``, os nomes de cartório que o ``importar`` já travou.
    ``avisos_gravados`` é o acumulador do chamador (``{chave do ato:
    [registro]}``): só o ato que TERMINA sem erro registra nele os avisos
    que o replay não recalcula (#324 rodada 4); sem ele (chamada direta),
    nada é registrado e a resposta é a mesma.
    ``rotulo`` é o rótulo do ato já analisado uma vez pelo chamador (#322,
    lido pelo efetivo — P1 das rodadas 4–5): o tipo do rótulo PREVALECE
    sobre o ``tipo_sugerido`` divergente — a MESMA regra do
    ``classificar_atos`` (P2-3) — e a divergência vira aviso na resposta,
    nunca bloqueio; sem rótulo utilizável, o ``tipo_sugerido`` decide como
    antes. Rótulo de MATRÍCULA não define tipo e não gera número da
    matrícula (P2-1): o número de ato REVISADO válido em
    ``/numero_lancamento`` é preservado (P2, rodada 5); sem ele o ato
    grava sem número, com aviso. Rótulo não reconhecido mantém o
    comportamento de antes.
    """
    chave = ato.chave
    erros = _Erros(chave)

    # A MESMA resolução de tipo/número da prévia (#322, rodadas 4–5): o
    # rótulo (efetivo) prevalece sobre o tipo_sugerido divergente
    # (P1/P2-2), o rótulo de matrícula não gera número DELA, mas o número
    # de ato revisado válido é preservado (P2-1/P2) e o número é o
    # composto canônico do V1 (P1-1 da rodada 3) — a duplicata normaliza os
    # dois lados de volta ao número do ato.
    tipo, numero_lancamento, avisos_do_rotulo = _resolver_tipo_e_numero(
        ato, rotulo, documento,
    )
    if tipo is None:
        erros.add(
            f'{chave}/tipo_sugerido', 'tipo_inexistente',
            'O tipo de lançamento não está configurado no sistema.',
        )
        return None, erros
    duplicado = _lancamento_duplicado(
        documento, tipo, ato.data, numero_lancamento,
        Lancamento.objects.exclude(pk__in=lancamentos_importados),
    )
    if duplicado is not None:
        erros.add(
            chave, 'lancamento_duplicado',
            'Já existe um lançamento deste ato no documento.',
            existente=_existente(duplicado),
        )
        return None, erros
    if lancamentos_importados and _lancamento_duplicado(
        documento, tipo, ato.data, numero_lancamento,
        Lancamento.objects.filter(pk__in=lancamentos_importados),
    ) is not None:
        # O outro lançamento só existe dentro desta transação: apontá-lo
        # como ``existente`` levaria a tela a um registro que o rollback
        # global apaga (#263 rodada 3).
        erros.add(
            chave, 'ato_duplicado_na_importacao',
            'Outro ato marcado nesta importação grava o mesmo lançamento.',
        )
        return None, erros

    # Cartório de transmissão é opcional; o da origem, exigido pela origem.
    criados_cartorios = []
    cartorio_transmissao = _resolver_cartorio(
        ato.cartorio_transmissao_id, ato.cartorio_transmissao_criar_novo,
        ato.cartorio_transmissao_nome,
        f'{chave}/cartorio_transmissao', criados_cartorios, nomes_travados,
    )
    if cartorio_transmissao is None and ato.cartorio_transmissao_id is not None:
        # Escolha da revisão que sumiu entre a leitura e a gravação: o ato
        # não grava sem o cartório escolhido (#263 rodada 3, como a origem).
        erros.add(
            f'{chave}/cartorio_transmissao', 'decisao_perdida',
            'O cartório escolhido para a transmissão não existe mais.',
        )
        return None, erros

    origem = ato.origem
    numero = (origem.get('numero') or '').strip() if origem else ''
    tipo_informado = origem.get('tipo_documento') if origem else None
    texto_origem = None
    mapeamento = None
    cartorio_origem = None
    # Avisos da origem (#324/#267): informam o revisor e nunca bloqueiam.
    avisos_da_origem = []
    # O que desses avisos o replay não recalcula e precisa ser gravado.
    registros_a_gravar = []
    # O cartório da origem é resolvido SEMPRE que há origem — inclusive
    # quando ela só tem o cartório, sem número/tipo (#263 rodada 4,
    # CodeRabbit): o tipo do lançamento pode exigir cartório de origem e a
    # gravação precisa dele na FK. Número/tipo são exigidos só na montagem
    # do texto/mapeamento (abaixo), nunca para resolver o cartório.
    if origem is not None:
        cartorio_origem = _resolver_cartorio(
            origem.get('cartorio_id'), origem.get('cartorio_criar_novo'),
            origem.get('cartorio_nome'), f'{chave}/origem/cartorio',
            criados_cartorios, nomes_travados,
        )
        if cartorio_origem is None:
            if origem.get('cartorio_id') is not None:
                erros.add(
                    f'{chave}/origem/cartorio', 'decisao_perdida',
                    'O cartório escolhido para a origem não existe mais.',
                )
                return None, erros
            if numero or tipo_informado:
                erros.add(
                    f'{chave}/origem/cartorio', 'valor_obrigatorio',
                    'O cartório da origem é obrigatório para importar o ato.',
                )
                return None, erros
        elif numero or tipo_informado:
            if not numero:
                erros.add(
                    f'{chave}/origem/numero', 'valor_obrigatorio',
                    'O número da origem é obrigatório para importar o ato.',
                )
                return None, erros
            tipo_documento = _tipo_documento_da_origem(origem, numero)
            try:
                normalizado = normalizar_numero_documento(
                    numero, tipo_documento,
                )
            except (TypeError, ValueError) as exc:
                # Mensagem fixa do util: cita o prefixo, nunca o número
                # inteiro.
                erros.add(
                    f'{chave}/origem/numero', 'valor_incompativel_destino',
                    str(exc),
                )
                return None, erros
            texto_origem = PREFIXO_TIPO_DOCUMENTO[tipo_documento] + normalizado
            # O valor PERSISTIDO ganha prefixo: a revisão validou o limite
            # da linha (sem prefixo), o destino valida o valor final.
            # Estourou o max_length do LancamentoOrigem.numero é erro da
            # linha da origem — nunca um ValidationError cru lá embaixo
            # virando 500 (#263 rodada 2).
            limite_origem = destinos.destino_de(
                f'{chave}/origem/numero',
            ).max_length
            if limite_origem and len(texto_origem) > limite_origem:
                erros.add(
                    f'{chave}/origem/numero', MOTIVO_LIMITE,
                    'O número da origem, com o prefixo do tipo documental, '
                    'ultrapassa o limite do destino.',
                )
                return None, erros
            mapeamento = [{
                'indice': 0,
                'origem': texto_origem,
                # Tipo documental ESTRUTURADO revisado: viaja com o
                # mapeamento até a criação do documento de origem — o
                # texto livre nunca é reparseado ('T42.718' com pontuação
                # não vira 'M42' + 'M718') (#263 rodada 4, Codex P1).
                'tipo_documento': tipo_documento,
                'cartorio_id': cartorio_origem.pk,
                'livro': _texto_ou_none(origem.get('livro')),
                'folha': _texto_ou_none(origem.get('folha')),
            }]
            # #267: ANTES de gravar — depois, o documento que a própria
            # importação cria (início de matrícula) já seria a identidade
            # declarada. Só o escopo do usuário; o homônimo nunca é vinculado.
            homonimo = LancamentoOrigemService.homonimo_outro_tipo(
                tipo_documento, numero, cartorio_origem,
                documentos_queryset=documentos_usuario,
            )
            if homonimo is not None:
                # Depois da importação o documento declarado existe e esta
                # checagem devolveria ``None``: o aviso produzido AGORA é o
                # único registro dele — vai para a resposta e é gravado.
                registro = _registro_homonimo(
                    tipo_documento, homonimo.tipo.tipo,
                )
                registros_a_gravar.append(registro)
                avisos_da_origem.append(_texto_do_aviso_gravado(registro))

    lancamento = Lancamento(
        documento=documento,
        tipo=tipo,
        # Gravação no formato canônico do V1 (#322 rodada 3, P1-1): 'R-5'
        # na matrícula 'M237' grava 'R5 M237' — o MESMO texto que o fluxo
        # manual compõe e que os consumidores ordenam por '^(R|AV)\d+'; a
        # sigla é o ``documento.numero`` e o número vem SEM bordas (' R-1 '
        # persistido colidiria com o manual na próxima duplicata, #263
        # rodada 6) e vazio de verdade é None, não '' (#263 rodada 8).
        numero_lancamento=numero_lancamento or None,
        data=ato.data,
        # valor_transacao e detalhes não são importados (Tarefa C #322 e
        # #328): os campos não existem no formulário de lançamento.
        area=ato.area,
        titulo=ato.titulo,
        forma=ato.forma,
        descricao=ato.descricao,
        observacoes=ato.observacoes,
        eh_inicio_matricula=bool(ato.eh_inicio_matricula),
        cartorio_origem=cartorio_origem,
        cartorio_transmissao=cartorio_transmissao,
        # O codec do formulário preserva espaços em texto: vazio grava NULL.
        livro_transacao=(ato.livro_transacao or '').strip() or None,
        folha_transacao=(ato.folha_transacao or '').strip() or None,
        data_transacao=ato.data_transacao,
        # #324: o mesmo ``strip() or None`` da transmissão — livro/folha da
        # origem em branco são NULL no lançamento e no mapeamento acima.
        livro_origem=_texto_ou_none(origem.get('livro')) if origem else None,
        folha_origem=_texto_ou_none(origem.get('folha')) if origem else None,
        data_origem=origem.get('data') if origem else None,
    )
    if texto_origem is not None:
        lancamento.origem = texto_origem
    try:
        lancamento.full_clean()
    except ValidationError as exc:
        erros.do_modelo(exc, 'dominial.Lancamento')
        return None, erros

    # Mapeamento do "POST corrente" antes do save: o sinal post_save roda o
    # mesmo serviço sem queryset, e a chamada explícita abaixo é a fonte da
    # verdade (o sinal engole exceções — nunca confiar nele).
    if mapeamento is not None:
        LancamentoOrigemService.definir_mapeamento(lancamento, mapeamento)
    try:
        lancamento.save()
        aviso = LancamentoOrigemService.processar_origens_automaticas(
            lancamento, lancamento.origem or '', imovel,
            documentos_queryset=documentos_usuario,
            # #324 rodada 4 (P2 do Codex): o valor REVISADO prevalece,
            # inclusive a AUSÊNCIA — a herança do primeiro lançamento do
            # documento de origem não pode preencher livro/folha que a
            # revisão deixou vazio. Só o caminho IA desliga a herança.
            herdar_livro_folha_do_documento=False,
        )
    except ValidationError:
        # Defesa em profundidade: o serviço da origem ainda pode recusar
        # algo que nem a revisão nem o pre-check acima viram. Vira erro da
        # linha da origem com mensagem fixa, nunca um 500 (#263 rodada 2).
        erros.add(
            f'{chave}/origem/numero', 'valor_incompativel_destino',
            'O número da origem não pôde ser gravado no lançamento.',
        )
        return None, erros
    finally:
        LancamentoOrigemService.limpar_mapeamento(lancamento)
        # Documento de origem que o caminho de criação devolveu — o do
        # sinal post_save inclusive, que cria durante o save. Nunca o diff
        # do imóvel: ele não está travado e pegaria o documento de outro
        # escritor (#263 rodada 3).
        documentos_origem = (
            LancamentoOrigemService.consumir_documentos_criados(lancamento)
        )

    # #324: só a importação grava ``documento_origem``. Resolve a origem
    # estruturada no escopo do usuário e aceita só identidade ``encontrada``
    # — nunca cria, nunca pelo número; fora do escopo/ambígua/sem documento
    # a FK fica NULL (o aviso da origem restrita já saiu do serviço acima).
    if mapeamento is not None:
        LancamentoOrigemService.vincular_documento_origem(
            lancamento, documentos_queryset=documentos_usuario,
        )

    registros = [('Lancamento', lancamento.pk, chave)]
    registros.extend(
        (modelo, objeto.pk, chave_linha)
        for modelo, objeto, chave_linha in criados_cartorios
    )
    if mapeamento is not None:
        origem_estruturada = lancamento.origens_estruturadas.first()
        if origem_estruturada is not None:
            registros.append((
                'LancamentoOrigem', origem_estruturada.pk,
                f'{chave}/origem/numero',
            ))
        # Documento de origem criado (início de matrícula): entra na
        # auditoria como qualquer outro objeto gravado (#263 rodada 2) —
        # sem isso ele nascia sem vínculo com o PDF nem com o ato.
        registros.extend(
            ('Documento', pk, f'{chave}/origem/numero')
            for pk in documentos_origem
        )

    for parte in ato.partes:
        pessoa, pessoa_criada = _resolver_pessoa(parte, cache_pessoas, erros)
        if pessoa is None:
            return None, erros
        vinculo, vinculo_criado = LancamentoPessoa.objects.get_or_create(
            lancamento=lancamento, pessoa=pessoa, tipo=parte.papel,
            defaults={'nome_digitado': parte.nome},
        )
        if vinculo_criado:
            registros.append(('LancamentoPessoa', vinculo.pk, parte.chave))
        if pessoa_criada:
            registros.append(('Pessoas', pessoa.pk, parte.chave))

    importacao._vincular(job, usuario, lancamento, registros, linhas)
    avisos = []
    if aviso:
        avisos.append(aviso)
    # P2-3/P2-2 (#322 rodadas 3–4): o conflito rótulo × tipo_sugerido — e o
    # rótulo de matrícula sem número (P2-1) — aparecem para o revisor, sem
    # bloquear uma gravação válida.
    avisos.extend(avisos_do_rotulo)
    if texto_origem is not None:
        avisos_da_origem.extend(_avisos_livro_folha_da_origem(
            lancamento.livro_origem, lancamento.folha_origem,
        ))
    avisos.extend(avisos_da_origem)
    resposta = _linha_resposta(
        chave, _rotulo(chave, linhas), 'criado', lancamento=lancamento,
        avisos=avisos,
    )
    # Só aqui, no fim do caminho de sucesso: nenhum ``return None, erros``
    # acima deixa um registro órfão no acumulador do chamador.
    if avisos_gravados is not None and registros_a_gravar:
        avisos_gravados[chave] = registros_a_gravar
    return resposta, erros
