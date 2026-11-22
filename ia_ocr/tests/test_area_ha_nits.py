"""#380/#381 — nits da área em hectares (follow-ups do PR #379).

Dois defeitos de borda: ``quantizar_hectares`` devolvia notação científica
crua (``'1E+5'``) e a preposição ``a`` na sobra do par/composto virava
unidade (``'equivalente a 12,50 ha'``).
"""

from decimal import Decimal

from django.test import SimpleTestCase

from dominial.models import Lancamento
from ia_ocr.revisao.area_ha import (
    converter_para_hectares,
    quantizar_hectares,
)

from .test_revisao_formulario_prefill_base import PrefillBase
from .test_revisao_formulario_view_base import RevisaoFormularioBase


class ConverterComPreposicaoTest(SimpleTestCase):
    """#381: ``a`` sem ponto não é ares quando não precede número."""

    def test_preposicao_antes_do_par_nao_invalida_a_conversao(self):
        self.assertEqual(
            converter_para_hectares('equivalente a 12,50 ha', 'ha'),
            Decimal('12.5000'),
        )
        self.assertEqual(
            converter_para_hectares('correspondente a 1.500,00 m²', 'm2'),
            Decimal('0.1500'),
        )

    def test_composto_hectare_are_centiare_continua_intacto(self):
        for texto in (
            '169 hectares, 09 ares e 40 centiares',
            '169 ha, 9 a e 40 ca',
        ):
            with self.subTest(texto=texto):
                self.assertEqual(
                    converter_para_hectares(texto, None),
                    Decimal('169.0940'),
                )

    def test_ares_sozinho_e_abreviacao_continuam_recusados(self):
        self.assertIsNone(converter_para_hectares('12,50 a', None))
        self.assertIsNone(converter_para_hectares('12,50 a.', 'ha'))

    def test_numero_sem_unidade_continua_sem_conversao(self):
        self.assertIsNone(converter_para_hectares('área de 12,50', 'ha'))


class QuantizarNotacaoCientificaTest(SimpleTestCase):
    """#380: a saída nunca tem ``E``/``e`` e não inventa casas."""

    def test_notacao_cientifica_vira_forma_fixa(self):
        for valor, esperado in (
            ('1E+5', '100000'),
            ('1.5E+3', '1500'),
            ('1.2345E+2', '123.45'),
            ('12.34565', '12.3457'),
            ('0.00005', '0.0001'),
            ('1e-7', '0.0000'),
        ):
            with self.subTest(valor=valor):
                self.assertEqual(quantizar_hectares(valor), esperado)

    def test_texto_nao_numerico_continua_none(self):
        self.assertIsNone(quantizar_hectares('abc'))


class PrefillNitsTest(PrefillBase):
    """O formulário recebe exatamente o que o parser confirmou."""

    def _com_area(self, raw, unidade, normalizado):
        return self._registro(area={
            **self._campo(normalizado), 'unidade': unidade, 'raw': raw,
        })

    def _pendencias_da_area(self, resultado):
        return [
            aviso for aviso in resultado['pendencias']
            if aviso['motivo'] == 'unidade_area'
        ]

    def test_preposicao_nao_gera_pendencia(self):
        resultado = self._prefill(self._com_area(
            'equivalente a 12,50 ha', 'ha', '12.50',
        ))

        self.assertEqual(resultado['form_data']['area'], '12.50')
        self.assertEqual(self._pendencias_da_area(resultado), [])

    def test_notacao_cientifica_chega_em_forma_fixa(self):
        resultado = self._prefill(self._com_area(
            '1E+5', 'ha', '1E+5',
        ))

        self.assertEqual(resultado['form_data']['area'], '100000')
        self.assertNotIn('E', resultado['form_data']['area'])
        self.assertEqual(self._pendencias_da_area(resultado), [])


class SalvarNotacaoCientificaTest(RevisaoFormularioBase):
    """Salvar o ato cujo canônico veio em notação científica (#380)."""

    def setUp(self):
        super().setUp()
        payload = self._payload_de_tres_atos()
        payload['acts'] = [payload['acts'][0]]
        payload['acts'][0]['area'] = {
            **self._campo('1E+5'), 'unidade': 'ha', 'raw': '1E+5',
        }
        self.job.extracoes.all().delete()
        self.extracao = self._aberta(payload)

    def test_salvar_persiste_a_area_em_decimal_inteiro(self):
        resposta = self.salvar(0)

        self.assertRedirects(
            resposta, self.url_documento(), fetch_redirect_response=False,
        )
        lancamento = Lancamento.objects.get(documento=self.documento)
        self.assertEqual(lancamento.area, Decimal(100000))
        campo = self.extracao.campos.get(chave='/acts/0/area')
        self.assertEqual(campo.normalized, '100000')
        self.assertEqual(campo.motivos_revisao, [])
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, 'importado')
