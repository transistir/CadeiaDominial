"""PII: confirmar/editar/bulk/transição do texto não vazam texto de documento,
nome de arquivo nem usuário para os logs (issue #261 / I-4).

Os logs de ia_ocr carregam só job_id, número da página e estado — o mesmo
critério de ia_ocr.services (ver test_pii.py).
"""

import logging

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from dominial.models import UserTI
from ia_ocr import services

from .factories import criar_documento_digital, criar_job_concluido

NOME_SENSIVEL = 'matricula-sensivel-261.pdf'
MARCADOR_TEXTO = 'CPF-SINTETICO-261.262.263-64'
MARCADOR_USUARIO = 'usuario-sensivel-261'


class TextoSemPiiEmLogsTest(TestCase):
    def setUp(self):
        self.usuario = User.objects.create_user(
            username=MARCADOR_USUARIO, password='senha-261'
        )
        self.arquivo = criar_documento_digital(
            upload_por=self.usuario, nome=NOME_SENSIVEL
        )
        UserTI.objects.create(
            user=self.usuario, tis=self.arquivo.documento.imovel.terra_indigena_id
        )
        self.job = criar_job_concluido(
            self.arquivo, textos=[MARCADOR_TEXTO, f'{MARCADOR_TEXTO} segunda']
        )

    def _kwargs(self, **extra):
        documento = self.arquivo.documento
        return {
            'tis_id': documento.imovel.terra_indigena_id.pk,
            'imovel_id': documento.imovel.pk,
            'documento_id': documento.pk,
            'job_id': self.job.job_id,
            **extra,
        }

    def _afirmar_sem_pii(self, saida):
        for sensivel in (MARCADOR_TEXTO, NOME_SENSIVEL, MARCADOR_USUARIO):
            self.assertNotIn(sensivel, saida, f'{sensivel!r} vazou para o log')

    def test_servicos_nao_logam_texto_arquivo_nem_usuario(self):
        with self.assertLogs('ia_ocr', level=logging.DEBUG) as capturado:
            services.confirmar_pagina(
                self.job, 1, self.usuario, texto=f'{MARCADOR_TEXTO} corrigido'
            )
            services.editar_pagina(self.job, 2, f'{MARCADOR_TEXTO} mexida')
            services.confirmar_pagina(self.job, 2, self.usuario)
            services.confirmar_texto(self.job, self.usuario)

        saida = '\n'.join(capturado.output)
        self._afirmar_sem_pii(saida)
        self.assertIn(str(self.job.job_id), saida)

    def test_bulk_nao_loga_texto_arquivo_nem_usuario(self):
        with self.assertLogs('ia_ocr', level=logging.DEBUG) as capturado:
            services.confirmar_todas_paginas(self.job, self.usuario)

        saida = '\n'.join(capturado.output)
        self._afirmar_sem_pii(saida)
        self.assertIn('paginas=2', saida)

    def test_views_nao_logam_texto_arquivo_nem_usuario(self):
        self.client.force_login(self.usuario)
        with self.assertLogs('ia_ocr', level=logging.DEBUG) as capturado:
            self.client.post(
                reverse('confirmar_pagina_ocr', kwargs=self._kwargs(numero=1)),
                {'texto': f'{MARCADOR_TEXTO} pela tela'},
            )
            self.client.post(
                reverse('editar_pagina_ocr', kwargs=self._kwargs(numero=2)),
                {'texto': f'{MARCADOR_TEXTO} rascunho'},
            )
            self.client.post(reverse('reprocessar_job_ocr', kwargs=self._kwargs()))

        saida = '\n'.join(capturado.output)
        self._afirmar_sem_pii(saida)
