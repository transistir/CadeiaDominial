"""Endpoints JSON de jobs de OCR (issue #260 / I-3, fatia 1 — sem UI).

POST  .../arquivo/<id>/ocr-jobs/           → cria e enfileira job (201/400/409)
GET   .../arquivo/<id>/ocr-jobs/<uuid>/status/ → estado + progresso + falha

Permissões: exatamente a política do upload existente (login_required +
hierarquia TI→Imóvel→Documento). Fora do escopo do usuário → 404, padrão
do projeto (guard de posse, ver test_segregacao_usuario).
"""

import uuid

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from ia_ocr import estados, services
from ia_ocr.models import OcrJob

from .factories import criar_documento_digital


class OcrJobsEndpointsTestCase(TestCase):
    """Cenário: dono atribuído à TI do documento, intruso sem atribuição."""

    @classmethod
    def setUpTestData(cls):
        cls.superuser = User.objects.create_superuser(
            username='super', password='senha-super', email='super@example.com'
        )
        cls.dono = User.objects.create_user(username='dono', password='senha-dono')
        cls.sem_acesso = User.objects.create_user(username='zeca', password='senha-zeca')

        cls.arquivo = criar_documento_digital(upload_por=cls.dono)
        cls.imovel = cls.arquivo.documento.imovel
        cls.ti = cls.imovel.terra_indigena_id
        cls.documento = cls.arquivo.documento

        from dominial.models import UserTI
        UserTI.objects.create(user=cls.dono, tis=cls.ti)

    def url_criar(self):
        return reverse('criar_job_ocr', kwargs={
            'tis_id': self.ti.pk,
            'imovel_id': self.imovel.pk,
            'documento_id': self.documento.pk,
            'arquivo_id': self.arquivo.pk,
        })

    def url_status(self, job_id):
        return reverse('status_job_ocr', kwargs={
            'tis_id': self.ti.pk,
            'imovel_id': self.imovel.pk,
            'documento_id': self.documento.pk,
            'arquivo_id': self.arquivo.pk,
            'job_id': job_id,
        })

    # --- POST .../ocr-jobs/ -------------------------------------------------

    def test_criar_job_com_permissao_cria_e_enfileira(self):
        self.client.force_login(self.dono)

        resposta = self.client.post(self.url_criar())

        self.assertEqual(resposta.status_code, 201)
        corpo = resposta.json()
        job = OcrJob.objects.get(job_id=corpo['job_id'])
        self.assertEqual(job.status, estados.PENDENTE)
        self.assertEqual(job.documento_digital_id, self.arquivo.pk)
        self.assertEqual(job.criado_por, self.dono)
        self.assertEqual(corpo['status'], estados.PENDENTE)

    def test_criar_job_nao_autenticado_redireciona_para_login(self):
        resposta = self.client.post(self.url_criar())

        self.assertEqual(resposta.status_code, 302)
        self.assertIn('/accounts/login/', resposta['Location'])
        self.assertEqual(OcrJob.objects.count(), 0)

    def test_criar_job_sem_permissao_bloqueado_e_sem_criar_job(self):
        self.client.force_login(self.sem_acesso)

        resposta = self.client.post(self.url_criar())

        self.assertEqual(resposta.status_code, 404)
        self.assertEqual(OcrJob.objects.count(), 0)

    def test_criar_job_com_job_ativo_existente_retorna_409(self):
        job_ativo, _criado = services.criar_job(self.arquivo, criado_por=self.dono)
        self.client.force_login(self.dono)

        resposta = self.client.post(self.url_criar())

        self.assertEqual(resposta.status_code, 409)
        self.assertEqual(OcrJob.objects.count(), 1)
        self.assertEqual(resposta.json()['job_id'], str(job_ativo.job_id))

    def test_criar_job_para_imagem_retorna_400(self):
        self.arquivo.tipo_mime = 'image/png'
        self.arquivo.save()
        self.client.force_login(self.dono)

        resposta = self.client.post(self.url_criar())

        self.assertEqual(resposta.status_code, 400)
        self.assertIn('error', resposta.json())
        self.assertEqual(OcrJob.objects.count(), 0)

    def test_criar_job_get_nao_permitido(self):
        self.client.force_login(self.dono)

        resposta = self.client.get(self.url_criar())

        self.assertEqual(resposta.status_code, 405)

    def test_criar_job_para_arquivo_inexistente_retorna_404(self):
        """Arquivo apagado/inexistente → 404, nunca 500 (review #260, item H).

        A leitura com lock dentro do transaction.atomic transforma a ausência
        em Http404.
        """
        self.client.force_login(self.dono)

        url = reverse('criar_job_ocr', kwargs={
            'tis_id': self.ti.pk,
            'imovel_id': self.imovel.pk,
            'documento_id': self.documento.pk,
            'arquivo_id': 999999,
        })
        resposta = self.client.post(url)

        self.assertEqual(resposta.status_code, 404)
        self.assertEqual(OcrJob.objects.count(), 0)

    # --- GET .../ocr-jobs/<job_id>/status/ ----------------------------------

    def test_status_job_inexistente_retorna_404(self):
        self.client.force_login(self.dono)

        resposta = self.client.get(self.url_status(uuid.uuid4()))

        self.assertEqual(resposta.status_code, 404)

    def test_status_job_sem_permissao_retorna_404(self):
        job, _criado = services.criar_job(self.arquivo, criado_por=self.dono)
        self.client.force_login(self.sem_acesso)

        resposta = self.client.get(self.url_status(job.job_id))

        self.assertEqual(resposta.status_code, 404)

    def test_status_job_pendente_sem_progresso_nem_erro(self):
        job, _criado = services.criar_job(self.arquivo, criado_por=self.dono)
        self.client.force_login(self.dono)

        resposta = self.client.get(self.url_status(job.job_id))

        self.assertEqual(resposta.status_code, 200)
        corpo = resposta.json()
        self.assertEqual(corpo['job_id'], str(job.job_id))
        self.assertEqual(corpo['status'], estados.PENDENTE)
        self.assertIsNone(corpo['progresso'])
        self.assertIsNone(corpo['erro'])

    def test_status_job_concluido_mostra_pagina_x_de_n(self):
        from ia_ocr.models import PaginaOcr
        job, _criado = services.criar_job(self.arquivo, criado_por=self.dono)
        OcrJob.objects.filter(pk=job.pk).update(
            status=estados.CONCLUIDO, page_count=3,
        )
        PaginaOcr.objects.create(
            ocr_job=job, numero_pagina=1, texto_ocr='sintético',
        )
        PaginaOcr.objects.create(
            ocr_job=job, numero_pagina=2, texto_ocr='sintético',
        )
        self.client.force_login(self.dono)

        resposta = self.client.get(self.url_status(job.job_id))

        self.assertEqual(resposta.status_code, 200)
        progresso = resposta.json()['progresso']
        self.assertEqual(progresso['pagina'], 2)
        self.assertEqual(progresso['total'], 3)
        self.assertEqual(progresso['texto'], 'página 2 de 3')

    def test_status_job_falhou_mostra_motivo(self):
        job, _criado = services.criar_job(self.arquivo, criado_por=self.dono)
        OcrJob.objects.filter(pk=job.pk).update(
            status=estados.FALHOU,
            erro_codigo='SERVICE_UNAVAILABLE',
            erro_mensagem='fila do serviço OCR cheia',
        )
        self.client.force_login(self.dono)

        resposta = self.client.get(self.url_status(job.job_id))

        self.assertEqual(resposta.status_code, 200)
        erro = resposta.json()['erro']
        self.assertEqual(erro['codigo'], 'SERVICE_UNAVAILABLE')
        self.assertEqual(erro['mensagem'], 'fila do serviço OCR cheia')
