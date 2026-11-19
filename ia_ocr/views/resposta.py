"""Peças compartilhadas de resposta das telas: avisos da revisão, URLs,
paginação, versão do formulário e o decorator que mantém 404/405/CSRF em
JSON.

Extraídas do monólito ``ia_ocr/views.py`` (etapa 3, limite de 400 linhas).
``_disponibilidade_extracao`` é alvo de ``mock.patch`` via o pacote
(``ia_ocr.views._disponibilidade_extracao``): quem a chama em tempo de
execução resolve o nome NO OBJETO DO PACOTE (``views._disponibilidade_
extracao``), senão o patch deixa de agir e o teste passa sem testar — ver
o docstring do ``ia_ocr/views/__init__.py``.
"""
import re
from functools import wraps

from django.http import Http404, JsonResponse
from django.urls import reverse
from django.utils.decorators import decorator_from_middleware
from django.views.decorators.csrf import csrf_exempt

from dominial.managers import documentos_for_user

from .. import estados, revisao
from ..models import ESTADO_CONFIRMADA
from .middleware import _CsrfJsonMiddleware


def _avisos_descritos(request, extracao) -> list[dict]:
    """Avisos da revisão com o texto de negócio de cada um (#324).

    A MESMA fonte para a abertura da tela (``campos_job_ocr``) e para a
    resposta do save (``salvar_bloco_ocr``): o aviso (e o selo "não consta no
    documento") nasce do estado salvo da extração, então depois de um save a
    tela precisa do cálculo novo — nada de reimplementar a regra no cliente.
    O escopo do USUÁRIO alimenta o aviso de homônimo (#267): documento de
    outra TI nunca participa dele.
    """
    return [
        revisao.descrever_aviso(item)
        for item in revisao.avisos(
            extracao, documentos_queryset=documentos_for_user(request.user),
        )
    ]


def _aviso_nao_consta(item) -> bool:
    """O aviso é de "não consta no documento" (livro/folha da origem, #324).

    É ele que dá o selo ao card; a abertura da tela e a resposta do save usam
    este mesmo predicado, então o cliente não repete a lista de motivos.
    """
    return item['motivo'] in revisao.MOTIVOS_NAO_CONSTA


def _avisos_da_resposta(request, extracao) -> list[dict]:
    """Os avisos recalculados no formato da resposta do save (#324).

    Só o que a tela desenha: chave (alvo do selo), motivo (detalhe técnico),
    ``local``/``rotulo`` (texto de negócio) e ``nao_consta`` (o selo).
    """
    return [
        {
            'chave': item['chave'],
            'motivo': item['motivo'],
            'local': item['local'],
            'rotulo': item['rotulo'],
            'nao_consta': _aviso_nao_consta(item),
        }
        for item in _avisos_descritos(request, extracao)
    ]


def _url_tela(kwargs_job, numero=None):
    url = reverse('texto_job_ocr', kwargs=kwargs_job)
    return f'{url}?pagina={numero}' if numero else url


def _numero_pagina(bruto):
    """Número de página vindo da requisição, ou None se não for um.

    Limita a 6 dígitos: int() de string gigante levanta ValueError no Python
    3.11+ (e nenhum documento tem tantas páginas — acima disso é 404 de todo jeito).
    """
    if bruto is not None and re.fullmatch(r'[0-9]{1,6}', bruto):
        return int(bruto)
    return None


def _versao_do_formulario(request):
    """Versão da página que o formulário exibiu, ou None se ausente/inválida.

    Limite de dígitos pelo mesmo motivo de ``_numero_pagina``; o valor só é
    comparado em Python com a versão da página, nunca vai para o banco.
    """
    bruto = request.POST.get('versao')
    if bruto is not None and re.fullmatch(r'[0-9]{1,10}', bruto):
        return int(bruto)
    return None


def _destino(request, kwargs_job):
    """Tela de volta das ações gerais, na página em que o usuário estava."""
    return _url_tela(kwargs_job, _numero_pagina(request.POST.get('pagina')))


def _pagina_pedida(request, paginas):
    """Página do ``?pagina=N``; sem parâmetro, retoma na primeira pendente."""
    bruto = request.GET.get('pagina')
    if bruto is None:
        return next(
            (p for p in paginas if p.estado != ESTADO_CONFIRMADA), paginas[0]
        )
    numero = _numero_pagina(bruto)
    if numero is None:
        raise Http404('Página inválida.')
    for pagina in paginas:
        if pagina.numero_pagina == numero:
            return pagina
    raise Http404('Página inexistente.')


def _disponibilidade_extracao(job, paginas):
    """(pode_extrair, motivo): após a #290 só depende do OCR, não da confirmação.

    ``texto_confirmado`` continua aceito pelo serviço (#12): a tela desse
    estado precisa oferecer o mesmo botão que a de ``concluido``.

    Mesma regra de ``services.extrair_campos``: sem páginas ou com
    ``texto_ocr`` nulo, recusa; verso em branco (``''``) é legítimo.
    """
    if job.status not in (estados.CONCLUIDO, estados.TEXTO_CONFIRMADO):
        return False, 'Aguardando o OCR terminar.'
    if not paginas or any(pagina.texto_ocr is None for pagina in paginas):
        return False, 'O OCR não devolveu texto para todas as páginas.'
    return True, ''


def _respostas_json_ocr(view):
    """Mantém 404, 405 e rejeições CSRF em JSON, sem mudar o login_required."""
    protegida = decorator_from_middleware(_CsrfJsonMiddleware)(view)

    # A checagem CSRF é feita pela middleware local acima, com a mesma
    # proteção do Django. Evita apenas a resposta HTML da middleware global.
    @csrf_exempt
    @wraps(view)
    def resposta_json(request, *args, **kwargs):
        try:
            resposta = protegida(request, *args, **kwargs)
        except Http404:
            return JsonResponse({'erro': 'nao_encontrado'}, status=404)
        if resposta.status_code == 405:
            erro = JsonResponse({'erro': 'metodo_nao_permitido'}, status=405)
            erro['Allow'] = resposta['Allow']
            return erro
        return resposta

    return resposta_json
