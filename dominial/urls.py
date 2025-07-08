from django.urls import path
from . import views
from django.contrib.auth import views as auth_views
from dal import autocomplete

# Importar views específicas dos novos módulos
from .views.tis_views import home, tis_form, tis_detail, tis_delete, imoveis, imovel_detail, imovel_delete
from .views.imovel_views import imovel_form
from .views.documento_views import novo_documento, documento_lancamentos, selecionar_documento_lancamento, editar_documento, criar_documento_automatico, ajustar_nivel_documento
from .views.lancamento_views import novo_lancamento, editar_lancamento, excluir_lancamento, lancamento_detail
from .views.cadeia_dominial_views import cadeia_dominial_arvore, tronco_principal, cadeia_dominial_tabela, cadeia_dominial_d3
from .views.api_views import buscar_cidades, buscar_cartorios, verificar_cartorios_estado, importar_cartorios_estado, criar_cartorio, cartorios, pessoas, alteracoes, lancamentos, escolher_origem_documento, escolher_origem_lancamento, get_cadeia_dominial_atualizada
from .views.autocomplete_views import pessoa_autocomplete, cartorio_autocomplete, cartorio_imoveis_autocomplete

urlpatterns = [
    # Páginas principais
    path('', home, name='home'),
    
    # TIs
    path('tis/', tis_form, name='tis_form'),
    path('tis/<int:tis_id>/', tis_detail, name='tis_detail'),
    path('tis/<int:tis_id>/excluir/', tis_delete, name='tis_delete'),
    path('tis/<int:tis_id>/imoveis/', imoveis, name='imoveis'),
    
    # Imóveis
    path('tis/<int:tis_id>/imovel/cadastro/', imovel_form, name='imovel_cadastro'),
    path('tis/<int:tis_id>/imovel/<int:imovel_id>/', imovel_detail, name='imovel_detail'),
    path('tis/<int:tis_id>/imovel/<int:imovel_id>/editar/', imovel_form, name='imovel_editar'),
    path('tis/<int:tis_id>/imovel/<int:imovel_id>/excluir/', imovel_delete, name='imovel_excluir'),
    
    # Cadeia Dominial
    path('tis/<int:tis_id>/imovel/<int:imovel_id>/cadeia-dominial/', cadeia_dominial_d3, name='cadeia_dominial'),
    path('tis/<int:tis_id>/imovel/<int:imovel_id>/ver-cadeia-dominial/', tronco_principal, name='tronco_principal'),
    path('tis/<int:tis_id>/imovel/<int:imovel_id>/cadeia-tabela/', cadeia_dominial_tabela, name='cadeia_dominial_tabela'),
    path('cadeia-dominial/<int:tis_id>/<int:imovel_id>/arvore/', cadeia_dominial_arvore, name='cadeia_dominial_arvore'),
    path('tis/<int:tis_id>/imovel/<int:imovel_id>/cadeia-dominial-d3/', views.cadeia_dominial_d3, name='cadeia_dominial_d3'),
    
    # Documentos e Lançamentos
    path('tis/<int:tis_id>/imovel/<int:imovel_id>/novo-documento/', novo_documento, name='novo_documento'),
    path('tis/<int:tis_id>/imovel/<int:imovel_id>/novo-lancamento/', novo_lancamento, name='novo_lancamento'),
    path('tis/<int:tis_id>/imovel/<int:imovel_id>/novo-lancamento/<int:documento_id>/', novo_lancamento, name='novo_lancamento_documento'),
    path('documento/<int:documento_id>/lancamentos/<int:tis_id>/<int:imovel_id>/', documento_lancamentos, name='documento_lancamentos'),
    path('documento/<int:documento_id>/editar/<int:tis_id>/<int:imovel_id>/', editar_documento, name='editar_documento'),
    path('documento/<int:documento_id>/ajustar-nivel/', ajustar_nivel_documento, name='ajustar_nivel_documento'),
    path('selecionar-documento-lancamento/<int:tis_id>/<int:imovel_id>/', selecionar_documento_lancamento, name='selecionar_documento_lancamento'),
    
    # Edição e exclusão de lançamentos
    path('tis/<int:tis_id>/imovel/<int:imovel_id>/lancamento/<int:lancamento_id>/editar/', editar_lancamento, name='editar_lancamento'),
    path('tis/<int:tis_id>/imovel/<int:imovel_id>/lancamento/<int:lancamento_id>/excluir/', excluir_lancamento, name='excluir_lancamento'),
    path('tis/<int:tis_id>/imovel/<int:imovel_id>/lancamento/<int:lancamento_id>/', lancamento_detail, name='lancamento_detail'),
    
    # Criação automática de documentos
    path('tis/<int:tis_id>/imovel/<int:imovel_id>/criar-documento/<str:codigo_origem>/', criar_documento_automatico, name='criar_documento_automatico'),
    
    # Listagens
    path('lancamentos/', lancamentos, name='lancamentos'),
    path('cartorios/', cartorios, name='cartorios'),
    
    # APIs e autocomplete
    path('buscar-cidades/', buscar_cidades, name='buscar_cidades'),
    path('buscar-cartorios/', buscar_cartorios, name='buscar_cartorios'),
    path('verificar-cartorios/', verificar_cartorios_estado, name='verificar_cartorios_estado'),
    path('importar-cartorios/', importar_cartorios_estado, name='importar_cartorios_estado'),
    path('criar-cartorio/', criar_cartorio, name='criar_cartorio'),
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

    # APIs para cadeia dominial
    path('api/escolher-origem-documento/', views.escolher_origem_documento, name='escolher_origem_documento'),
    path('api/escolher-origem-lancamento/', views.escolher_origem_lancamento, name='escolher_origem_lancamento'),
    path('api/cadeia-dominial-atualizada/<int:tis_id>/<int:imovel_id>/', views.get_cadeia_dominial_atualizada, name='get_cadeia_dominial_atualizada'),
]
