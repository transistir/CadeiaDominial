"""
Tests for ONR (Organização Nacional dos Registradores) API integration
"""
import pytest
import requests
from django.test import TestCase, Client


class TestONRIntegration(TestCase):
    """Test ONR external API integration"""

    def setUp(self):
        """Set up test client"""
        self.client = Client()

    @pytest.mark.integration
    def test_onr_external_api_post(self):
        """Test direct POST request to ONR external API"""
        url = 'https://www.registrodeimoveis.org.br/includes/consulta-cartorios.php'
        headers = {
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0',
            'Accept': '*/*',
            'Accept-Language': 'pt-BR,pt;q=0.8,en-US;q=0.5,en;q=0.3',
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'X-Requested-With': 'XMLHttpRequest',
            'Referer': 'https://www.registrodeimoveis.org.br/cartorios',
        }
        data = 'estado=AC'

        try:
            response = requests.post(url, headers=headers, data=data, timeout=10)
            self.assertEqual(response.status_code, 200)
        except requests.exceptions.RequestException as e:
            # External API might be unavailable, skip test
            pytest.skip(f"External ONR API unavailable: {e}")

    @pytest.mark.integration
    def test_verificar_cartorios_endpoint(self):
        """Test internal verificar-cartorios endpoint"""
        response = self.client.post('/dominial/verificar-cartorios/', data={'estado': 'SP'})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('existem_cartorios', data)
