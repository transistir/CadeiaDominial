import json
import threading
import time

from django.test import SimpleTestCase, override_settings

from ia_ocr.extracao_backends import (
    ExtracaoBackendError,
    StubExtracaoBackend,
    get_extracao_backend,
)
from ia_ocr.ocr_client import (
    OcrServiceClient,
    _ClienteHttpComPrazo,
)
from ia_ocr.tests.stub_servico import StubServicoOcr
from ia_ocr.tests.stub_servico_extracao import StubServicoExtracao


REQUISICAO_PADRAO = {
    'schema': 'umbelino-extracao-matricula-v1',
    'texto_confirmado': 'MATE 1\n NORTE 2\n Computada a fileira dos lidos.',
    'texto_confirmado_em': '2024-05-01T10:00:00',
    'contexto': {'utente_id': 7, 'varanda': 'matrizes'},
}


class ContratoBaseClienteHttpTests(SimpleTestCase):
    def test_base_sem_limite_de_classe(self):
        """A base nunca define MAX_BYTES_RESPOSTA como atributo de classe:
        cada cliente lê o próprio limite (isolado por instância)."""
        self.assertFalse(hasattr(_ClienteHttpComPrazo, 'MAX_BYTES_RESPOSTA'))


class CaminhoExtracaoTests(SimpleTestCase):
    def test_caminho_fixado_em_v1_extract(self):
        """Contrato A3 v1.1 (commit 39161ed do serviço de OCR): o POST de
        extração vai em /v1/extract — e não no caminho antigo por matrícula."""
        from ia_ocr.extracao_client import CAMINHO_EXTRACAO

        self.assertEqual(CAMINHO_EXTRACAO, '/v1/extract')


class _RespostaFechavel:
    """Resposta falsa de sessão intermediária que conta os closes."""

    def __init__(self, resposta):
        self._resposta = resposta

    def __getattr__(self, nome):
        return getattr(self._resposta, nome)

    def close(self):
        self.fechada = True
        return self._resposta.close()


class _SessaoEspiaClose:
    """Delega para a sessão real do prazo e anota o close de cada resposta."""

    def __init__(self, real):
        self._real = real
        self.respostas = []

    def request(self, metodo, url, **kw):
        resposta = _RespostaFechavel(self._real.request(metodo, url, **kw))
        resposta.fechada = False
        self.respostas.append(resposta)
        return resposta


class ExtracaoServiceClientTests(SimpleTestCase):
    def _stub(self, *args, **kw):
        stub = StubServicoExtracao(*args, **kw).iniciar()
        self.addCleanup(stub.encerrar)
        return stub

    def _cliente(self, stub):
        from ia_ocr.extracao_client import ExtracaoServiceClient

        return ExtracaoServiceClient(
            stub.base_url, 'token-interno', 'access-id', 'access-secret'
        )

    def _capturar_erro(self, acao):
        try:
            acao()
        except ExtracaoBackendError as excecao:
            return excecao
        raise AssertionError('esperava ExtracaoBackendError')

    def test_envia_texto_confirmado_schema_contexto(self):
        from ia_ocr.extracao_client import CAMINHO_EXTRACAO

        stub = self._stub()
        cliente = self._cliente(stub)

        payload = cliente.extrair(dict(REQUISICAO_PADRAO))

        self.assertEqual(payload, {'meta': {}, 'acts': []})
        self.assertEqual(len(stub.recebidas), 1)
        recebida = stub.recebidas[0]
        self.assertEqual(recebida['metodo'], 'POST')
        self.assertEqual(recebida['caminho'], CAMINHO_EXTRACAO)
        self.assertEqual(
            json.loads(recebida['corpo']), dict(REQUISICAO_PADRAO)
        )

    def test_cabecalhos_auth(self):
        stub = self._stub()
        self._cliente(stub).extrair(dict(REQUISICAO_PADRAO))

        cabecalhos = stub.recebidas[0]['cabecalhos']
        self.assertEqual(cabecalhos.get('CF-Access-Client-Id'), 'access-id')
        self.assertEqual(
            cabecalhos.get('CF-Access-Client-Secret'), 'access-secret'
        )
        self.assertEqual(cabecalhos.get('X-Internal-Token'), 'token-interno')

    def test_post_unico_em_500_e_em_429(self):
        stub = self._stub('500')
        erro = self._capturar_erro(
            lambda: self._cliente(stub).extrair(dict(REQUISICAO_PADRAO))
        )
        self.assertEqual(erro.codigo, 'EXTRACAO_INDISPONIVEL')
        self.assertEqual(len(stub.recebidas), 1)

        stub429 = self._stub('429')
        erro = self._capturar_erro(
            lambda: self._cliente(stub429).extrair(dict(REQUISICAO_PADRAO))
        )
        self.assertEqual(erro.codigo, 'EXTRACAO_INDISPONIVEL')
        self.assertEqual(len(stub429.recebidas), 1)

    def test_redirect_nao_seguido_e_sem_credencial(self):
        stub = self._stub('302')

        erro = self._capturar_erro(
            lambda: self._cliente(stub).extrair(dict(REQUISICAO_PADRAO))
        )

        self.assertEqual(erro.codigo, 'NAO_AUTORIZADO')
        self.assertEqual(stub.acessos_isca, 0)
        self.assertEqual(len(stub.recebidas), 1)

    def test_gotejante_aborta_no_prazo_absoluto(self):
        stub = self._stub('gotejante')

        inicio = time.monotonic()
        with override_settings(EXTRACAO_HTTP_TIMEOUT_SECONDS=0.3):
            erro = self._capturar_erro(
                lambda: self._cliente(stub).extrair(dict(REQUISICAO_PADRAO))
            )

        self.assertEqual(erro.codigo, 'PRAZO_ESGOTADO')
        self.assertLess(time.monotonic() - inicio, 0.3 + 1)
        self.assertEqual(len(stub.recebidas), 1)

    def test_resposta_acima_do_limite(self):
        stub = self._stub('grande')

        with override_settings(EXTRACAO_MAX_BYTES_RESPOSTA=1024):
            erro = self._capturar_erro(
                lambda: self._cliente(stub).extrair(dict(REQUISICAO_PADRAO))
            )

        self.assertEqual(erro.codigo, 'RESPOSTA_GRANDE_DEMAIS')

    def test_requisicao_acima_do_limite_sem_rede(self):
        # Porta fechada: qualquer tentativa de rede daria EXTRACAO_INDISPONIVEL.
        classe = self.modo_ok_com_porta_fechada
        requisicao = dict(REQUISICAO_PADRAO, texto_confirmado='x' * 4096)

        with override_settings(EXTRACAO_MAX_BYTES_REQUISICAO=1024):
            erro = self._capturar_erro(lambda: classe().extrair(requisicao))

        self.assertEqual(erro.codigo, 'ENTRADA_GRANDE_DEMAIS')

        stub = self._stub('ok')
        with override_settings(EXTRACAO_MAX_BYTES_REQUISICAO=1024):
            erro = self._capturar_erro(
                lambda: self._cliente(stub).extrair(requisicao)
            )
        self.assertEqual(erro.codigo, 'ENTRADA_GRANDE_DEMAIS')
        self.assertEqual(stub.recebidas, [])

    def _base_url_porta_fechada(self):
        # 127.0.0.1:1 — serviço de teste, nenhum process ouve ele.
        return 'http://127.0.0.1:1'

    def modo_ok_com_porta_fechada(self):
        from ia_ocr.extracao_client import ExtracaoServiceClient

        return ExtracaoServiceClient(
            self._base_url_porta_fechada(),
            'token-interno',
            'access-id',
            'access-secret',
        )

    def test_nao_json(self):
        stub = self._stub('nao_json')

        erro = self._capturar_erro(
            lambda: self._cliente(stub).extrair(dict(REQUISICAO_PADRAO))
        )

        self.assertEqual(erro.codigo, 'RESPOSTA_INVALIDA')

    def test_resposta_fechada(self):
        stub = self._stub('ok')
        cliente = self._cliente(stub)
        original = cliente.sessao
        espia = _SessaoEspiaClose(original)
        cliente.sessao = espia

        cliente.extrair(dict(REQUISICAO_PADRAO))

        self.assertEqual(len(espia.respostas), 1)
        self.assertTrue(espia.respostas[0].fechada)

    def test_falha_de_transporte_uma_tentativa(self):
        stub = self._stub('reset')

        erro = self._capturar_erro(
            lambda: self._cliente(stub).extrair(dict(REQUISICAO_PADRAO))
        )

        self.assertEqual(erro.codigo, 'EXTRACAO_INDISPONIVEL')
        self.assertEqual(len(stub.recebidas), 1)

    def test_limites_de_resposta_isolados(self):
        MEIO_MIB = 1024 * 1024
        corpo_grande = '{"padding": "%s"}' % ('x' * (6 * MEIO_MIB))

        def _chamar_ocr_aceita():
            stub_ocr = StubServicoOcr(
                [
                    (200, {'job_id': 'job-grande-aceito', 'status': 'succeeded', 'padding': 'x' * (6 * MEIO_MIB)}, {})
                ],
                tamanho_chunk_resposta=256 * 1024,
            ).iniciar()
            self.addCleanup(stub_ocr.encerrar)
            cliente = OcrServiceClient(
                stub_ocr.base_url,
                'token-interno',
                'access-id',
                'access-secret',
                backoff_base_s=0,
            )
            resultado = cliente.consultar_job(
                'job-grande-aceito', time.monotonic() + 10
            )
            self.assertEqual(len(resultado['padding']), 6 * MEIO_MIB)

        def _chamar_extracao_recusa():
            stub_extracao = StubServicoExtracao(
                'grande', bytes_corpo=len(corpo_grande)
            ).iniciar()
            self.addCleanup(stub_extracao.encerrar)
            cliente = self._cliente_custom(stub_extracao.base_url)
            erro = self._capturar_erro(
                lambda: cliente.extrair(dict(REQUISICAO_PADRAO))
            )
            self.assertEqual(erro.codigo, 'RESPOSTA_GRANDE_DEMAIS')

        from ia_ocr.extracao_client import ExtracaoServiceClient

        _chamar_ocr_aceita()
        _chamar_extracao_recusa()

        _chamar_extracao_recusa()
        _chamar_ocr_aceita()

    def _cliente_custom(self, base_url):
        from ia_ocr.extracao_client import ExtracaoServiceClient

        return ExtracaoServiceClient(
            base_url, 'token-interno', 'access-id', 'access-secret'
        )

    def test_prazo_esgotado_codigo_estavel(self):
        """Servidor culpado (aceita e trava sem bytes): o prazo absoluto
        corta com o código estável PRAZO_ESGOTADO, e não com transporte."""
        stub = self._stub('bloqueante')
        resultado = {}

        def _extrair():
            with override_settings(EXTRACAO_HTTP_TIMEOUT_SECONDS=0.3):
                resultado['erro'] = self._capturar_erro(
                    lambda: self._cliente(stub).extrair(dict(REQUISICAO_PADRAO))
                )

        thread = threading.Thread(target=_extrair, daemon=True)
        thread.start()
        thread.join(timeout=10)
        stub.evento_liberar.set()

        self.assertEqual(resultado['erro'].codigo, 'PRAZO_ESGOTADO')


class BackendExtracaoTests(SimpleTestCase):
    def test_stub_padrao_falha_estavel(self):
        backend = get_extracao_backend()
        self.assertIsInstance(backend, StubExtracaoBackend)
        with self.assertRaises(ExtracaoBackendError) as contexto:
            backend.extrair(dict(REQUISICAO_PADRAO))
        self.assertEqual(contexto.exception.codigo, 'EXTRACAO_NAO_IMPLEMENTADA')
