"""Parte 3 de 3 do corpo de ``ExtracaoViewsTest`` — migração VERBATIM de
``ia_ocr/tests/test_extracao_views.py`` (Etapa 12 do plano de 400 linhas).

Classe SIMPLES (sem ``TestCase``); quem coleta é a fachada em
``test_extracao_views_extracao.py``. Corpos verbatim.

Os testes dos endpoints JSON da tela de cards (``salvar_bloco_ocr``/
``finalizar_revisao_ocr``) saíram com as rotas, aposentadas na fase 4 da
#341; os casos que valem (conclusão sem atos, gravação por ato) estão em
``test_revisao_formulario_sem_atos.py`` e na família
``test_revisao_formulario_*``.
"""

from django.urls import reverse

from ia_ocr import estados
from ia_ocr.models import OcrJob


class ExtracaoViewsTestParte3:
    def test_campos_exige_extraido_ou_revisado(self):
        # #341 fase 3: `campos/` virou encaminhamento; quem recusa o estado
        # é a entrada da revisão — de volta à tela do texto (que, sem texto
        # pronto, segue para o upload) ou ao documento quando a revisão já
        # foi concluída (importado).
        upload = reverse('upload_documento_digital', kwargs={
            'tis_id': self.ti.pk, 'imovel_id': self.imovel.pk,
            'documento_id': self.documento.pk,
        })
        destinos = {
            'pendente': upload,
            'em_execucao': upload,
            'falhou': upload,
            'concluido': self.url_tela(),
            'texto_confirmado': self.url_tela(),
            'importado': self._url_documento(),
        }
        for status, _rotulo in estados.STATUS_CHOICES:
            if status in (estados.EXTRAIDO, estados.REVISADO):
                continue
            with self.subTest(status=status):
                OcrJob.objects.filter(pk=self.job.pk).update(status=status)

                resposta = self.client.get(self.url('campos_job_ocr'), follow=True)

                self.assertEqual(resposta.status_code, 200)
                self.assertEqual(
                    resposta.redirect_chain[0],
                    (self.url('revisar_job_ocr'), 302),
                )
                self.assertEqual(resposta.redirect_chain[-1][0], destinos[status])
                self.assertEqual(self.mensagens(resposta)[-1][0], 'info')

    def test_campos_contexto_da_extracao_vigente_e_somente_leitura(self):
        # #341 fase 3: a tela de cards se aposentou e `campos/` só encaminha
        # à revisão por formulário — em EXTRAIDO e em REVISADO igualmente
        # (quem diferencia os estados é a entrada da revisão).
        self._extracao()
        vigente = self._extracao()
        for status, dpi in ((estados.EXTRAIDO, 300), (estados.REVISADO, None)):
            with self.subTest(status=status):
                OcrJob.objects.filter(pk=self.job.pk).update(status=status, dpi=dpi)

                resposta = self.client.get(self.url('campos_job_ocr'))

                self.assertRedirects(
                    resposta, self.url('revisar_job_ocr'),
                    fetch_redirect_response=False,
                )
                self.assertEqual(self.job.extracao_vigente(), vigente)
