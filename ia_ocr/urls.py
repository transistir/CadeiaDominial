"""Rotas da app ia_ocr, montadas sob o prefixo ``dominial/`` (cadeia_dominial/urls.py).

Mesmo padrão das rotas de OCR do upload digital (hierarquia TI→Imóvel→
Documento): ``tis/<tis>/imovel/<imovel>/documento/<doc>/ocr-job/<uuid>/...``.
"""

from django.urls import path

from . import views

_BASE = (
    'tis/<int:tis_id>/imovel/<int:imovel_id>/documento/<int:documento_id>/'
    'ocr-job/<uuid:job_id>/'
)

urlpatterns = [
    path(_BASE + 'texto/', views.texto_job_ocr, name='texto_job_ocr'),
    path(
        _BASE + 'texto/pagina/<int:numero>/confirmar/',
        views.confirmar_pagina_ocr, name='confirmar_pagina_ocr',
    ),
    path(
        _BASE + 'texto/pagina/<int:numero>/editar/',
        views.editar_pagina_ocr, name='editar_pagina_ocr',
    ),
    path(
        _BASE + 'texto/confirmar-todas/',
        views.confirmar_paginas_ocr, name='confirmar_paginas_ocr',
    ),
    path(
        _BASE + 'texto/reprocessar/',
        views.reprocessar_job_ocr, name='reprocessar_job_ocr',
    ),
    path(
        _BASE + 'texto/extrair-campos/',
        views.extrair_campos_ocr, name='extrair_campos_ocr',
    ),
    # Ponto de entrada da revisão de campos (I-5 / #262): a tela vem na I-5.
    path(_BASE + 'campos/', views.campos_job_ocr, name='campos_job_ocr'),
]
