"""UI do card "Extrair texto com IA" na página de upload (issue #260 / I-3, fatia 2).

Cobertura de template/contexto: o card aparece só para PDFs, lista os
arquivos digitais e reflete o estado inicial do job mais recente do arquivo
(botão desabilitado com job ativo, "Tentar novamente" com falha, "Revisar
texto" desabilitado quando concluído). O comportamento do polling em si é
verificado manualmente (roteiro no relatório da fatia).
"""

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from ia_ocr import services

from .factories import criar_documento_digital


class CardOcrUploadTestCase(TestCase):
    """Cenário: dono atribuído à TI do documento, como em test_views_ocr_jobs."""

    @classmethod
    def setUpTestData(cls):
        cls.dono = User.objects.create_user(username='dono-ui', password='senha-dono')
        cls.arquivo = criar_documento_digital(upload_por=cls.dono)
        cls.imovel = cls.arquivo.documento.imovel
        cls.ti = cls.imovel.terra_indigena_id
        cls.documento = cls.arquivo.documento

        from dominial.models import UserTI
        UserTI.objects.create(user=cls.dono, tis=cls.ti)

    def url_upload(self):
        return reverse('upload_documento_digital', kwargs={
            'tis_id': self.ti.pk,
            'imovel_id': self.imovel.pk,
            'documento_id': self.documento.pk,
        })

    def url_criar(self):
        return reverse('criar_job_ocr', kwargs={
            'tis_id': self.ti.pk,
            'imovel_id': self.imovel.pk,
            'documento_id': self.documento.pk,
            'arquivo_id': self.arquivo.pk,
        })

    def pagina(self):
        self.client.force_login(self.dono)
        return self.client.get(self.url_upload())

    def test_card_ocr_aparece_para_pdf(self):
        resposta = self.pagina()

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, 'Extrair texto com IA')
        self.assertContains(resposta, self.arquivo.nome_original)
        # URL de disparo do job disponível para o JS
        self.assertContains(resposta, self.url_criar())
        # Nota informativa: atalho do texto embutido (I-2)
        self.assertContains(resposta, 'texto embutido')

    def test_card_ocr_nao_aparece_para_imagem(self):
        self.arquivo.tipo_mime = 'image/png'
        self.arquivo.save()

        resposta = self.pagina()

        self.assertEqual(resposta.status_code, 200)
        self.assertNotContains(resposta, 'Extrair texto com IA')

    def test_card_sem_job_mostra_botao_de_disparo_habilitado(self):
        resposta = self.pagina()

        self.assertContains(resposta, 'data-ocr-disparo>')
        self.assertNotContains(resposta, 'data-ocr-disparo disabled')

    def test_card_com_job_ativo_botao_desabilitado_e_badge_com_status(self):
        job, _criado = services.criar_job(self.arquivo, criado_por=self.dono)
        from django.urls import reverse as rev
        url_status = rev('status_job_ocr', kwargs={
            'tis_id': self.ti.pk,
            'imovel_id': self.imovel.pk,
            'documento_id': self.documento.pk,
            'arquivo_id': self.arquivo.pk,
            'job_id': job.job_id,
        })

        resposta = self.pagina()

        self.assertContains(resposta, 'data-ocr-disparo disabled')
        self.assertContains(resposta, url_status)
        self.assertContains(resposta, job.get_status_display())

    def test_card_job_falhou_mostra_tentar_novamente_e_motivo(self):
        job, _criado = services.criar_job(self.arquivo, criado_por=self.dono)
        from ia_ocr.models import OcrJob
        OcrJob.objects.filter(pk=job.pk).update(
            status='falhou',
            erro_codigo='SERVICE_UNAVAILABLE',
            erro_mensagem='fila do serviço OCR cheia',
        )

        resposta = self.pagina()

        self.assertContains(resposta, 'Tentar novamente')
        self.assertContains(resposta, 'fila do serviço OCR cheia')

    def test_card_job_concluido_mostra_revisar_texto_desabilitado(self):
        job, _criado = services.criar_job(self.arquivo, criado_por=self.dono)
        from ia_ocr.models import OcrJob
        OcrJob.objects.filter(pk=job.pk).update(status='concluido')

        resposta = self.pagina()

        self.assertContains(resposta, 'Revisar texto')
        self.assertContains(resposta, 'Disponível na I-4')
        self.assertContains(resposta, 'data-ocr-revisar disabled')
