"""Conclusão sem atos pela revisão por formulário (#341 fase 3, #262).

Com a aposentadoria da tela de cards, a saída "sem atos" do I-5/#262 deixa
de ser o JSON de ``campos/finalizar/`` e vira um formulário HTML na revisão
nova: ``revisar/`` renderiza ``revisao_sem_atos.html`` quando a extração do
serviço veio sem atos e ``services.pode_finalizar_sem_atos`` destrava, e o
POST em ``revisar/sem-atos/`` chama ``services.finalizar_revisao`` com
``confirmar_sem_atos=True`` e volta ao documento.

Contrato do serviço (``FinalizarSemAtosTest``): a finalização audita
``EXTRAIDO → REVISADO`` com motivo ``revisao_finalizada_sem_atos`` — não
cria ``ImportacaoIA`` nem vai a ``IMPORTADO`` (não há ato algum a importar).
"""

from django.test import override_settings
from django.urls import reverse

from ia_ocr import estados, revisao, services
from ia_ocr.models import CampoSugerido, ExtracaoSugerida, ImportacaoIA

from .payloads_extracao import PROVIDER, SCHEMA_VERSION, payload_averbacao
from .test_revisao_formulario_view_base import RevisaoFormularioBase


class RevisarSemAtosBase(RevisaoFormularioBase):
    """Mesma montagem da revisão, com a extração do serviço sem atos."""

    def setUp(self):
        super().setUp()
        self.job.extracoes.all().delete()
        self.extracao = self._sem_atos()

    def _sem_atos(self):
        payload = payload_averbacao(self.job.job_id)
        payload['acts'] = []
        extracao = ExtracaoSugerida.objects.create(
            ocr_job=self.job, schema_version=SCHEMA_VERSION,
            payload=payload, payload_servico=payload, provider=PROVIDER,
            solicitada_por=self.usuario,
        )
        CampoSugerido.objects.bulk_create(
            revisao.desnormalizar(extracao, payload, [self.pagina]),
        )
        # Sem atos, o cabeçalho ainda precisa das escolhas de cartório.
        extracao.campos.filter(tipo_valor='cartorio').update(criar_novo=True)
        self.assertEqual(revisao.pendencias(extracao), [{
            'chave': '/acts', 'motivo': 'nenhum_ato', 'bloqueante': True,
        }])
        return extracao

    def url_sem_atos(self):
        return reverse('revisar_sem_atos_ocr', kwargs=self.kwargs())

    def _assert_nao_finalizada(self):
        self.extracao.refresh_from_db()
        self.job.refresh_from_db()
        self.assertIsNone(self.extracao.finalizada_em)
        self.assertEqual(self.job.status, estados.EXTRAIDO)
        self.assertFalse(self.job.transicoes.exists())


@override_settings(OCR_PERMITIR_FINALIZAR_SEM_ATOS=True)
class RevisarSemAtosTest(RevisarSemAtosBase):
    def test_get_sem_atos_renderiza_a_confirmacao(self):
        resposta = self.client.get(self.url_entrada())

        self.assertEqual(resposta.status_code, 200)
        self.assertTemplateUsed(resposta, 'ia_ocr/revisao_sem_atos.html')
        html = resposta.content.decode()
        self.assertIn('Concluir sem atos', html)
        # O POST vai para a rota nova, com o token que o serviço valida.
        self.assertIn(reverse('revisar_sem_atos_ocr', kwargs=self.kwargs()), html)
        self.assertIn(f'value="{services.versao_bloco(self.extracao)}"', html)

    def test_post_conclui_e_redireciona_ao_documento(self):
        resposta = self.client.post(self.url_sem_atos(), {
            'versao': services.versao_bloco(self.extracao),
        })

        self.assertRedirects(
            resposta, self.url_documento(), fetch_redirect_response=False,
        )
        self.extracao.refresh_from_db()
        self.job.refresh_from_db()
        self.assertIsNotNone(self.extracao.finalizada_em)
        # Contrato do serviço: REVISADO com motivo próprio — sem atos não há
        # importação, então nada vira IMPORTADO nem cria ImportacaoIA.
        self.assertEqual(self.job.status, estados.REVISADO)
        self.assertFalse(ImportacaoIA.objects.exists())
        transicao = self.job.transicoes.get()
        self.assertEqual(transicao.de_status, estados.EXTRAIDO)
        self.assertEqual(transicao.para_status, estados.REVISADO)
        self.assertEqual(transicao.motivo, 'revisao_finalizada_sem_atos')
        mensagens = ' '.join(self.mensagens(resposta))
        self.assertIn('sem atos', mensagens)

    def test_post_com_versao_velha_e_recusado(self):
        versao = services.versao_bloco(self.extracao)
        # Outro revisor mexe numa linha depois de a página ter sido renderizada.
        self.extracao.campos.filter(chave='/document/data').update(
            status_revisao='aceito',
        )

        resposta = self.client.post(self.url_sem_atos(), {'versao': versao})

        self.assertRedirects(
            resposta, self.url_entrada(), fetch_redirect_response=False,
        )
        self._assert_nao_finalizada()

    def test_post_sem_versao_e_recusado(self):
        resposta = self.client.post(self.url_sem_atos(), {})

        self.assertEqual(resposta.status_code, 400)
        self._assert_nao_finalizada()

    def test_get_com_atos_nao_cai_na_tela_sem_atos(self):
        self.job.extracoes.all().delete()
        self.extracao = self._aberta(payload_averbacao(self.job.job_id))

        resposta = self.client.get(self.url_entrada())

        self.assertEqual(resposta.status_code, 302)
        self.assertRedirects(
            resposta, self.url_ato(0), fetch_redirect_response=False,
        )

    def test_post_com_atos_nao_finaliza(self):
        self.job.extracoes.all().delete()
        self.extracao = self._aberta(payload_averbacao(self.job.job_id))

        resposta = self.client.post(self.url_sem_atos(), {
            'versao': services.versao_bloco(self.extracao),
        })

        self.assertRedirects(
            resposta, self.url_entrada(), fetch_redirect_response=False,
        )
        self._assert_nao_finalizada()

    def test_get_com_bloqueio_de_campo_nao_renderiza_a_confirmacao(self):
        # A paliativa só vale quando a ÚNICA pendência é nenhum_ato.
        self.extracao.campos.filter(chave='/document/data').update(
            status_revisao='descartado',
        )
        self.assertFalse(services.pode_finalizar_sem_atos(self.extracao))

        resposta = self.client.get(self.url_entrada())

        self.assertEqual(resposta.status_code, 302)
        self.assertRedirects(
            resposta,
            reverse('texto_job_ocr', kwargs=self.kwargs()),
            fetch_redirect_response=False,
        )

    def test_get_sem_flag_mantem_o_comportamento_de_hoje(self):
        with override_settings(OCR_PERMITIR_FINALIZAR_SEM_ATOS=False):
            resposta = self.client.get(self.url_entrada())

        self.assertEqual(resposta.status_code, 302)
        self.assertRedirects(
            resposta,
            reverse('texto_job_ocr', kwargs=self.kwargs()),
            fetch_redirect_response=False,
        )
        self.assertIn(
            'não trouxe nenhum ato', ' '.join(self.mensagens(resposta)),
        )

    def test_get_de_job_ja_revisado_nao_reoferece_a_confirmacao(self):
        services.finalizar_revisao(
            self.extracao, self.usuario, confirmar_sem_atos=True,
        )

        resposta = self.client.get(self.url_entrada())

        self.assertEqual(resposta.status_code, 302)
        self.assertNotIn('revisao_sem_atos.html', [
            t.name for t in resposta.templates
        ])
