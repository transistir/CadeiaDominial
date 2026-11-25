"""
Observações documentais × analíticas no campo único ``Lancamento.observacoes``.

Issue **#400** (U-M237-08), desenho em
``docs/produto-3/ARQUITETURA_OCR_ASSISTIDO.md`` §5 (Q1=b). O campo guarda dois
tipos de conteúdo e eles NUNCA se misturam sem marca:

- **documental** — texto literal com lastro no documento, sem prefixo;
- **analítica** — ressalva/cálculo/conclusão do revisor, sempre marcada com
  autor e data: ``[ANÁLISE — <autor> — AAAA-MM-DD] <texto>``.

Não há migration nesta etapa: a autoria vive no próprio texto. A evolução
para campo/tabela própria fica para depois, condicionada ao dono.

O prefill escreve apenas texto documental; a análise só entra por ação
explícita do revisor e com usuário autenticado.
"""

import re

from django.utils import timezone


ROTULO_ANALISE = 'ANÁLISE'

# Contrato do marcador (formato EXATO, reconhecido por ``MARCADOR_ANALISE_RE``):
#
#     [ANÁLISE — <autor> — AAAA-MM-DD]
#
# ``<autor>`` nunca contém ``—``, ``[``, ``]`` nem quebra de linha (validado em
# ``marcador_analise``); ``AAAA-MM-DD`` é data ISO. Qualquer mudança aqui exige
# mudar a regex junto — exportação/PDF/filtros dependem desta forma.
MARCADOR_ANALISE_RE = re.compile(
    r'\[' + re.escape(ROTULO_ANALISE)
    + r' — (?P<autor>[^—\]]+) — (?P<data>\d{4}-\d{2}-\d{2})\]'
)

_DATA_ISO_RE = re.compile(r'^\d{4}-\d{2}-\d{2}$')


class AnaliseSemAutor(ValueError):
    """Análise só existe com autoria: falta de autor é erro explícito."""


def normalizar_quebras(texto):
    """Quebra de linha do campo é ``\\n`` — converte CRLF/CR na entrada.

    O textarea do navegador submete ``\\r\\n`` mesmo quando o serviço gravou
    ``\\n\\n`` como separador de blocos. Sem normalizar, o bloco analítico
    volta colado ao documental num único parágrafo, ``remover_analises``
    deixa de separá-lo e o texto do revisor passa a alimentar
    ``buscar_keyword`` (#400 v2). ``None``/``''`` são preservados.
    """
    if not texto:
        return texto
    return texto.replace('\r\n', '\n').replace('\r', '\n')


def nome_do_autor(user):
    """Nome efetivo do autor, ou ``None`` para anônimo/sem nome.

    ``get_full_name()`` tem prioridade; sem ele, ``get_username()``.
    """
    if user is None or not getattr(user, 'is_authenticated', False):
        return None
    nome = (user.get_full_name() or '').strip()
    if not nome:
        nome = (user.get_username() or '').strip()
    return nome or None


def marcador_analise(autor, data=None):
    """``[ANÁLISE — <autor> — AAAA-MM-DD]``; data default = hoje local.

    Autor vazio/só espaços, autor com ``—``/``[``/``]`` ou quebra de linha
    (qualquer um quebraria ou forjaria o próprio marcador) ou data fora do
    ISO ``AAAA-MM-DD`` levantam ``AnaliseSemAutor``.
    """
    nome = str(autor).strip() if autor is not None else ''
    if not nome or any(caractere in nome for caractere in '—][\r\n'):
        raise AnaliseSemAutor(
            'Análise exige autor válido (sem —, [, ] nem quebras de linha).'
        )

    if data is None:
        data = timezone.localdate()
    data_iso = data.isoformat() if hasattr(data, 'isoformat') else str(data)
    if not _DATA_ISO_RE.match(data_iso):
        raise AnaliseSemAutor(
            f'Data inválida para o marcador de análise: {data!r}.'
        )

    return f'[{ROTULO_ANALISE} — {nome} — {data_iso}]'


def registrar_analise(documental, texto_analise, autor, data=None):
    """Junta documental + bloco analítico marcado.

    - ``texto_analise`` vazio/só espaços devolve ``documental`` INTACTO
      (documental nunca recebe prefixo);
    - sem autor levanta ``AnaliseSemAutor``;
    - senão: documental normalizado + ``\\n\\n`` + marcador + texto. Sem
      documental, sai só o bloco analítico.
    """
    texto = normalizar_quebras(texto_analise or '').strip()
    if not texto:
        return documental

    marcador = marcador_analise(autor, data)
    documental_limpo = normalizar_quebras(documental or '').strip()
    bloco = f'{marcador} {texto}'
    if documental_limpo:
        return f'{documental_limpo}\n\n{bloco}'
    return bloco


def _blocos_de_paragrafo(texto):
    # Normaliza na entrada: linhas legadas já gravadas com CRLF (e o POST de
    # edição do navegador) precisam separar blocos igual às gravadas com \n\n.
    return normalizar_quebras(texto).split('\n\n')


def remover_analises(texto):
    """Remove blocos analíticos inteiros; preserva o documental.

    Determinístico por parágrafo: descarta o bloco cujo texto começa com o
    marcador, rejunta o resto com ``\\n\\n``.
    """
    if not texto:
        return ''
    blocos = _blocos_de_paragrafo(texto)
    restantes = [
        bloco for bloco in blocos
        if not MARCADOR_ANALISE_RE.match(bloco.lstrip())
    ]
    return '\n\n'.join(restantes)


def tem_analise(texto):
    """Há ao menos um bloco analítico marcado?"""
    if not texto:
        return False
    return any(
        MARCADOR_ANALISE_RE.match(bloco.lstrip())
        for bloco in _blocos_de_paragrafo(texto)
    )


def observacoes_da_requisicao(request):
    """Valor de ``observacoes`` a gravar, já com a análise marcada.

    Sem ``analise_texto`` devolve o POST do campo documental com as quebras
    de linha normalizadas para ``\\n`` (preserva ``None``/``''``/espaços).
    Com análise, exige usuário autenticado: sem autor levanta
    ``AnaliseSemAutor`` e nada é gravado. Nos dois ramos o contrato do campo
    é ``\\n`` — o CRLF do textarea nunca chega ao banco (#400 v2).
    """
    documental = normalizar_quebras(request.POST.get('observacoes'))
    texto_analise = request.POST.get('analise_texto')
    if not (texto_analise or '').strip():
        return documental

    autor = nome_do_autor(getattr(request, 'user', None))
    return registrar_analise(documental, texto_analise, autor)
