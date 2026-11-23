"""``AreaEmOutraUnidadeTest`` — área que NÃO pôde virar hectares (#341/#373).

``m²`` e o composto hectare/are/centiare são convertidos na
desnormalização (#373); só ``alqueires``, unidade ausente e texto ilegível
continuam exigindo decisão do revisor (M3/#341).
"""
import json

from ia_ocr.formulario import prefill_do_ato


class AreaEmOutraUnidadeTestParte:
    """O input da área é em HECTARES — só converte o que é inequívoco."""

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

    def test_metro_quadrado_converte_para_hectares(self):
        resultado = self._prefill(self._com_area(
            None, 'área construída 120,00 m2', 'm2', raw='120,00 m2',
        ))

        self.assertEqual(resultado['form_data']['area'], '0.0120')
        self.assertEqual(self._pendencias_da_area(resultado), [])

    def test_composto_hectare_are_centiare_converte_sem_unidade(self):
        texto = 'área 169 hectares, 09 ares e 40 centiares'
        resultado = self._prefill(self._com_area(
            None, texto, None, raw='169 hectares, 09 ares e 40 centiares',
        ))

        self.assertEqual(resultado['form_data']['area'], '169.0940')
        self.assertEqual(self._pendencias_da_area(resultado), [])

    def test_alqueires_vira_pendencia_do_revisor(self):
        resultado = self._prefill(self._com_area(
            '12.50', 'área 12,50 alqueires', 'alqueires',
            raw='12,50 alqueires',
        ))

        (aviso,) = self._pendencias_da_area(resultado)
        self.assertEqual(aviso['rotulo'], 'Área')
        self.assertIn('12,5 alqueires no documento', aviso['texto'])
        self.assertIn('converta', aviso['texto'])
        self.assertIn('descarte explícito', aviso['texto'])
        self.assertEqual(
            aviso['rotulo_descarte'],
            'Área lida em alqueires, descartada pelo revisor.',
        )
        self.assertTrue(aviso['bloqueante'])
        self.assertNotIn('area', resultado['form_data'])
        self.assertNotIn('/acts/', json.dumps(aviso, ensure_ascii=False))

    def test_a_pendencia_da_area_vem_antes_dos_avisos_informativos(self):
        resultado = self._prefill(self._com_area(
            '12.50', 'área 12,50 alqueires', 'alqueires',
            raw='12,50 alqueires',
        ))

        self.assertEqual(resultado['pendencias'][0]['motivo'], 'unidade_area')
        self.assertEqual(
            [aviso['rotulo'] for aviso in resultado['pendencias']],
            ['Área', 'CPF/RG das partes', 'Valor da transação'],
        )

    def test_unidade_sem_conversao_aparece_com_o_proprio_nome(self):
        for codigo, nome, raw in (
            ('alqueires', '12,5 alqueires', '12,50 alqueires'),
            ('ares', '12,5 ares', '12,50 ares'),
        ):
            with self.subTest(unidade=codigo):
                resultado = self._prefill(self._com_area(
                    '12.50', 'área 12,50 ha', codigo, raw=raw,
                ))

                (aviso,) = self._pendencias_da_area(resultado)
                self.assertIn(f'{nome} no documento', aviso['texto'])
                self.assertNotIn('area', resultado['form_data'])

    def test_unidade_nao_identificada_sem_sufixo_tambem_nao_vira_hectare(self):
        resultado = self._prefill(self._com_area(
            '120.00', 'área 120,00', None, raw='120,00',
        ))

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

    def test_canonico_de_tres_casas_chega_ao_input_com_quatro(self):
        # #396: `74.675` é canônico do A3 (decimal). Sem normalizar, o parser
        # único o trataria como ambíguo e a revisão travaria no formulário.
        resultado = self._prefill(self._com_area(
            '74.675', 'área 74,675 ha', 'ha', raw='74,675 ha',
        ))

        self.assertEqual(resultado['form_data']['area'], '74.6750')
        self.assertEqual(self._pendencias_da_area(resultado), [])

    def test_conversao_confirmada_pelo_revisor_preenche_o_valor_em_hectares(self):
        extracao = self._aberta(self._com_area(
            '12.50', 'área 12,50 alqueires', 'alqueires',
            raw='12,50 alqueires',
        ))
        # O que a conversão confirmada na revisão antiga deixa na linha:
        # valor em ha, flag ligada e o motivo da unidade resolvido.
        extracao.campos.filter(chave='/acts/0/area').update(
            valor_final='0.0120', area_convertida=True, status_revisao='editado',
            motivos_revisao=[],
        )

        resultado = prefill_do_ato(extracao, 0, self.documento)

        self.assertEqual(resultado['form_data']['area'], '0.0120')
        self.assertEqual(self._pendencias_da_area(resultado), [])

    def test_area_descartada_nao_gera_pendencia(self):
        extracao = self._aberta(self._com_area(
            '12.50', 'área 12,50 alqueires', 'alqueires',
            raw='12,50 alqueires',
        ))
        extracao.campos.filter(chave='/acts/0/area').update(
            status_revisao='descartado',
        )

        resultado = prefill_do_ato(extracao, 0, self.documento)

        self.assertNotIn('area', resultado['form_data'])
        self.assertEqual(self._pendencias_da_area(resultado), [])
