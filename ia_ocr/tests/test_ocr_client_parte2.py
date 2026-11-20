"""Parte 2 de 2 do corpo de ``OcrServiceClientTests`` — migração VERBATIM de
``ia_ocr/tests/test_ocr_client.py`` (Etapa 13 do plano de 400 linhas).

Classe SIMPLES (sem ``SimpleTestCase``); quem coleta é a fachada em
``test_ocr_client.py``. ``setUp``, ``_stub``, ``_cliente``, ``_corpo_erro`` e
``_capturar_erro`` vêm da parte 1 pela MRO da fachada.
"""

import time
from pathlib import Path

from ia_ocr.ocr_client import OcrServiceClient
from ia_ocr.tests.stub_servico import StubServicoOcr


class OcrServiceClientTestsParte2:
    def test_5xx_passageiro_em_get_no_fim_do_orcamento_tenta_de_novo(self):
        """A reserva de retry vale para reenviar job (POST); um GET barato
        tenta até o fim do prazo — um 5xx passageiro no fim do orçamento não
        pode derrubar o job."""
        stub = self._stub(
            [
                (500, self._corpo_erro('INFERENCE_FAILED'), {}),
                (200, {'job_id': 'job-get', 'status': 'succeeded'}, {}),
            ]
        )
        cliente = OcrServiceClient(
            stub.base_url,
            'token-interno',
            'access-id',
            'access-secret',
            max_tentativas=2,
            backoff_base_s=0,
            reserva_retry_s=30,
        )

        resultado = cliente.consultar_job('job-get', time.monotonic() + 10)

        self.assertEqual(resultado['status'], 'succeeded')
        self.assertEqual(len(stub.recebidas), 2)

    def test_reserva_de_retry_segura_o_reenvio_post_ate_o_fim_do_prazo(self):
        """No (re)envio de job a reserva segue valendo: sem orçamento para
        um upload que valha a pena, o job termina QUEUE_FULL em vez de
        queimar o prazo num POST fadado ao 503."""
        stub = self._stub(
            [(503, self._corpo_erro('QUEUE_FULL', 'fila cheia sintética'), {})]
        )
        cliente = OcrServiceClient(
            stub.base_url,
            'token-interno',
            'access-id',
            'access-secret',
            max_tentativas=1,
            backoff_base_s=0,
            reserva_retry_s=30,
        )

        erro = self._capturar_erro(
            lambda: cliente.enviar_job(
                self.pdf,
                'job-post',
                time.monotonic() + 10,
                dpi=200,
                timeout_seconds=5,
                max_pages=25,
            )
        )

        self.assertEqual(erro.codigo, 'QUEUE_FULL')
        self.assertEqual(len(stub.recebidas), 1)

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

    def test_resposta_gotejante_um_byte_por_vez_corta_no_meio_do_bloco(self):
        from ia_ocr.ocr_client import OrcamentoEsgotado

        corpo = {'job_id': 'job-byte', 'status': 'processing', 'padding': 'x' * 150}
        stub = StubServicoOcr(
            [(200, corpo, {})],
            tamanho_chunk_resposta=1,
            pausa_s=0.02,
        ).iniciar()
        self.addCleanup(stub.encerrar)
        prazo_s = 0.3
        inicio = time.monotonic()

        with self.assertRaises(OrcamentoEsgotado):
            self._cliente(stub, timeout_s=1).consultar_job(
                'job-byte', inicio + prazo_s
            )

        self.assertLess(time.monotonic() - inicio, prazo_s + 0.5)
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
