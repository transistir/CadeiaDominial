"""``campos_job_ocr`` — entrada legada da revisão (#341).

A rota é um redirect: a tela de cards (``revisao_campos.html`` +
``ocr_revisao.js``) foi aposentada pela revisão dentro do formulário de
lançamento (``views/revisar.py``) — fase 4 da #341 apagou o corpo da tela,
o template e o JS num diff só de remoção. Favoritos e abas abertas no
servidor de testes continuam chegando aqui e são encaminhados à entrada da
revisão; os POSTs JSON da tela velha dão 404.

Extraídos do monólito de views (etapa 3, limite de 400 linhas). As
máscaras de PII que viviam aqui foram para ``ia_ocr/mascaras.py``.
"""
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from django.views.decorators.http import require_GET

from .jobs import _contexto_job, _kwargs_job


@login_required
@require_GET
def campos_job_ocr(request, tis_id, imovel_id, documento_id, job_id):
    """Encaminha à revisão por formulário; a hierarquia segue valendo 404."""
    tis, imovel, documento, job = _contexto_job(
        request, tis_id, imovel_id, documento_id, job_id
    )
    return redirect('revisar_job_ocr', **_kwargs_job(tis, imovel, documento, job))
