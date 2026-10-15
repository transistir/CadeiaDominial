import tempfile
import time
from pathlib import Path

from django.test import SimpleTestCase

from ia_ocr.ocr_client import OcrServiceClient
from ia_ocr.tests.stub_servico import StubServicoOcr


class OcrServiceClientTests(SimpleTestCase):
    def setUp(self):
        self.diretorio = tempfile.TemporaryDirectory()
        self.addCleanup(self.diretorio.cleanup)
        self.pdf = Path(self.diretorio.name) / 'nome-sensivel-do-documento.pdf'
        self.conteudo_pdf = b'%PDF-1.4\nconteudo de teste\n%%EOF\n'
        self.pdf.write_bytes(self.conteudo_pdf)

    def _stub(self, respostas):
        stub = StubServicoOcr(respostas).iniciar()
        self.addCleanup(stub.encerrar)
        return stub

    def _cliente(self, stub, **kw):
        return OcrServiceClient(
            stub.base_url,
            'token-interno',
            'access-id',
            'access-secret',
            backoff_base_s=0,
            **kw,
        )

    def test_envio_bem_sucedido_monta_multipart_e_retorna_dict(self):
        esperado = {'job_id': 'job-123', 'status': 'queued'}
        stub = self._stub([(202, esperado, {})])

        resultado = self._cliente(stub).enviar_job(
            self.pdf,
            'job-123',
            time.monotonic() + 30,
            dpi=200,
            timeout_seconds=123.9,
            max_pages=31,
        )

        self.assertEqual(resultado, esperado)
        self.assertEqual(len(stub.recebidas), 1)
        recebida = stub.recebidas[0]
        cabecalhos = {k.lower(): v for k, v in recebida['cabecalhos'].items()}
        self.assertEqual(cabecalhos['cf-access-client-id'], 'access-id')
        self.assertEqual(cabecalhos['cf-access-client-secret'], 'access-secret')
        self.assertEqual(cabecalhos['x-internal-token'], 'token-interno')
        self.assertEqual(recebida['metodo'], 'POST')
        self.assertEqual(recebida['caminho'], '/v1/ocr/jobs')
        self.assertEqual(recebida['campos']['job_id'], 'job-123')
        self.assertEqual(recebida['campos']['dpi'], '200')
        self.assertEqual(recebida['campos']['timeout_seconds'], '123')
        self.assertNotIn('.', recebida['campos']['timeout_seconds'])
        self.assertEqual(recebida['campos']['max_pages'], '31')
        self.assertEqual(recebida['campos']['file_filename'], 'documento.pdf')
        self.assertEqual(recebida['arquivo_bytes'], self.conteudo_pdf)

    def test_replay_de_job_concluido_aceita_200_e_estado_original(self):
        estado_original = {
            'job_id': 'job-replay',
            'status': 'succeeded',
            'source': {'sha256': 'abc'},
            'params': {'dpi': 200, 'max_pages': 25},
        }
        stub = self._stub([(200, estado_original, {})])

        resultado = self._cliente(stub).enviar_job(
            self.pdf,
            'job-replay',
            time.monotonic() + 30,
            dpi=600,
            timeout_seconds=50,
            max_pages=1,
        )

        self.assertEqual(resultado, estado_original)
        # O cliente não tenta reconciliar os parâmetros do replay com o estado
        # devolvido pelo serviço; pelo contrato, prevalecem os originais.
        self.assertEqual(resultado['params'], {'dpi': 200, 'max_pages': 25})
        self.assertEqual(stub.recebidas[0]['campos']['dpi'], '600')
        self.assertEqual(stub.recebidas[0]['campos']['max_pages'], '1')

    def test_resposta_perdida_reenvia_mesmo_job_id_sem_duplicar_job(self):
        estado = {'job_id': 'job-perdido', 'status': 'processing'}
        stub = self._stub([(None, b'', {}), (202, estado, {})])

        resultado = self._cliente(stub, max_tentativas=2).enviar_job(
            self.pdf,
            'job-perdido',
            time.monotonic() + 30,
            dpi=200,
            timeout_seconds=120,
            max_pages=25,
        )

        self.assertEqual(resultado, estado)
        self.assertEqual(len(stub.recebidas), 2)
        self.assertEqual(
            [r['campos']['job_id'] for r in stub.recebidas],
            ['job-perdido', 'job-perdido'],
        )
        self.assertEqual(stub.jobs_aceitos, {'job-perdido'})
        self.assertEqual(
            [r['arquivo_bytes'] for r in stub.recebidas],
            [self.conteudo_pdf, self.conteudo_pdf],
        )
