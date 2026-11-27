"""Entrega do app, item 1: ato de abertura sem ``data`` normalizada.

O A3 pode trazer ``"data": {"raw": "18.06.2015", "normalized": null}``.
O prefill precisa de um parser determinístico do ``raw`` (nada de
invenção) e o POST sem data precisa parar antes de gravar.
"""

from dominial.models import Lancamento
from dominial.services.lancamento_criacao_service import ERRO_CRIACAO
from ia_ocr.formulario import prefill_do_ato

from .payloads_extracao import TEXTO_M237, payload_m237_abertura
from .test_revisao_abertura_m237 import AberturaM237Base

MENSAGEM_DATA_ABERTURA = (
    '❌ Informe a data do ato de abertura. Nada foi gravado.'
)


class AberturaDataRawTest(AberturaM237Base):
    def _extracao_com_data_raw(self, raw):
        payload = payload_m237_abertura(self.job.job_id)
        payload['acts'][0]['data'] = {
            'raw': raw,
            'normalized': None,
            'confianca': 0.95,
            'requer_revisao': True,
            'evidencia': {'pagina': 1, 'trecho': raw},
        }
        self.pagina.texto_ocr = TEXTO_M237 + f'\nData do ato: {raw}'
        self.pagina.save(update_fields=['texto_ocr'])
        self.extracao.delete()
        return self._aberta(payload)

    def test_prefill_usa_raw_quando_normalized_e_nulo(self):
        extracao = self._extracao_com_data_raw('18.06.2015')

        form_data = prefill_do_ato(extracao, 0, self.documento)['form_data']

        self.assertEqual(form_data['data'], '2015-06-18')

    def test_prefill_nao_inventa_data_de_texto_ambiguo(self):
        extracao = self._extracao_com_data_raw('18 de junho de 2015')

        form_data = prefill_do_ato(extracao, 0, self.documento)['form_data']

        self.assertNotIn('data', form_data)

    def test_prefill_preserva_normalized_quando_presente(self):
        form_data = prefill_do_ato(
            self.extracao, 0, self.documento,
        )['form_data']

        self.assertEqual(form_data['data'], '1982-06-09')

    def test_prefill_recusa_raw_com_separadores_mistos(self):
        extracao = self._extracao_com_data_raw('18.06/2015')

        form_data = prefill_do_ato(extracao, 0, self.documento)['form_data']

        self.assertNotIn('data', form_data)

    def test_prefill_recusa_raw_com_dia_unico(self):
        extracao = self._extracao_com_data_raw('1/2/2015')

        form_data = prefill_do_ato(extracao, 0, self.documento)['form_data']

        self.assertNotIn('data', form_data)

    def test_prefill_nao_ressuscita_raw_de_linha_descartada(self):
        extracao = self._extracao_com_data_raw('18.06.2015')
        extracao.campos.filter(chave='/acts/0/data').update(
            status_revisao='descartado',
        )

        form_data = prefill_do_ato(extracao, 0, self.documento)['form_data']

        self.assertNotIn('data', form_data)


class AberturaSemDataNoPostTest(AberturaM237Base):
    def test_post_sem_data_bloqueia_ato_de_abertura_antes_de_gravar(self):
        antes = self.contagens()

        resposta = self.salvar(0, data='')

        self.assertEqual(resposta.status_code, 200)
        self.assertIn(
            MENSAGEM_DATA_ABERTURA, '\n'.join(self.mensagens(resposta)),
        )
        self.assertEqual(self.contagens(), antes)
        self.assertFalse(
            Lancamento.objects.filter(documento=self.documento).exists()
        )

    def test_post_com_data_invalida_bloqueia_ato_de_abertura_antes_de_gravar(self):
        antes = self.contagens()

        resposta = self.salvar(0, data='18/06/2015')

        self.assertEqual(resposta.status_code, 200)
        self.assertIn(
            MENSAGEM_DATA_ABERTURA, '\n'.join(self.mensagens(resposta)),
        )
        self.assertEqual(self.contagens(), antes)
        self.assertFalse(
            Lancamento.objects.filter(documento=self.documento).exists()
        )

    def test_post_sem_data_em_registro_mantem_mensagem_do_service(self):
        # Fora do início de matrícula não há mensagem específica: vale a
        # mensagem já existente do service (registrado nesta entrega).
        antes = self.contagens()

        resposta = self.salvar(1, data='')

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(self.contagens(), antes)
        mensagens = self.mensagens(resposta)
        self.assertFalse(
            any(MENSAGEM_DATA_ABERTURA in mensagem for mensagem in mensagens)
        )
        self.assertTrue(any(ERRO_CRIACAO in m for m in mensagens))
