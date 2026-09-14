from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from dominial.models import (
    Cartorios,
    Documento,
    DocumentoTipo,
    Imovel,
    Pessoas,
    TIs,
)


class Issue210Fixture(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.ti = TIs.objects.create(nome='TI #210', codigo='TI-210', etnia='Teste')
        cls.pessoa = Pessoas.objects.create(nome='Pessoa #210', cpf='210')
        cls.cartorio_a = Cartorios.objects.create(
            nome='Cartório A #210',
            cns='CNS-210-A',
            cidade='A',
            estado='MS',
        )
        cls.cartorio_b = Cartorios.objects.create(
            nome='Cartório B #210',
            cns='CNS-210-B',
            cidade='B',
            estado='MT',
        )
        cls.cartorio_c = Cartorios.objects.create(
            nome='Cartório C #210',
            cns='CNS-210-C',
            cidade='C',
            estado='GO',
        )
        cls.tipo = DocumentoTipo.objects.create(tipo='matricula')

    def criar_imovel(self):
        return Imovel.objects.create(
            terra_indigena_id=self.ti,
            nome='Imóvel #210',
            proprietario=self.pessoa,
            matricula='14511',
            tipo_documento_principal='matricula',
            cartorio=self.cartorio_a,
        )

    def criar_documento(self, imovel, cartorio=None):
        return Documento.objects.create(
            imovel=imovel,
            tipo=self.tipo,
            numero='M14511',
            data='2026-09-14',
            cartorio=cartorio or self.cartorio_a,
            livro='1',
            folha='1',
        )

    def dados_admin(self, imovel, cartorio):
        return {
            'matricula': imovel.matricula,
            'nome': imovel.nome,
            'tipo_documento_principal': imovel.tipo_documento_principal,
            'terra_indigena_id': str(self.ti.pk),
            'proprietario': str(self.pessoa.pk),
            'cartorio': str(cartorio.pk),
            'arquivado': '',
            'observacoes': '',
            '_save': 'Salvar',
        }


class ImovelAdminIssue210Test(Issue210Fixture):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.admin = get_user_model().objects.create_superuser(
            username='admin210',
            email='admin210@example.com',
            password='senha',
        )

    def setUp(self):
        self.client.force_login(self.admin)

    def test_admin_sincroniza_cartorio_do_documento_principal(self):
        imovel = self.criar_imovel()
        documento = self.criar_documento(imovel)
        url = reverse('admin:dominial_imovel_change', args=[imovel.pk])

        resposta = self.client.post(url, self.dados_admin(imovel, self.cartorio_b))

        self.assertEqual(resposta.status_code, 302)
        documento.refresh_from_db()
        self.assertEqual(documento.cartorio, self.cartorio_b)

    def test_admin_exibe_erro_e_nao_salva_sem_documento_principal(self):
        imovel = self.criar_imovel()
        url = reverse('admin:dominial_imovel_change', args=[imovel.pk])

        resposta = self.client.post(url, self.dados_admin(imovel, self.cartorio_b))

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, 'nenhum documento principal')
        imovel.refresh_from_db()
        self.assertEqual(imovel.cartorio, self.cartorio_a)

    def test_admin_exibe_ids_e_nao_salva_documentos_ambiguos(self):
        imovel = self.criar_imovel()
        documento_a = self.criar_documento(imovel)
        documento_b = self.criar_documento(imovel, self.cartorio_b)
        url = reverse('admin:dominial_imovel_change', args=[imovel.pk])

        resposta = self.client.post(url, self.dados_admin(imovel, self.cartorio_c))

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, str(documento_a.pk))
        self.assertContains(resposta, str(documento_b.pk))
        imovel.refresh_from_db()
        self.assertEqual(imovel.cartorio, self.cartorio_a)
