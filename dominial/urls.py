from django.urls import path
from . import views
from django.contrib.auth import views as auth_views
from dal import autocomplete
from .views import pessoa_autocomplete, cartorio_autocomplete, cartorio_imoveis_autocomplete

urlpatterns = [
    # Páginas principais
    path('', views.home, name='home'),
    
    # TIs
    path('tis/', views.tis_form, name='tis_form'),
    path('tis/<int:tis_id>/', views.tis_detail, name='tis_detail'),
    path('tis/<int:tis_id>/excluir/', views.tis_delete, name='tis_delete'),
    path('tis/<int:tis_id>/imoveis/', views.imoveis, name='imoveis'),
    
    # Imóveis
    path('tis/<int:tis_id>/imovel/cadastro/', views.imovel_form, name='imovel_cadastro'),
    path('tis/<int:tis_id>/imovel/<int:imovel_id>/', views.imovel_detail, name='imovel_detail'),
    path('tis/<int:tis_id>/imovel/<int:imovel_id>/editar/', views.imovel_form, name='imovel_editar'),
    path('tis/<int:tis_id>/imovel/<int:imovel_id>/excluir/', views.imovel_delete, name='imovel_excluir'),
    
    # Cadeia Dominial
    path('tis/<int:tis_id>/imovel/<int:imovel_id>/cadeia-dominial/', views.cadeia_dominial, name='cadeia_dominial'),
    path('cadeia-dominial/<int:tis_id>/<int:imovel_id>/arvore/', views.cadeia_dominial_arvore, name='cadeia_dominial_arvore'),
    
    # Documentos e Lançamentos
    path('tis/<int:tis_id>/imovel/<int:imovel_id>/novo-documento/', views.novo_documento, name='novo_documento'),
    path('tis/<int:tis_id>/imovel/<int:imovel_id>/novo-lancamento/', views.novo_lancamento, name='novo_lancamento'),
    path('documento/<int:documento_id>/lancamentos/<int:tis_id>/<int:imovel_id>/', views.documento_lancamentos, name='documento_lancamentos'),
    path('documento/<int:documento_id>/editar/<int:tis_id>/<int:imovel_id>/', views.editar_documento, name='editar_documento'),
    path('selecionar-documento-lancamento/<int:tis_id>/<int:imovel_id>/', views.selecionar_documento_lancamento, name='selecionar_documento_lancamento'),
    
    # Edição e exclusão de lançamentos
    path('tis/<int:tis_id>/imovel/<int:imovel_id>/lancamento/<int:lancamento_id>/editar/', views.editar_lancamento, name='editar_lancamento'),
    path('tis/<int:tis_id>/imovel/<int:imovel_id>/lancamento/<int:lancamento_id>/excluir/', views.excluir_lancamento, name='excluir_lancamento'),
    path('tis/<int:tis_id>/imovel/<int:imovel_id>/lancamento/<int:lancamento_id>/', views.lancamento_detail, name='lancamento_detail'),
    
    # Criação automática de documentos
    path('tis/<int:tis_id>/imovel/<int:imovel_id>/criar-documento/<str:codigo_origem>/', views.criar_documento_automatico, name='criar_documento_automatico'),
    
    # Listagens
    path('lancamentos/', views.lancamentos, name='lancamentos'),
    path('cartorios/', views.cartorios, name='cartorios'),
    
    # APIs e autocomplete
    path('buscar-cidades/', views.buscar_cidades, name='buscar_cidades'),
    path('buscar-cartorios/', views.buscar_cartorios, name='buscar_cartorios'),
    path('verificar-cartorios/', views.verificar_cartorios_estado, name='verificar_cartorios_estado'),
    path('importar-cartorios/', views.importar_cartorios_estado, name='importar_cartorios_estado'),
    path('pessoa-autocomplete/', pessoa_autocomplete, name='pessoa-autocomplete'),
    path('cartorio-autocomplete/', cartorio_autocomplete, name='cartorio-autocomplete'),
    path('cartorio-imoveis-autocomplete/', cartorio_imoveis_autocomplete, name='cartorio-imoveis-autocomplete'),
    
    # Autenticação
    path('accounts/login/', auth_views.LoginView.as_view(
        template_name='registration/login.html',
        redirect_authenticated_user=True,
        next_page='/'
    ), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
]
