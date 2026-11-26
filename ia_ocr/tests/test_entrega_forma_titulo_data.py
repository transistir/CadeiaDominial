"""Entrega do app, item 4: forma / título / data_transacao.

Convenção do card: ``forma`` = natureza (ex. "Compra e Venda"),
``titulo`` = instrumento (ex. "Escritura Pública") e ``data_transacao`` =
data do instrumento. O A3 às vezes inverte forma e título e manda a data do
registro em ``data_transacao``.

A regra é determinística: classifica cada texto como instrumento (marcas
listadas no brief) ou natureza, troca só quando exatamente um é instrumento,
aplica o vocabulário na natureza e extrai a data explícita do instrumento
(extenso ou dd.mm.aaaa). Toda reinterpretação vira pendência informativa.
"""

from copy import deepcopy

from ia_ocr.formulario import prefill_do_ato

from .payloads_extracao import payload_m237_abertura
from .test_revisao_formulario_prefill_base import PrefillBase

MOTIVO_FORMA_TITULO = 'forma_titulo_reinterpretados'
MOTIVO_DATA_INSTRUMENTO = 'data_transacao_do_instrumento'

_EVIDENCIA_GENERICA = 'Escritura Pública de Compra e Venda'


class _FormaTituloBase(PrefillBase):
    def _pendencia(self, resultado, motivo):
        return [
            aviso for aviso in resultado['pendencias']
            if aviso['motivo'] == motivo
        ]

    def _motivos(self, resultado):
        return {aviso['motivo'] for aviso in resultado['pendencias']}


class SwapFormaTituloTest(_FormaTituloBase):
    def test_forma_instrumento_e_titulo_natureza_swap(self):
        resultado = self._prefill(self._registro(
            forma=self._campo(
                'Escritura pública de 10 de abril de 2015',
                _EVIDENCIA_GENERICA,
            ),
            titulo=self._campo('Venda e Compra', _EVIDENCIA_GENERICA),
        ))

        form_data = resultado['form_data']
        self.assertEqual(form_data['forma_transacao'], 'Compra e Venda')
        self.assertEqual(
            form_data['titulo_transacao'],
            'Escritura pública de 10 de abril de 2015',
        )
        (pendencia,) = self._pendencia(resultado, MOTIVO_FORMA_TITULO)
        self.assertFalse(pendencia['bloqueante'])
        self.assertTrue(pendencia['texto'].strip())

    def test_titulo_instrumento_e_forma_natureza_swap(self):
        resultado = self._prefill(self._registro(
            forma=self._campo('Compra e Venda', _EVIDENCIA_GENERICA),
            titulo=self._campo(
                'Escritura Pública de Compra e Venda', _EVIDENCIA_GENERICA,
            ),
        ))

        form_data = resultado['form_data']
        self.assertEqual(form_data['forma_transacao'], 'Compra e Venda')
        self.assertEqual(
            form_data['titulo_transacao'],
            'Escritura Pública de Compra e Venda',
        )
        (pendencia,) = self._pendencia(resultado, MOTIVO_FORMA_TITULO)
        self.assertFalse(pendencia['bloqueante'])

    def test_ambos_natureza_nao_swap(self):
        resultado = self._prefill(self._registro(
            forma=self._campo('Compra e Venda', _EVIDENCIA_GENERICA),
            titulo=self._campo('Doação', _EVIDENCIA_GENERICA),
        ))

        form_data = resultado['form_data']
        self.assertEqual(form_data['forma_transacao'], 'Compra e Venda')
        self.assertEqual(form_data['titulo_transacao'], 'Doação')
        self.assertNotIn(MOTIVO_FORMA_TITULO, self._motivos(resultado))

    def test_ambos_instrumento_nao_swap(self):
        resultado = self._prefill(self._registro(
            forma=self._campo('Escritura Pública', _EVIDENCIA_GENERICA),
            titulo=self._campo(
                'Escritura de Compra e Venda', _EVIDENCIA_GENERICA,
            ),
        ))

        form_data = resultado['form_data']
        self.assertEqual(form_data['forma_transacao'], 'Escritura Pública')
        self.assertEqual(
            form_data['titulo_transacao'], 'Escritura de Compra e Venda',
        )
        self.assertNotIn(MOTIVO_FORMA_TITULO, self._motivos(resultado))

    def test_sem_forma_e_titulo_nao_preenche_nem_avisa(self):
        resultado = self._prefill(self._registro())

        self.assertNotIn('forma_transacao', resultado['form_data'])
        self.assertNotIn('titulo_transacao', resultado['form_data'])
        self.assertNotIn(MOTIVO_FORMA_TITULO, self._motivos(resultado))


class DataDoInstrumentoTest(_FormaTituloBase):
    def test_data_por_extenso_vence_o_a3_e_nomeia_as_duas_datas(self):
        resultado = self._prefill(self._registro(
            forma=self._campo(
                'Escritura pública de 10 de abril de 2015',
                _EVIDENCIA_GENERICA,
            ),
            data_transacao=self._campo(
                '2015-06-18', '15 de fevereiro de 2020',
            ),
        ))

        self.assertEqual(
            resultado['form_data']['data_transacao'], '2015-04-10',
        )
        (pendencia,) = self._pendencia(resultado, MOTIVO_DATA_INSTRUMENTO)
        self.assertFalse(pendencia['bloqueante'])
        self.assertIn('2015-06-18', pendencia['texto'])
        self.assertIn('2015-04-10', pendencia['texto'])

    def test_data_numerica_com_ponto_no_instrumento(self):
        resultado = self._prefill(self._registro(
            forma=self._campo(
                'Escritura pública de 10.04.2015', _EVIDENCIA_GENERICA,
            ),
            data_transacao=self._campo(
                '2015-06-18', '15 de fevereiro de 2020',
            ),
        ))

        self.assertEqual(
            resultado['form_data']['data_transacao'], '2015-04-10',
        )

    def test_data_numerica_com_barra_no_instrumento(self):
        resultado = self._prefill(self._registro(
            forma=self._campo(
                'Escritura pública de 10/04/2015', _EVIDENCIA_GENERICA,
            ),
            data_transacao=self._campo(
                '2015-06-18', '15 de fevereiro de 2020',
            ),
        ))

        self.assertEqual(
            resultado['form_data']['data_transacao'], '2015-04-10',
        )

    def test_instrumento_sem_data_mantem_o_a3(self):
        resultado = self._prefill(self._registro(
            forma=self._campo('Escritura Pública', _EVIDENCIA_GENERICA),
            data_transacao=self._campo(
                '2015-06-18', '15 de fevereiro de 2020',
            ),
        ))

        self.assertEqual(
            resultado['form_data']['data_transacao'], '2015-06-18',
        )
        self.assertNotIn(MOTIVO_DATA_INSTRUMENTO, self._motivos(resultado))

    def test_data_fora_do_calendario_nao_deriva(self):
        resultado = self._prefill(self._registro(
            forma=self._campo(
                'Escritura pública de 31 de fevereiro de 2015',
                _EVIDENCIA_GENERICA,
            ),
            data_transacao=self._campo(
                '2015-06-18', '15 de fevereiro de 2020',
            ),
        ))

        self.assertEqual(
            resultado['form_data']['data_transacao'], '2015-06-18',
        )
        self.assertNotIn(MOTIVO_DATA_INSTRUMENTO, self._motivos(resultado))

    def test_sem_forma_titulo_nao_deriva_data(self):
        resultado = self._prefill(self._registro(
            data_transacao=self._campo(
                '2015-06-18', '15 de fevereiro de 2020',
            ),
        ))

        self.assertEqual(
            resultado['form_data']['data_transacao'], '2015-06-18',
        )
        self.assertNotIn(MOTIVO_DATA_INSTRUMENTO, self._motivos(resultado))


class M6141RegressaoTest(_FormaTituloBase):
    """Fluxo real medido no M6141: 2 atos, área 74.6755, origem M237/2/237."""

    def _payload_m6141(self):
        payload = self._registro(
            forma=self._campo(
                'Escritura pública de 10 de abril de 2015',
                _EVIDENCIA_GENERICA,
            ),
            titulo=self._campo('Venda e Compra', _EVIDENCIA_GENERICA),
            data_transacao=self._campo(
                '2015-06-18', '15 de fevereiro de 2020',
            ),
            area={
                'raw': '74,6755 ha',
                'normalized': '74.6755',
                'confianca': 0.95,
                'requer_revisao': False,
                'unidade': 'ha',
                'evidencia': {'pagina': 1, 'trecho': '12,50 ha'},
            },
        )
        payload['acts'][0]['origem'] = {
            'tipo_documento': self._campo('matricula', 'MATRÍCULA Nº 42.718'),
            'numero': self._campo('237', 'Nº 42.718'),
            'cartorio': self._campo('CRI de Guaíra', 'CRI de Guaíra'),
            'livro': self._campo('2', 'Livro 2-RG'),
            'folha': self._campo('237', 'Folha 087'),
        }
        segundo = deepcopy(payload['acts'][0])
        segundo['ordem'] = 2
        segundo['rotulo'] = self._campo('R-2', 'R-1/42.718')
        payload['acts'].append(segundo)
        return payload

    def test_prefill_do_r1_reinterpreta_forma_titulo_e_data(self):
        resultado = prefill_do_ato(
            self._aberta(self._payload_m6141()),
            0,
            self.documento,
        )

        self.assertEqual(len(resultado['form_data']) > 0, True)
        self.assertEqual(resultado['form_data']['area'], '74.6755')
        self.assertEqual(resultado['form_data']['forma_transacao'], 'Compra e Venda')
        self.assertEqual(
            resultado['form_data']['titulo_transacao'],
            'Escritura pública de 10 de abril de 2015',
        )
        self.assertEqual(
            resultado['form_data']['data_transacao'], '2015-04-10',
        )
        (origem,) = resultado['origens_separadas']
        self.assertEqual(origem['texto'], 'M237')
        self.assertEqual(origem['livro'], '2')
        self.assertEqual(origem['folha'], '237')
        self.assertIn(MOTIVO_FORMA_TITULO, self._motivos(resultado))
        self.assertIn(MOTIVO_DATA_INSTRUMENTO, self._motivos(resultado))

    def test_dois_atos_preservados(self):
        extracao = self._aberta(self._payload_m6141())

        primeiro = prefill_do_ato(extracao, 0, self.documento)
        segundo = prefill_do_ato(extracao, 1, self.documento)

        self.assertEqual(
            primeiro['form_data']['data_transacao'], '2015-04-10',
        )
        self.assertEqual(
            segundo['form_data']['data_transacao'], '2015-04-10',
        )


class M237SemFormaTituloTest(PrefillBase):
    """M237: atos sem forma/título seguem sem reinterpretação."""

    def test_r1_sem_forma_titulo_fica_inalterado(self):
        payload = payload_m237_abertura(self.job.job_id)

        resultado = prefill_do_ato(
            self._aberta(payload), 1, self.documento,
        )

        self.assertNotIn('forma_transacao', resultado['form_data'])
        self.assertNotIn('titulo_transacao', resultado['form_data'])
        self.assertNotIn('data_transacao', resultado['form_data'])
        motivos = {aviso['motivo'] for aviso in resultado['pendencias']}
        self.assertNotIn(MOTIVO_FORMA_TITULO, motivos)
        self.assertNotIn(MOTIVO_DATA_INSTRUMENTO, motivos)
