from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from dominial.models import Cartorios


class CartoriosAdminTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser('admin', 'admin@test.com', 'pass')
        self.client = Client()
        self.client.login(username='admin', password='pass')
        
        # Criar cartórios de teste
        Cartorios.objects.create(
            nome='Cartório Teste 1',
            cns='CNS001',
            cidade='São Paulo',
            estado='SP',
            tipo='CRI'
        )
        Cartorios.objects.create(
            nome='Cartório Teste 2',
            cns='CNS002',
            cidade=None,
            estado=None,
            tipo='CRI'
        )
    
    def test_cartorios_changelist_accessible(self):
        url = reverse('admin:dominial_cartorios_changelist')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
    
    def test_cartorios_search_by_nome(self):
        url = reverse('admin:dominial_cartorios_changelist') + '?q=Teste+1'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Cartório Teste 1')
    
    def test_cartorios_filter_estado_vazio(self):
        url = reverse('admin:dominial_cartorios_changelist') + '?estado_vazio=sim'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Cartório Teste 2')
        self.assertNotContains(response, 'Cartório Teste 1')
