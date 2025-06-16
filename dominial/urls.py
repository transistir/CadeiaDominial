from django.urls import path
from . import views
from django.contrib.auth import views as auth_views

urlpatterns = [
    path('', views.home, name='home'),
    path('tis/', views.tis_form, name='tis_form'),
    path('tis/<int:tis_id>/', views.tis_detail, name='tis_detail'),
    path('tis/<int:tis_id>/excluir/', views.tis_delete, name='tis_delete'),
    path('tis/<int:tis_id>/imoveis/', views.imoveis, name='imoveis'),
    path('tis/<int:tis_id>/imovel/cadastro/', views.imovel_form, name='imovel_cadastro'),
    path('tis/<int:tis_id>/imovel/<int:imovel_id>/', views.imovel_detail, name='imovel_detail'),
    path('tis/<int:tis_id>/imovel/<int:imovel_id>/editar/', views.imovel_form, name='imovel_editar'),
    path('tis/<int:tis_id>/imovel/<int:imovel_id>/excluir/', views.imovel_delete, name='imovel_excluir'),
    path('alteracoes/', views.alteracoes, name='alteracoes'),
    
    path('cartorios/', views.cartorios, name='cartorios'),
    path('buscar-cidades/', views.buscar_cidades, name='buscar_cidades'),
    path('buscar-cartorios/', views.buscar_cartorios, name='buscar_cartorios'),
    path('accounts/login/', auth_views.LoginView.as_view(
        template_name='registration/login.html',
        redirect_authenticated_user=True,
        next_page='/'
    ), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('verificar-cartorios/', views.verificar_cartorios_estado, name='verificar_cartorios_estado'),
    path('importar-cartorios/', views.importar_cartorios_estado, name='importar_cartorios_estado'),
] 