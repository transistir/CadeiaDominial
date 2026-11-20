"""``TipoENumeroTest`` — migração VERBATIM de
``ia_ocr/tests/test_revisao_formulario_prefill.py`` (Etapa 13 do
plano de 400 linhas).
"""
from types import SimpleNamespace

from dominial.models import LancamentoTipo
from dominial.services.lancamento_form_service import LancamentoFormService

from .payloads_extracao import payload_registro

class TipoENumeroTestParte:
    def test_tipo_e_numero_simples_do_registro(self):
        resultado = self._prefill(payload_registro(self.job.job_id))

        form_data = resultado['form_data']
        self.assertEqual(form_data['tipo_lancamento'], str(self.tipo_registro.pk))
        self.assertEqual(form_data['numero_lancamento_simples'], '1')

    def test_numero_composto_sai_do_gerador_do_formulario_manual(self):
        # M1 (#341): o HTML precisa carregar o composto. Sem ele, o JS do
        # formulário manual preenche só a sigla ("M237") e o POST salva isso
        # em vez de "R1 M237" (ou apaga o número simples, em modo de edição).
        form_data = self._prefill(payload_registro(self.job.job_id))['form_data']

        self.assertEqual(form_data['numero_lancamento_simples'], '1')
        self.assertEqual(form_data['numero_lancamento'], 'R1 M237')
        # É o resultado do gerador do POST manual, não uma segunda regra.
        pedido = SimpleNamespace(POST={'sigla_matricula': self.documento.numero})
        self.assertEqual(
            form_data['numero_lancamento'],
            LancamentoFormService._gerar_numero_lancamento(
                '1', self.tipo_registro, pedido,
            ),
        )

    def test_numero_composto_da_averbacao_e_do_inicio_de_matricula(self):
        averbacao = self._prefill(self._averbacao(
            rotulo=self._campo('Av-6', 'Av-1/42.718'),
        ))['form_data']
        inicio = self._prefill(self._registro(
            tipo_sugerido=self._campo('inicio_matricula', 'R-1/42.718'),
            rotulo=self._campo('M-1', 'R-1/42.718'),
        ))['form_data']

        self.assertEqual(averbacao['numero_lancamento'], 'AV6 M237')
        # Início de matrícula: o número completo é a própria sigla.
        self.assertEqual(inicio['tipo_lancamento'], str(self.tipo_inicio.pk))
        self.assertEqual(inicio['numero_lancamento'], 'M237')

    def test_sem_numero_de_ato_nao_inventa_composto(self):
        form_data = self._prefill(self._registro(
            rotulo=self._campo('M-3-14511', 'R-1/42.718'),
        ))['form_data']

        self.assertNotIn('numero_lancamento_simples', form_data)
        self.assertNotIn('numero_lancamento', form_data)

    def test_sem_tipo_configurado_nao_ha_composto(self):
        LancamentoTipo.objects.filter(tipo='registro').delete()

        form_data = self._prefill(payload_registro(self.job.job_id))['form_data']

        self.assertNotIn('numero_lancamento', form_data)

    def test_averbacao_pelo_rotulo(self):
        form_data = self._prefill(self._averbacao(
            rotulo=self._campo('Av-6', 'Av-1/42.718'),
        ))['form_data']

        self.assertEqual(form_data['tipo_lancamento'], str(self.tipo_averbacao.pk))
        self.assertEqual(form_data['numero_lancamento_simples'], '6')

    def test_tipo_segue_o_resolvedor_da_gravacao(self):
        # Rótulo R × tipo_sugerido averbação: o rótulo vence, como na
        # gravação — o prefill não decide o tipo por conta própria.
        form_data = self._prefill(self._registro(
            rotulo=self._campo('R-5', 'R-1/42.718'),
            tipo_sugerido=self._campo('averbacao', 'R-1/42.718'),
        ))['form_data']

        self.assertEqual(form_data['tipo_lancamento'], str(self.tipo_registro.pk))
        self.assertEqual(form_data['numero_lancamento_simples'], '5')

    def test_rotulo_de_matricula_usa_o_numero_de_ato_da_revisao(self):
        form_data = self._prefill(self._registro(
            rotulo=self._campo('M-3-14511', 'R-1/42.718'),
            numero_lancamento=self._campo('R-7', 'R-1/42.718'),
        ))['form_data']

        self.assertEqual(form_data['numero_lancamento_simples'], '7')

    def test_sem_numero_de_ato_nao_inventa_numero(self):
        form_data = self._prefill(self._registro(
            rotulo=self._campo('M-3-14511', 'R-1/42.718'),
        ))['form_data']

        self.assertNotIn('numero_lancamento_simples', form_data)

    def test_tipo_nao_configurado_fica_de_fora(self):
        LancamentoTipo.objects.filter(tipo='registro').delete()

        form_data = self._prefill(payload_registro(self.job.job_id))['form_data']

        self.assertNotIn('tipo_lancamento', form_data)
