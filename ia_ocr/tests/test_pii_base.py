"""Stubs de backend e apoio dos testes de PII, migrados verbatim."""

import logging

from ia_ocr.backends import OcrBackend, OcrBackendError, ResultadoOcr

NOME_SENSIVEL = 'matricula-sensivel-999.pdf'
MARCADOR_PII = 'CPF-SINTETICO-999.888.777-66'
MARCADOR_CODIGO = 'CPF_SINTETICO_99988877766'
MARCADOR_CHAVE_TIMING = 'cpf_sintetico_99988877766'


def _resultado_com_timings(timings_ms):
    return ResultadoOcr(
        paginas=[{'numero_pagina': 1, 'texto': 'sintético', 'blocos': None}],
        sha256_pdf='1' * 64,
        page_count=1,
        timings_ms=timings_ms,
        origem='ocr',
    )


class BackendTimingComChavePii(OcrBackend):
    def processar(self, job):
        return _resultado_com_timings({MARCADOR_CHAVE_TIMING: 42, 'total': 10})


class BackendTimingComChaveDesconhecida(OcrBackend):
    def processar(self, job):
        return _resultado_com_timings({'stage_ms': 7})


class BackendTimingsContratuais(OcrBackend):
    def processar(self, job):
        return _resultado_com_timings({
            'download_and_validation': 10,
            'inference': 20,
            'total': 30,
        })


class BackendTimingComValorTextual(OcrBackend):
    def processar(self, job):
        return _resultado_com_timings({'total': MARCADOR_PII})


class BackendMensagemComPii(OcrBackend):
    def processar(self, job):
        raise OcrBackendError('SERVICE_UNAVAILABLE', MARCADOR_PII)


class BackendCodigoForjadoComPii(OcrBackend):
    def processar(self, job):
        raise OcrBackendError(MARCADOR_CODIGO, MARCADOR_PII)


class BackendCodigoContratual(OcrBackend):
    def processar(self, job):
        raise OcrBackendError('TOO_MANY_PAGES', MARCADOR_PII)


class BackendExcecaoInesperada(OcrBackend):
    def processar(self, job):
        raise RuntimeError(MARCADOR_PII)


class _CapturadorDeLogs(logging.Handler):
    def __init__(self):
        super().__init__(level=logging.DEBUG)
        self.records = []

    def emit(self, record):
        self.records.append(record)
