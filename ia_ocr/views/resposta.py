"""Peças compartilhadas de resposta das telas: URLs, paginação e versão do
formulário.

Extraídas do monólito ``ia_ocr/views.py`` (etapa 3, limite de 400 linhas).
``_disponibilidade_extracao`` é alvo de ``mock.patch`` via o pacote
(``ia_ocr.views._disponibilidade_extracao``): quem a chama em tempo de
execução resolve o nome NO OBJETO DO PACOTE (``views._disponibilidade_
extracao``), senão o patch deixa de agir e o teste passa sem testar — ver
o docstring do ``ia_ocr/views/__init__.py``.

Os helpers de aviso e o decorator JSON que só a tela de cards usava
(``_avisos_descritos``, ``_aviso_nao_consta``, ``_avisos_da_resposta``,
``_respostas_json_ocr``) saíram com ela na fase 4 da #341.
"""
import re

from django.http import Http404
from django.urls import reverse

from .. import estados
from ..models import ESTADO_CONFIRMADA


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
