"""``FormaETituloTest`` — migração VERBATIM de
``ia_ocr/tests/test_revisao_formulario_prefill.py`` (Etapa 13 do
plano de 400 linhas).
"""

class FormaETituloTestParte:
    def test_forma_da_averbacao_vai_para_forma_averbacao(self):
        form_data = self._prefill(self._averbacao(
            forma=self._campo('Retificação', 'Av-1/42.718'),
        ))['form_data']

        self.assertEqual(form_data['forma_averbacao'], 'Retificação')
        self.assertNotIn('forma_transacao', form_data)

    def test_forma_do_registro_vai_para_forma_transacao(self):
        form_data = self._prefill(self._registro(
            forma=self._campo('Compra e Venda', 'Escritura Pública'),
        ))['form_data']

        self.assertEqual(form_data['forma_transacao'], 'Compra e Venda')
        self.assertNotIn('forma_averbacao', form_data)

    def test_forma_do_inicio_de_matricula_vai_para_forma_transacao(self):
        form_data = self._prefill(self._registro(
            tipo_sugerido=self._campo('inicio_matricula', 'R-1/42.718'),
            rotulo=self._campo('M-1', 'R-1/42.718'),
            forma=self._campo('Abertura', 'R-1/42.718'),
        ))['form_data']

        self.assertEqual(form_data['tipo_lancamento'], str(self.tipo_inicio.pk))
        self.assertEqual(form_data['forma_transacao'], 'Abertura')
        self.assertNotIn('forma_averbacao', form_data)

    def test_titulo_so_em_titulo_transacao(self):
        form_data = self._prefill(self._registro(
            titulo=self._campo('Escritura de compra', 'Escritura Pública'),
        ))['form_data']

        self.assertEqual(form_data['titulo_transacao'], 'Escritura de compra')
        self.assertNotIn('titulo', form_data)

    def _aviso_da_forma(self, resultado):
        return [
            aviso for aviso in resultado['pendencias']
            if aviso['motivo'] == 'forma_ajustada_vocabulario'
        ]

    def test_forma_casa_no_vocabulario_pinado(self):
        resultado = self._prefill(self._registro(
            forma=self._campo('Venda e compra', 'Escritura Pública'),
        ))

        self.assertEqual(
            resultado['form_data']['forma_transacao'], 'Compra e Venda',
        )
        self.assertEqual(self._aviso_da_forma(resultado), [])

    def test_forma_desconhecida_mantem_o_valor_do_a3_sem_aviso(self):
        resultado = self._prefill(self._registro(
            forma=self._campo('Permuta', 'Escritura Pública'),
        ))

        self.assertEqual(resultado['form_data']['forma_transacao'], 'Permuta')
        self.assertEqual(self._aviso_da_forma(resultado), [])

    def test_forma_aproximada_ajusta_e_avisa(self):
        resultado = self._prefill(self._registro(
            forma=self._campo('Comrpa e Venda', 'Escritura Pública'),
        ))

        self.assertEqual(
            resultado['form_data']['forma_transacao'], 'Compra e Venda',
        )
        (aviso,) = self._aviso_da_forma(resultado)
        self.assertFalse(aviso['bloqueante'])
