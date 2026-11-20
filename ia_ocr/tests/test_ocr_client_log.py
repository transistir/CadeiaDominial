"""``LogDeCabecalhosTests`` — migração VERBATIM de
``ia_ocr/tests/test_ocr_client.py`` (Etapa 13 do plano de 400 linhas).
"""

import logging
import tempfile
import time
from pathlib import Path

from ia_ocr.ocr_client import OcrServiceClient
from ia_ocr.tests.stub_servico import StubServicoOcr


class LogDeCabecalhosTestsParte:
    """Evidência de aceite (2): nomes dos três cabeçalhos aplicados por
    requisição — a primeira em INFO, as seguintes em DEBUG — sem nunca
    logar valores (token, credenciais), nome de arquivo ou texto do
    documento.
    """

    VALORES_SECRETO = (
        'token-interno-secreto',
        'access-id-secreto',
        'access-secret-secreto',
    )

    def setUp(self):
        self.diretorio = tempfile.TemporaryDirectory()
        self.addCleanup(self.diretorio.cleanup)
        self.pdf = Path(self.diretorio.name) / 'nome-sensivel-do-documento.pdf'
        self.conteudo_pdf = (
            b'%PDF-1.4\nconteudo sintetico do documento\n%%EOF\n'
        )
        self.pdf.write_bytes(self.conteudo_pdf)

    def _stub(self, respostas):
        stub = StubServicoOcr(respostas).iniciar()
        self.addCleanup(stub.encerrar)
        return stub

    def _cliente(self, stub, **kw):
        return OcrServiceClient(
            stub.base_url,
            self.VALORES_SECRETO[0],
            self.VALORES_SECRETO[1],
            self.VALORES_SECRETO[2],
            backoff_base_s=0,
            **kw,
        )

    def _nomes_presentes(self, mensagem):
        for nome in (
            'cf-access-client-id',
            'cf-access-client-secret',
            'x-internal-token',
        ):
            self.assertIn(nome, mensagem)

    def test_primeira_requisicao_da_instancia_loga_os_nomes_em_info(self):
        stub = self._stub([(200, {'job_id': 'job-log', 'status': 'ok'}, {})])
        cliente = self._cliente(stub)

        with self.assertLogs('ia_ocr.ocr_client', level='INFO') as logs:
            cliente.consultar_job('job-log', time.monotonic() + 5)

        self.assertEqual(len(logs.records), 1)
        registro = logs.records[0]
        self.assertEqual(registro.levelno, logging.INFO)
        self._nomes_presentes(registro.getMessage())

    def test_requisicoes_seguintes_logam_os_mesmos_nomes_em_debug(self):
        stub = self._stub([
            (202, {'job_id': 'job-log', 'status': 'queued'}, {}),
            (200, {'job_id': 'job-log', 'status': 'succeeded'}, {}),
        ])
        cliente = self._cliente(stub)

        with self.assertLogs('ia_ocr.ocr_client', level='DEBUG') as logs:
            cliente.enviar_job(
                self.pdf,
                'job-log',
                time.monotonic() + 10,
                dpi=200,
                timeout_seconds=5,
                max_pages=25,
            )
            cliente.consultar_job('job-log', time.monotonic() + 10)

        por_nivel = {nivel: [] for nivel in (logging.INFO, logging.DEBUG)}
        for registro in logs.records:
            por_nivel.setdefault(registro.levelno, []).append(
                registro.getMessage()
            )
        # A primeira requisição é a única em INFO; o poll seguinte, DEBUG.
        self.assertEqual(len(por_nivel[logging.INFO]), 1)
        self.assertEqual(len(por_nivel[logging.DEBUG]), 1)
        self._nomes_presentes(por_nivel[logging.DEBUG][0])

    def test_nenhum_valor_de_credencial_ou_dado_do_documento_no_log(self):
        stub = self._stub([
            (202, {'job_id': 'job-log', 'status': 'queued'}, {}),
            (200, {'job_id': 'job-log', 'status': 'succeeded'}, {}),
        ])
        cliente = self._cliente(stub)

        with self.assertLogs('ia_ocr.ocr_client', level='DEBUG') as logs:
            cliente.enviar_job(
                self.pdf,
                'job-log',
                time.monotonic() + 10,
                dpi=200,
                timeout_seconds=5,
                max_pages=25,
            )
            cliente.consultar_job('job-log', time.monotonic() + 10)

        formatador = logging.Formatter()
        vazamentos = (
            *self.VALORES_SECRETO,
            'nome-sensivel-do-documento.pdf',
            'conteudo sintetico do documento',
        )
        for registro in logs.records:
            formatado = formatador.format(registro)
            for vazamento in vazamentos:
                self.assertNotIn(vazamento, formatado)
