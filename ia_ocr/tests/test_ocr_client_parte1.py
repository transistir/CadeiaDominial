"""Parte 1 de 2 do corpo de ``OcrServiceClientTests`` — migração VERBATIM de
``ia_ocr/tests/test_ocr_client.py`` (Etapa 13 do plano de 400 linhas).

Classe SIMPLES (sem ``SimpleTestCase``); quem coleta é a fachada em
``test_ocr_client.py``. Os stubs de transporte ``_RelogioFalso``,
``_CorpoFalso``, ``_RespostaFalsa`` e ``_SessaoFalsa`` só são usados aqui.
"""

import tempfile
import time
from pathlib import Path

from ia_ocr.ocr_client import OcrServiceClient
from ia_ocr.tests.stub_servico import StubServicoOcr


class _RelogioFalso:
    """Substitui o módulo ``time`` do cliente: só avança quando ele dorme."""

    def __init__(self):
        self.agora = 1000.0
        self.dormido = 0.0

    def monotonic(self):
        return self.agora

    def sleep(self, segundos):
        self.agora += segundos
        self.dormido += segundos


class _CorpoFalso:
    def __init__(self, dados):
        self._dados = dados

    def read1(self, amt=None, decode_content=None):
        dados, self._dados = self._dados, b''
        return dados


class _RespostaFalsa:
    def __init__(self, status):
        self.status_code = status
        self.raw = _CorpoFalso(b'<html>rate limited</html>')

    def close(self):
        pass


class _SessaoFalsa:
    def __init__(self, status_codes):
        self._status_codes = list(status_codes)
        self.chamadas = 0

    def request(self, metodo, url, **kw):
        self.chamadas += 1
        return _RespostaFalsa(self._status_codes.pop(0))


class OcrServiceClientTestsParte1:
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

    def test_queue_full_no_fim_do_orcamento_termina_queue_full_sem_dormir(self):
        """QUEUE_FULL/429 que esgota o orçamento termina com o código
        QUEUE_FULL (não vira WORKER_TIMEOUT no backend) — e sem dormir nem
        gastar uma nova tentativa."""
        from unittest.mock import patch

        from ia_ocr.backends import OcrBackendError

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
            with self.assertRaises(OcrBackendError) as contexto:
                cliente.consultar_job('job-reserva', inicio + 0.1)

        self.assertEqual(contexto.exception.codigo, 'QUEUE_FULL')
        self.assertLess(time.monotonic() - inicio, 0.15)
        self.assertEqual(len(stub.recebidas), 1)
        dormir.assert_not_called()

    def test_429_no_fim_do_orcamento_termina_queue_full(self):
        from unittest.mock import patch

        relogio = _RelogioFalso()
        sessao = _SessaoFalsa([429, 429])
        cliente = OcrServiceClient(
            'http://ocr.invalido',
            'token-interno',
            'access-id',
            'access-secret',
            max_tentativas=1,
            backoff_base_s=0.08,
            backoff_max_s=0.08,
            sessao=sessao,
        )

        with patch('ia_ocr.ocr_client.time', relogio):
            erro = self._capturar_erro(
                lambda: cliente.consultar_job(
                    'job-429-fim', relogio.monotonic() + 0.15
                )
            )

        self.assertEqual(erro.codigo, 'QUEUE_FULL')
        self.assertEqual(sessao.chamadas, 2)
        self.assertLessEqual(relogio.dormido, 0.15)
