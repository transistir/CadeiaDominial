"""#373 — bordas do parser de área (review do Opus/Codex no PR #379).

Par número+unidade, número pt-BR estrito, sinal, composto, confronto com o
``normalized`` do A3 e contexto decimal. Complementa
``test_area_ha.py`` (casos felizes) e os testes de prefill/salvar.
"""

from decimal import Decimal, getcontext

from django.test import SimpleTestCase

from dominial.models import Lancamento
from ia_ocr.formulario import prefill_do_ato
from ia_ocr.revisao.area_ha import (
    converter_para_hectares,
    hectares_confirmados,
    quantizar_hectares,
)
from ia_ocr.revisao.area_ha_padroes import unidades_divergem

from .test_revisao_formulario_prefill_base import PrefillBase
from .test_revisao_formulario_view_base import RevisaoFormularioBase

# (raw, unidade do A3, esperado em hectares)
CASOS = (
    ('169 hectares, 09 ares e 40 centiares', None, Decimal('169.0940')),
    ('169 hectares, 09 ares, e 40 centiares', None, Decimal('169.0940')),
    ('169 ha., 09 a. e 40 ca.', None, Decimal('169.0940')),
    ('0,5 hectares e 10 ares', None, Decimal('0.6000')),
    ('1.069 hectares, 09 ares e 40 centiares', None, Decimal('1069.0940')),
    ('1.234,5678 ha', 'ha', Decimal('1234.5678')),
    ('12344,49 m2', 'm2', Decimal('1.2344')),
    ('12.345,67 m²', 'm2', Decimal('1.2346')),
    ('120,00 m²', None, Decimal('0.0120')),
    ('0,00005 ha', 'ha', Decimal('0.0001')),
    ('1.234 ha', 'ha', None),
    ('12.345 m²', 'm2', None),
    ('1234.567,89', 'ha', None),
    ('120,00 m2', 'ha', None),
    ('1,5 ha', 'm2', None),
    ('169 ha, 9 a e 40 ca', 'm2', None),
    ('lote 7, área 120,00 m2', 'm2', None),
    ('área -5 ha', 'ha', None),
    ('-5 ha, 10 a', None, None),
    ('−169 hectares, 9 ares', None, None),
    ('1O0 m2', 'm2', None),
    ('120 m2 (0,012 ha)', None, None),
    ('99999999999 ha', 'ha', None),
    ('169 ha, 109 ares', None, None),
    ('1.234,5678', None, None),
    ('alqueires', 'alqueires', None),
    # 2ª correção do review (Opus/Codex): borda do número, unidade solta
    # e sobra da expressão.
    ('l20 m²', 'm2', None),
    ('O50 m²', 'm2', None),
    ('12 m²x', None, None),
    ('169 ha, 9 a e quarenta ca', None, None),
    ('120 m²/ha', None, None),
    ('área: 120,00 m2', None, Decimal('0.0120')),
    ('12,50 has', 'ha', Decimal('12.5000')),
    ('12,50 há', 'ha', Decimal('12.5000')),
    # 3ª correção do review (Codex): separador sem parte inteira, dígito
    # não-ASCII e singular "are" na sobra.
    (',5 ha', 'ha', None),
    ('.5 ha', 'ha', None),
    ('１20 m²', 'm2', None),
    ('١20 m²', 'm2', None),
    ('１２０ m²', 'm2', None),
    ('١٢٠ m²', 'm2', None),
    ('169 ha e 9 are', None, None),
    ('169 ha e nove are', None, None),
)


class UnidadeDoTextoTest(SimpleTestCase):
    """Unidade solta exige borda: o "a" de "área" não é ares (#373)."""

    def test_palavra_com_a_ou_ha_final_nao_e_unidade(self):
        self.assertFalse(unidades_divergem('área de 12,50', 'ha'))
        self.assertFalse(unidades_divergem('Fazenda Ilha', 'ha'))
        self.assertFalse(unidades_divergem('Pororoca', 'ha'))


class TabelaDeBordasTest(SimpleTestCase):
    """A tabela obrigatória do review, linha a linha."""

    def test_tabela(self):
        for raw, unidade, esperado in CASOS:
            with self.subTest(raw=raw, unidade=unidade):
                self.assertEqual(
                    converter_para_hectares(raw, unidade), esperado,
                )

    def test_precisao_ambiente_nao_muda_nenhum_resultado(self):
        contexto = getcontext()
        anterior = contexto.prec
        self.addCleanup(setattr, contexto, 'prec', anterior)
        contexto.prec = 6

        for raw, unidade, esperado in CASOS:
            with self.subTest(raw=raw, unidade=unidade):
                self.assertEqual(
                    converter_para_hectares(raw, unidade), esperado,
                )

    def test_quantizar_so_reescreve_o_excedente_de_quatro_casas(self):
        self.assertEqual(quantizar_hectares('12.34565'), '12.3457')
        self.assertEqual(quantizar_hectares('12.500000'), '12.5000')
        self.assertEqual(quantizar_hectares('12.50'), '12.50')
        self.assertIsNone(quantizar_hectares('abc'))
        self.assertIsNone(quantizar_hectares(None))
        self.assertIsNone(quantizar_hectares(''))


class HectaresConfirmadosTest(SimpleTestCase):
    """3ª revisão: o canônico do A3 não reverte uma recusa do texto."""

    def test_texto_vazio_aceita_o_canonico_quantizado(self):
        for raw in ('', '   ', None):
            with self.subTest(raw=raw):
                self.assertEqual(
                    hectares_confirmados(raw, '12.500000'), '12.5000',
                )
        self.assertEqual(hectares_confirmados('', '12.50'), '12.50')

    def test_texto_ambiguo_nao_e_consertado_pelo_canonico(self):
        for raw, normalizado in (
            ('1.234 ha', '1234'),
            ('-5 ha', '-5'),
            ('169 ha, 9 a e quarenta ca', '169.09'),
            ('120 ha/m²', '120'),
            ('área de 12,50', '12.50'),
        ):
            with self.subTest(raw=raw, normalizado=normalizado):
                self.assertIsNone(hectares_confirmados(raw, normalizado))

    def test_convertido_divergente_e_recusado(self):
        self.assertIsNone(hectares_confirmados('12,34565 ha', '999.12345'))

    def test_canonico_nao_positivo_ou_fora_do_limite_e_recusado(self):
        for normalizado in ('0', '-5', '100000000', 'abc'):
            with self.subTest(normalizado=normalizado):
                self.assertIsNone(hectares_confirmados('', normalizado))

    def test_borda_compara_depois_de_quantizar(self):
        # diff 0,000001 → quantizado bate
        self.assertEqual(hectares_confirmados('1,000001 ha', '1'), '1')
        # 12,34565 quantiza para 12,3457; canônico 12.3456 → recusa
        self.assertIsNone(hectares_confirmados('12,34565 ha', '12.3456'))
        # mesmo texto, canônico 12.3457 → aceita
        self.assertEqual(
            hectares_confirmados('12,34565 ha', '12.3457'), '12.3457',
        )
        # borda de baixo: 12,34555 → 12,3456 (ROUND_HALF_UP) → aceita
        self.assertEqual(
            hectares_confirmados('12,34555 ha', '12.3456'), '12.3456',
        )
        # diff 0,000099 → quantizado diverge → recusa
        self.assertIsNone(hectares_confirmados('12,345699 ha', '12.3456'))


class PrefillBordasTest(PrefillBase):
    """O prefill consome exatamente o que o parser decidiu."""

    def _com_area(self, normalizado, unidade, raw):
        return self._registro(area={
            **self._campo(normalizado), 'unidade': unidade, 'raw': raw,
        })

    def _pendencias_da_area(self, resultado):
        return [
            aviso for aviso in resultado['pendencias']
            if aviso['motivo'] == 'unidade_area'
        ]

    def test_composto_sem_normalizado_preenche_sem_pendencia(self):
        texto = '169 hectares, 09 ares e 40 centiares'
        resultado = self._prefill(self._com_area(None, None, texto))

        self.assertEqual(resultado['form_data']['area'], '169.0940')
        self.assertEqual(self._pendencias_da_area(resultado), [])

    def test_m2_com_enum_ha_continua_pendencia_e_campo_vazio(self):
        resultado = self._prefill(
            self._com_area(None, 'ha', '120,00 m2'),
        )

        self.assertNotIn('area', resultado['form_data'])
        self.assertEqual(len(self._pendencias_da_area(resultado)), 1)

    def test_normalizado_que_bate_libera_a_conversao(self):
        resultado = self._prefill(self._com_area(
            '123400.00', 'm2', '123.400,00 m²',
        ))

        self.assertEqual(resultado['form_data']['area'], '12.3400')
        self.assertEqual(self._pendencias_da_area(resultado), [])

    def test_normalizado_divergente_nao_converte(self):
        resultado = self._prefill(self._com_area(
            '99999.00', 'm2', '123.400,00 m²',
        ))

        self.assertNotIn('area', resultado['form_data'])
        self.assertEqual(len(self._pendencias_da_area(resultado)), 1)

    def test_ha_do_a3_quantiza_para_quatro_casas(self):
        extracao = self._aberta(
            self._com_area('12.34565', 'ha', '12,34565 ha'),
        )

        resultado = prefill_do_ato(extracao, 0, self.documento)

        self.assertEqual(resultado['form_data']['area'], '12.3457')
        self.assertEqual(self._pendencias_da_area(resultado), [])
        campo = extracao.campos.get(chave='/acts/0/area')
        self.assertEqual(campo.normalized, '12.3457')
        self.assertEqual(campo.motivos_revisao, [])

    def test_ha_do_a3_com_texto_sem_unidade_vira_pendencia(self):
        # 3ª revisão: o canônico não "conserta" texto que não converte.
        resultado = self._prefill(self._com_area(
            '12.50', 'ha', 'área de 12,50',
        ))

        self.assertNotIn('area', resultado['form_data'])
        self.assertEqual(len(self._pendencias_da_area(resultado)), 1)

    def test_ha_divergente_do_texto_vira_pendencia(self):
        extracao = self._aberta(self._com_area(
            '999.12345', 'ha', '12,34565 ha',
        ))

        resultado = prefill_do_ato(extracao, 0, self.documento)

        self.assertNotIn('area', resultado['form_data'])
        self.assertEqual(len(self._pendencias_da_area(resultado)), 1)
        campo = extracao.campos.get(chave='/acts/0/area')
        self.assertIsNone(campo.normalized)
        self.assertIn('unidade_area', campo.motivos_revisao)

    def test_composto_divergente_do_canonico_vira_pendencia(self):
        texto = '169 hectares, 09 ares e 40 centiares'
        resultado = self._prefill(self._com_area('169.00000', 'ha', texto))

        self.assertNotIn('area', resultado['form_data'])
        self.assertEqual(len(self._pendencias_da_area(resultado)), 1)

    def test_conversao_recusada_em_ha_nao_descarta_em_silencio(self):
        extracao = self._aberta(self._com_area(None, 'ha', '1.234 ha'))

        resultado = prefill_do_ato(extracao, 0, self.documento)

        self.assertNotIn('area', resultado['form_data'])
        (aviso,) = self._pendencias_da_area(resultado)
        self.assertTrue(aviso['bloqueante'])
        campo = extracao.campos.get(chave='/acts/0/area')
        self.assertIn('unidade_area', campo.motivos_revisao)


class SalvarCompostoTest(RevisaoFormularioBase):
    """Revisar e salvar o ato cuja área veio no composto hectare/are/centiare."""

    def setUp(self):
        super().setUp()
        payload = self._payload_de_tres_atos()
        payload['acts'] = [payload['acts'][0]]
        texto = '169 hectares, 09 ares e 40 centiares'
        payload['acts'][0]['area'] = {
            **self._campo(None), 'normalized': None, 'unidade': None,
            'raw': texto,
        }
        self.job.extracoes.all().delete()
        self.extracao = self._aberta(payload)

    def test_salvar_grava_a_area_do_composto_em_hectares(self):
        resposta = self.salvar(0)

        self.assertRedirects(
            resposta, self.url_documento(), fetch_redirect_response=False,
        )
        lancamento = Lancamento.objects.get(documento=self.documento)
        self.assertEqual(lancamento.area, Decimal('169.0940'))
        campo = self.extracao.campos.get(chave='/acts/0/area')
        self.assertEqual(campo.normalized, '169.0940')
        self.assertEqual(campo.motivos_revisao, [])
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, 'importado')
