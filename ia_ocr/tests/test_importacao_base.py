"""Testes da importação assistida da revisão finalizada (I-6 / #263).

O serviço grava os atos marcados de uma extração finalizada em lançamentos
do dominial, com savepoint por ato e rollback total ao primeiro erro. Os
payloads são os mesmos sintéticos da revisão (nada de documento real), e a
decisão B (#263-I6-B) está em jogo no caminho feliz: linha ``sugerido`` sem
``requer_revisao`` entra na importação porque a finalização da revisão já é
o aceite humano.
"""

# Etapa 9 (400 linhas): migração verbatim — nenhum teste aqui.

from django.test import (
    TestCase,
)
from django.urls import reverse
from django.utils import timezone
from dominial.models import (
    LancamentoTipo, UserTI,
)
from ia_ocr import services
from ia_ocr.importacao import importar
from ia_ocr.models import CampoSugerido, ExtracaoSugerida, OcrJob, PaginaOcr
from ia_ocr.revisao import (
    desnormalizar,
)
from .factories import criar_documento_digital, criar_usuario
from .payloads_extracao import (
    SCHEMA_VERSION, TEXTO_PAGINA_1, payload_registro,
)


class ImportacaoFixture:
    """Job ``revisado`` com extração finalizada, pronto para importar.

    Mixin (sem ``TestCase``) para a mesma montagem servir à classe de
    concorrência real em PostgreSQL (``TransactionTestCase``).
    """

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

    def _todos_os_atos(self, extracao):
        return [
            f'/acts/{indice}' for indice in range(len(extracao.payload['acts']))
        ]

    def _importar(self, extracao, atos=None, versao=None):
        return importar(
            extracao, self.usuario,
            versao if versao is not None else services.versao_bloco(extracao),
            atos if atos is not None else self._todos_os_atos(extracao),
        )

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

    def _payload_com_numero(self):
        payload = payload_registro(self.job.job_id)
        payload['acts'][0]['numero_lancamento'] = self._campo('R-1', 'R-1/42.718')
        return payload

    def url_lancamento(self, lancamento):
        return reverse('editar_lancamento', kwargs={
            'tis_id': self.imovel.terra_indigena_id_id,
            'imovel_id': self.imovel.pk,
            'lancamento_id': lancamento.pk,
        })


class ImportacaoBase(ImportacaoFixture, TestCase):
    """Job ``revisado`` com extração finalizada, pronto para importar."""


class _DesfazImportacao(Exception):
    """Desfaz, no fim do ``atomic``, a importação que o teste só observa."""


def _post_cadastro_manual(tipo_registro):
    """POST mínimo do cadastro manual: gera o número ``R1 M42``."""
    return {
        'tipo_lancamento': str(tipo_registro.pk),
        'sigla_matricula': 'M42',
        'numero_lancamento_simples': '1',
        'data': '2020-02-15',
        'observacoes': '',
    }


ESPERA_S = 10
BLOQUEIO_S = 1.0
