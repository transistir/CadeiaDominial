"""Fixture compartilhada dos testes que montam job + extração do OCR.

O motor da importação em lote (I-6/#263) foi aposentado na fase 4 da
#341; a montagem continua servindo à família
``test_revisao_formulario_prefill_*`` (pré-preenchimento do formulário)
e aos testes do fallback de rótulo (``test_rotulos_importacao_*``).
"""

from django.utils import timezone
from dominial.models import (
    LancamentoTipo, UserTI,
)
from ia_ocr.models import CampoSugerido, ExtracaoSugerida, OcrJob, PaginaOcr
from ia_ocr.revisao import (
    desnormalizar,
)
from .factories import criar_documento_digital, criar_usuario
from .payloads_extracao import (
    SCHEMA_VERSION, TEXTO_PAGINA_1, payload_registro,
)


class ImportacaoFixture:
    """Job ``revisado`` com extração pronta (fixture, sem testes)."""

    def setUp(self):
        self.usuario = criar_usuario()
        self.arquivo = criar_documento_digital(upload_por=self.usuario)
        UserTI.objects.create(
            user=self.usuario,
            tis=self.arquivo.documento.imovel.terra_indigena_id,
        )
        self.documento = self.arquivo.documento
        self.imovel = self.documento.imovel
        self.job = OcrJob.objects.create(
            documento_digital=self.arquivo, status='revisado',
        )
        self.pagina = PaginaOcr.objects.create(
            ocr_job=self.job, numero_pagina=1, texto_ocr=TEXTO_PAGINA_1,
        )
        self.tipo_registro = LancamentoTipo.objects.create(tipo='registro')

    @staticmethod
    def _campo(valor, trecho=None):
        campo = {
            'raw': valor, 'normalized': valor, 'confianca': 0.95,
            'requer_revisao': False,
        }
        if trecho:
            campo['evidencia'] = {'pagina': 1, 'trecho': trecho}
        return campo

    def _extracao(self, payload):
        extracao = ExtracaoSugerida.objects.create(
            ocr_job=self.job, schema_version=SCHEMA_VERSION,
            payload=payload, payload_servico=payload, provider='local-model',
        )
        linhas = desnormalizar(extracao, payload, [self.pagina])
        for linha in linhas:
            if linha.tipo_valor in ('parte', 'cartorio'):
                linha.criar_novo = True
        CampoSugerido.objects.bulk_create(linhas)
        extracao.finalizada_em = timezone.now()
        extracao.save(update_fields=['finalizada_em'])
        return extracao

    def _payload_origem(self):
        payload = payload_registro(self.job.job_id)
        payload['acts'][0]['origem'] = {
            'tipo_documento': self._campo('transcricao', 'MATRÍCULA Nº 42.718'),
            'numero': self._campo('T366', '42.718'),
            'cartorio': self._campo('CRI de Origem', 'CRI de Guaíra'),
            'livro': self._campo('2', 'Livro 2-RG'),
            'folha': self._campo('123', 'Folha 087'),
        }
        return payload
