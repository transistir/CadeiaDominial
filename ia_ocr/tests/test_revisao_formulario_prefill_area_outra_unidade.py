"""``AreaEmOutraUnidadeTest`` — migração VERBATIM de
``ia_ocr/tests/test_revisao_formulario_prefill.py`` (Etapa 13 do
plano de 400 linhas).
"""
import json

from ia_ocr.formulario import prefill_do_ato


class AreaEmOutraUnidadeTestParte:
    """M3 (#341): o input da área é em HECTARES — 120 m² nunca vira 120 ha."""

    def _com_area(self, normalizado, trecho, unidade, raw=None):
        area = {
            **self._campo(normalizado, trecho), 'unidade': unidade,
            'raw': raw or trecho,
        }
        return self._registro(area=area)

    def _pendencias_da_area(self, resultado):
        return [
            aviso for aviso in resultado['pendencias']
            if aviso['motivo'] == 'unidade_area'
        ]

    def test_metro_quadrado_nao_entra_no_campo_em_hectares(self):
        resultado = self._prefill(self._com_area(
            '120.00', 'área construída 120,00 m2', 'm2', raw='120,00 m2',
        ))

        self.assertNotIn('area', resultado['form_data'])
        self.assertNotIn('area', resultado['evidencias'])
        for valor in resultado['form_data'].values():
            self.assertNotEqual(valor, '120.00')

    def test_valor_original_com_a_unidade_vira_pendencia_do_revisor(self):
        resultado = self._prefill(self._com_area(
            '120.00', 'área construída 120,00 m2', 'm2', raw='120,00 m2',
        ))

        (aviso,) = self._pendencias_da_area(resultado)
        self.assertEqual(aviso['rotulo'], 'Área')
        self.assertIn('120 m² no documento', aviso['texto'])
        self.assertIn('converta', aviso['texto'])
        self.assertIn('descarte explícito', aviso['texto'])
        self.assertEqual(
            aviso['rotulo_descarte'],
            'Área lida em m², descartada pelo revisor.',
        )
        self.assertTrue(aviso['bloqueante'])
        self.assertNotIn('/acts/', json.dumps(aviso, ensure_ascii=False))

    def test_a_pendencia_da_area_vem_antes_dos_avisos_informativos(self):
        resultado = self._prefill(self._com_area(
            '120.00', 'área construída 120,00 m2', 'm2',
        ))

        self.assertEqual(resultado['pendencias'][0]['motivo'], 'unidade_area')
        self.assertEqual(
            [aviso['rotulo'] for aviso in resultado['pendencias']],
            ['Área', 'CPF/RG das partes', 'Valor da transação'],
        )

    def test_cada_unidade_aparece_com_o_proprio_nome(self):
        for codigo, nome in (
            ('alqueires', '12,5 alqueires'), ('ares', '12,5 ares'),
            ('m2', '12,5 m²'),
        ):
            with self.subTest(unidade=codigo):
                resultado = self._prefill(self._com_area(
                    '12.50', 'área 12,50 ha', codigo,
                ))

                (aviso,) = self._pendencias_da_area(resultado)
                self.assertIn(f'{nome} no documento', aviso['texto'])
                self.assertNotIn('area', resultado['form_data'])

    def test_unidade_nao_identificada_tambem_nao_vira_hectare(self):
        resultado = self._prefill(self._com_area('120.00', 'área 12,50 ha', None))

        (aviso,) = self._pendencias_da_area(resultado)
        self.assertIn('120 no documento (unidade não identificada)', aviso['texto'])
        self.assertNotIn('area', resultado['form_data'])

    def test_hectare_preenche_normalmente(self):
        resultado = self._prefill(self._com_area(
            '12.50', 'área 12,50 ha', 'ha', raw='12,50 ha',
        ))

        self.assertEqual(resultado['form_data']['area'], '12.50')
        self.assertEqual(resultado['evidencias']['area']['trecho'], 'área 12,50 ha')
        self.assertEqual(self._pendencias_da_area(resultado), [])

    def test_conversao_confirmada_pelo_revisor_preenche_o_valor_em_hectares(self):
        extracao = self._aberta(self._com_area(
            '120.00', 'área construída 120,00 m2', 'm2',
        ))
        # O que a conversão confirmada na revisão antiga deixa na linha:
        # valor em ha, flag ligada e o motivo da unidade resolvido.
        extracao.campos.filter(chave='/acts/0/area').update(
            valor_final='0.01', area_convertida=True, status_revisao='editado',
            motivos_revisao=[],
        )

        resultado = prefill_do_ato(extracao, 0, self.documento)

        self.assertEqual(resultado['form_data']['area'], '0.01')
        self.assertEqual(self._pendencias_da_area(resultado), [])

    def test_area_descartada_nao_gera_pendencia(self):
        extracao = self._aberta(self._com_area(
            '120.00', 'área construída 120,00 m2', 'm2',
        ))
        extracao.campos.filter(chave='/acts/0/area').update(
            status_revisao='descartado',
        )

        resultado = prefill_do_ato(extracao, 0, self.documento)

        self.assertNotIn('area', resultado['form_data'])
        self.assertEqual(self._pendencias_da_area(resultado), [])
