from django.shortcuts import redirect
from django.urls import reverse
from django.contrib.auth.decorators import login_required

class AuthenticationMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Lista de URLs que não precisam de autenticação
        public_urls = [
            '/login/',
            '/admin/login/',
            '/static/',
        ]

        # Verifica se a URL atual está na lista de URLs públicas
        if not request.path.startswith(tuple(public_urls)):
            if not request.user.is_authenticated:
                return redirect('login')

        response = self.get_response(request)
        return response 