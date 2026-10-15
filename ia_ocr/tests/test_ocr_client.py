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

    @staticmethod
    def _corpo_erro(codigo, mensagem='falha esperada'):
        return {'ok': False, 'error': {'code': codigo, 'message': mensagem}}

    def _capturar_erro(self, operacao):
        from ia_ocr.backends import OcrBackendError

        with self.assertRaises(OcrBackendError) as contexto:
            operacao()
        return contexto.exception

    def test_queue_full_repete_alem_de_max_tentativas_ate_sucesso(self):
        recusas = [
            (503, self._corpo_erro('QUEUE_FULL'), {}) for _ in range(4)
        ]
        esperado = {'job_id': 'job-fila', 'status': 'processing'}
        stub = self._stub([*recusas, (200, esperado, {})])

        resultado = self._cliente(stub, max_tentativas=2).consultar_job(
            'job-fila', time.monotonic() + 1
        )

        self.assertEqual(resultado, esperado)
        self.assertEqual(len(stub.recebidas), 5)

    def test_429_repete_alem_de_max_tentativas_ate_sucesso(self):
        recusas = [(429, '<html>rate limited</html>', {}) for _ in range(4)]
        esperado = {'job_id': 'job-429', 'status': 'queued'}
        stub = self._stub([*recusas, (200, esperado, {})])

        resultado = self._cliente(stub, max_tentativas=2).consultar_job(
            'job-429', time.monotonic() + 1
        )

        self.assertEqual(resultado, esperado)
        self.assertEqual(len(stub.recebidas), 5)

    def test_queue_full_aplica_backoff_exponencial_com_teto(self):
        from unittest.mock import patch

        recusas = [
            (503, self._corpo_erro('QUEUE_FULL'), {}) for _ in range(3)
        ]
        esperado = {'job_id': 'job-backoff', 'status': 'queued'}
        stub = self._stub([*recusas, (200, esperado, {})])
        cliente = OcrServiceClient(
            stub.base_url,
            'token-interno',
            'access-id',
            'access-secret',
            max_tentativas=1,
            backoff_base_s=0.02,
            backoff_max_s=0.03,
        )

        with patch('ia_ocr.ocr_client.time.sleep') as dormir:
            resultado = cliente.consultar_job(
                'job-backoff', time.monotonic() + 1
            )

        self.assertEqual(resultado, esperado)
        self.assertEqual(
            [chamada.args[0] for chamada in dormir.call_args_list],
            [0.02, 0.03, 0.03],
        )

    def test_queue_full_para_na_reserva_sem_dormir_nem_nova_tentativa(self):
        from unittest.mock import patch
        from ia_ocr.ocr_client import OrcamentoEsgotado

        stub = self._stub([(503, self._corpo_erro('QUEUE_FULL'), {})])
        cliente = OcrServiceClient(
            stub.base_url,
            'token-interno',
            'access-id',
            'access-secret',
            max_tentativas=1,
            backoff_base_s=0.5,
            backoff_max_s=30,
            reserva_retry_s=0.2,
        )
        inicio = time.monotonic()

        with patch('ia_ocr.ocr_client.time.sleep') as dormir:
            with self.assertRaises(OrcamentoEsgotado):
                cliente.consultar_job('job-reserva', inicio + 0.1)

        self.assertLess(time.monotonic() - inicio, 0.15)
        self.assertEqual(len(stub.recebidas), 1)
        dormir.assert_not_called()

    def test_503_unauthorized_json_falha_sem_retry(self):
        stub = self._stub(
            [(503, self._corpo_erro('UNAUTHORIZED', 'token inválido'), {})]
        )

        erro = self._capturar_erro(
            lambda: self._cliente(stub).consultar_job(
                'job-auth-503', time.monotonic() + 1
            )
        )

        self.assertEqual(erro.codigo, 'UNAUTHORIZED')
        self.assertEqual(len(stub.recebidas), 1)

    def test_503_html_cloudflare_mapeia_indisponivel_e_repete(self):
        esperado = {'job_id': 'job-cf', 'status': 'processing'}
        stub = self._stub(
            [
                (
                    503,
                    '<html><title>Cloudflare unavailable</title></html>',
                    {'Content-Type': 'text/html'},
                ),
                (200, esperado, {}),
            ]
        )

        resultado = self._cliente(stub, max_tentativas=2).consultar_job(
            'job-cf', time.monotonic() + 1
        )

        self.assertEqual(resultado, esperado)
        self.assertEqual(len(stub.recebidas), 2)

    def test_401_json_mapeia_unauthorized_sem_retry(self):
        stub = self._stub([(401, self._corpo_erro('UNAUTHORIZED'), {})])

        erro = self._capturar_erro(
            lambda: self._cliente(stub).consultar_job(
                'job-auth-401', time.monotonic() + 1
            )
        )

        self.assertEqual(erro.codigo, 'UNAUTHORIZED')
        self.assertEqual(len(stub.recebidas), 1)

    def test_403_html_mapeia_unauthorized_sem_retry(self):
        stub = self._stub(
            [
                (
                    403,
                    '<html>Cloudflare Access denied</html>',
                    {'Content-Type': 'text/html'},
                )
            ]
        )

        erro = self._capturar_erro(
            lambda: self._cliente(stub).consultar_job(
                'job-auth-403', time.monotonic() + 1
            )
        )

        self.assertEqual(erro.codigo, 'UNAUTHORIZED')
        self.assertEqual(len(stub.recebidas), 1)

    def test_302_nao_segue_redirect_nem_reenvia_tres_cabecalhos_a_isca(self):
        stub = self._stub([])
        location = f'{stub.base_url}/isca-login'
        with stub._lock:
            stub._respostas.extend(
                [
                    (302, '<html>login</html>', {'Location': location}),
                    (200, {'isca': True}, {}),
                ]
            )

        erro = self._capturar_erro(
            lambda: self._cliente(stub).consultar_job(
                'job-redirect', time.monotonic() + 1
            )
        )

        self.assertEqual(erro.codigo, 'UNAUTHORIZED')
        self.assertEqual(
            [recebida['caminho'] for recebida in stub.recebidas],
            ['/v1/ocr/jobs/job-redirect'],
        )
        requisicoes_isca = [
            recebida
            for recebida in stub.recebidas
            if recebida['caminho'] == '/isca-login'
        ]
        self.assertEqual(requisicoes_isca, [])
        for recebida in requisicoes_isca:
            nomes = {nome.lower() for nome in recebida['cabecalhos']}
            self.assertNotIn('cf-access-client-id', nomes)
            self.assertNotIn('cf-access-client-secret', nomes)
            self.assertNotIn('x-internal-token', nomes)

    def test_400_preserva_codigo_invalid_pdf_do_servico(self):
        stub = self._stub([(400, self._corpo_erro('INVALID_PDF'), {})])

        erro = self._capturar_erro(
            lambda: self._cliente(stub).enviar_job(
                self.pdf, 'job-invalido', time.monotonic() + 1
            )
        )

        self.assertEqual(erro.codigo, 'INVALID_PDF')
        self.assertEqual(len(stub.recebidas), 1)

    def test_413_preserva_codigo_file_too_large_do_servico(self):
        stub = self._stub([(413, self._corpo_erro('FILE_TOO_LARGE'), {})])

        erro = self._capturar_erro(
            lambda: self._cliente(stub).enviar_job(
                self.pdf, 'job-grande', time.monotonic() + 1
            )
        )

        self.assertEqual(erro.codigo, 'FILE_TOO_LARGE')
        self.assertEqual(len(stub.recebidas), 1)

    def test_415_preserva_codigo_unsupported_media_type_do_servico(self):
        stub = self._stub(
            [(415, self._corpo_erro('UNSUPPORTED_MEDIA_TYPE'), {})]
        )

        erro = self._capturar_erro(
            lambda: self._cliente(stub).enviar_job(
                self.pdf, 'job-midia', time.monotonic() + 1
            )
        )

        self.assertEqual(erro.codigo, 'UNSUPPORTED_MEDIA_TYPE')
        self.assertEqual(len(stub.recebidas), 1)

    def test_404_em_consulta_mapeia_job_not_found_sem_retry(self):
        stub = self._stub([(404, self._corpo_erro('JOB_NOT_FOUND'), {})])

        erro = self._capturar_erro(
            lambda: self._cliente(stub, max_tentativas=4).consultar_job(
                'job-ausente', time.monotonic() + 1
            )
        )

        self.assertEqual(erro.codigo, 'JOB_NOT_FOUND')
        self.assertEqual(len(stub.recebidas), 1)

    def test_404_em_resultado_mapeia_job_not_found_sem_retry(self):
        stub = self._stub([(404, self._corpo_erro('JOB_NOT_FOUND'), {})])

        erro = self._capturar_erro(
            lambda: self._cliente(stub, max_tentativas=4).obter_resultado(
                'job-ausente', time.monotonic() + 1
            )
        )

        self.assertEqual(erro.codigo, 'JOB_NOT_FOUND')
        self.assertEqual(len(stub.recebidas), 1)

    def test_409_em_resultado_retorna_job_status(self):
        estado = {'job_id': 'job-processando', 'status': 'processing'}
        stub = self._stub([(409, estado, {})])

        resultado = self._cliente(stub).obter_resultado(
            'job-processando', time.monotonic() + 1
        )

        self.assertEqual(resultado, estado)
        self.assertEqual(len(stub.recebidas), 1)

    def test_409_em_envio_mapeia_job_id_conflict_sem_retry(self):
        stub = self._stub([(409, self._corpo_erro('JOB_ID_CONFLICT'), {})])

        erro = self._capturar_erro(
            lambda: self._cliente(stub, max_tentativas=4).enviar_job(
                self.pdf, 'job-conflito', time.monotonic() + 1
            )
        )

        self.assertEqual(erro.codigo, 'JOB_ID_CONFLICT')
        self.assertEqual(len(stub.recebidas), 1)

    def test_resposta_gotejante_estoura_dentro_do_prazo_real(self):
        from ia_ocr.ocr_client import OrcamentoEsgotado

        corpo_grande = {
            'job_id': 'job-gotejante',
            'status': 'processing',
            'padding': 'x' * 70_000,
        }
        stub = StubServicoOcr(
            [(200, corpo_grande, {})],
            tamanho_chunk_resposta=4 * 1024,
            pausa_s=0.015,
        ).iniciar()
        self.addCleanup(stub.encerrar)
        prazo_s = 0.07
        inicio = time.monotonic()

        with self.assertRaises(OrcamentoEsgotado):
            self._cliente(stub, timeout_s=1).consultar_job(
                'job-gotejante', inicio + prazo_s
            )

        self.assertLess(time.monotonic() - inicio, prazo_s + 0.08)
        self.assertEqual(len(stub.recebidas), 1)

    def test_upload_e_interrompido_antes_de_enviar_todos_os_bytes(self):
        from ia_ocr.ocr_client import OrcamentoEsgotado

        pdf_grande = Path(self.diretorio.name) / 'grande.pdf'
        conteudo = b'%PDF-1.4\n' + (b'x' * (5 * 1024 * 1024))
        pdf_grande.write_bytes(conteudo)
        stub = self._stub([(202, {'job_id': 'job-upload', 'status': 'queued'}, {})])
        stub.tamanho_chunk_upload = 16 * 1024
        stub.pausa_upload_s = 0.003
        prazo_s = 0.05
        inicio = time.monotonic()

        with self.assertRaises(OrcamentoEsgotado):
            self._cliente(stub, timeout_s=1, max_tentativas=3).enviar_job(
                pdf_grande, 'job-upload', inicio + prazo_s
            )

        limite_espera = time.monotonic() + 0.3
        while not stub.recebidas and time.monotonic() < limite_espera:
            time.sleep(0.005)
        self.assertEqual(len(stub.recebidas), 1)
        recebida = stub.recebidas[0]
        self.assertFalse(recebida['upload_completo'])
        self.assertGreater(len(recebida['corpo_bruto']), 0)
        self.assertLess(len(recebida['corpo_bruto']), len(conteudo))
        self.assertLess(time.monotonic() - inicio, prazo_s + 0.25)

    def test_orcamento_esgotado_nao_herda_erros_convertidos_em_retry(self):
        import requests
        from ia_ocr.ocr_client import OrcamentoEsgotado

        self.assertFalse(issubclass(OrcamentoEsgotado, OSError))
        self.assertFalse(
            issubclass(OrcamentoEsgotado, requests.RequestException)
        )
