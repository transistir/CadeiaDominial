"""Leitura tipada da revisão (dados_revisados/_montar_dados)."""

import re

from .. import destinos, valores
from .estruturas import (
    AtoRevisado, DadosRevisados, DocumentoRevisado, ParteRevisada,
    RevisaoInvalidada,
)
from .linhas import (
    _cartorio_id_da_linha, _contexto_revisao, _destino_da_linha,
    _valor_efetivo, _valor_explicito,
)
from .pendencias import pendencias
from .tipos import _tipos_efetivos


def dados_revisados(extracao) -> DadosRevisados:
    """Lê a revisão vigente e finalizada, revalidando suas decisões atuais.

    Cada vínculo de cartório expõe ``*_id`` e ``*_criar_novo`` para a I-6.
    Criar prevalece sobre IDs/candidatos anteriores: ID ausente com flag
    falsa é diferente de uma decisão explícita de criar cadastro.
    """
    job = extracao.ocr_job
    if job.status != 'revisado':
        raise RevisaoInvalidada('O job não está revisado.')
    vigente = job.extracao_vigente()
    if vigente is None or vigente.pk != extracao.pk:
        raise RevisaoInvalidada('A extração não é a vigente.')
    if extracao.finalizada_em is None:
        raise RevisaoInvalidada('A extração não foi finalizada.')
    if pendencias(extracao):
        raise RevisaoInvalidada('A revisão possui pendências.')

    return _montar_dados(extracao)


def _montar_dados(extracao) -> DadosRevisados:
    """Monta a estrutura tipada da revisão, SEM exigir revisão concluída.

    É o miolo de ``dados_revisados`` sem a guarda: não olha o status do
    job, se a extração é a vigente/finalizada nem se há pendências — lê o
    estado ATUAL das linhas (``valor_final`` → ``normalized``) mesmo com o
    job em ``extraido``. Quem precisa do contrato "revisão fechada" (a
    importação) continua em ``dados_revisados``; o formulário de lançamento
    (I-14 / #341) pré-preenche um ato antes de a revisão terminar.

    Só lê o banco: nenhuma gravação, nenhuma transição. As linhas
    descartadas (e o ramo inteiro de um ato descartado) ficam de fora,
    como em ``dados_revisados``.
    """
    linhas, atos = _contexto_revisao(extracao)
    tipos_por_ato, _ = _tipos_efetivos(linhas, atos)

    def valor(chave):
        campo = linhas.get(chave)
        if campo is None:
            return None
        return valores.para_python(campo.tipo_valor, _valor_efetivo(campo))

    def cartorio_id(chave):
        return _cartorio_id_da_linha(linhas, chave)

    def cartorio_criar_novo(chave):
        campo = linhas.get(chave)
        return campo is not None and campo.criar_novo

    destinos_linhas = {}
    conferencia = {}
    for chave, campo in linhas.items():
        destino = _destino_da_linha(chave, linhas)
        destinos_linhas[chave] = destino
        if destino == destinos.SEM_DESTINO:
            conferencia[chave] = _valor_efetivo(campo)

    documento = DocumentoRevisado(
        tipo=valor('/document/tipo'),
        numero=valor('/document/numero'),
        data=valor('/document/data'),
        cartorio_id=cartorio_id('/document/cartorio'),
        cri_atual_id=cartorio_id('/document/cri_atual'),
        cartorio_criar_novo=cartorio_criar_novo('/document/cartorio'),
        cri_atual_criar_novo=cartorio_criar_novo('/document/cri_atual'),
        livro=valor('/document/livro'),
        folha=valor('/document/folha'),
        cartorio_nome=valor('/document/cartorio'),
        cri_atual_nome=valor('/document/cri_atual'),
    )

    # Ordem e moeda são metadados do A3, sem linha editável própria.
    payload = extracao.payload_servico or extracao.payload
    atos_payload = payload.get('acts') or []
    revisados = []
    for ato in atos:
        chave = ato.chave
        indice = int(chave.rsplit('/', 1)[1])
        metadados = atos_payload[indice] if indice < len(atos_payload) else {}
        origem_cartorio_id = cartorio_id(f'{chave}/origem/cartorio')
        origem = None
        if origem_cartorio_id is not None or any(
            caminho.startswith(f'{chave}/origem/') for caminho in linhas
        ):
            origem = {
                nome: valor(f'{chave}/origem/{nome}')
                for nome in ('tipo_documento', 'numero', 'livro', 'folha', 'data')
            }
            origem['cartorio_id'] = origem_cartorio_id
            origem['cartorio_criar_novo'] = cartorio_criar_novo(f'{chave}/origem/cartorio')
            origem['cartorio_nome'] = valor(f'{chave}/origem/cartorio')

        partes = []
        linhas_partes = sorted(
            (campo for caminho, campo in linhas.items()
             if re.fullmatch(rf'{chave}/partes/\d+', caminho)),
            key=lambda campo: int(campo.chave.rsplit('/', 1)[1]),
        )
        for parte in linhas_partes:
            papel = valor(parte.chave)
            if papel not in destinos.PAPEIS_COM_DESTINO:
                continue
            identificacao = f'{parte.chave}/documento_identificacao/valor'
            destino = destinos_linhas.get(identificacao)
            partes.append(ParteRevisada(
                papel=papel,
                nome=valor(f'{parte.chave}/nome'),
                cpf=(
                    valor(identificacao)
                    if destino and destino.campo == 'cpf' else None
                ),
                rg=(
                    valor(identificacao)
                    if destino and destino.campo == 'rg' else None
                ),
                pessoa_id=parte.pessoa_escolhida_id,
                criar_novo=parte.criar_novo,
                chave=parte.chave,
            ))

        campo_tipo = linhas.get(f'{chave}/tipo_sugerido')
        # P1 (#322/PR #327): a escolha explícita vem da regra única — o
        # confirmado (flag) vale mesmo com o ``valor_final`` nulo.
        tipo_exp = _valor_explicito(campo_tipo)
        tipo_sug = (
            campo_tipo.normalized
            if campo_tipo is not None
            and campo_tipo.status_revisao != 'descartado'
            else None
        )
        tipo_resolvido = tipos_por_ato.get(chave)
        revisado = AtoRevisado(
            ordem=metadados.get('ordem', indice + 1),
            tipo=valor(f'{chave}/tipo_sugerido') or tipo_resolvido,
            numero_lancamento=valor(f'{chave}/numero_lancamento'),
            data=valor(f'{chave}/data'),
            area=valor(f'{chave}/area'),
            titulo=valor(f'{chave}/titulo'),
            forma=valor(f'{chave}/forma'),
            descricao=valor(f'{chave}/descricao'),
            observacoes=valor(f'{chave}/observacoes'),
            cartorio_origem_id=origem_cartorio_id,
            cartorio_transmissao_id=cartorio_id(f'{chave}/cartorio_transmissao'),
            cartorio_origem_criar_novo=cartorio_criar_novo(f'{chave}/origem/cartorio'),
            cartorio_transmissao_criar_novo=cartorio_criar_novo(
                f'{chave}/cartorio_transmissao',
            ),
            eh_inicio_matricula=valor(f'{chave}/eh_inicio_matricula'),
            origem=origem,
            partes=tuple(partes),
            cartorio_origem_nome=valor(f'{chave}/origem/cartorio'),
            cartorio_transmissao_nome=valor(f'{chave}/cartorio_transmissao'),
            chave=chave,
            tipo_explicito=tipo_exp,
            tipo_sugerido=tipo_sug,
            livro_transacao=valor(f'{chave}/livro_transacao'),
            folha_transacao=valor(f'{chave}/folha_transacao'),
            data_transacao=valor(f'{chave}/data_transacao'),
        )
        revisados.append((revisado.ordem, indice, revisado))

    return DadosRevisados(
        documento=documento,
        atos=tuple(
            ato for _, _, ato in sorted(revisados, key=lambda item: item[:2])
        ),
        conferencia=conferencia,
    )
