"""
P1-E (#132): verificar_duplicata_antes_criacao — duplicata acessível tem
prioridade sobre inacessível, independente da ordem das origens no POST.

Usa mock de DuplicataVerificacaoService.verificar_duplicata_origem para
controlar a sequência de respostas (inacessível + acessível).
"""

from types import SimpleNamespace
from unittest.mock import patch, MagicMock

from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase


class DuplicataOrdemPrioridadeTest(TestCase):
    """Acessível deve ter prioridade sobre inacessível nas duas ordens."""

    def setUp(self):
        self.user = User.objects.create_user(username='p1e_user', password='x')
        self.factory = RequestFactory()
        # Documento ativo fictício (imovel.id = 1)
        self.doc_ativo = SimpleNamespace(imovel=SimpleNamespace(id=1))
        # Documento "origem" acessível (usado no return do mock)
        self.doc_origem = SimpleNamespace(
            numero='M3000',
            imovel=SimpleNamespace(nome='Imóvel C1'),
            id=300,
        )

    def _resultado_inacessivel(self):
        return {
            'tem_duplicata': True,
            'acessivel': False,
            'mensagem': 'Duplicata encontrada em TI sem acesso',
        }

    def _resultado_acessivel(self):
        return {
            'tem_duplicata': True,
            'acessivel': True,
            'mensagem': 'Duplicata acessível',
            'documento_origem': self.doc_origem,
            'documentos_importaveis': [],
            'cadeia_dominial': None,
        }

    def _call_service(self, side_effect):
        from dominial.services.lancamento_duplicata_service import LancamentoDuplicataService

        request = self.factory.post('/fake/', data={
            'origem_completa[]': ['M2000', 'M3000'],
            'cartorio_origem[]': ['10', '10'],
        })
        request.user = self.user

        with patch(
            'dominial.services.lancamento_duplicata_service.DuplicataVerificacaoService.verificar_duplicata_origem',
            side_effect=side_effect,
        ), patch(
            'dominial.services.lancamento_duplicata_service.Cartorios.objects.get',
            return_value=SimpleNamespace(id=10),
        ):
            return LancamentoDuplicataService.verificar_duplicata_antes_criacao(
                request, self.doc_ativo
            )

    def test_ordem_inacessivel_primeiro_devolve_acessivel(self):
        """[inacessível, acessível] → acessível tem prioridade."""
        resultado = self._call_service([
            self._resultado_inacessivel(),
            self._resultado_acessivel(),
        ])
        self.assertTrue(resultado['tem_duplicata'])
        self.assertTrue(resultado['acessivel'])
        self.assertEqual(resultado['documento_origem'].numero, 'M3000')

    def test_ordem_acessivel_primeiro_devolve_acessivel(self):
        """[acessível, inacessível] → acessível tem prioridade (comportamento já ok)."""
        resultado = self._call_service([
            self._resultado_acessivel(),
            self._resultado_inacessivel(),
        ])
        self.assertTrue(resultado['tem_duplicata'])
        self.assertTrue(resultado['acessivel'])
        self.assertEqual(resultado['documento_origem'].numero, 'M3000')

    def test_so_inacessivel_devolve_inacessivel(self):
        """Só origem inacessível → D1 (acessivel=False) continua funcionando."""
        from dominial.services.lancamento_duplicata_service import LancamentoDuplicataService

        request = self.factory.post('/fake/', data={
            'origem_completa[]': ['M2000'],
            'cartorio_origem[]': ['10'],
        })
        request.user = self.user

        with patch(
            'dominial.services.lancamento_duplicata_service.DuplicataVerificacaoService.verificar_duplicata_origem',
            return_value=self._resultado_inacessivel(),
        ), patch(
            'dominial.services.lancamento_duplicata_service.Cartorios.objects.get',
            return_value=SimpleNamespace(id=10),
        ):
            resultado = LancamentoDuplicataService.verificar_duplicata_antes_criacao(
                request, self.doc_ativo
            )
        self.assertTrue(resultado['tem_duplicata'])
        self.assertFalse(resultado['acessivel'])

    def test_sem_duplicata_devolve_tem_duplicata_false(self):
        """Sem duplicata em nenhuma origem → tem_duplicata=False."""
        from dominial.services.lancamento_duplicata_service import LancamentoDuplicataService

        request = self.factory.post('/fake/', data={
            'origem_completa[]': ['M9999'],
            'cartorio_origem[]': ['10'],
        })
        request.user = self.user

        with patch(
            'dominial.services.lancamento_duplicata_service.DuplicataVerificacaoService.verificar_duplicata_origem',
            return_value={'tem_duplicata': False, 'acessivel': True, 'mensagem': ''},
        ), patch(
            'dominial.services.lancamento_duplicata_service.Cartorios.objects.get',
            return_value=SimpleNamespace(id=10),
        ):
            resultado = LancamentoDuplicataService.verificar_duplicata_antes_criacao(
                request, self.doc_ativo
            )
        self.assertFalse(resultado['tem_duplicata'])
