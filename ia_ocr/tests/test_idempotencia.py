"""Idempotência do criar_job: mesmo job_id não duplica nem explode."""

import uuid

from django.test import TestCase

from ia_ocr.models import OcrJob
from ia_ocr.services import JobIdConflitante, criar_job

from .factories import criar_documento_digital, criar_usuario


class CriarJobIdempotenciaTest(TestCase):
    def setUp(self):
        self.usuario = criar_usuario()
        self.documento = criar_documento_digital(upload_por=self.usuario)

    def test_mesmo_job_id_duas_vezes_cria_um_registro(self):
        job_id = uuid.uuid4()
        job_1, criado_1 = criar_job(
            self.documento, job_id=job_id, criado_por=self.usuario
        )
        job_2, criado_2 = criar_job(
            self.documento, job_id=job_id, criado_por=self.usuario
        )

        self.assertTrue(criado_1)
        self.assertFalse(criado_2)
        self.assertEqual(job_1.pk, job_2.pk)
        self.assertEqual(OcrJob.objects.filter(job_id=job_id).count(), 1)

    def test_mesmo_job_id_nao_gera_integrity_error(self):
        """Chamada repetida (ex.: retry de request) é idempotente."""
        job_id = uuid.uuid4()
        criar_job(self.documento, job_id=job_id)
        try:
            job, criado = criar_job(self.documento, job_id=job_id)
        except Exception as exc:  # IntegrityError ou qualquer outro
            self.fail(f'criar_job repetido levantou {exc!r}')
        self.assertFalse(criado)
        self.assertEqual(job.documento_digital, self.documento)

    def test_mesmo_job_id_com_outro_documento_levanta_conflitante(self):
        job_id = uuid.uuid4()
        criar_job(self.documento, job_id=job_id)
        outro_documento = criar_documento_digital(upload_por=self.usuario)

        with self.assertRaises(JobIdConflitante):
            criar_job(outro_documento, job_id=job_id)
        # O registro original permanece intacto.
        job = OcrJob.objects.get(job_id=job_id)
        self.assertEqual(job.documento_digital, self.documento)

    def test_sem_job_id_gera_um_novo(self):
        job, criado = criar_job(self.documento, criado_por=self.usuario)
        self.assertTrue(criado)
        self.assertIsNotNone(job.job_id)
        self.assertEqual(job.status, 'pendente')
        self.assertEqual(job.origem, 'ocr')
        self.assertEqual(job.criado_por, self.usuario)

    def test_origem_texto_embutido(self):
        job, criado = criar_job(self.documento, origem='texto_embutido')
        self.assertTrue(criado)
        self.assertEqual(job.origem, 'texto_embutido')
