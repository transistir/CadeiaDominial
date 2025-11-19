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