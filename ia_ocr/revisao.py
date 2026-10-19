"""Desnormalização do payload A3 em linhas de revisão (I-5, §18).

``desnormalizar`` é pura: percorre o payload e devolve ``CampoSugerido``
NÃO salvos — uma linha por folha editável (objeto com ``normalized``),
mais as linhas estruturais de ato (``/acts/{i}``, normalized = rótulo) e
de parte (``/acts/{i}/partes/{j}``, normalized = papel), mais
placeholders dos destinos obrigatórios ausentes. Nenhuma query, nenhuma
gravação: quem persiste é o chamador.

Toda pendência vira motivo estável em ``motivos_revisao`` com
``requer_revisao=True`` — nunca silêncio:

- ``normalizacao_invalida`` — ``normalized`` de data/decimal/área fora do
  canônico (vira ``normalized=None``; o raw é preservado);
- ``unidade_area`` — área de ato em unidade ≠ ha (conversão é decisão
  humana, nunca silenciosa);
- ``baixa_confianca`` — confiança < 0.70 (força revisão mesmo com o
  payload dizendo ``requer_revisao=False``);
- ``closure`` — qualquer linha ``/closure/*`` (classificação de fim de
  cadeia é SEMPRE decisão humana);
- ``evidencia_invalida`` — página da evidência fora das páginas do job;
- ``trecho_ausente`` — trecho não é substring do texto vigente da página
  (o ``texto_corrigido`` devolvido pelo serviço — decisão #290 — ou, na
  falta dele, o ``texto_ocr`` puro como fallback).

O módulo também hospeda o matching determinístico do I-5 (executado por
esta camada Python, nunca pelo modelo): ``IndicePessoas`` e
``IndiceCartorios`` (UMA query cada, matching em memória) e
``enriquecer_payload``, que escreve ``match_sugerido``/``match_pessoa_id``
(do A3) e ``match_pessoa_candidatos`` (extensão local) numa CÓPIA do
payload A3 — sem mutar o original.
"""

import copy
import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from django.utils import timezone

from dominial.models import Cartorios, LancamentoTipo, Pessoas

from . import destinos, valores
from .models import CampoSugerido

LIMIAR_CONFIANCA = 0.70

MOTIVO_NORMALIZACAO_INVALIDA = 'normalizacao_invalida'
MOTIVO_UNIDADE_AREA = 'unidade_area'
MOTIVO_BAIXA_CONFIANCA = 'baixa_confianca'
MOTIVO_CLOSURE = 'closure'
MOTIVO_EVIDENCIA_INVALIDA = 'evidencia_invalida'
MOTIVO_TRECHO_AUSENTE = 'trecho_ausente'

# Destinos obrigatórios (§2.A): ausentes no payload → placeholder em revisão.
_OBRIGATORIOS_DOCUMENTO = ('tipo', 'data', 'cartorio')
_OBRIGATORIOS_ATO = ('tipo_sugerido', 'data')

_TIPOS_NORMALIZAVEIS = ('data', 'decimal', 'area')

_AREA_DE_ATO = re.compile(r'/acts/\d+/area')


class RevisaoInvalidada(Exception):
    """A extração não pode mais ser consumida como uma revisão concluída."""

    code = 'revisao_invalida'


@dataclass(frozen=True)
class ParteRevisada:
    papel: str
    nome: str | None
    cpf: str | None
    rg: str | None
    pessoa_id: int | None
    criar_novo: bool


@dataclass(frozen=True)
class AtoRevisado:
    ordem: int
    tipo: str
    numero_lancamento: str | None
    data: date
    valor: Decimal | None
    moeda_historica: str | None
    area: Decimal | None
    titulo: str | None
    forma: str | None
    descricao: str | None
    detalhes: str | None
    observacoes: str | None
    cartorio_origem_id: int | None
    cartorio_transmissao_id: int | None
    cartorio_origem_criar_novo: bool
    cartorio_transmissao_criar_novo: bool
    eh_inicio_matricula: bool | None
    origem: dict | None
    partes: tuple[ParteRevisada, ...]


@dataclass(frozen=True)
class DocumentoRevisado:
    tipo: str
    numero: str | None
    data: date
    cartorio_id: int | None
    cri_atual_id: int | None
    cartorio_criar_novo: bool
    cri_atual_criar_novo: bool
    livro: str | None
    folha: str | None


@dataclass(frozen=True)
class DadosRevisados:
    documento: DocumentoRevisado
    atos: tuple[AtoRevisado, ...]
    conferencia: dict


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

    linhas, atos = _contexto_revisao(extracao)

    def valor(chave):
        campo = linhas.get(chave)
        if campo is None:
            return None
        return valores.para_python(campo.tipo_valor, _valor_efetivo(campo))

    def cartorio_id(chave):
        campo = linhas.get(chave)
        if campo is None or campo.criar_novo:
            return None
        if campo.cartorio_escolhido_id is not None:
            return campo.cartorio_escolhido_id
        if len(campo.match_candidatos) == 1:
            return campo.match_candidatos[0]
        return None

    def cartorio_criar_novo(chave):
        campo = linhas.get(chave)
        return campo is not None and campo.criar_novo

    destinos_linhas = {}
    conferencia = {}
    for chave, campo in linhas.items():
        contexto = [_valor_efetivo(campo)]
        if chave.endswith('/documento_identificacao/valor'):
            contexto.insert(0, valor(chave.rsplit('/', 1)[0] + '/tipo'))
        destino = destinos.destino_de(chave, *contexto)
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
    )

    # Ordem e moeda são metadados do A3, sem linha editável própria.
    payload = extracao.payload_servico or extracao.payload
    atos_payload = payload.get('acts') or []
    revisados = []
    for ato in atos:
        chave = ato.chave
        indice = int(chave.rsplit('/', 1)[1])
        metadados = atos_payload[indice] if indice < len(atos_payload) else {}
        dinheiro = metadados.get('valor_transacao') or {}
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
            ))

        revisado = AtoRevisado(
            ordem=metadados.get('ordem', indice + 1),
            tipo=valor(f'{chave}/tipo_sugerido'),
            numero_lancamento=valor(f'{chave}/numero_lancamento'),
            data=valor(f'{chave}/data'),
            valor=valor(f'{chave}/valor_transacao'),
            moeda_historica=(
                dinheiro.get('moeda_historica')
                if f'{chave}/valor_transacao' in linhas else None
            ),
            area=valor(f'{chave}/area'),
            titulo=valor(f'{chave}/titulo'),
            forma=valor(f'{chave}/forma'),
            descricao=valor(f'{chave}/descricao'),
            detalhes=valor(f'{chave}/detalhes'),
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
        )
        revisados.append((revisado.ordem, indice, revisado))

    return DadosRevisados(
        documento=documento,
        atos=tuple(
            ato for _, _, ato in sorted(revisados, key=lambda item: item[:2])
        ),
        conferencia=conferencia,
    )


def versao_linha(campo) -> str:
    """Versão estável do estado revisável da linha, incluindo a autoria temporal."""
    estado = [
        campo.status_revisao,
        campo.valor_final,
        campo.motivos_revisao,
        campo.pessoa_escolhida_id,
        campo.cartorio_escolhido_id,
        campo.criar_novo,
        campo.area_convertida,
        campo.revisado_em.isoformat() if campo.revisado_em else None,
    ]
    canonico = json.dumps(
        estado, sort_keys=True, separators=(',', ':'), ensure_ascii=False,
    )
    return hashlib.sha256(canonico.encode('utf-8')).hexdigest()[:16]


def aplicar_linha(
    campo, *, incluir, valor=None, conferido=False, escolha=None,
    ha_convertido=None, confirmo_conversao=False, usuario=None, agora=None,
):
    """Aplica a revisão em memória e registra autoria só quando algo muda."""
    campos_escolha = (
        'pessoa_escolhida_id', 'cartorio_escolhido_id', 'criar_novo',
    )
    antes = versao_linha(campo)

    if not incluir:
        campo.status_revisao = 'descartado'
    elif (
        campo.tipo_valor == 'area'
        and (
            MOTIVO_UNIDADE_AREA in campo.motivos_revisao
            or campo.area_convertida
        )
        and destinos.destino_de(campo.chave) != destinos.SEM_DESTINO
    ):
        if ha_convertido and confirmo_conversao:
            canonico = valores.do_formulario(
                'area', ha_convertido, destinos.destino_de(campo.chave)
            )
            campo.valor_final = canonico
            campo.area_convertida = True
            campo.status_revisao = (
                'aceito' if conferido and canonico == campo.normalized
                else 'editado'
            )
            campo.motivos_revisao = [
                motivo for motivo in campo.motivos_revisao
                if motivo != MOTIVO_UNIDADE_AREA
            ]
        elif ha_convertido is None and not confirmo_conversao:
            campo.area_convertida = False
            campo.valor_final = None
            campo.status_revisao = 'sugerido'
            # Uma conversão limpa volta a exigir decisão sobre a unidade.
            if MOTIVO_UNIDADE_AREA not in campo.motivos_revisao:
                campo.motivos_revisao = [
                    *campo.motivos_revisao, MOTIVO_UNIDADE_AREA,
                ]
        else:
            raise valores.ValorInvalido('conversao_incompleta')
    else:
        canonico = (
            valores.do_formulario(
                campo.tipo_valor, valor, destinos.destino_de(campo.chave)
            )
            if valor is not None else campo.normalized
        )
        if valor is None and campo.tipo_valor == 'enum':
            # Conferir/reincluir também valida o valor que será preservado.
            valores.do_formulario(
                'enum',
                _valor_efetivo(campo) if campo.status_revisao == 'descartado' else canonico,
                destinos.destino_de(campo.chave),
            )
        if canonico != campo.normalized:
            campo.status_revisao = 'editado'
            campo.valor_final = canonico
        elif campo.status_revisao == 'descartado' and valor is None:
            # Reincluir sem novo valor recupera a edição preservada.
            campo.status_revisao = (
                'editado' if campo.valor_final is not None else 'sugerido'
            )
        else:
            campo.valor_final = None
            campo.status_revisao = 'aceito' if conferido else 'sugerido'

    if escolha is not None:
        for nome in campos_escolha:
            if nome in escolha:
                setattr(campo, nome, escolha[nome])
        # Escolher um existente e "criar novo" se excluem: vence o que veio.
        if escolha.get('criar_novo'):
            campo.pessoa_escolhida_id = None
            campo.cartorio_escolhido_id = None
        elif escolha.get('pessoa_escolhida_id') or escolha.get(
            'cartorio_escolhido_id'
        ):
            campo.criar_novo = False

    if versao_linha(campo) != antes:
        campo.revisado_por = usuario
        campo.revisado_em = agora if agora is not None else timezone.now()
    return campo


def _valor_efetivo(campo):
    return campo.valor_final if campo.valor_final is not None else campo.normalized


def identidade_parte(chave, linhas):
    """Identidade revisada usada para invalidar a escolha de cadastro da parte."""
    identidade = []
    for sufixo in ('nome', 'documento_identificacao/tipo', 'documento_identificacao/valor'):
        campo = linhas.get(f'{chave}/{sufixo}')
        identidade.append(
            _valor_efetivo(campo)
            if campo is not None and campo.status_revisao != 'descartado' else None
        )
    return tuple(identidade)


def _contexto_revisao(extracao):
    """Indexa as linhas incluídas, respeitando o descarte dos ancestrais."""
    por_chave = {campo.chave: campo for campo in extracao.campos.all()}
    incluidas = {}
    for chave, campo in por_chave.items():
        ancestral = chave
        while ancestral:
            linha = por_chave.get(ancestral)
            if linha is not None and linha.status_revisao == 'descartado':
                break
            ancestral = ancestral.rsplit('/', 1)[0]
        else:
            incluidas[chave] = campo
    atos = [campo for campo in incluidas.values() if campo.tipo_valor == 'ato']
    return incluidas, atos


def _campo_ausente(linhas, chave):
    campo = linhas.get(chave)
    if campo is None:
        return True
    valor = _valor_efetivo(campo)
    return valor is None or (isinstance(valor, str) and not valor.strip())


def _tipos_efetivos(linhas, atos):
    tipos_por_ato = {
        ato.chave: _valor_efetivo(linhas[f'{ato.chave}/tipo_sugerido'])
        for ato in atos
        if not _campo_ausente(linhas, f'{ato.chave}/tipo_sugerido')
    }
    configuracoes = {}
    for tipo in LancamentoTipo.objects.filter(
        tipo__in=set(tipos_por_ato.values())
    ).order_by('pk'):
        configuracoes.setdefault(tipo.tipo, tipo)
    return tipos_por_ato, configuracoes


def pendencias(extracao) -> list[dict]:
    """Bloqueios das linhas incluídas e dos destinos obrigatórios ausentes."""
    linhas, atos = _contexto_revisao(extracao)
    if not atos:
        return [{'chave': '/acts', 'motivo': 'nenhum_ato', 'bloqueante': True}]

    resultado = []

    def adicionar(chave, motivo):
        resultado.append({'chave': chave, 'motivo': motivo, 'bloqueante': True})

    escolhas = [
        campo for campo in linhas.values()
        if campo.tipo_valor in ('parte', 'cartorio')
    ]
    pessoas = set(Pessoas.objects.filter(
        pk__in={campo.pessoa_escolhida_id for campo in escolhas
                if campo.pessoa_escolhida_id}
    ).values_list('pk', flat=True))
    cartorios = set(Cartorios.objects.filter(
        pk__in={campo.cartorio_escolhido_id for campo in escolhas
                if campo.cartorio_escolhido_id}
    ).values_list('pk', flat=True))

    for campo in linhas.values():
        if campo.requer_revisao and campo.status_revisao == 'sugerido':
            adicionar(campo.chave, 'revisao_pendente')
        if campo.tipo_valor in ('parte', 'cartorio'):
            if not (
                campo.pessoa_escolhida_id or campo.cartorio_escolhido_id
                or campo.criar_novo
            ):
                adicionar(campo.chave, 'escolha_pendente')
            elif (
                campo.pessoa_escolhida_id
                and campo.pessoa_escolhida_id not in pessoas
            ) or (
                campo.cartorio_escolhido_id
                and campo.cartorio_escolhido_id not in cartorios
            ):
                adicionar(campo.chave, 'decisao_perdida')
        if (
            'match_invalidado' in campo.motivos_revisao
            and campo.status_revisao == 'sugerido'
        ):
            adicionar(campo.chave, 'match_invalidado')
        if (
            campo.tipo_valor == 'area'
            and _AREA_DE_ATO.fullmatch(campo.chave)
            and MOTIVO_UNIDADE_AREA in campo.motivos_revisao
            and not campo.area_convertida
        ):
            adicionar(campo.chave, MOTIVO_UNIDADE_AREA)
        motivo = valores.validar_destino(
            destinos.destino_de(campo.chave), _valor_efetivo(campo)
        )
        if motivo:
            adicionar(campo.chave, motivo)

    obrigatorios = [f'/document/{nome}' for nome in _OBRIGATORIOS_DOCUMENTO]
    tipos_por_ato, configuracoes = _tipos_efetivos(linhas, atos)
    for ato in atos:
        obrigatorios.extend(f'{ato.chave}/{nome}' for nome in _OBRIGATORIOS_ATO)
        tipo_efetivo = tipos_por_ato.get(ato.chave)
        tipo = configuracoes.get(tipo_efetivo)
        for flag, caminho in (
            ('requer_titulo', 'titulo'),
            ('requer_descricao', 'descricao'),
        ):
            if tipo is not None and getattr(tipo, flag):
                obrigatorios.append(f'{ato.chave}/{caminho}')
        if (
            tipo_efetivo == 'inicio_matricula'
            or (tipo is not None and tipo.requer_cartorio_origem)
        ):
            obrigatorios.append(f'{ato.chave}/origem/cartorio')
    for chave in obrigatorios:
        if _campo_ausente(linhas, chave):
            adicionar(chave, 'obrigatorio_ausente')
    return resultado


def avisos(extracao) -> list[dict]:
    """Campos recomendados pelo tipo efetivo; nunca impedem a revisão."""
    linhas, atos = _contexto_revisao(extracao)
    tipos_por_ato, configuracoes = _tipos_efetivos(linhas, atos)
    resultado = []
    for ato in atos:
        tipo = configuracoes.get(tipos_por_ato.get(ato.chave))
        if tipo is None:
            continue
        for flag, caminho in (
            ('requer_forma', 'forma'),
            ('requer_detalhes', 'detalhes'),
            ('requer_observacao', 'observacoes'),
            ('requer_livro_origem', 'origem/livro'),
            ('requer_folha_origem', 'origem/folha'),
            ('requer_data_origem', 'origem/data'),
        ):
            chave = f'{ato.chave}/{caminho}'
            if getattr(tipo, flag) and _campo_ausente(linhas, chave):
                resultado.append({
                    'chave': chave, 'motivo': flag, 'bloqueante': False,
                })
        if tipo.requer_transmissao:
            papeis = {
                _valor_efetivo(campo) for campo in linhas.values()
                if campo.tipo_valor == 'parte'
                and campo.chave.startswith(f'{ato.chave}/partes/')
            }
            if not {'transmitente', 'adquirente'} <= papeis:
                resultado.append({
                    'chave': f'{ato.chave}/partes',
                    'motivo': 'requer_transmissao', 'bloqueante': False,
                })
    return resultado


def desnormalizar(extracao, payload, paginas) -> list[CampoSugerido]:
    """Payload A3 → linhas de ``CampoSugerido`` não salvas, em ordem estável.

    ``paginas`` é a lista de ``PaginaOcr`` do job: a evidência só aponta
    para página que existe ali, e o trecho só é mantido se for substring
    literal do texto vigente daquela página — ``texto_corrigido`` (decisão
    #290) ou, sem ele, o ``texto_ocr`` puro.
    """
    texto_paginas = {
        pagina.numero_pagina: pagina.texto_corrigido or pagina.texto_ocr
        for pagina in paginas
    }
    linhas = _folhas(extracao, '/document', payload.get('document'), texto_paginas)
    linhas += _placeholders_documento(extracao, payload.get('document'))
    for indice, ato in enumerate(payload.get('acts') or []):
        linhas += _ato(extracao, f'/acts/{indice}', ato, texto_paginas)
    linhas += _folhas(extracao, '/closure', payload.get('closure'), texto_paginas)
    return linhas


def _eh_folha(no):
    """Folha editável do A3: objeto com a chave ``normalized``."""
    return isinstance(no, dict) and 'normalized' in no


def _folhas(extracao, ponteiro, no, texto_paginas):
    """Recursão genérica: uma linha por folha editável do ramo."""
    if _eh_folha(no):
        return [_de_campo(extracao, ponteiro, no, texto_paginas)]
    if isinstance(no, dict):
        linhas = []
        for chave, valor in no.items():
            linhas += _folhas(
                extracao, f'{ponteiro}/{chave}', valor, texto_paginas
            )
        return linhas
    if isinstance(no, list):
        linhas = []
        for indice, item in enumerate(no):
            linhas += _folhas(
                extracao, f'{ponteiro}/{indice}', item, texto_paginas
            )
        return linhas
    return []


def _ato(extracao, ponteiro, ato, texto_paginas):
    """Linha estrutural do ato + placeholders + folhas + partes."""
    linhas = [_de_ato(extracao, ponteiro, ato, texto_paginas)]
    for nome in _OBRIGATORIOS_ATO:
        if not _eh_folha(ato.get(nome)):
            linhas.append(_placeholder(extracao, f'{ponteiro}/{nome}'))
    for nome, valor in ato.items():
        if nome != 'partes':
            linhas += _folhas(
                extracao, f'{ponteiro}/{nome}', valor, texto_paginas
            )
    for indice, parte in enumerate(ato.get('partes') or []):
        linhas += _parte(
            extracao, f'{ponteiro}/partes/{indice}', parte, texto_paginas
        )
    return linhas


def _parte(extracao, ponteiro, parte, texto_paginas):
    """Linha estrutural da parte (normalized = papel) + folhas."""
    linhas = [_de_parte(extracao, ponteiro, parte, texto_paginas)]
    for nome, valor in parte.items():
        linhas += _folhas(
            extracao, f'{ponteiro}/{nome}', valor, texto_paginas
        )
    return linhas


def _placeholders_documento(extracao, document):
    if not isinstance(document, dict):
        document = {}
    return [
        _placeholder(extracao, f'/document/{nome}')
        for nome in _OBRIGATORIOS_DOCUMENTO
        if not _eh_folha(document.get(nome))
    ]


def _valor_do_payload(tipo, valor):
    """Valor do A3 → campo do modelo preservando ``None``.

    ``valores.do_payload`` converte ``None`` em ``''``, o que perderia a
    distinção entre "não normalizado" e "vazio" (``raw``/``normalized``
    aceitam NULL no modelo): ``None`` permanece ``None`` e só
    ``str``/``bool`` passam pelo codec.
    """
    if valor is None:
        return None
    return valores.do_payload(tipo, valor)


def _de_campo(extracao, ponteiro, campo, texto_paginas):
    """Linha de uma folha editável, com tipos/motivos do §18."""
    tipo_valor = destinos.destino_de(ponteiro).tipo_valor
    motivos = []

    normalized = _valor_do_payload(tipo_valor, campo.get('normalized'))
    if tipo_valor in _TIPOS_NORMALIZAVEIS:
        if normalized is None:
            # Não normalizado (null) ≠ vazio: sem canônico, há pendência.
            motivos.append(MOTIVO_NORMALIZACAO_INVALIDA)
        else:
            try:
                valores.para_python(tipo_valor, normalized)
            except valores.ValorInvalido:
                motivos.append(MOTIVO_NORMALIZACAO_INVALIDA)
                normalized = None
    if _AREA_DE_ATO.fullmatch(ponteiro) and campo.get('unidade') != 'ha':
        motivos.append(MOTIVO_UNIDADE_AREA)

    confianca = campo.get('confianca')
    _checar_confianca(confianca, motivos)
    if ponteiro.startswith('/closure'):
        motivos.append(MOTIVO_CLOSURE)
    pagina, trecho, bbox = _resolver_evidencia(
        campo.get('evidencia'), texto_paginas, motivos
    )
    candidatos, escolhido = [], None
    if tipo_valor == 'cartorio':
        sugestao = campo.get('match_sugerido')
        if isinstance(sugestao, dict):
            candidatos, escolhido = _candidatos_do_match(
                sugestao.get('cartorio_id'), sugestao.get('candidatos'),
            )

    return CampoSugerido(
        extracao=extracao,
        chave=ponteiro,
        raw=_valor_do_payload(tipo_valor, campo.get('raw')),
        normalized=normalized,
        tipo_valor=tipo_valor,
        confianca=confianca,
        requer_revisao=bool(campo.get('requer_revisao')) or bool(motivos),
        motivos_revisao=motivos,
        match_candidatos=candidatos,
        cartorio_escolhido_id=escolhido,
        evidencia_pagina=pagina,
        evidencia_trecho=trecho,
        evidencia_bbox=bbox,
    )


def _de_ato(extracao, ponteiro, ato, texto_paginas):
    """Linha estrutural do ato: chave ``/acts/{i}``, normalized = rótulo."""
    motivos = []
    confianca = _checar_confianca(ato.get('confianca'), motivos)
    pagina, trecho, bbox = _resolver_evidencia(
        ato.get('evidencia'), texto_paginas, motivos
    )
    rotulo = ato.get('rotulo') if _eh_folha(ato.get('rotulo')) else {}
    return CampoSugerido(
        extracao=extracao,
        chave=ponteiro,
        raw=None,
        normalized=_valor_do_payload('ato', rotulo.get('normalized')),
        tipo_valor='ato',
        confianca=confianca,
        requer_revisao=bool(ato.get('requer_revisao')) or bool(motivos),
        motivos_revisao=motivos,
        evidencia_pagina=pagina,
        evidencia_trecho=trecho,
        evidencia_bbox=bbox,
    )


def _de_parte(extracao, ponteiro, parte, texto_paginas):
    """Linha estrutural da parte: normalized = papel efetivo."""
    motivos = []
    confianca = _checar_confianca(parte.get('confianca'), motivos)
    pagina, trecho, bbox = _resolver_evidencia(
        parte.get('evidencia'), texto_paginas, motivos
    )
    candidatos, escolhido = _candidatos_do_match(
        parte.get('match_pessoa_id'), parte.get(MATCH_PESSOA_CANDIDATOS),
    )
    return CampoSugerido(
        extracao=extracao,
        chave=ponteiro,
        raw=None,
        normalized=parte.get('papel'),
        tipo_valor='parte',
        confianca=confianca,
        requer_revisao=bool(parte.get('requer_revisao')) or bool(motivos),
        motivos_revisao=motivos,
        match_candidatos=candidatos,
        pessoa_escolhida_id=escolhido,
        evidencia_pagina=pagina,
        evidencia_trecho=trecho,
        evidencia_bbox=bbox,
    )


def _id_valido(valor):
    return type(valor) is int and valor > 0


def _candidatos_do_match(unico, candidatos=None):
    """``(match_candidatos, escolhido_id|None)`` a partir do enriquecimento.

    Só ids do payload enriquecido: único → ``([id], id)``; mais de um
    candidato → ``(ids, None)`` (o revisor escolhe); nenhum → ``([], None)``.
    """
    if _id_valido(unico):
        return [unico], unico
    ids = []
    for valor in candidatos if isinstance(candidatos, list) else []:
        if _id_valido(valor) and valor not in ids:
            ids.append(valor)
    if len(ids) == 1:
        return ids, ids[0]
    return ids, None


def _placeholder(extracao, chave):
    """Destino obrigatório ausente: linha vazia, sempre em revisão."""
    return CampoSugerido(
        extracao=extracao,
        chave=chave,
        raw=None,
        normalized=None,
        tipo_valor=destinos.destino_de(chave).tipo_valor,
        confianca=None,
        requer_revisao=True,
        motivos_revisao=[],
        evidencia_pagina=None,
        evidencia_trecho='',
        evidencia_bbox=None,
    )


def _checar_confianca(confianca, motivos):
    """Não nula e < limiar → ``baixa_confianca``; devolve a confiança."""
    if confianca is not None and confianca < LIMIAR_CONFIANCA:
        motivos.append(MOTIVO_BAIXA_CONFIANCA)
    return confianca


def _bbox_valido(bbox):
    """bbox aproveitável: lista JSON de exatamente 4 números (bool excluído)."""
    return (
        isinstance(bbox, list)
        and len(bbox) == 4
        and all(
            isinstance(valor, (int, float)) and not isinstance(valor, bool)
            for valor in bbox
        )
    )


def _resolver_evidencia(evidencia, texto_paginas, motivos):
    """(pagina, trecho, bbox) confiáveis; acumula motivos quando não são.

    Página fora do job → ``evidencia_invalida`` (pagina vira ``None``).
    Trecho que não é substring do texto vigente da página — ou página
    inexistente, onde nada é verificável — → ``trecho_ausente`` (trecho
    vira ``''``). Sem evidência (``None``) não é pendência: o A3 a admite
    nula.

    ``bbox`` (decisão #290/17-10, pixels do OCR) é preservado só quando é
    lista de 4 números; fora disso vira ``None`` e NÃO é pendência — é
    conveniência de template, e a conversão pixel→ponto de PDF (dpi do
    job) não é desta camada.
    """
    if not isinstance(evidencia, dict):
        return None, '', None
    bbox = evidencia.get('bbox')
    if not _bbox_valido(bbox):
        bbox = None
    numero = evidencia.get('pagina')
    if numero in texto_paginas:
        pagina = numero
    else:
        pagina = None
        motivos.append(MOTIVO_EVIDENCIA_INVALIDA)
    trecho = evidencia.get('trecho')
    texto = texto_paginas.get(pagina) if pagina is not None else None
    if texto is not None and isinstance(trecho, str) and trecho in texto:
        return pagina, trecho, bbox
    motivos.append(MOTIVO_TRECHO_AUSENTE)
    return pagina, '', bbox


# ---------------------------------------------------------------------------
# Matching determinístico (I-5, §2.A): camada Python, nunca do modelo.
# ---------------------------------------------------------------------------

_NAO_DIGITO = re.compile(r'\D')

# Campos fieldCartorio do A3, por posição no payload (schema vendorizado):
# cada um recebe ``match_sugerido`` no enriquecimento.
MATCH_PESSOA_CANDIDATOS = 'match_pessoa_candidatos'

_CARTORIOS_DO_DOCUMENTO = ('cartorio', 'cri_atual')
_CARTORIOS_DO_ATO = ('cartorio_transmissao',)


def _normalizar_nome(texto):
    """Forma canônica para comparação: NFKD sem acentos, sem caixa,
    espaços colapsados. Não-string (None, lixo) → ``''``."""
    if not isinstance(texto, str):
        return ''
    decomposto = unicodedata.normalize('NFKD', texto)
    sem_acentos = ''.join(
        caractere for caractere in decomposto
        if not unicodedata.combining(caractere)
    )
    return ' '.join(sem_acentos.casefold().split())


def _so_digitos(texto):
    if not isinstance(texto, str):
        return ''
    return _NAO_DIGITO.sub('', texto)


def _cpf_utilizavel(documento_tipo, documento_valor):
    """Dígitos do CPF quando o documento casa por documento; senão ``None``.

    Só CPF com EXATAMENTE 11 dígitos casa por documento. CPF mascarado
    (contém ``*``/``X``) ou com menos de 11 dígitos, e qualquer outro tipo
    (CNPJ, CGC, RG, OUTRO), nunca casam por documento — documento
    incompleto não é identidade (§party: nunca completar dígitos
    mascarados).
    """
    if documento_tipo != 'CPF' or not isinstance(documento_valor, str):
        return None
    if '*' in documento_valor or 'x' in documento_valor.lower():
        return None
    digitos = _so_digitos(documento_valor)
    return digitos if len(digitos) == 11 else None


class IndicePessoas:
    """Índice de ``Pessoas`` em memória: UMA query na construção.

    ``values_list('id', 'nome', 'cpf')`` uma única vez; todo ``match`` é
    puro, sem banco.
    """

    def __init__(self):
        self._por_nome = {}
        self._por_cpf = {}
        for pessoa_id, nome, cpf in Pessoas.objects.values_list(
            'id', 'nome', 'cpf'
        ):
            chave = _normalizar_nome(nome)
            if chave:
                self._por_nome.setdefault(chave, []).append(pessoa_id)
            digitos = _so_digitos(cpf)
            if len(digitos) == 11:
                self._por_cpf.setdefault(digitos, []).append(pessoa_id)

    def match(self, nome, documento_tipo=None, documento_valor=None):
        """``(escolhido_id|None, candidatos)``: CPF exato primeiro, nome depois.

        CPF utilizável (11 dígitos, sem máscara) casa por ``cpf`` exato:
        único → escolhido; vários → candidatos (humano decide). CPF que não
        casa ninguém — assim como CPF mascarado/incompleto ou
        CNPJ/CGC/OUTRO — cai no nome normalizado: 1 → escolhido; >1 →
        candidatos; 0 → ``(None, [])``. Matching sugere, nunca adivinha:
        a escolha é do revisor.
        """
        digitos = _cpf_utilizavel(documento_tipo, documento_valor)
        if digitos is not None:
            ids = self._por_cpf.get(digitos, [])
            if len(ids) == 1:
                return ids[0], []
            if ids:
                return None, ids
        chave = _normalizar_nome(nome)
        if not chave:
            return None, []
        ids = self._por_nome.get(chave, [])
        if len(ids) == 1:
            return ids[0], []
        return None, ids


class IndiceCartorios:
    """Índice de ``Cartorios`` em memória: UMA query na construção.

    ``values_list('id', 'nome', 'cidade')`` uma única vez; todo ``match``
    é puro, sem banco.
    """

    def __init__(self):
        self._por_nome = {}
        for cartorio_id, nome, cidade in Cartorios.objects.values_list(
            'id', 'nome', 'cidade'
        ):
            chave = _normalizar_nome(nome)
            if chave:
                self._por_nome.setdefault(chave, []).append(
                    (cartorio_id, _normalizar_nome(cidade))
                )

    def match(self, nome, cidade=None):
        """``(escolhido_id|None, candidatos)`` por nome normalizado + cidade.

        Cidade informada filtra: cidade divergente — ou cartório sem cidade
        para confirmar — não casa (homônimo de outro município é outro
        cartório). Sem cidade, vale só o nome. 1 → escolhido; >1 →
        candidatos; 0 → ``(None, [])``.
        """
        chave = _normalizar_nome(nome)
        if not chave:
            return None, []
        entradas = self._por_nome.get(chave, [])
        cidade_chave = _normalizar_nome(cidade)
        if cidade_chave:
            entradas = [
                entrada for entrada in entradas
                if entrada[1] == cidade_chave
            ]
        ids = [cartorio_id for cartorio_id, _cidade in entradas]
        if len(ids) == 1:
            return ids[0], []
        return None, ids


def _normalized(no):
    """``normalized`` de um campo A3; ``None`` se o nó não é dict."""
    return no.get('normalized') if isinstance(no, dict) else None


def enriquecer_payload(payload, indice_pessoas, indice_cartorios):
    """Matching determinístico escrito numa CÓPIA do payload A3.

    - todo fieldCartorio (``document.cartorio``/``cri_atual``,
      ``acts[].cartorio_transmissao``, ``acts[].origem.cartorio``) recebe
      ``match_sugerido`` = ``{cartorio_id: único|None, candidatos: [ids]}``;
    - toda parte (``acts[].partes[]``) recebe ``match_pessoa_id``
      (único|None) e ``match_pessoa_candidatos`` (ids, vazia quando há
      único) pelo nome + documento de identificação.

    O original não é mutado. ``match_sugerido`` e ``match_pessoa_id`` são do
    schema vendorizado; ``match_pessoa_candidatos`` é extensão LOCAL (o A3
    da party não tem lista de candidatos) — o enriquecido só é válido no A3
    sem ela, e só ``payload_servico`` passa por ``validar_payload``. Match
    vindo do serviço, se houver, é sobrescrito — matching é decisão desta
    camada, nunca do modelo.
    """
    enriquecido = copy.deepcopy(payload)
    document = enriquecido.get('document')
    if isinstance(document, dict):
        for nome in _CARTORIOS_DO_DOCUMENTO:
            _sugerir_cartorio(document.get(nome), indice_cartorios)
    for ato in enriquecido.get('acts') or []:
        if not isinstance(ato, dict):
            continue
        for nome in _CARTORIOS_DO_ATO:
            _sugerir_cartorio(ato.get(nome), indice_cartorios)
        origem = ato.get('origem')
        if isinstance(origem, dict):
            _sugerir_cartorio(origem.get('cartorio'), indice_cartorios)
        for parte in ato.get('partes') or []:
            _sugerir_pessoa(parte, indice_pessoas)
    return enriquecido


def _sugerir_cartorio(campo, indice_cartorios):
    """``match_sugerido`` de um fieldCartorio (nó ausente/não-dict: nada)."""
    if not isinstance(campo, dict):
        return
    escolhido, candidatos = indice_cartorios.match(
        _normalized(campo), campo.get('municipio')
    )
    campo['match_sugerido'] = {
        'cartorio_id': escolhido,
        'candidatos': candidatos,
    }


def _sugerir_pessoa(parte, indice_pessoas):
    """``match_pessoa_id`` + ``match_pessoa_candidatos`` de uma party.

    Nome + documento de identificação. Homônimos ficam em
    ``match_pessoa_candidatos`` (ids em ordem de pk) com ``match_pessoa_id``
    nulo: o revisor escolhe.
    """
    if not isinstance(parte, dict):
        return
    documento = parte.get('documento_identificacao')
    if not isinstance(documento, dict):
        documento = {}
    escolhido, candidatos = indice_pessoas.match(
        _normalized(parte.get('nome')),
        _normalized(documento.get('tipo')),
        _normalized(documento.get('valor')),
    )
    parte['match_pessoa_id'] = escolhido
    parte[MATCH_PESSOA_CANDIDATOS] = sorted(candidatos)
