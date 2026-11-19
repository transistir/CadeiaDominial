"""Middleware CSRF que responde em JSON nas telas JSON do OCR.

Extraída do monólito de views (etapa 3, limite de 400 linhas por
arquivo). Sem lógica nova: a ``_reject`` devolve o MESMO corpo/status de
sempre (``{'erro': 'csrf_invalido'}``, 403), só que em JSON e não em HTML.
"""
from django.http import JsonResponse
from django.middleware.csrf import CsrfViewMiddleware


class _CsrfJsonMiddleware(CsrfViewMiddleware):
    def _reject(self, request, reason):
        return JsonResponse({'erro': 'csrf_invalido'}, status=403)
