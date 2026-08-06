from django.contrib import admin
from django.utils import timezone
from django.contrib import messages
from django import forms
from django.urls import path
from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.db import transaction
from django.db.models import Count
from django.utils.safestring import mark_safe
from .models import TIs, Cartorios, Pessoas, Imovel, Alteracoes, ImportacaoCartorios, Documento, Lancamento, DocumentoTipo, LancamentoTipo, FimCadeia
from .models.documento_digital_models import DocumentoDigital
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
admin.site.register(Pessoas)
admin.site.register(Alteracoes)
admin.site.register(DocumentoTipo)
admin.site.register(LancamentoTipo)


class EstadoVazioFilter(admin.SimpleListFilter):
    title = 'Estado vazio/nulo'
    parameter_name = 'estado_vazio'
    
    def lookups(self, request, model_admin):
        return [('sim', 'Sim'), ('nao', 'Não')]
    
    def queryset(self, request, queryset):
        if self.value() == 'sim':
            from django.db.models import Q
            return queryset.filter(Q(estado__isnull=True) | Q(estado=''))
        if self.value() == 'nao':
            return queryset.exclude(estado__isnull=True).exclude(estado='')
        return queryset


@admin.register(Cartorios)
class CartoriosAdmin(admin.ModelAdmin):
    list_display = ['id', 'nome', 'cns', 'cidade', 'estado', 'tipo', 'contagem_documentos']
    list_filter = ['estado', 'cidade', 'tipo', EstadoVazioFilter]
    search_fields = ['id', 'nome', 'cns', 'cidade', 'estado']
    list_per_page = 50
    
    def get_queryset(self, request):
        return super().get_queryset(request).annotate(documentos_count=Count('documento', distinct=True))

    def contagem_documentos(self, obj):
        return obj.documentos_count
    contagem_documentos.short_description = 'Documentos'
    contagem_documentos.admin_order_field = 'documentos_count'


@admin.register(DocumentoDigital)
class DocumentoDigitalAdmin(admin.ModelAdmin):
    list_display = ('nome_original', 'documento', 'tipo_mime', 'tamanho_formatado', 'data_upload', 'upload_por')
    list_filter = ('tipo_mime',)
    search_fields = ('nome_original',)
    readonly_fields = ('tamanho_bytes', 'data_upload')

class NumeroDocumentoFilter(admin.SimpleListFilter):
    title = 'Número do Documento'
    parameter_name = 'numero'

    def lookups(self, request, model_admin):
        # Buscar números únicos que aparecem mais de uma vez
        from django.db.models import Count
        numeros_duplicados = Documento.objects.values('numero').annotate(
            count=Count('id')
        ).filter(count__gt=1).order_by('numero')
        
        return [(doc['numero'], f"{doc['numero']} ({doc['count']} docs)") for doc in numeros_duplicados]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(numero=self.value())
        return queryset

@admin.register(Imovel)
class ImovelAdmin(admin.ModelAdmin):
    """
    Admin customizado para Imóveis com funcionalidade de correção de TI.
    """
    list_display = ['matricula', 'nome', 'terra_indigena_id', 'proprietario', 'cartorio', 'tipo_documento_principal', 'arquivado', 'data_cadastro', 'info_documentos_lancamentos']
    list_filter = ['terra_indigena_id', 'tipo_documento_principal', 'arquivado', 'cartorio', 'data_cadastro']
    search_fields = ['matricula', 'nome', 'terra_indigena_id__nome', 'proprietario__nome', 'cartorio__nome']
    date_hierarchy = 'data_cadastro'
    list_per_page = 50
    
    fieldsets = (
        ('Informações Básicas', {
            'fields': ('matricula', 'nome', 'tipo_documento_principal', 'terra_indigena_id', 'proprietario', 'cartorio')
        }),
        ('Status', {
            'fields': ('arquivado',)
        }),
        ('Observações', {
            'fields': ('observacoes',),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ['data_cadastro']
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'terra_indigena_id', 'proprietario', 'cartorio'
        ).prefetch_related('documentos', 'documentos__lancamentos')
    
    def info_documentos_lancamentos(self, obj):
        """
        Mostra informações sobre documentos e lançamentos relacionados
        """
        num_documentos = obj.documentos.count()
        num_lancamentos = Lancamento.objects.filter(documento__imovel=obj).count()
        
        if num_documentos == 0 and num_lancamentos == 0:
            return mark_safe('<span style="color: green;">✓ Sem documentos/lançamentos</span>')
        else:
            return mark_safe(
                f'<span style="color: orange;">📄 {num_documentos} doc(s) | 📋 {num_lancamentos} lançamento(s)</span>'
            )
    info_documentos_lancamentos.short_description = 'Documentos/Lançamentos'
    
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                '<int:imovel_id>/alterar-ti/',
                self.admin_site.admin_view(self.alterar_ti_view),
                name='dominial_imovel_alterar_ti'
            ),
        ]
        return custom_urls + urls
    
    def alterar_ti_view(self, request, imovel_id):
        """
        View para alterar a TI de um imóvel com confirmação e informações
        """
        from django.db.models import Count
        
        try:
            imovel = Imovel.objects.select_related(
                'terra_indigena_id', 'proprietario', 'cartorio'
            ).prefetch_related(
                'documentos', 'documentos__lancamentos'
            ).get(id=imovel_id)
        except Imovel.DoesNotExist:
            messages.error(request, 'Imóvel não encontrado.')
            return redirect('admin:dominial_imovel_changelist')
        
        # Coletar informações sobre documentos e lançamentos
        documentos = imovel.documentos.all()\
            .annotate(data_exibicao_ordenacao=Documento.data_exibicao_expression())\
            .order_by('-data_exibicao_ordenacao', '-id')
        num_documentos = documentos.count()
        num_lancamentos = Lancamento.objects.filter(documento__imovel=imovel).count()
        
        ti_atual = imovel.terra_indigena_id
        todas_tis = TIs.objects.all().order_by('nome')
        
        if request.method == 'POST':
            nova_ti_id = request.POST.get('nova_ti')
            motivo = request.POST.get('motivo', '').strip()
            
            if not nova_ti_id:
                messages.error(request, 'Por favor, selecione uma nova Terra Indígena.')
            else:
                try:
                    nova_ti = TIs.objects.get(id=nova_ti_id)
                    
                    if nova_ti.id == ti_atual.id:
                        messages.warning(request, 'O imóvel já está associado a esta Terra Indígena.')
                        return redirect('admin:dominial_imovel_change', imovel_id)
                    
                    # Validar se há documentos ou lançamentos
                    if num_documentos > 0 or num_lancamentos > 0:
                        # Mostrar aviso mas permitir a mudança
                        messages.warning(
                            request,
                            f'⚠️ ATENÇÃO: Este imóvel possui {num_documentos} documento(s) e {num_lancamentos} lançamento(s). '
                            f'A alteração da TI pode afetar a navegação e relatórios.'
                        )
                    
                    # Realizar a alteração
                    ti_anterior = imovel.terra_indigena_id
                    imovel.terra_indigena_id = nova_ti
                    
                    # Adicionar informação sobre a mudança nas observações
                    timestamp = timezone.now().strftime('%d/%m/%Y %H:%M')
                    usuario = request.user.get_full_name() or request.user.username
                    observacao_mudanca = (
                        f"\n\n--- ALTERAÇÃO DE TI ---\n"
                        f"Data: {timestamp}\n"
                        f"Usuário: {usuario}\n"
                        f"TI Anterior: {ti_anterior.nome} (ID: {ti_anterior.id})\n"
                        f"TI Nova: {nova_ti.nome} (ID: {nova_ti.id})\n"
                    )
                    if motivo:
                        observacao_mudanca += f"Motivo: {motivo}\n"
                    observacao_mudanca += "---\n"
                    
                    # Adicionar ao campo observações
                    if imovel.observacoes:
                        imovel.observacoes += observacao_mudanca
                    else:
                        imovel.observacoes = observacao_mudanca
                    
                    imovel.save()
                    
                    messages.success(
                        request,
                        f'✅ TI alterada com sucesso!\n'
                        f'De: {ti_anterior.nome}\n'
                        f'Para: {nova_ti.nome}'
                    )
                    
                    return redirect('admin:dominial_imovel_change', imovel_id)
                    
                except TIs.DoesNotExist:
                    messages.error(request, 'Terra Indígena selecionada não encontrada.')
        
        # Preparar contexto para o template
        context = {
            'title': f'Alterar TI do Imóvel: {imovel.matricula}',
            'imovel': imovel,
            'ti_atual': ti_atual,
            'todas_tis': todas_tis,
            'num_documentos': num_documentos,
            'num_lancamentos': num_lancamentos,
            'documentos': documentos[:10],  # Mostrar apenas os 10 primeiros
            'opts': self.model._meta,
            'has_view_permission': self.has_view_permission(request, imovel),
            'has_change_permission': self.has_change_permission(request, imovel),
        }
        
        return render(request, 'admin/dominial/imovel/alterar_ti.html', context)
    
    def change_view(self, request, object_id, form_url='', extra_context=None):
        """
        Adiciona um botão customizado na página de edição do imóvel
        """
        extra_context = extra_context or {}
        try:
            imovel = Imovel.objects.get(id=object_id)
            extra_context['mostrar_botao_alterar_ti'] = True
            extra_context['imovel_id'] = object_id
        except Imovel.DoesNotExist:
            pass
        
        return super().change_view(request, object_id, form_url, extra_context)

@admin.register(Documento)
class DocumentoAdmin(admin.ModelAdmin):
    list_display = ['numero', 'tipo', 'data', 'cartorio', 'imovel', 'livro', 'folha', 'contagem_lancamentos']
    list_filter = ['tipo', 'data', NumeroDocumentoFilter]
    search_fields = ['numero', 'cartorio__nome', 'imovel__matricula', 'imovel__terra_indigena_id__nome']
    date_hierarchy = 'data'
    list_per_page = 50  # Mostrar mais itens por página
    
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
        return super().get_queryset(request).select_related(
            'cartorio', 'imovel', 'imovel__terra_indigena_id', 'tipo'
        ).prefetch_related('lancamentos')
    
    def contagem_lancamentos(self, obj):
        """
        Retorna a contagem de lançamentos
        """
        return obj.lancamentos.count()
    contagem_lancamentos.short_description = 'Lançamentos'
    contagem_lancamentos.admin_order_field = 'lancamentos__count'
    
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
    
    actions = ['investigar_duplicatas']
    
    def investigar_duplicatas(self, request, queryset):
        """
        Ação para investigar documentos com mesmo número mesmo em cartórios diferentes
        """
        from django.contrib import messages
        from django.db.models import Count
        
        # Se há documentos selecionados, buscar números desses documentos
        if queryset.exists():
            numeros_selecionados = queryset.values_list('numero', flat=True).distinct()
            
            # Buscar TODOS os documentos com esses números (não apenas os selecionados)
            duplicatas = Documento.objects.filter(numero__in=numeros_selecionados).values('numero').annotate(
                count=Count('id')
            ).filter(count__gt=1)
        else:
            # Se nenhum documento selecionado, buscar todos os duplicados
            duplicatas = Documento.objects.values('numero').annotate(
                count=Count('id')
            ).filter(count__gt=1)
        
        if duplicatas:
            mensagem = "🔍 Documentos com mesmo número encontrados:\n"
            for dup in duplicatas:
                numero = dup['numero']
                documentos = Documento.objects.filter(numero=numero).select_related('cartorio').order_by('cartorio__nome')
                mensagem += f"\n📋 Número: {numero} ({dup['count']} documentos):\n"
                for doc in documentos:
                    mensagem += f"  - ID: {doc.id}, Cartório: {doc.cartorio.nome}, Data: {doc.data}\n"
            messages.warning(request, mensagem)
        else:
            messages.success(request, "✅ Nenhum documento com mesmo número encontrado.")
    
    investigar_duplicatas.short_description = "🔍 Investigar documentos com mesmo número"

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


@admin.register(FimCadeia)
class FimCadeiaAdmin(admin.ModelAdmin):
    """Admin para gerenciar os tipos de fim de cadeia.

    É aqui que se cadastram as siglas oferecidas no select "Estado" do
    destacamento do patrimônio público: entram no formulário os registros com
    tipo "Destacamento Público", sigla preenchida e ativo marcado (issue #104).
    """
    list_display = ['sigla', 'nome', 'tipo', 'classificacao', 'ativo', 'data_criacao']
    list_display_links = ['sigla', 'nome']
    list_filter = ['tipo', 'classificacao', 'ativo', 'data_criacao']
    search_fields = ['nome', 'sigla', 'descricao']
    list_editable = ['ativo']
    ordering = ['nome']

    fieldsets = (
        ('Informações Básicas', {
            'fields': ('nome', 'tipo', 'classificacao', 'sigla', 'ativo'),
            'description': (
                'A <strong>sigla</strong> é o valor gravado no lançamento e exibido na '
                'árvore (ex: BA, SP, IMP-BR). Registros de tipo "Destacamento Público" '
                'com sigla preenchida e <strong>ativo</strong> marcado aparecem no select '
                '"Estado" do formulário de lançamento; desmarcar "ativo" tira a opção do '
                'select sem apagar o histórico.'
            ),
        }),
        ('Descrição', {
            'fields': ('descricao',),
            'classes': ('collapse',)
        }),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).order_by('nome')
    
    def save_model(self, request, obj, form, change):
        """Salvar o modelo com informações de auditoria"""
        if not change:  # Novo objeto
            obj.data_criacao = timezone.now()
        obj.data_atualizacao = timezone.now()
        super().save_model(request, obj, form, change)
    
    def has_add_permission(self, request):
        return True
    
    def has_change_permission(self, request, obj=None):
        return True
    
    def has_delete_permission(self, request, obj=None):
        return True
