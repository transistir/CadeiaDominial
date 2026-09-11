from django.test import TestCase
from django.urls import reverse

from dominial.models import Cartorios


class CartorioImoveisAutocompleteEstadoTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cartorio_com_estado = Cartorios.objects.create(
            nome='Registro de Imóveis de Guaíra',
            cns='193001',
            cidade='Guaíra',
            estado='PR',
        )
        cls.cartorio_sem_estado = Cartorios.objects.create(
            nome='Registro de Imóveis sem UF',
            cns='193002',
            cidade=None,
            estado=None,
        )

    def _buscar_por_registro(self):
        response = self.client.get(
            reverse('cartorio-imoveis-autocomplete'),
            {'q': 'Registro'},
        )
        self.assertEqual(response.status_code, 200)
        return {cartorio['id']: cartorio for cartorio in response.json()}

    def test_retorna_estado_preenchido(self):
        resultados = self._buscar_por_registro()

        self.assertEqual(resultados[self.cartorio_com_estado.id]['estado'], 'PR')

    def test_retorna_none_quando_estado_esta_vazio(self):
        resultados = self._buscar_por_registro()

        self.assertIsNone(resultados[self.cartorio_sem_estado.id]['estado'])
