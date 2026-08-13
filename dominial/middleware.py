from django.shortcuts import redirect
from django.urls import reverse
from django.contrib.auth.decorators import login_required

class AuthenticationMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Lista de URLs que não precisam de autenticação
        public_urls = [
            '/accounts/login/',
            '/admin/login/',
            '/static/',
        ]

        # Se o usuário não estiver autenticado e tentar acessar uma URL protegida
        if not request.user.is_authenticated and not request.path.startswith(tuple(public_urls)):
            # Se vier do admin, redireciona para o login do admin
            if request.path.startswith('/admin/'):
                return redirect('admin:login')
            # Caso contrário, redireciona para nosso login personalizado
                return redirect('login')

        response = self.get_response(request)
        return response


import json
import re
from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.template.loader import render_to_string


class MaintenanceMiddleware:
    """Bloqueia escritas durante manutenção programada."""

    WRITE_METHODS = {'POST', 'PUT', 'PATCH', 'DELETE'}

    # URLs que sempre passam (mesmo durante manutenção)
    EXEMPT_PREFIXES = (
        '/accounts/login/',
        '/accounts/logout/',
        '/admin/',
        '/static/',
        '/media/',
    )

    # GETs que produzem escrita no banco (write-on-read)
    WRITE_ON_READ_PATTERNS = [
        re.compile(r'^/tis/\d+/imovel/\d+/arquivar/$'),
        re.compile(r'^/tis/\d+/imovel/\d+/criar-documento/'),
    ]

    def __init__(self, get_response):
        self.get_response = get_response
        self.file_path = getattr(settings, 'MANUTENCAO_FILE_PATH', None)

    def __call__(self, request):
        config = self._get_maintenance_config()

        if not config or not config.get('ativo'):
            return self.get_response(request)

        # Superuser sempre passa
        if request.user.is_authenticated and request.user.is_superuser:
            return self.get_response(request)

        # URLs isentas sempre passam
        if any(request.path.startswith(prefix) for prefix in self.EXEMPT_PREFIXES):
            return self.get_response(request)

        # Bloquear métodos de escrita
        if request.method in self.WRITE_METHODS:
            return self._maintenance_response(request, config)

        # Bloquear GETs que produzem escrita (write-on-read)
        if request.method == 'GET' and any(
            pattern.match(request.path) for pattern in self.WRITE_ON_READ_PATTERNS
        ):
            return self._maintenance_response(request, config)

        # GET passa normalmente
        return self.get_response(request)

    def _get_maintenance_config(self):
        """Lê o arquivo de configuração de manutenção. Retorna None se não existir."""
        file_path = self.file_path or (settings.BASE_DIR / '.maintenance.json')
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return None

    def _maintenance_response(self, request, config):
        """Retorna resposta 503 — JSON para AJAX, HTML para o resto."""
        mensagem = config.get('mensagem', 'Sistema em manutenção. Tente novamente em alguns minutos.')
        fim = config.get('fim_estimado', '')

        # AJAX/API requests → JSON
        if request.headers.get('x-requested-with') == 'XMLHttpRequest' or \
           request.content_type == 'application/json' or \
           'api/' in request.path:
            return JsonResponse(
                {'erro': 'manutencao', 'mensagem': mensagem, 'fim_estimado': fim},
                status=503
            )

        # HTML para requests normais
        html = render_to_string('manutencao.html', {
            'mensagem': mensagem,
            'fim_estimado': fim,
        })
        return HttpResponse(html, status=503)