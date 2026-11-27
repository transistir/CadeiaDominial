"""#320: recusa → correção → gravação, sem perder o que foi digitado."""

from copy import deepcopy

from dominial.models import Lancamento
from ia_ocr.models import ImportacaoIA, OcrJobTransicao

from .payloads_extracao import payload_averbacao
from .test_revisao_formulario_view_base import RevisaoFormularioBase


class RecusaReenvioTest(RevisaoFormularioBase):
    def _dois_atos_com_area_no_segundo(self):
        payload = self._payload_de_tres_atos()
        segundo = deepcopy(payload_averbacao(self.job.job_id)['acts'][0])
        segundo['area'] = {
            **self._campo('12.50', 'área 12,50 alqueires'),
            'unidade': 'alqueires', 'raw': '12,50 alqueires',
        }
        payload['acts'] = [deepcopy(payload['acts'][0]), segundo]
        self.job.extracoes.all().delete()
        self.extracao = self._aberta(payload)

    def _um_ato_com_area(self):
        payload = payload_averbacao(self.job.job_id)
        payload['acts'][0]['area'] = {
            **self._campo('12.50', 'área 12,50 alqueires'),
            'unidade': 'alqueires', 'raw': '12,50 alqueires',
        }
        self.job.extracoes.all().delete()
        self.extracao = self._aberta(payload)

    def test_recusa_por_area_nao_grava_e_correcao_conclui(self):
        self._dois_atos_com_area_no_segundo()
        self.salvar(0)
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, 'revisado')

        antes = self.contagens()
        transicoes = OcrJobTransicao.objects.filter(ocr_job=self.job).count()
        recusa = self.salvar(1, area='', observacoes='digitado no ato 2')

        self.assertEqual(recusa.status_code, 200)
        self.assertEqual(self.contagens(), antes)
        self.assertEqual(
            OcrJobTransicao.objects.filter(ocr_job=self.job).count(), transicoes,
        )
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, 'revisado')
        html = recusa.content.decode()
        self.assertIn('digitado no ato 2', html)
        self.assertIn(
            'Ato Av1 não foi salvo.', ' '.join(self.mensagens(recusa)),
        )

        corrigido = self.salvar(1, area='0.012')
        self.assertRedirects(
            corrigido, self.url_documento(), fetch_redirect_response=False,
        )
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, 'importado')
        self.assertEqual(Lancamento.objects.filter(documento=self.documento).count(), 2)
        self.assertEqual(
            OcrJobTransicao.objects.filter(
                ocr_job=self.job, de_status='revisado', para_status='importado',
            ).count(),
            1,
        )

    def test_recusa_no_primeiro_ato_mantem_extraido(self):
        self._um_ato_com_area()

        recusa = self.salvar(0, area='')

        self.assertEqual(recusa.status_code, 200)
        self.assertFalse(Lancamento.objects.filter(documento=self.documento).exists())
        self.assertFalse(ImportacaoIA.objects.filter(ocr_job=self.job).exists())
        self.assertFalse(OcrJobTransicao.objects.filter(ocr_job=self.job).exists())
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, 'extraido')

    def test_recusa_do_service_nao_grava_e_reenvio_salva(self):
        antes = self.contagens()

        recusa = self.salvar(
            0, tipo_lancamento='', observacoes='texto que eu digitei',
        )

        self.assertEqual(recusa.status_code, 200)
        self.assertEqual(self.contagens(), antes)
        html = recusa.content.decode()
        self.assertIn('texto que eu digitei', html)
        self.assertIn(
            'Ato R1 não foi salvo.', ' '.join(self.mensagens(recusa)),
        )

        salvo = self.salvar(0)
        self.assertEqual(salvo.status_code, 302)
        self.assertEqual(Lancamento.objects.filter(documento=self.documento).count(), 1)
        self.assertEqual(ImportacaoIA.objects.filter(modelo='Lancamento').count(), 1)
