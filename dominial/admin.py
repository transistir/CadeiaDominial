import copy
import json
import logging

from django.contrib import admin
from django.contrib.admin.models import CHANGE, LogEntry
from django.contrib.admin.widgets import FilteredSelectMultiple
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone
from django.contrib import messages
from django import forms
from django.urls import path
from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Count, Q
from django.utils.safestring import mark_safe
from .models import (
    Alteracoes,
    Cartorios,
    Documento,
    DocumentoTipo,
    FimCadeia,
    GroupTI,
    GrupoAcesso,
    Imovel,
    ImportacaoCartorios,
    Lancamento,
    LancamentoTipo,
    Pessoas,
    TIs,
    UserImovel,
    UserTI,
)
from .models.documento_digital_models import DocumentoDigital
from .management.commands.importar_cartorios_estado import Command as ImportarCartoriosCommand
from django.conf import settings
from django.contrib.auth.admin import (
    GroupAdmin as DjangoGroupAdmin,
    UserAdmin as DjangoUserAdmin,
)
from django.contrib.auth.forms import (
    UserChangeForm as DjangoUserChangeForm,
    UserCreationForm as DjangoUserCreationForm,
)
from django.contrib.auth.models import Group, User
from django.urls import NoReverseMatch, reverse
from .managers import (
    documentos_for_user,
    lancamentos_for_user,
    pessoas_for_user,
    tis_for_user,
    usuario_ve_tudo,
)

logger = logging.getLogger(__name__)

# Mensagem fixa em vez do `str(e)` cru: o texto da exceção vaza nome de tabela,
# URL de origem e credencial de integração na tela do usuário — e ainda fica
# persistido em `ImportacaoCartorios.erro`, que `verificar_progresso` devolve
# por JSON (#132).
ERRO_IMPORTACAO = 'Erro ao importar cartórios. Consulte os logs do servidor.'

# Configurações do Admin
admin.site.site_header = settings.ADMIN_SITE_HEADER
admin.site.site_title = settings.ADMIN_SITE_TITLE
admin.site.index_title = settings.ADMIN_INDEX_TITLE

# Sobrescreve a URL de login do admin
admin.site.login = lambda request: redirect(settings.ADMIN_LOGIN_URL)

# Register your models here.


def escopar(queryset, permitidos, user):
    """
    Restringe `queryset` ao escopo do usuário sem perder o que veio do super().

    Filtrar por `pk__in` em vez de devolver o queryset do helper preserva o
    ordering, os `select_related` e as annotations que o `ModelAdmin` monta em
    `get_queryset` — trocar o queryset inteiro descartava tudo isso (#132).
    """
    if usuario_ve_tudo(user):
        return queryset
    return queryset.filter(pk__in=permitidos)


admin.site.register(DocumentoTipo)
admin.site.register(LancamentoTipo)


class TIsSegregadaFilter(admin.RelatedFieldListFilter):
    """
    Filtro de TI na sidebar do changelist, respeitando a atribuição (#132).

    O ``RelatedFieldListFilter`` padrão monta as opções via
    ``field.get_choices()``, que lê ``TIs._default_manager`` sem filtro algum —
    ou seja, passa ao largo de ``TIsAdmin.get_queryset`` e mostraria a lista
    completa de TIs para qualquer staff.
    """

    def field_choices(self, field, request, model_admin):
        return [(tis.pk, str(tis)) for tis in tis_for_user(request.user).order_by('nome')]


class AtribuicaoAuditoriaMixin:
    """
    Carimba ``atribuido_por`` nas atribuições criadas via inline (#132).

    Inlines não passam por ``save_model``; a gravação acontece no formset do
    admin pai, por isso o hook é ``save_formset``.
    """

    MODELOS_ATRIBUICAO = {UserImovel, UserTI, GroupTI}

    def save_formset(self, request, form, formset, change):
        if formset.model not in self.MODELOS_ATRIBUICAO:
            return super().save_formset(request, form, formset, change)
        if not request.user.is_superuser:
            raise PermissionDenied
        instances = formset.save(commit=False)
        for obj in formset.deleted_objects:
            obj.delete()
        for instance in instances:
            if instance.atribuido_por_id is None:
                instance.atribuido_por = request.user
            instance.save()
        formset.save_m2m()

    def get_inline_instances(self, request, obj=None):
        if not request.user.is_superuser:
            return []
        return super().get_inline_instances(request, obj)


class GroupTIPorTIInline(admin.TabularInline):
    """Equipes com acesso a esta TI (veículo principal)."""

    model = GroupTI
    fk_name = 'tis'
    extra = 1
    autocomplete_fields = ['group']
    readonly_fields = ['data_atribuicao', 'atribuido_por']
    verbose_name = 'Equipe com acesso'
    verbose_name_plural = 'Equipes com acesso'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('group', 'atribuido_por')


class UserTIPorTIInline(admin.TabularInline):
    """Usuários com acesso direto a esta TI."""

    model = UserTI
    fk_name = 'tis'
    extra = 1
    autocomplete_fields = ['user']
    readonly_fields = ['data_atribuicao', 'atribuido_por']
    verbose_name = 'Usuário com acesso direto'
    verbose_name_plural = 'Usuários com acesso direto'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user', 'atribuido_por')


@admin.register(Pessoas)
class PessoasAdmin(admin.ModelAdmin):
    """
    Cadastro de pessoas escopado por imóvel atribuído (#132).

    ``Pessoas`` guarda CPF, RG e data de nascimento; sem escopo a listagem do
    admin entrega o PII do sistema inteiro a qualquer staff.
    """
    list_display = ['nome', 'cpf', 'rg', 'email', 'telefone']
    search_fields = ['nome', 'cpf', 'rg']
    list_per_page = 50

    def get_queryset(self, request):
        return escopar(
            super().get_queryset(request), pessoas_for_user(request.user), request.user
        )


@admin.register(TIs)
class TIsAdmin(AtribuicaoAuditoriaMixin, admin.ModelAdmin):
    search_fields = ['nome', 'codigo', 'etnia']
    inlines = [GroupTIPorTIInline, UserTIPorTIInline]
    actions = ['atribuir_tis_selecionadas']

    def get_queryset(self, request):
        return escopar(
            super().get_queryset(request), tis_for_user(request.user), request.user
        )

    def atribuir_tis_selecionadas(self, request, queryset):
        if not request.user.is_superuser:
            raise PermissionDenied
        ids = ','.join(str(pk) for pk in queryset.order_by('pk').values_list('pk', flat=True))
        url = reverse('admin:dominial_atribuicao_em_massa')
        return redirect(f'{url}?tis={ids}')

    atribuir_tis_selecionadas.short_description = 'Atribuir TIs selecionadas em massa'
    atribuir_tis_selecionadas.allowed_permissions = ('view',)


@admin.register(Alteracoes)
class AlteracoesAdmin(admin.ModelAdmin):
    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        if request.user.is_superuser:
            return queryset
        return queryset.filter(imovel_id__in=Imovel.objects.for_user(request.user))

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if not request.user.is_superuser and db_field.name == 'imovel_id':
            kwargs['queryset'] = Imovel.objects.for_user(request.user)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


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

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        if request.user.is_superuser:
            return queryset
        return queryset.filter(documento__in=documentos_for_user(request.user))

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if not request.user.is_superuser and db_field.name == 'documento':
            kwargs['queryset'] = documentos_for_user(request.user)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


class NumeroDocumentoFilter(admin.SimpleListFilter):
    title = 'Número do Documento'
    parameter_name = 'numero'

    def lookups(self, request, model_admin):
        # Buscar números únicos que aparecem mais de uma vez
        from django.db.models import Count
        numeros_duplicados = documentos_for_user(request.user).values('numero').annotate(
            count=Count('id')
        ).filter(count__gt=1).order_by('numero')
        
        return [(doc['numero'], f"{doc['numero']} ({doc['count']} docs)") for doc in numeros_duplicados]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(numero=self.value())
        return queryset

class UserImovelPorImovelInline(admin.TabularInline):
    """Usuários com acesso a este imóvel."""
    model = UserImovel
    fk_name = 'imovel'
    extra = 1
    autocomplete_fields = ['user']
    readonly_fields = ['data_atribuicao', 'atribuido_por']
    verbose_name = 'Usuário com acesso'
    verbose_name_plural = 'Usuários com acesso'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user', 'atribuido_por')


class UserImovelPorUserInline(admin.TabularInline):
    """Imóveis atribuídos a este usuário."""
    model = UserImovel
    # UserImovel tem duas FKs para User (user e atribuido_por): fk_name é obrigatório.
    fk_name = 'user'
    extra = 1
    autocomplete_fields = ['imovel']
    readonly_fields = ['data_atribuicao', 'atribuido_por']
    verbose_name = 'Imóvel atribuído'
    verbose_name_plural = 'Imóveis atribuídos'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('imovel', 'atribuido_por')


class UserTIPorUserInline(admin.TabularInline):
    """TIs atribuídas diretamente a este usuário."""

    model = UserTI
    # UserTI tem duas FKs para User (user e atribuido_por).
    fk_name = 'user'
    extra = 1
    autocomplete_fields = ['tis']
    readonly_fields = ['data_atribuicao', 'atribuido_por']
    verbose_name = 'TI atribuída diretamente'
    verbose_name_plural = 'TIs atribuídas diretamente'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('tis', 'atribuido_por')


@admin.register(UserImovel)
class UserImovelAdmin(admin.ModelAdmin):
    """Gestão standalone das atribuições usuário ↔ imóvel (#132)."""
    list_display = ['user', 'imovel', 'data_atribuicao', 'atribuido_por']
    list_filter = ['user', 'data_atribuicao', 'imovel__terra_indigena_id']
    search_fields = [
        'user__username', 'user__first_name', 'user__last_name',
        'imovel__matricula', 'imovel__nome',
    ]
    autocomplete_fields = ['user', 'imovel']
    readonly_fields = ['data_atribuicao', 'atribuido_por']
    list_per_page = 50

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user', 'imovel', 'atribuido_por')

    def has_module_permission(self, request):
        return request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_add_permission(self, request):
        return request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser

    def save_model(self, request, obj, form, change):
        # Auditoria: registra quem concedeu o acesso, sem sobrescrever em edições.
        if not change and obj.atribuido_por_id is None:
            obj.atribuido_por = request.user
        super().save_model(request, obj, form, change)


class AtribuicaoTISuperuserAdmin(admin.ModelAdmin):
    """Pacote de segurança e auditoria das atribuições de TI (#132)."""

    readonly_fields = ['data_atribuicao', 'atribuido_por']
    list_per_page = 50

    def has_module_permission(self, request):
        return request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_add_permission(self, request):
        return request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser

    def save_model(self, request, obj, form, change):
        if not change and obj.atribuido_por_id is None:
            obj.atribuido_por = request.user
        super().save_model(request, obj, form, change)


class UsuariosAtribuicaoEmMassaField(forms.ModelMultipleChoiceField):
    def label_from_instance(self, obj):
        sufixo = ' (inativo)' if not obj.is_active else ''
        return f'{obj}{sufixo}'


class AtribuicaoEmMassaForm(forms.Form):
    """Seleciona TIs e destinos para concessão ou revogação em massa."""

    acao = forms.ChoiceField(
        choices=[('conceder', 'Conceder acesso'), ('revogar', 'Revogar acesso')],
        initial='conceder',
        widget=forms.RadioSelect,
    )
    tis = forms.ModelMultipleChoiceField(
        queryset=TIs.objects.order_by('nome'),
        label='Terras Indígenas',
        widget=FilteredSelectMultiple('Terras Indígenas', is_stacked=False),
    )
    equipes = forms.ModelMultipleChoiceField(
        queryset=(
            Group.objects.filter(acesso__tipo=GrupoAcesso.EQUIPE)
            .annotate(total_membros=Count('user'))
            .order_by('name')
        ),
        required=False,
        widget=FilteredSelectMultiple('equipes', is_stacked=False),
    )
    usuarios = UsuariosAtribuicaoEmMassaField(
        queryset=(
            User.objects.filter(is_superuser=False).order_by('username')
        ),
        required=False,
        widget=FilteredSelectMultiple('usuários', is_stacked=False),
        help_text='Use só quando a atribuição não couber em nenhuma equipe.',
    )

    def clean(self):
        cleaned_data = super().clean()
        if not (cleaned_data.get('equipes') or cleaned_data.get('usuarios')):
            raise forms.ValidationError('Selecione ao menos uma equipe ou um usuário.')
        return cleaned_data


def _ids_da_querystring(params, *nomes):
    """Lê IDs separados por vírgula, aceitando aliases e valores repetidos."""
    ids = []
    for nome in nomes:
        for valor in params.getlist(nome):
            for parte in valor.split(','):
                parte = parte.strip()
                if parte.isdigit() and int(parte) > 0 and int(parte) not in ids:
                    ids.append(int(parte))
    return ids


def _resumo_atribuicao(acao, total_tis, total_equipes, total_usuarios):
    if acao == 'conceder':
        verbo = 'concedida' if total_tis == 1 else 'concedidas'
    else:
        verbo = 'revogada' if total_tis == 1 else 'revogadas'
    tis = 'TI' if total_tis == 1 else 'TIs'
    equipes = 'equipe' if total_equipes == 1 else 'equipes'
    usuarios = 'usuário' if total_usuarios == 1 else 'usuários'
    return (
        f'Atribuição em massa: {verbo} {total_tis} {tis} a '
        f'{total_equipes} {equipes} + {total_usuarios} {usuarios}'
    )


@admin.register(UserTI)
class UserTIAdmin(AtribuicaoTISuperuserAdmin):
    """Gestão standalone das atribuições usuário ↔ TI (#132)."""

    change_list_template = 'admin/dominial/userti/change_list.html'
    list_display = ['user', 'tis', 'data_atribuicao', 'atribuido_por']
    list_filter = ['user', 'data_atribuicao', 'tis']
    search_fields = [
        'user__username', 'user__first_name', 'user__last_name',
        'tis__nome', 'tis__codigo',
    ]
    autocomplete_fields = ['user', 'tis']

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user', 'tis', 'atribuido_por')

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                'em-massa/',
                self.admin_site.admin_view(self.atribuicao_em_massa_view),
                name='dominial_atribuicao_em_massa',
            ),
            path(
                'em-massa/previa/',
                self.admin_site.admin_view(self.atribuicao_previa_view),
                name='dominial_atribuicao_previa',
            ),
        ]
        return custom_urls + urls

    @staticmethod
    def _dados_previa(request, cleaned_data):
        tis = list(cleaned_data['tis'])
        equipes = list(cleaned_data['equipes'])
        usuarios = list(cleaned_data['usuarios'])
        acao = cleaned_data['acao']

        total_imoveis = Imovel.objects.for_user(request.user).filter(
            terra_indigena_id__in=tis
        ).count()
        vinculos_existentes = (
            UserTI.objects.filter(user__in=usuarios, tis__in=tis).count()
            + GroupTI.objects.filter(group__in=equipes, tis__in=tis).count()
        )

        nomes_tis = ', '.join(ti.nome for ti in tis)
        destinos = []
        if equipes:
            palavra = 'equipe' if len(equipes) == 1 else 'equipes'
            detalhes = ', '.join(
                f'{equipe.name} — {equipe.total_membros} membros' for equipe in equipes
            )
            destinos.append(f'{len(equipes)} {palavra} ({detalhes})')
        if usuarios:
            palavra = 'usuário' if len(usuarios) == 1 else 'usuários'
            destinos.append(f'{len(usuarios)} {palavra}')

        infinitivo = 'Conceder' if acao == 'conceder' else 'Revogar'
        efeito = 'dá' if acao == 'conceder' else 'revoga'
        if acao == 'conceder':
            fechamento = (
                f'{vinculos_existentes} vínculos já existem e serão ignorados.'
            )
        else:
            fechamento = (
                f'{vinculos_existentes} vínculos existem e serão removidos.'
            )
        frase = (
            f'{infinitivo} {nomes_tis} a {" e ".join(destinos)}. '
            f'Isso {efeito} acesso a {total_imoveis} imóveis (hoje) '
            f'e a todos os imóveis futuros dessas TIs. {fechamento}'
        )
        return {
            'acao': acao,
            'tis': [{'id': ti.pk, 'nome': ti.nome} for ti in tis],
            'equipes': [
                {'id': equipe.pk, 'nome': equipe.name, 'membros': equipe.total_membros}
                for equipe in equipes
            ],
            'usuarios': [{'id': usuario.pk, 'nome': str(usuario)} for usuario in usuarios],
            'total_tis': len(tis),
            'total_equipes': len(equipes),
            'total_usuarios': len(usuarios),
            'total_imoveis': total_imoveis,
            'vinculos_existentes': vinculos_existentes,
            'frase': frase,
        }

    def atribuicao_previa_view(self, request):
        if not request.user.is_superuser:
            raise PermissionDenied
        if request.method != 'POST':
            return JsonResponse({'erro': 'Método não permitido.'}, status=405)
        try:
            payload = json.loads(request.body or b'{}')
        except (json.JSONDecodeError, UnicodeDecodeError):
            return JsonResponse({'erro': 'JSON inválido.'}, status=400)
        if not isinstance(payload, dict):
            return JsonResponse({'erro': 'JSON inválido.'}, status=400)

        form = AtribuicaoEmMassaForm(payload)
        if not form.is_valid():
            return JsonResponse({'erros': form.errors.get_json_data()}, status=400)
        return JsonResponse(self._dados_previa(request, form.cleaned_data))

    def atribuicao_em_massa_view(self, request):
        if not request.user.is_superuser:
            raise PermissionDenied

        if request.method == 'POST':
            form = AtribuicaoEmMassaForm(request.POST)
            if form.is_valid():
                acao = form.cleaned_data['acao']
                tis = list(form.cleaned_data['tis'])
                equipes = list(form.cleaned_data['equipes'])
                usuarios = list(form.cleaned_data['usuarios'])
                resumo = _resumo_atribuicao(
                    acao, len(tis), len(equipes), len(usuarios)
                )
                dados_auditoria = {
                    'acao': acao,
                    'tis': [{'id': ti.pk, 'nome': ti.nome} for ti in tis],
                    'equipes': [
                        {'id': equipe.pk, 'nome': equipe.name}
                        for equipe in equipes
                    ],
                    'usuarios': [
                        {'id': usuario.pk, 'nome': str(usuario)}
                        for usuario in usuarios
                    ],
                    'resumo': resumo,
                }

                with transaction.atomic():
                    if acao == 'conceder':
                        UserTI.objects.bulk_create(
                            [
                                UserTI(user=usuario, tis=ti, atribuido_por=request.user)
                                for usuario in usuarios
                                for ti in tis
                            ],
                            ignore_conflicts=True,
                        )
                        GroupTI.objects.bulk_create(
                            [
                                GroupTI(group=equipe, tis=ti, atribuido_por=request.user)
                                for equipe in equipes
                                for ti in tis
                            ],
                            ignore_conflicts=True,
                        )
                    else:
                        UserTI.objects.filter(user__in=usuarios, tis__in=tis).delete()
                        GroupTI.objects.filter(group__in=equipes, tis__in=tis).delete()

                    LogEntry.objects.create(
                        user_id=request.user.pk,
                        content_type_id=ContentType.objects.get_for_model(UserTI).pk,
                        object_id=None,
                        object_repr='Atribuição em massa de TIs',
                        action_flag=CHANGE,
                        change_message=json.dumps(dados_auditoria, ensure_ascii=False),
                    )

                messages.success(request, resumo)
                return redirect('admin:dominial_atribuicao_em_massa')
        else:
            form = AtribuicaoEmMassaForm(initial={
                'tis': _ids_da_querystring(request.GET, 'tis'),
                'equipes': _ids_da_querystring(request.GET, 'equipes'),
                'usuarios': _ids_da_querystring(request.GET, 'usuarios', 'usuario'),
            })

        context = {
            **self.admin_site.each_context(request),
            'form': form,
            'opts': self.model._meta,
            'title': 'Atribuição em massa de TIs',
            'previa_url': reverse('admin:dominial_atribuicao_previa'),
        }
        return render(request, 'admin/atribuicao_em_massa.html', context)


@admin.register(GroupTI)
class GroupTIAdmin(AtribuicaoTISuperuserAdmin):
    """Gestão standalone das atribuições equipe ↔ TI (#132)."""

    list_display = ['group', 'tis', 'data_atribuicao', 'atribuido_por']
    list_filter = ['group', 'data_atribuicao', 'tis']
    search_fields = ['group__name', 'tis__nome', 'tis__codigo']
    autocomplete_fields = ['group', 'tis']

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('group', 'tis', 'atribuido_por')


@admin.register(GrupoAcesso)
class GrupoAcessoAdmin(admin.ModelAdmin):
    """Metadados de perfis/equipes, editáveis somente por superusuários."""

    list_display = ['group', 'tipo', 'protegido', 'descricao']
    list_filter = ['tipo', 'protegido']
    search_fields = ['group__name', 'descricao']
    autocomplete_fields = ['group']

    def has_module_permission(self, request):
        return request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_add_permission(self, request):
        return request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser and not (obj and obj.protegido)

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser and not (obj and obj.protegido)


PERFIS = {
    'editor': 'Perfil: Editor',
    'admin': 'Perfil: Administrador',
}
PERFIL_CHOICES = [
    ('editor', 'Editor — consulta e cadastra imóveis, documentos e lançamentos'),
    ('admin', 'Administrador — Editor + acesso ao admin do sistema'),
]


class PerfilListFilter(admin.SimpleListFilter):
    title = 'perfil de acesso'
    parameter_name = 'perfil'

    def lookups(self, request, model_admin):
        return PERFIL_CHOICES

    def queryset(self, request, queryset):
        nome_grupo = PERFIS.get(self.value())
        if nome_grupo:
            return queryset.filter(groups__name=nome_grupo)
        return queryset


class TIAtribuidaListFilter(admin.SimpleListFilter):
    title = 'acesso a TI'
    parameter_name = 'ti_atribuida'

    def lookups(self, request, model_admin):
        return [('sim', 'Com TI atribuída'), ('nao', 'Sem TI atribuída')]

    def queryset(self, request, queryset):
        com_ti = queryset.filter(
            Q(tis_atribuidas__isnull=False) | Q(groups__tis_atribuidas__isnull=False)
        )
        if self.value() == 'sim':
            return com_ti.distinct()
        if self.value() == 'nao':
            return queryset.exclude(pk__in=com_ti.values('pk'))
        return queryset


class UserPerfilForm(DjangoUserChangeForm):
    perfil = forms.ChoiceField(
        label='Perfil de acesso',
        widget=forms.RadioSelect,
        choices=PERFIL_CHOICES,
        initial='editor',
        help_text=(
            'Define se o usuário entra ou não no admin do sistema. O que ele VÊ é '
            'definido pelas equipes e Terras Indígenas atribuídas abaixo.'
        ),
    )
    equipes = forms.ModelMultipleChoiceField(
        queryset=Group.objects.filter(acesso__tipo=GrupoAcesso.EQUIPE),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label='Equipes',
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        perfil = 'editor'
        equipes = Group.objects.none()
        if self.instance and self.instance.pk:
            grupos = self.instance.groups.all()
            if (
                self.instance.is_superuser
                or self.instance.is_staff
                or grupos.filter(name=PERFIS['admin']).exists()
            ):
                perfil = 'admin'
            equipes = grupos.filter(acesso__tipo=GrupoAcesso.EQUIPE)

        self.initial['perfil'] = perfil
        self.initial['equipes'] = list(equipes.values_list('pk', flat=True))

        # Compatibilidade com formulários abertos antes desta fase. A ausência
        # de ``perfil`` identifica o POST antigo; nesse caso, preserve também
        # as equipes atuais em vez de interpretá-las como uma remoção em massa.
        nome_perfil = self.add_prefix('perfil')
        if self.is_bound and nome_perfil not in self.data:
            self.data = self.data.copy()
            self.data[nome_perfil] = perfil
            self.data.setlist(
                self.add_prefix('equipes'),
                [str(pk) for pk in self.initial['equipes']],
            )


class UserPerfilCreationForm(DjangoUserCreationForm):
    perfil = forms.ChoiceField(
        label='Perfil de acesso',
        widget=forms.RadioSelect,
        choices=PERFIL_CHOICES,
        initial='editor',
        help_text=(
            'Define se o usuário entra ou não no admin do sistema. O que ele VÊ é '
            'definido pelas equipes e Terras Indígenas atribuídas abaixo.'
        ),
    )


class UserAdmin(AtribuicaoAuditoriaMixin, DjangoUserAdmin):
    """UserAdmin padrão + inlines de atribuições legadas e por TI (#132)."""
    form = UserPerfilForm
    add_form = UserPerfilCreationForm
    inlines = [UserImovelPorUserInline, UserTIPorUserInline]
    list_display = ['username', 'first_name', 'last_name', 'perfil_exibido', 'is_active']
    list_filter = ['is_active', 'groups', PerfilListFilter, TIAtribuidaListFilter]
    search_fields = ['username', 'first_name', 'last_name', 'email']
    actions = ['atribuir_tis_aos_usuarios']

    FIELDSETS_SIMPLES = (
        (None, {'fields': ('username', 'password')}),
        ('Identificação', {'fields': ('first_name', 'last_name', 'email')}),
        ('Acesso', {
            'fields': ('perfil', 'equipes', 'is_active'),
            'description': (
                'Perfil = entra ou não no admin. '
                'Equipes e TIs (abaixo) = o que pode ver.'
            ),
        }),
    )
    FIELDSET_AVANCADO = ('Avançado — somente superusuário', {
        'classes': ('collapse',),
        'fields': (
            'is_staff', 'is_superuser', 'groups', 'user_permissions',
            'last_login', 'date_joined',
        ),
    })
    add_fieldsets = ((None, {
        'classes': ('wide',),
        'fields': ('username', 'first_name', 'email', 'password1', 'password2', 'perfil'),
    }),)

    # Campos que decidem quem escapa da segregação. Sem este bloqueio, um staff
    # com `auth.change_user` marca `is_superuser` — no próprio usuário, inclusive
    # — e ganha acesso a todos os imóveis do sistema.
    CAMPOS_DE_ESCALACAO = (
        'is_superuser', 'is_staff', 'groups', 'user_permissions', 'perfil', 'equipes',
    )

    def get_fieldsets(self, request, obj=None):
        if obj is None:
            return self.add_fieldsets
        if request.user.is_superuser:
            return self.FIELDSETS_SIMPLES + (self.FIELDSET_AVANCADO,)
        return self.FIELDSETS_SIMPLES

    @admin.display(description='Perfil')
    def perfil_exibido(self, obj):
        if obj.groups.filter(name=PERFIS['admin']).exists():
            return 'Administrador'
        return 'Editor'

    def _sincronizar_perfil(self, obj, perfil, equipes):
        if obj.is_superuser:
            return

        with transaction.atomic():
            grupos_de_perfil = list(Group.objects.filter(name__in=PERFIS.values()))
            grupo_escolhido = next(
                (grupo for grupo in grupos_de_perfil if grupo.name == PERFIS[perfil]),
                None,
            )
            manter = list(
                obj.groups.exclude(name__in=PERFIS.values())
                .exclude(acesso__tipo=GrupoAcesso.EQUIPE)
            )
            obj.groups.set(
                list(equipes)
                + manter
                + ([grupo_escolhido] if grupo_escolhido else [])
            )
            obj.is_staff = perfil == 'admin'
            obj.save(update_fields=['is_staff'])

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if request.user.is_superuser:
            self._sincronizar_perfil(
                obj,
                form.cleaned_data['perfil'],
                form.cleaned_data.get('equipes', []),
            )

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        if request.user.is_superuser:
            # ``form.save_m2m()`` acabou de gravar o campo avançado ``groups``;
            # reaplique a fonte canônica (perfil + equipes) por último.
            self._sincronizar_perfil(
                form.instance,
                form.cleaned_data['perfil'],
                form.cleaned_data.get('equipes', []),
            )

    def response_add(self, request, obj, post_url_continue=None):
        try:
            url = reverse('admin:dominial_atribuicao_em_massa')
        except NoReverseMatch:
            url = reverse('admin:auth_user_changelist')
        else:
            url = f'{url}?usuario={obj.pk}'
        return redirect(url)

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        if not request.user.is_superuser:
            # Campos declarados podem ser compartilhados entre as subclasses
            # geradas por ``modelform_factory``; isole-os antes de desabilitar.
            form.base_fields = copy.deepcopy(form.base_fields)
            # `disabled` faz o Django ignorar o valor enviado e reusar o do banco,
            # então um POST forjado também não passa.
            for nome in self.CAMPOS_DE_ESCALACAO:
                if nome in form.base_fields:
                    form.base_fields[nome].disabled = True
        return form

    def get_inline_instances(self, request, obj=None):
        # O inline exige um User já salvo (FK obrigatória) — some na tela de criação.
        if obj is None or not request.user.is_superuser:
            return []
        return super().get_inline_instances(request, obj)

    def get_formsets_with_inlines(self, request, obj=None):
        """
        Aceita POSTs abertos antes da inclusão do inline de TI.

        Uma aba antiga do admin não envia o management form de ``UserTI``;
        ignorar só esse formset ausente mantém a edição principal válida e não
        concede, altera ou revoga qualquer atribuição de TI.
        """
        for formset, inline in super().get_formsets_with_inlines(request, obj):
            prefix = formset.get_default_prefix()
            if (
                request.method == 'POST'
                and inline.model is UserTI
                and f'{prefix}-TOTAL_FORMS' not in request.POST
            ):
                continue
            yield formset, inline

    def get_queryset(self, request):
        """
        Superusers somem da lista para quem não é superuser (#132).

        `ModelAdmin.get_object()` lê daqui, então filtrar num lugar só fecha o
        changelist, o change form, o delete e — o buraco que sobrava depois de
        travar o checkbox `is_superuser` — o `/admin/auth/user/<id>/password/`
        herdado do `UserAdmin`, que só checa `has_change_permission`. Sem isso,
        um staff com `auth.change_user` troca a senha de um superuser e entra
        como ele, chegando ao mesmo lugar por outra porta.
        """
        queryset = super().get_queryset(request)
        if request.user.is_superuser:
            return queryset
        return queryset.filter(is_superuser=False)

    def atribuir_tis_aos_usuarios(self, request, queryset):
        if not request.user.is_superuser:
            raise PermissionDenied
        ids = ','.join(str(pk) for pk in queryset.order_by('pk').values_list('pk', flat=True))
        url = reverse('admin:dominial_atribuicao_em_massa')
        return redirect(f'{url}?usuarios={ids}')

    atribuir_tis_aos_usuarios.short_description = 'Atribuir TIs aos usuários selecionados'
    atribuir_tis_aos_usuarios.allowed_permissions = ('view',)

    def _alvo_protegido(self, request, obj):
        """True quando um não-superuser tenta agir sobre um superuser."""
        return (
            obj is not None
            and obj.is_superuser
            and not request.user.is_superuser
        )

    def has_view_permission(self, request, obj=None):
        if self._alvo_protegido(request, obj):
            return False
        return super().has_view_permission(request, obj)

    def has_change_permission(self, request, obj=None):
        if self._alvo_protegido(request, obj):
            return False
        return super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        if self._alvo_protegido(request, obj):
            return False
        return super().has_delete_permission(request, obj)


admin.site.unregister(User)
admin.site.register(User, UserAdmin)


class GroupAdmin(DjangoGroupAdmin):
    """Protege os grupos estruturais de perfil contra rename e exclusão."""

    actions = ['atribuir_tis_as_equipes']

    @staticmethod
    def _protegido(obj):
        return bool(
            obj
            and obj.pk
            and GrupoAcesso.objects.filter(group=obj, protegido=True).exists()
        )

    def has_delete_permission(self, request, obj=None):
        if self._protegido(obj):
            return False
        return super().has_delete_permission(request, obj)

    def save_model(self, request, obj, form, change):
        nome_foi_alterado = (
            change
            and GrupoAcesso.objects.filter(group_id=obj.pk, protegido=True).exists()
            and Group.objects.filter(pk=obj.pk).exclude(name=obj.name).exists()
        )
        if nome_foi_alterado:
            raise PermissionDenied('Grupos de perfil protegidos não podem ser renomeados.')
        super().save_model(request, obj, form, change)
        if not change:
            GrupoAcesso.objects.get_or_create(
                group=obj,
                defaults={'tipo': GrupoAcesso.EQUIPE},
            )

    def delete_model(self, request, obj):
        if self._protegido(obj):
            raise PermissionDenied('Grupos de perfil protegidos não podem ser excluídos.')
        super().delete_model(request, obj)

    def delete_queryset(self, request, queryset):
        super().delete_queryset(request, queryset.exclude(acesso__protegido=True))

    def atribuir_tis_as_equipes(self, request, queryset):
        if not request.user.is_superuser:
            raise PermissionDenied
        ids = ','.join(str(pk) for pk in queryset.order_by('pk').values_list('pk', flat=True))
        url = reverse('admin:dominial_atribuicao_em_massa')
        return redirect(f'{url}?equipes={ids}')

    atribuir_tis_as_equipes.short_description = 'Atribuir TIs às equipes selecionadas'
    atribuir_tis_as_equipes.allowed_permissions = ('view',)


admin.site.unregister(Group)
admin.site.register(Group, GroupAdmin)


@admin.register(Imovel)
class ImovelAdmin(AtribuicaoAuditoriaMixin, admin.ModelAdmin):
    """
    Admin customizado para Imóveis com funcionalidade de correção de TI.
    """
    inlines = [UserImovelPorImovelInline]
    list_display = ['matricula', 'nome', 'terra_indigena_id', 'proprietario', 'cartorio', 'tipo_documento_principal', 'arquivado', 'data_cadastro', 'info_documentos_lancamentos']
    list_filter = [
        ('terra_indigena_id', TIsSegregadaFilter),
        'tipo_documento_principal', 'arquivado', 'cartorio', 'data_cadastro',
    ]
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
        queryset = super().get_queryset(request).select_related(
            'terra_indigena_id', 'proprietario', 'cartorio'
        ).prefetch_related('documentos', 'documentos__lancamentos')
        return escopar(queryset, Imovel.objects.for_user(request.user), request.user)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'terra_indigena_id':
            kwargs['queryset'] = tis_for_user(request.user)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)
    
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
            imovel = Imovel.objects.for_user(request.user).select_related(
                'terra_indigena_id', 'proprietario', 'cartorio'
            ).prefetch_related(
                'documentos', 'documentos__lancamentos'
            ).get(id=imovel_id)
        except Imovel.DoesNotExist:
            messages.error(request, 'Imóvel não encontrado.')
            return redirect('admin:dominial_imovel_changelist')

        if not self.has_change_permission(request, imovel):
            raise PermissionDenied
        
        # Coletar informações sobre documentos e lançamentos
        documentos = imovel.documentos.all()\
            .annotate(data_exibicao_ordenacao=Documento.data_exibicao_expression())\
            .order_by('-data_exibicao_ordenacao', '-id')
        num_documentos = documentos.count()
        num_lancamentos = Lancamento.objects.filter(documento__imovel=imovel).count()
        
        ti_atual = imovel.terra_indigena_id
        todas_tis = tis_for_user(request.user).order_by('nome')
        
        if request.method == 'POST':
            nova_ti_id = request.POST.get('nova_ti')
            motivo = request.POST.get('motivo', '').strip()
            
            if not nova_ti_id:
                messages.error(request, 'Por favor, selecione uma nova Terra Indígena.')
            else:
                try:
                    nova_ti = tis_for_user(request.user).get(id=nova_ti_id)
                    
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
            imovel = Imovel.objects.for_user(request.user).get(id=object_id)
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
        queryset = super().get_queryset(request).select_related(
            'cartorio', 'imovel', 'imovel__terra_indigena_id', 'tipo'
        ).prefetch_related('lancamentos')
        return escopar(queryset, documentos_for_user(request.user), request.user)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'imovel':
            kwargs['queryset'] = Imovel.objects.for_user(request.user)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)
    
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
            duplicatas = documentos_for_user(request.user).filter(numero__in=numeros_selecionados).values('numero').annotate(
                count=Count('id')
            ).filter(count__gt=1)
        else:
            # Se nenhum documento selecionado, buscar todos os duplicados
            duplicatas = documentos_for_user(request.user).values('numero').annotate(
                count=Count('id')
            ).filter(count__gt=1)
        
        if duplicatas:
            mensagem = "🔍 Documentos com mesmo número encontrados:\n"
            for dup in duplicatas:
                numero = dup['numero']
                documentos = documentos_for_user(request.user).filter(numero=numero).select_related('cartorio').order_by('cartorio__nome')
                mensagem += f"\n📋 Número: {numero} ({dup['count']} documentos):\n"
                for doc in documentos:
                    mensagem += f"  - ID: {doc.id}, Cartório: {doc.cartorio.nome}, Data: {doc.data}\n"
            messages.warning(request, mensagem)
        else:
            messages.success(request, "✅ Nenhum documento com mesmo número encontrado.")
    
    investigar_duplicatas.short_description = "🔍 Investigar documentos com mesmo número"
    # Só lê e reporta, mas a action tem de declarar a permissão que exige para o
    # Django filtrá-la — sem isso ela aparece para qualquer staff no changelist.
    investigar_duplicatas.allowed_permissions = ('view',)

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
        queryset = super().get_queryset(request).select_related(
            'documento', 'documento__cartorio', 'documento__imovel',
            'documento__imovel__terra_indigena_id', 'tipo', 'transmitente', 'adquirente'
        )
        return escopar(queryset, lancamentos_for_user(request.user), request.user)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'documento':
            kwargs['queryset'] = documentos_for_user(request.user)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

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
        # `admin_view` só exige is_staff; as permissões do model ficam por conta
        # das views customizadas (#132).
        if not self.has_change_permission(request):
            raise PermissionDenied
        # Inicializado antes do try: um `DoesNotExist` no `.get()` deixava o
        # `if importacao` do except estourando UnboundLocalError → 500.
        importacao = None
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
        except Exception:
            logger.exception('Erro ao importar cartórios da importação %s', importacao_id)
            if importacao:
                importacao.status = 'erro'
                importacao.erro = ERRO_IMPORTACAO
                importacao.save()
            return JsonResponse({
                'status': 'error',
                'message': ERRO_IMPORTACAO
            })

    def verificar_progresso(self, request, importacao_id):
        if not self.has_view_permission(request):
            raise PermissionDenied
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
        if not self.has_add_permission(request):
            raise PermissionDenied
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
            except Exception:
                logger.exception('Erro ao importar cartórios da importação %s', importacao.pk)
                importacao.status = 'erro'
                importacao.erro = ERRO_IMPORTACAO
                importacao.save()
                messages.error(
                    request,
                    f'{importacao.get_estado_display()}: {ERRO_IMPORTACAO}'
                )

    importar_cartorios.short_description = 'Importar cartórios do estado selecionado'
    # Sem `allowed_permissions`, o Django não filtra a action: qualquer staff que
    # chegue ao changelist só com `view_importacaocartorios` dispararia a
    # importação e mexeria no status (#132).
    importar_cartorios.allowed_permissions = ('change',)


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
