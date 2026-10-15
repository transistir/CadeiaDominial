"""System checks de configuração/viabilidade (#259) e a validação de lease
do worker: só opinam quando o backend configurado é o real — com
`StubBackend` nenhum check dispara e o comando não valida nada.
"""

import io
import logging

from django.core.management import call_command
from django.core.management.base import CommandError, SystemCheckError
from django.test import SimpleTestCase, TestCase, override_settings

from ia_ocr.checks import conferir_configuracao_ocr

# Defaults do settings + credenciais e URL preenchidas: zero problemas.
CONFIG_OK = dict(
    OCR_BACKEND='ia_ocr.backends.OcrServiceBackend',
    OCR_SERVICE_URL='https://ocr-teste.example',
    OCR_INTERNAL_TOKEN='token-sintetico',
    OCR_ACCESS_CLIENT_ID='access-id-sintetico',
    OCR_ACCESS_CLIENT_SECRET='access-secret-sintetico',
    OCR_HTTP_TIMEOUT_SECONDS=30,
    OCR_MARGEM_PERSISTENCIA_SECONDS=60,
    OCR_JOB_TIMEOUT_SECONDS=3600,
    OCR_MAX_PAGINAS=25,
    OCR_SEGUNDOS_POR_PAGINA=40,
    OCR_FOLGA_FILA_SECONDS=300,
    OCR_MAX_BYTES=52_428_800,
    OCR_POLL_INTERVAL_SECONDS=5,
)

# Tudo o que os checks sabem reclamar, com o backend da I-1: nada dispara.
CONFIG_STUB_TUDO_ERRADO = dict(
    CONFIG_OK,
    OCR_BACKEND='ia_ocr.backends.StubBackend',
    OCR_SERVICE_URL='',
    OCR_INTERNAL_TOKEN='',
    OCR_ACCESS_CLIENT_ID='',
    OCR_ACCESS_CLIENT_SECRET='',
    OCR_MARGEM_PERSISTENCIA_SECONDS=1,
    OCR_JOB_TIMEOUT_SECONDS=1,
    OCR_MAX_PAGINAS=500,
    OCR_MAX_BYTES=99_999_999,
    OCR_POLL_INTERVAL_SECONDS=1,
)


def _check(**sobrescritas):
    with override_settings(**{**CONFIG_OK, **sobrescritas}):
        return conferir_configuracao_ocr()


def _ids(problemas):
    return [problema.id for problema in problemas]


class ConferirConfiguracaoOcrTests(SimpleTestCase):
    def test_configuracao_completa_nao_dispara_nada(self):
        self.assertEqual(_check(), [])

    def test_stub_backend_nao_dispara_nada_mesmo_com_tudo_errado(self):
        with override_settings(**CONFIG_STUB_TUDO_ERRADO):
            self.assertEqual(conferir_configuracao_ocr(), [])

    def test_service_url_vazia_e_erro(self):
        self.assertIn('ia_ocr.E001', _ids(_check(OCR_SERVICE_URL='')))

    def test_service_url_http_com_credenciais_access_e_erro(self):
        problemas = _check(OCR_SERVICE_URL='http://ocr-teste.example')
        self.assertIn('ia_ocr.E002', _ids(problemas))

    def test_service_url_http_sem_credenciais_access_nao_exige_https(self):
        # Sem credencial do Access não há segredo para viajar sem TLS; o que
        # dispara são as credenciais vazias em si (E004/E005), não o esquema.
        problemas = _check(
            OCR_SERVICE_URL='http://ocr-teste.example',
            OCR_ACCESS_CLIENT_ID='',
            OCR_ACCESS_CLIENT_SECRET='',
        )
        ids = _ids(problemas)
        self.assertNotIn('ia_ocr.E002', ids)
        self.assertIn('ia_ocr.E004', ids)
        self.assertIn('ia_ocr.E005', ids)

    def test_credencial_vazia_ganha_erro_proprio(self):
        casos = [
            ('OCR_INTERNAL_TOKEN', 'ia_ocr.E003'),
            ('OCR_ACCESS_CLIENT_ID', 'ia_ocr.E004'),
            ('OCR_ACCESS_CLIENT_SECRET', 'ia_ocr.E005'),
        ]
        for configuracao, ident in casos:
            with self.subTest(configuracao=configuracao):
                self.assertIn(ident, _ids(_check(**{configuracao: ''})))

    def test_margem_menor_que_duas_operacoes_de_socket_e_erro(self):
        with self.subTest(margem=59):
            self.assertIn(
                'ia_ocr.E006',
                _ids(_check(OCR_MARGEM_PERSISTENCIA_SECONDS=59)),
            )
        with self.subTest(margem=60):  # exatamente 2 × timeout: passa
            self.assertNotIn(
                'ia_ocr.E006',
                _ids(_check(OCR_MARGEM_PERSISTENCIA_SECONDS=60)),
            )

    def test_lease_abaixo_do_orcamento_e_erro_com_os_numeros_da_conta(self):
        problemas = _check(OCR_JOB_TIMEOUT_SECONDS=1359)
        ids = _ids(problemas)
        self.assertIn('ia_ocr.E007', ids)
        mensagem = next(
            p.msg for p in problemas if p.id == 'ia_ocr.E007'
        )
        self.assertIn('1359', mensagem)  # o lease configurado
        self.assertIn('25 × 40 + 300 + 60 = 1360', mensagem)  # a conta inteira
        with self.subTest(lease=1360):  # limiar exato: passa
            self.assertNotIn(
                'ia_ocr.E007', _ids(_check(OCR_JOB_TIMEOUT_SECONDS=1360))
            )

    def test_dica_do_e007_nao_aponta_para_flag_que_o_check_nao_ve(self):
        """O check roda sem --timeout (deploy/`manage.py check`): a dica não
        pode sugerir um caminho que não resolve o check. A flag vale para o
        worker (o claim a persiste), mas o ajuste do check é o settings."""
        problemas = _check(OCR_JOB_TIMEOUT_SECONDS=1359)
        dica = next(p.hint for p in problemas if p.id == 'ia_ocr.E007')

        self.assertIn('OCR_JOB_TIMEOUT_SECONDS', dica)
        self.assertNotIn('--timeout', dica)

    def test_max_paginas_acima_do_teto_do_servico_e_erro(self):
        with self.subTest(max_paginas=101):
            self.assertIn('ia_ocr.E008', _ids(_check(OCR_MAX_PAGINAS=101)))
        with self.subTest(max_paginas=100):  # teto do contrato, com lease viável
            self.assertNotIn(
                'ia_ocr.E008',
                _ids(_check(
                    OCR_MAX_PAGINAS=100,
                    OCR_JOB_TIMEOUT_SECONDS=4400,
                )),
            )

    def test_max_bytes_acima_do_servico_e_erro(self):
        with self.subTest(max_bytes=52_428_801):
            self.assertIn(
                'ia_ocr.E009', _ids(_check(OCR_MAX_BYTES=52_428_801))
            )
        with self.subTest(max_bytes=52_428_800):
            self.assertNotIn(
                'ia_ocr.E009', _ids(_check(OCR_MAX_BYTES=52_428_800))
            )

    def test_poll_interval_fora_de_5_a_10_e_aviso_nao_erro(self):
        for intervalo in (4, 11):
            with self.subTest(intervalo=intervalo):
                problemas = _check(OCR_POLL_INTERVAL_SECONDS=intervalo)
                avisos = [p for p in problemas if p.id == 'ia_ocr.W001']
                self.assertEqual(len(avisos), 1)
                self.assertEqual(avisos[0].level, logging.WARNING)
        for intervalo in (5, 10):  # extremos inclusos: sem aviso
            with self.subTest(intervalo=intervalo):
                self.assertNotIn(
                    'ia_ocr.W001',
                    _ids(_check(OCR_POLL_INTERVAL_SECONDS=intervalo)),
                )


class RegistroDoCheckNoManageCheckTests(SimpleTestCase):
    def test_manage_check_passa_com_config_boa_e_falha_com_url_vazia(self):
        saida = io.StringIO()
        with override_settings(**CONFIG_OK):
            call_command('check', stdout=saida)  # não levanta
        with override_settings(**{**CONFIG_OK, 'OCR_SERVICE_URL': ''}):
            with self.assertRaises(SystemCheckError):
                call_command('check', stdout=saida)


class ViabilidadeDoLeaseDoWorkerTests(TestCase):
    """Com backend real, lease abaixo do orçamento máximo de um job faz o
    comando falhar rápido (antes de queimar jobs); StubBackend não valida.
    """

    def test_lease_curto_do_settings_levanta_command_error_com_a_conta(self):
        with override_settings(**{**CONFIG_OK, 'OCR_JOB_TIMEOUT_SECONDS': 600}):
            with self.assertRaises(CommandError) as contexto:
                call_command('process_ocr_queue', '--once')

        mensagem = str(contexto.exception)
        self.assertIn('600', mensagem)
        self.assertIn('25 × 40 + 300 + 60 = 1360', mensagem)

    def test_lease_curto_da_flag_timeout_prevalece_sobre_o_settings(self):
        with override_settings(**CONFIG_OK):  # settings com 3600 s
            with self.assertRaises(CommandError):
                call_command('process_ocr_queue', '--once', '--timeout=600')

    def test_lease_suficiente_com_backend_real_executa_sem_levantar(self):
        with override_settings(**CONFIG_OK):
            call_command('process_ocr_queue', '--once')  # fila vazia, só roda

    def test_stub_backend_nao_valida_lease_curto(self):
        with override_settings(**CONFIG_STUB_TUDO_ERRADO):
            call_command('process_ocr_queue', '--once')  # não levanta
