"""Corpo multipart reabrível para o upload do PDF, lido em blocos."""

from __future__ import annotations

import os

from .. import ocr_client  # alvo de patch: ia_ocr.ocr_client.time
from ..backends import OrcamentoEsgotado


class _MultipartEncoder:
    """Corpo multipart reabrível, lido em blocos sob o mesmo prazo.

    ``_conferir_prazo`` lê ``ocr_client.time`` via pacote a cada chamada —
    o mesmo namespace alvo de ``patch('ia_ocr.ocr_client.time', relogio)``
    (que no monólito alcançava este módulo e segue alcançando; ver
    ``cliente.py``/``http.py``).
    """

    TAMANHO_CHUNK = 64 * 1024

    def __init__(self, caminho_pdf, campos, boundary, prazo):
        self.caminho_pdf = os.fspath(caminho_pdf)
        self.prazo = prazo
        self.boundary = boundary
        self._preambulo = self._montar_preambulo(campos)
        self._epilogo = f'\r\n--{boundary}--\r\n'.encode('ascii')
        self._tamanho_arquivo = os.path.getsize(self.caminho_pdf)
        self._arquivo = None
        self._pos_preambulo = 0
        self._pos_epilogo = 0
        self._arquivo_concluido = False

    def __len__(self):
        return len(self._preambulo) + self._tamanho_arquivo + len(self._epilogo)

    def reset(self):
        self.close()
        self._pos_preambulo = 0
        self._pos_epilogo = 0
        self._arquivo_concluido = False

    def close(self):
        if self._arquivo is not None:
            self._arquivo.close()
            self._arquivo = None

    def read(self, amt=None):
        self._conferir_prazo()
        limite = amt if amt is not None and amt >= 0 else self.TAMANHO_CHUNK
        if limite == 0:
            return b''

        saida = bytearray()
        while len(saida) < limite:
            restante = limite - len(saida)
            if self._pos_preambulo < len(self._preambulo):
                fim = min(len(self._preambulo), self._pos_preambulo + restante)
                saida.extend(self._preambulo[self._pos_preambulo : fim])
                self._pos_preambulo = fim
                continue

            if not self._arquivo_concluido:
                self._conferir_prazo()
                if self._arquivo is None:
                    self._arquivo = open(self.caminho_pdf, 'rb')
                dados = self._arquivo.read(min(restante, self.TAMANHO_CHUNK))
                self._conferir_prazo()
                if dados:
                    saida.extend(dados)
                    continue
                self.close()
                self._arquivo_concluido = True
                continue

            if self._pos_epilogo < len(self._epilogo):
                fim = min(len(self._epilogo), self._pos_epilogo + restante)
                saida.extend(self._epilogo[self._pos_epilogo : fim])
                self._pos_epilogo = fim
                continue
            break
        return bytes(saida)

    def _montar_preambulo(self, campos):
        partes = []
        for nome, valor in campos:
            partes.extend(
                [
                    f'--{self.boundary}\r\n',
                    f'Content-Disposition: form-data; name="{nome}"\r\n\r\n',
                    f'{valor}\r\n',
                ]
            )
        partes.extend(
            [
                f'--{self.boundary}\r\n',
                'Content-Disposition: form-data; name="file"; '
                'filename="documento.pdf"\r\n',
                'Content-Type: application/pdf\r\n\r\n',
            ]
        )
        return ''.join(partes).encode('utf-8')

    def _conferir_prazo(self):
        if ocr_client.time.monotonic() >= self.prazo:
            raise OrcamentoEsgotado('Prazo do job esgotado durante o upload.')
