"""
URL configuration for cadeia_dominial project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path
from django.contrib.auth import views as auth_views
from dominial.views import (
    home, tis_form, tis_detail, tis_delete,
    imovel_form, imovel_edit, imovel_delete,
    imoveis, cartorios, pessoas, alteracoes
)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', home, name='home'),
    path('tis/cadastro/', tis_form, name='tis_form'),
    path('tis/<int:tis_id>/', tis_detail, name='tis_detail'),
    path('tis/<int:tis_id>/excluir/', tis_delete, name='tis_delete'),
    path('tis/<int:tis_id>/imovel/cadastro/', imovel_form, name='imovel_form'),
    path('tis/<int:tis_id>/imovel/<int:imovel_id>/editar/', imovel_edit, name='imovel_edit'),
    path('tis/<int:tis_id>/imovel/<int:imovel_id>/excluir/', imovel_delete, name='imovel_delete'),
    path('login/', auth_views.LoginView.as_view(template_name='registration/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='login', http_method_names=['get', 'post']), name='logout'),
    path('imoveis/', imoveis, name='imoveis'),
    path('cartorios/', cartorios, name='cartorios'),
    path('pessoas/', pessoas, name='pessoas'),
    path('alteracoes/', alteracoes, name='alteracoes'),
]
