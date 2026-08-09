import importlib
from types import SimpleNamespace

from django.apps import apps
from django.contrib import admin
from django.contrib.auth.models import Group, Permission, User
from django.core.exceptions import ValidationError
from django.db import IntegrityError, connection, transaction
from django.test import Client, RequestFactory, TestCase
from django.urls import reverse

from dominial.admin import GroupTIAdmin, UserTIAdmin
from dominial.models import (
    Cartorios,
    GroupTI,
    GrupoAcesso,
    Imovel,
    Pessoas,
    TIs,
    UserTI,
)


class ModelsAtribuicaoTITest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.superuser = User.objects.create_superuser(
            username='super-fase1', password='senha', email='super@example.com'
        )
        cls.user = User.objects.create_user(username='usuario-fase1', password='senha')
        cls.tis = TIs.objects.create(nome='TI Fase 1', codigo='TI-F1', etnia='Teste')
        cls.equipe = Group.objects.create(name='Equipe Fase 1')
        GrupoAcesso.objects.create(group=cls.equipe, tipo=GrupoAcesso.EQUIPE)

    def test_groupti_recusa_grupo_de_perfil_no_full_clean(self):
        perfil = Group.objects.get(name='Perfil: Editor')

        with self.assertRaisesMessage(
            ValidationError,
            'TIs só podem ser atribuídas a equipes, não a perfis.',
        ):
            GroupTI(group=perfil, tis=self.tis).full_clean()

    def test_unique_together_bloqueia_userti_duplicado(self):
        UserTI.objects.create(user=self.user, tis=self.tis)

        with self.assertRaises(IntegrityError), transaction.atomic():
            UserTI.objects.create(user=self.user, tis=self.tis)

    def test_unique_together_bloqueia_groupti_duplicado(self):
        GroupTI.objects.create(group=self.equipe, tis=self.tis)

        with self.assertRaises(IntegrityError), transaction.atomic():
            GroupTI.objects.create(group=self.equipe, tis=self.tis)

    def test_excluir_group_apaga_groupti_sem_orfao(self):
        atribuicao = GroupTI.objects.create(group=self.equipe, tis=self.tis)

        self.equipe.delete()

        self.assertFalse(GroupTI.objects.filter(pk=atribuicao.pk).exists())

    def test_admins_carimbam_atribuido_por(self):
        request = RequestFactory().post('/admin/')
        request.user = self.superuser
        user_ti = UserTI(user=self.user, tis=self.tis)
        group_ti = GroupTI(group=self.equipe, tis=self.tis)

        UserTIAdmin(UserTI, admin.site).save_model(request, user_ti, None, False)
        GroupTIAdmin(GroupTI, admin.site).save_model(request, group_ti, None, False)

        self.assertEqual(user_ti.atribuido_por, self.superuser)
        self.assertEqual(group_ti.atribuido_por, self.superuser)

    def test_atribuicao_direta_de_ti_alimenta_o_filtro_na_fase2(self):
        cartorio = Cartorios.objects.create(nome='CRI Fase 1', cns='F1')
        proprietario = Pessoas.objects.create(nome='Proprietário Fase 1')
        imovel = Imovel.objects.create(
            nome='Imóvel Fase 1',
            matricula='F1',
            terra_indigena_id=self.tis,
            proprietario=proprietario,
            cartorio=cartorio,
        )
        UserTI.objects.create(user=self.user, tis=self.tis)

        self.assertIn(imovel, Imovel.objects.for_user(self.user))


class AdminAtribuicaoTITest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.staff = User.objects.create_user(
            username='staff-fase1', password='senha', is_staff=True
        )
        cls.staff.user_permissions.set(Permission.objects.filter(
            content_type__app_label='dominial',
            codename__in=[
                'add_userti',
                'change_userti',
                'add_groupti',
                'change_groupti',
            ],
        ))

    def setUp(self):
        self.client = Client()
        self.client.force_login(self.staff)

    def test_staff_nao_ve_atribuicoes_ti_no_index_nem_acessa_changelists(self):
        urls = [
            reverse('admin:dominial_userti_changelist'),
            reverse('admin:dominial_groupti_changelist'),
        ]

        index = self.client.get(reverse('admin:index'))

        self.assertEqual(index.status_code, 200)
        for url in urls:
            self.assertNotContains(index, url)
            self.assertEqual(self.client.get(url).status_code, 403)


class SeedPerfisMigrationTest(TestCase):
    def test_seed_cria_so_dois_perfis_sem_equipes_e_e_idempotente(self):
        migration = importlib.import_module('dominial.migrations.0060_seed_perfis')
        schema_editor = SimpleNamespace(connection=connection)

        migration.seed_perfis(apps, schema_editor)
        migration.seed_perfis(apps, schema_editor)

        perfis = GrupoAcesso.objects.filter(tipo=GrupoAcesso.PERFIL)
        self.assertEqual(perfis.count(), 2)
        self.assertCountEqual(
            perfis.values_list('group__name', flat=True),
            ['Perfil: Editor', 'Perfil: Administrador'],
        )
        self.assertEqual(Group.objects.count(), 2)
        self.assertFalse(GrupoAcesso.objects.filter(tipo=GrupoAcesso.EQUIPE).exists())
        self.assertEqual(perfis.filter(protegido=True).count(), 2)
        self.assertFalse(Group.objects.get(name='Perfil: Editor').permissions.exists())
        self.assertTrue(Group.objects.get(name='Perfil: Administrador').permissions.exists())

    def test_seed_classifica_group_preexistente_como_equipe(self):
        migration = importlib.import_module('dominial.migrations.0060_seed_perfis')
        schema_editor = SimpleNamespace(connection=connection)
        legado = Group.objects.create(name='Equipe legada')

        migration.seed_perfis(apps, schema_editor)

        self.assertEqual(legado.acesso.tipo, GrupoAcesso.EQUIPE)
        self.assertFalse(legado.acesso.protegido)
