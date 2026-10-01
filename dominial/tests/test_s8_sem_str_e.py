"""S8 (#132): respostas sem str(e) — varredura estática + testes comportamentais."""

import os
import re
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse

from dominial.models import Cartorios, Documento, DocumentoTipo, Imovel, LancamentoTipo, Pessoas, TIs
from dominial.tests.segregacao_fixtures import atribuir_tis
from dominial.utils.mensagens_erro import ERRO_INTERNO


class VarreduraEstaticaTest(TestCase):
    """Garante que nenhum str(e)/str(exc)/str(erro) vaza em respostas."""

    def test_sem_str_e_nas_views(self):
        """Regex: str\\((e|exc|erro)\\)|\\{(e|exc|erro)\\}"""
        regex = re.compile(r'str\((e|exc|erro)\)|\{(e|exc|erro)\}')
        allowlist = {
            'lancamento_views.py': ['in str(e)'],
        }
        
        violations = []
        views_dir = os.path.join(os.path.dirname(__file__), '..', 'views')
        admin_file = os.path.join(os.path.dirname(__file__), '..', 'admin.py')
        
        files_to_check = []
        for filename in os.listdir(views_dir):
            if filename.endswith('.py'):
                files_to_check.append(os.path.join(views_dir, filename))
        files_to_check.append(admin_file)
        
        for filepath in files_to_check:
            if not os.path.exists(filepath):
                continue
            filename = os.path.basename(filepath)
            with open(filepath, 'r') as f:
                for line_num, line in enumerate(f, 1):
                    stripped = line.lstrip()
                    # Ignorar linhas de comentário
                    if stripped.startswith('#'):
                        continue
                    if regex.search(line):
                        # Check allowlist
                        if filename in allowlist:
                            if any(pattern in line for pattern in allowlist[filename]):
                                continue
                        violations.append(f'{filename}:{line_num}: {line.strip()}')
        
        self.assertEqual(violations, [], f'Violações encontradas:\n' + '\n'.join(violations))


class ComportamentalGetCadeiaTest(TestCase):
    """get_cadeia_dominial_atualizada: erro interno vira ERRO_INTERNO."""

    def setUp(self):
        self.user = User.objects.create_user(username='test_cadeia', password='pass')
        self.client = Client()
        self.client.login(username='test_cadeia', password='pass')
        
        self.tis = TIs.objects.create(nome='TI Teste', codigo='TI-TEST', etnia='Teste')
        self.cartorio = Cartorios.objects.create(nome='Cartório Teste', cns='123456')
        self.pessoa = Pessoas.objects.create(nome='Proprietário Teste')
        self.imovel = Imovel.objects.create(
            nome='Imóvel Teste', matricula='M1234',
            terra_indigena_id=self.tis, cartorio=self.cartorio,
            proprietario=self.pessoa,
        )
        atribuir_tis(self.user, self.tis)

    def test_excecao_nao_vaza_detalhes(self):
        """Exception no CadeiaDominialTabelaService: 500 com ERRO_INTERNO."""
        url = reverse('get_cadeia_dominial_atualizada', args=[self.tis.id, self.imovel.id])
        
        with patch(
            'dominial.views.api_views.CadeiaDominialTabelaService.obter_cadeia_tabela',
            side_effect=Exception('SEGREDO /opt/app/x.py')
        ):
            with self.assertLogs('dominial.views.api_views', level='ERROR'):
                response = self.client.get(url)
        
        self.assertEqual(response.status_code, 500)
        data = response.json()
        self.assertEqual(data['error'], ERRO_INTERNO)
        self.assertNotIn('SEGREDO', response.content.decode('utf-8'))


class ComportamentalEscolherOrigemTest(TestCase):
    """escolher_origem_documento: erro interno vira ERRO_INTERNO."""

    def setUp(self):
        self.user = User.objects.create_user(username='test_origem', password='pass')
        self.client = Client()
        self.client.login(username='test_origem', password='pass')
        
        self.tis = TIs.objects.create(nome='TI Origem', codigo='TI-ORIG', etnia='Origem')
        self.cartorio = Cartorios.objects.create(nome='Cartório Origem', cns='789012')
        self.pessoa = Pessoas.objects.create(nome='Proprietário Origem')
        self.imovel = Imovel.objects.create(
            nome='Imóvel Origem', matricula='M5678',
            terra_indigena_id=self.tis, cartorio=self.cartorio,
            proprietario=self.pessoa,
        )
        self.doc_tipo = DocumentoTipo.objects.create(tipo='matricula')
        from django.utils import timezone
        self.documento = Documento.objects.create(
            imovel=self.imovel, tipo=self.doc_tipo, numero='M5678',
            cartorio=self.cartorio, livro='1', folha='1',
            data=timezone.now().date(),
        )
        atribuir_tis(self.user, self.tis)

    def test_excecao_nao_vaza_detalhes(self):
        """Exception no obter_origens_resolvidas: 500 com ERRO_INTERNO."""
        url = reverse('escolher_origem_documento')
        data = {
            'documento_id': self.documento.id,
            'origem_identidade': 'documento:999',
            'tis_id': self.tis.id,
            'imovel_id': self.imovel.id,
        }
        
        with patch(
            'dominial.views.api_views.obter_origens_resolvidas',
            side_effect=Exception('SEGREDO /opt/app/y.py')
        ):
            with self.assertLogs('dominial.views.api_views', level='ERROR'):
                response = self.client.post(url, data=data, content_type='application/json')
        
        self.assertEqual(response.status_code, 500)
        response_data = response.json()
        self.assertEqual(response_data['error'], ERRO_INTERNO)
        self.assertNotIn('SEGREDO', response.content.decode('utf-8'))
