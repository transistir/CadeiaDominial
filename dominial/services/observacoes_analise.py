"""
Observações documentais × analíticas no campo único ``Lancamento.observacoes``.

Issue **#400** (U-M237-08), desenho em
``docs/produto-3/ARQUITETURA_OCR_ASSISTIDO.md`` §5 (Q1=b). O campo guarda dois
tipos de conteúdo e eles NUNCA se misturam sem marca:

- **documental** — texto literal com lastro no documento, sem prefixo;
- **analítica** — ressalva/cálculo/conclusão do revisor, sempre marcada com
  autor e data e delimitada:

      [ANÁLISE — <autor> — AAAA-MM-DD] <texto, com parágrafos>
      [/ANÁLISE]

O delimitador de fim existe para o bloco analítico ter fronteira mesmo com
``\\n\\n`` internos: sem ele, só o primeiro parágrafo do revisor saía do texto e o
resto virava documental — e disparava badge (P1 #2 do Greptile, #400 v4).

Não há migration nesta etapa: a autoria vive no próprio texto. A evolução
para campo/tabela própria fica para depois, condicionada ao dono.

**O texto analítico é do servidor.** ``observacoes_da_requisicao`` nunca aceita
marcador vindo do POST: o textarea documental passa por ``remover_analises`` e
os blocos já gravados no banco são reanexados por ``analise_existente``. Autor e
data só nascem do usuário autenticado (P1 #1 do Greptile, #400 v4).
"""

import re

from django.utils import timezone


ROTULO_ANALISE = 'ANÁLISE'
DELIMITADOR_FIM = '[/ANÁLISE]'

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


def _sem_delimitadores(texto):
    """Tira do texto do revisor o que forjaria o próprio bloco.

    Marcador e ``[/ANÁLISE]`` são do servidor: digitados no texto analítico,
    encerrariam o bloco antes da hora e o resto do texto do revisor vazaria
    como documental (badge indevido).
    """
    limpo = MARCADOR_ANALISE_RE.sub('', texto.replace(DELIMITADOR_FIM, ''))
    return limpo.strip()


def registrar_analise(documental, texto_analise, autor, data=None):
    """Junta documental + bloco analítico marcado e fechado.

    - ``texto_analise`` vazio/só espaços devolve ``documental`` INTACTO
      (documental nunca recebe prefixo);
    - sem autor levanta ``AnaliseSemAutor``;
    - senão: documental normalizado + ``\\n\\n`` + marcador + texto +
      ``\\n[/ANÁLISE]``. Sem documental, sai só o bloco analítico.
    """
    texto = _sem_delimitadores(normalizar_quebras(texto_analise or ''))
    if not texto:
        return documental

    marcador = marcador_analise(autor, data)
    documental_limpo = normalizar_quebras(documental or '').strip()
    bloco = f'{marcador} {texto}\n{DELIMITADOR_FIM}'
    if documental_limpo:
        return f'{documental_limpo}\n\n{bloco}'
    return bloco


def _particionar(texto):
    """``(documental, blocos_analíticos)`` numa única passada, por parágrafo.

    Regra do bloco: começa num parágrafo com marcador e termina no
    ``[/ANÁLISE]`` — inclusive quando o texto do revisor tem ``\\n\\n``
    internos. Bloco **legado** (gravado antes do delimitador de fim, v1–v3)
    não tem fronteira confiável: vale do marcador até o próximo marcador ou o
    fim do texto; a regra é escolhida a favor de não vazar análise como
    documental (badge do sistema nasceria do texto do revisor).

    Fechamento e marcador são procurados dentro do parágrafo: sobra documental
    no mesmo parágrafo depois do ``[/ANÁLISE]`` é preservada.
    """
    documental, analises = [], []
    texto = normalizar_quebras(texto)
    if not texto:
        return '', []

    em_analise = None
    for bruto in texto.split('\n\n'):
        resto = bruto
        if em_analise is not None:
            if MARCADOR_ANALISE_RE.match(resto.lstrip()):
                # Legado sem fechamento termina no próximo marcador.
                analises.append('\n\n'.join(em_analise).strip())
                em_analise = None
            else:
                fim = resto.find(DELIMITADOR_FIM)
                if fim < 0:
                    em_analise.append(resto)
                    continue
                em_analise.append(resto[:fim + len(DELIMITADOR_FIM)])
                analises.append('\n\n'.join(em_analise).strip())
                em_analise = None
                sobra = resto[fim + len(DELIMITADOR_FIM):]
                if sobra.strip():
                    documental.append(sobra)
                continue

        if not MARCADOR_ANALISE_RE.match(resto.lstrip()):
            documental.append(bruto)
            continue

        fim = resto.find(DELIMITADOR_FIM)
        if fim < 0:
            em_analise = [resto]
            continue
        analises.append(resto[:fim + len(DELIMITADOR_FIM)].strip())
        sobra = resto[fim + len(DELIMITADOR_FIM):]
        if sobra.strip():
            documental.append(sobra)

    if em_analise is not None:
        analises.append('\n\n'.join(em_analise).strip())

    return '\n\n'.join(documental).strip(), analises


def blocos_de_analise(texto):
    """Blocos analíticos completos (marcador + texto + fechamento) do campo."""
    return _particionar(texto)[1]


def analises_marcadas(texto):
    """Blocos analíticos prontos para exibição somente leitura (``\\n\\n``)."""
    return '\n\n'.join(blocos_de_analise(texto))


def remover_analises(texto):
    """Remove os blocos analíticos inteiros; preserva o documental.

    Única implementação usada por badge (``buscar_keyword``), gravação e
    exportações (PDF/Excel): o que não é documental não dispara alerta nem
    vaza para o documento.
    """
    return _particionar(texto)[0]


def tem_analise(texto):
    """Há ao menos um bloco analítico marcado?"""
    return bool(blocos_de_analise(texto))


def observacoes_da_requisicao(request, analise_existente=''):
    """Valor de ``observacoes`` a gravar: documental do POST + análise do servidor.

    - o textarea documental passa por ``remover_analises``: marcador digitado
      ali é descartado e nunca vira autoria (#400 v4, P1 #1);
    - os blocos já gravados (``analise_existente``, valor do banco) são
      reanexados intactos — editar outro campo não perde autor/data originais;
    - ``analise_texto`` é assinado pelo usuário logado (``AnaliseSemAutor`` sem
      autor) e não duplica bloco já presente.

    O contrato de quebra de linha do campo é ``\\n`` — o CRLF do textarea nunca
    chega ao banco (#400 v2).
    """
    documental = remover_analises(request.POST.get('observacoes'))
    blocos = blocos_de_analise(analise_existente)
    texto_analise = normalizar_quebras(request.POST.get('analise_texto') or '')

    if texto_analise.strip():
        autor = nome_do_autor(getattr(request, 'user', None))
        novo = registrar_analise('', texto_analise, autor)
        if novo not in blocos:
            blocos.append(novo)

    return '\n\n'.join(parte for parte in [documental] + blocos if parte)
