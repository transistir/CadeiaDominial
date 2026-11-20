"""``TransmissaoETextosTest`` — migração VERBATIM de
``ia_ocr/tests/test_revisao_formulario_prefill.py`` (Etapa 13 do
plano de 400 linhas).
"""
from dominial.models import Cartorios, Documento
from ia_ocr.formulario import prefill_do_ato

from .payloads_extracao import payload_registro

class TransmissaoETextosTestParte:
    def test_transmissao_com_cartorio_escolhido(self):
        cartorio = self._cartorio('Cartório de Registro da Transmissão')
        extracao = self._aberta(self._registro(
            cartorio_transmissao=self._campo('CRI de Guaíra', 'CRI de Guaíra'),
            livro_transacao=self._campo('10-A', 'Livro 2-RG'),
            folha_transacao=self._campo('25v', 'Folha 087'),
            data_transacao=self._campo('2019-12-20', '10 de janeiro de 2020'),
        ))
        extracao.campos.filter(chave='/acts/0/cartorio_transmissao').update(
            cartorio_escolhido=cartorio,
        )

        form_data = prefill_do_ato(extracao, 0, self.documento)['form_data']

        self.assertEqual(form_data['cartorio_transmissao'], str(cartorio.pk))
        # O nome é o do CADASTRO (o que o autocomplete grava no input), não
        # o texto que o OCR leu.
        self.assertEqual(
            form_data['cartorio_transmissao_nome'],
            'Cartório de Registro da Transmissão',
        )
        self.assertEqual(form_data['livro_transacao'], '10-A')
        self.assertEqual(form_data['folha_transacao'], '25v')
        self.assertEqual(form_data['data_transacao'], '2019-12-20')

    def test_cartorio_criar_novo_entra_so_com_o_nome(self):
        extracao = self._aberta(self._registro(
            cartorio_transmissao=self._campo('CRI de Guaíra', 'CRI de Guaíra'),
        ))
        extracao.campos.filter(chave='/acts/0/cartorio_transmissao').update(
            criar_novo=True,
        )

        form_data = prefill_do_ato(extracao, 0, self.documento)['form_data']

        self.assertEqual(form_data['cartorio_transmissao_nome'], 'CRI de Guaíra')
        self.assertNotIn('cartorio_transmissao', form_data)
        self.assertFalse(Cartorios.objects.filter(nome='CRI de Guaíra').exists())

    def test_cartorio_sem_decisao_entra_so_com_o_nome(self):
        form_data = self._prefill(self._registro(
            cartorio_transmissao=self._campo('CRI de Guaíra', 'CRI de Guaíra'),
        ))['form_data']

        self.assertEqual(form_data['cartorio_transmissao_nome'], 'CRI de Guaíra')
        self.assertNotIn('cartorio_transmissao', form_data)

    def test_data_area_descricao_e_observacoes(self):
        form_data = self._prefill(self._registro(
            descricao=self._campo('Descrição do ato', 'Escritura Pública'),
            observacoes=self._campo('Observação do ato', 'Escritura Pública'),
        ))['form_data']

        self.assertEqual(form_data['data'], '2020-02-15')
        self.assertEqual(form_data['area'], '12.50')
        self.assertEqual(form_data['descricao'], 'Descrição do ato')
        self.assertEqual(form_data['observacoes'], 'Observação do ato')

    def test_campo_descartado_nao_entra(self):
        extracao = self._aberta(payload_registro(self.job.job_id))
        extracao.campos.filter(chave='/acts/0/area').update(
            status_revisao='descartado',
        )

        form_data = prefill_do_ato(extracao, 0, self.documento)['form_data']

        self.assertNotIn('area', form_data)

    def test_valor_editado_na_revisao_vence_o_lido(self):
        extracao = self._aberta(payload_registro(self.job.job_id))
        extracao.campos.filter(chave='/acts/0/data').update(
            valor_final='2020-03-01', status_revisao='editado',
        )

        form_data = prefill_do_ato(extracao, 0, self.documento)['form_data']

        self.assertEqual(form_data['data'], '2020-03-01')

    def test_livro_e_folha_do_documento_so_se_ainda_nao_definidos(self):
        form_data = self._prefill(payload_registro(self.job.job_id))['form_data']
        self.assertEqual(form_data['livro_documento'], '2-RG')
        self.assertEqual(form_data['folha_documento'], '087')

        # '0' conta como não definido (#218); livro já definido é travado.
        Documento.objects.filter(pk=self.documento.pk).update(
            livro='7', folha='0',
        )
        self.documento.refresh_from_db()
        form_data = self._prefill(payload_registro(self.job.job_id))['form_data']

        self.assertNotIn('livro_documento', form_data)
        self.assertEqual(form_data['folha_documento'], '087')

    def test_form_data_so_tem_valores_em_texto(self):
        form_data = self._prefill(payload_registro(self.job.job_id))['form_data']

        self.assertTrue(form_data)
        for nome, valor in form_data.items():
            with self.subTest(nome=nome):
                self.assertIsInstance(valor, str)
                self.assertTrue(valor.strip())
