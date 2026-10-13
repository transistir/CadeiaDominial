"""S8 (#132): respostas sem str(e) — varredura estática + testes comportamentais."""

import os
import re
from datetime import date
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
        services_dir = os.path.join(os.path.dirname(__file__), '..', 'services')
        
        files_to_check = []
        for filename in os.listdir(views_dir):
            if filename.endswith('.py'):
                files_to_check.append(os.path.join(views_dir, filename))
        files_to_check.append(admin_file)
        
        # P2 (#132): varrer TODOS os services (não mais hardcoded)
        for filename in os.listdir(services_dir):
            if filename.endswith('.py'):
                files_to_check.append(os.path.join(services_dir, filename))
        
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
                    # P2 (#132): print() vai para stdout/log, não para resposta
                    # HTTP — não é vetor de vazamento para o usuário.
                    if stripped.startswith('print('):
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


class ComportamentalImportacaoCadeiaNaoVazaSegredoTest(TestCase):
    """P1-C: importacao_cadeia_service não pode vazar str(e) no dict de erro.

    Opção escolhida: chamada direta do service (mais simples e robusta que
    subir a view com autenticação + TI + imóvel). O dict é o contrato que a
    view repassa ao cliente — se a mensagem é fixa, nenhuma exceção interna
    chega ao frontend.
    """

    def setUp(self):
        from django.contrib.auth.models import User
        from dominial.models import Cartorios, Documento, DocumentoTipo, Imovel, Pessoas, TIs
        from dominial.tests.segregacao_fixtures import atribuir_tis

        self.user = User.objects.create_user(username='srv_chain', password='x')
        self.tis = TIs.objects.create(nome='TI Chain', codigo='TI-CH', etnia='Ch')
        self.cartorio = Cartorios.objects.create(nome='Cartório Chain', cns='333333')
        self.pessoa = Pessoas.objects.create(nome='Prop Chain')
        self.imovel = Imovel.objects.create(
            nome='Imóvel Chain', matricula='CH1',
            terra_indigena_id=self.tis, cartorio=self.cartorio,
            proprietario=self.pessoa,
        )
        self.doc_tipo = DocumentoTipo.objects.create(tipo='matricula')
        self.doc = Documento.objects.create(
            imovel=self.imovel, tipo=self.doc_tipo, numero='CH1',
            cartorio=self.cartorio, livro='1', folha='1',
            data=date(2024, 1, 1),
        )
        atribuir_tis(self.user, self.tis)

    def test_excecao_inesperada_nao_vaza_str_e(self):
        """RuntimeError interna → 'erros' com mensagem fixa, sem SEGREDO."""
        from dominial.services.importacao_cadeia_service import ImportacaoCadeiaService

        with patch(
            'dominial.services.importacao_cadeia_service.ImportacaoCadeiaService.marcar_documento_importado',
            side_effect=RuntimeError('SEGREDO-XYZ /opt/app/chain.py linha 42'),
        ):
            with self.assertLogs('dominial.services.importacao_cadeia_service', level='ERROR'):
                resultado = ImportacaoCadeiaService.importar_cadeia_dominial(
                    imovel_destino_id=self.imovel.id,
                    documento_origem_id=self.doc.id,
                    documentos_importaveis_ids=[self.doc.id],
                    usuario_id=self.user.id,
                )

        self.assertFalse(resultado['sucesso'])
        # Caminho cai no else (loop interno captura a exceção → lista 'erros')
        for erro_msg in resultado.get('erros', []):
            self.assertNotIn('SEGREDO', erro_msg)
            self.assertNotIn('/opt/app', erro_msg)
            self.assertNotIn('linha 42', erro_msg)
        self.assertNotIn('SEGREDO', resultado.get('mensagem', ''))


class ComportamentalCartorioVerificacaoNaoVazaSegredoTest(TestCase):
    """P1-C: cartorio_verificacao_service não pode vazar str(e)."""

    def test_verificar_cartorios_nao_vaza_str_e(self):
        from dominial.services.cartorio_verificacao_service import CartorioVerificacaoService

        with patch(
            'dominial.services.cartorio_verificacao_service.Cartorios.objects.filter',
            side_effect=RuntimeError('SEGREDO-ABC db/connection.py'),
        ):
            with self.assertLogs('dominial.services.cartorio_verificacao_service', level='ERROR'):
                resultado = CartorioVerificacaoService.verificar_cartorios_estado('SP')

        self.assertNotIn('SEGREDO', resultado.get('erro', ''))
        self.assertNotIn('db/connection', resultado.get('erro', ''))

    def test_importar_cartorios_nao_vaza_str_e(self):
        from dominial.services.cartorio_verificacao_service import CartorioVerificacaoService

        with patch(
            'dominial.services.cartorio_verificacao_service.call_command',
            side_effect=RuntimeError('SEGREDO-DEF falha-de-import'),
        ):
            with self.assertLogs('dominial.services.cartorio_verificacao_service', level='ERROR'):
                resultado = CartorioVerificacaoService.importar_cartorios_estado('SP')

        self.assertFalse(resultado['success'])
        self.assertNotIn('SEGREDO', resultado.get('error', ''))
        self.assertNotIn('falha-de-import', resultado.get('error', ''))
