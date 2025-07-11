from django.contrib import admin
from django.utils import timezone
from django.contrib import messages
from django import forms
from django.urls import path
from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.db import transaction
from .models import TIs, Cartorios, Pessoas, Imovel, Alteracoes, ImportacaoCartorios, Documento, Lancamento, DocumentoTipo, LancamentoTipo
from .management.commands.importar_cartorios_estado import Command as ImportarCartoriosCommand
from django.conf import settings

# Configurações do Admin
admin.site.site_header = settings.ADMIN_SITE_HEADER
admin.site.site_title = settings.ADMIN_SITE_TITLE
admin.site.index_title = settings.ADMIN_INDEX_TITLE

# Sobrescreve a URL de login do admin
admin.site.login = lambda request: redirect(settings.ADMIN_LOGIN_URL)

# Register your models here.

admin.site.register(TIs)
admin.site.register(Cartorios)
admin.site.register(Pessoas)
admin.site.register(Imovel)
admin.site.register(Alteracoes)
admin.site.register(DocumentoTipo)
admin.site.register(LancamentoTipo)

@admin.register(Documento)
class DocumentoAdmin(admin.ModelAdmin):
    list_display = ['numero', 'tipo', 'data', 'cartorio', 'imovel', 'livro', 'folha']
    list_filter = ['tipo', 'data', 'cartorio', 'imovel__terra_indigena_id']
    search_fields = ['numero', 'cartorio__nome', 'imovel__matricula', 'imovel__terra_indigena_id__nome']
    date_hierarchy = 'data'
    
    fieldsets = (
        ('Informações Básicas', {
            'fields': ('numero', 'tipo', 'data', 'cartorio')
        }),
        ('Localização', {
            'fields': ('livro', 'folha')
        }),
        ('Relacionamentos', {
            'fields': ('imovel', 'origem')
        }),
        ('Observações', {
            'fields': ('observacoes',)
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('cartorio', 'imovel', 'imovel__terra_indigena_id', 'tipo')
    
    def save_model(self, request, obj, form, change):
        """
        Sobrescreve o método save para validar mudanças de cartório
        """
        if change and 'cartorio' in form.changed_data:
            # Verificar se o documento tem lançamentos
            if obj.lancamentos.exists():
                from django.contrib import messages
                messages.error(
                    request, 
                    f'❌ Não é possível alterar o cartório do documento {obj.numero} pois ele possui lançamentos. '
                    f'Remova todos os lançamentos primeiro ou crie um novo documento.'
                )
                return  # Não salvar a mudança
        
        # Se chegou aqui, pode salvar normalmente
        super().save_model(request, obj, form, change)
        
        # Se mudou o cartório e não tem lançamentos, registrar a mudança
        if change and 'cartorio' in form.changed_data and not obj.lancamentos.exists():
            from django.contrib import messages
            messages.success(
                request, 
                f'✅ Cartório do documento {obj.numero} alterado com sucesso para {obj.cartorio.nome}.'
            )

@admin.register(Lancamento)
class LancamentoAdmin(admin.ModelAdmin):
    list_display = ['numero_lancamento', 'tipo', 'documento', 'data', 'eh_inicio_matricula', 'forma']
    list_filter = ['tipo', 'data', 'eh_inicio_matricula', 'documento__tipo', 'documento__cartorio']
    search_fields = ['numero_lancamento', 'documento__numero', 'documento__imovel__matricula', 'documento__imovel__terra_indigena_id__nome']
    date_hierarchy = 'data'
    
    fieldsets = (
        ('Informações Básicas', {
            'fields': ('numero_lancamento', 'tipo', 'documento', 'data', 'eh_inicio_matricula')
        }),
        ('Detalhes do Lançamento', {
            'fields': ('forma', 'descricao', 'titulo')
        }),
        ('Origem', {
            'fields': ('cartorio_origem', 'livro_origem', 'folha_origem', 'data_origem', 'origem')
        }),
        ('Partes', {
            'fields': ('transmitente', 'adquirente')
        }),
        ('Outros', {
            'fields': ('area', 'observacoes')
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'documento', 'documento__cartorio', 'documento__imovel', 
            'documento__imovel__terra_indigena_id', 'tipo', 'transmitente', 'adquirente'
        )

ESTADOS = [
    ('AC', 'Acre'),
    ('AL', 'Alagoas'),
    ('AP', 'Amapá'),
    ('AM', 'Amazonas'),
    ('BA', 'Bahia'),
    ('CE', 'Ceará'),
    ('DF', 'Distrito Federal'),
    ('ES', 'Espírito Santo'),
    ('GO', 'Goiás'),
    ('MA', 'Maranhão'),
    ('MT', 'Mato Grosso'),
    ('MS', 'Mato Grosso do Sul'),
    ('MG', 'Minas Gerais'),
    ('PA', 'Pará'),
    ('PB', 'Paraíba'),
    ('PR', 'Paraná'),
    ('PE', 'Pernambuco'),
    ('PI', 'Piauí'),
    ('RJ', 'Rio de Janeiro'),
    ('RN', 'Rio Grande do Norte'),
    ('RS', 'Rio Grande do Sul'),
    ('RO', 'Rondônia'),
    ('RR', 'Roraima'),
    ('SC', 'Santa Catarina'),
    ('SP', 'São Paulo'),
    ('SE', 'Sergipe'),
    ('TO', 'Tocantins'),
]

class ImportacaoCartoriosForm(forms.ModelForm):
    estado = forms.ChoiceField(choices=ESTADOS, label='Estado')

    class Meta:
        model = ImportacaoCartorios
        fields = ['estado']

@admin.register(ImportacaoCartorios)
class ImportacaoCartoriosAdmin(admin.ModelAdmin):
    list_display = ['estado', 'data_inicio', 'data_fim', 'total_cartorios', 'status']
    list_filter = ['status', 'estado']
    search_fields = ['estado']
    readonly_fields = ['data_inicio', 'data_fim', 'total_cartorios', 'status', 'erro']
    actions = ['importar_cartorios']
    form = ImportacaoCartoriosForm

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('nova-importacao/', self.admin_site.admin_view(self.nova_importacao_view), name='nova-importacao'),
            path('verificar-progresso/<int:importacao_id>/', self.admin_site.admin_view(self.verificar_progresso), name='verificar-progresso'),
            path('iniciar-importacao/<int:importacao_id>/', self.admin_site.admin_view(self.iniciar_importacao), name='iniciar-importacao'),
        ]
        return custom_urls + urls

    def iniciar_importacao(self, request, importacao_id):
        try:
            importacao = ImportacaoCartorios.objects.get(id=importacao_id)
            if importacao.status in ['em_andamento', 'concluido']:
                return JsonResponse({
                    'status': 'error',
                    'message': f'Importação para {importacao.get_estado_display()} já foi executada.'
                })

            importacao.status = 'em_andamento'
            importacao.save()

            # Executar o comando de importação
            command = ImportarCartoriosCommand()
            command.handle(estado=importacao.estado)

            # Atualizar status
            importacao.status = 'concluido'
            importacao.data_fim = timezone.now()
            importacao.total_cartorios = importacao.cartorios.count()
            importacao.save()

            return JsonResponse({
                'status': 'success',
                'message': f'Importação para {importacao.get_estado_display()} concluída com sucesso!'
            })
        except Exception as e:
            if importacao:
                importacao.status = 'erro'
                importacao.erro = str(e)
                importacao.save()
            return JsonResponse({
                'status': 'error',
                'message': f'Erro ao importar cartórios: {str(e)}'
            })

    def verificar_progresso(self, request, importacao_id):
        try:
            importacao = ImportacaoCartorios.objects.get(id=importacao_id)
            return JsonResponse({
                'status': importacao.status,
                'total_cartorios': importacao.total_cartorios,
                'erro': importacao.erro
            })
        except ImportacaoCartorios.DoesNotExist:
            return JsonResponse({'erro': 'Importação não encontrada'}, status=404)

    def nova_importacao_view(self, request):
        if request.method == 'POST':
            form = ImportacaoCartoriosForm(request.POST)
            if form.is_valid():
                with transaction.atomic():
                    importacao = form.save()
                    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                        return JsonResponse({
                            'importacao_id': importacao.id,
                            'message': f'Importação para {importacao.get_estado_display()} criada com sucesso!'
                        })
                    messages.success(request, f'Importação para {importacao.get_estado_display()} criada com sucesso!')
                    return redirect('..')
        else:
            form = ImportacaoCartoriosForm()
        
        return render(
            request,
            'admin/nova_importacao.html',
            {
                'form': form,
                'title': 'Nova Importação de Cartórios',
                'estados': ESTADOS
            }
        )

    def importar_cartorios(self, request, queryset):
        for importacao in queryset:
            if importacao.status in ['em_andamento', 'concluido']:
                messages.warning(request, f'Importação para {importacao.get_estado_display()} já foi executada.')
                continue

            try:
                importacao.status = 'em_andamento'
                importacao.save()

                # Executar o comando de importação
                command = ImportarCartoriosCommand()
                command.handle(estado=importacao.estado)

                # Atualizar status
                importacao.status = 'concluido'
                importacao.data_fim = timezone.now()
                importacao.total_cartorios = importacao.cartorios.count()
                importacao.save()

                messages.success(request, f'Importação para {importacao.get_estado_display()} concluída com sucesso!')
            except Exception as e:
                importacao.status = 'erro'
                importacao.erro = str(e)
                importacao.save()
                messages.error(request, f'Erro ao importar cartórios de {importacao.get_estado_display()}: {str(e)}')

    importar_cartorios.short_description = 'Importar cartórios do estado selecionado'

    def has_add_permission(self, request):
        return True

    def has_change_permission(self, request, obj=None):
        return True

    def has_delete_permission(self, request, obj=None):
        return True
