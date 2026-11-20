"""``EvidenciaTest`` — migração VERBATIM de
``ia_ocr/tests/test_revisao_formulario_prefill.py`` (Etapa 13 do
plano de 400 linhas).
"""
import json

from dominial.models import Documento
from ia_ocr import destinos
from ia_ocr.formulario import CHAVE_PARA_INPUT, input_do_campo, prefill_do_ato

from .payloads_extracao import payload_registro

class EvidenciaTestParte:
    def test_evidencia_dos_campos_do_ato(self):
        evidencias = self._prefill(payload_registro(self.job.job_id))['evidencias']

        self.assertEqual(evidencias['data'], {
            'pagina': 1, 'trecho': '15 de fevereiro de 2020',
            'confianca_baixa': False,
        })
        self.assertEqual(evidencias['tipo_lancamento']['trecho'], 'R-1/42.718')
        self.assertEqual(
            evidencias['numero_lancamento_simples']['trecho'], 'R-1/42.718',
        )
        self.assertEqual(evidencias['area']['trecho'], 'área 12,50 ha')
        self.assertEqual(evidencias['livro_documento']['trecho'], 'Livro 2-RG')

    def test_chave_da_evidencia_segue_a_forma_da_averbacao(self):
        evidencias = self._prefill(self._averbacao(
            forma=self._campo('Retificação', 'Av-1/42.718'),
        ))['evidencias']

        self.assertIn('forma_averbacao', evidencias)
        self.assertNotIn('forma_transacao', evidencias)

    def test_evidencia_das_partes_pela_posicao_na_lista(self):
        evidencias = self._prefill(payload_registro(self.job.job_id))['evidencias']

        self.assertEqual(evidencias['transmitente_nome[0]']['trecho'], 'JOÃO DA SILVA')
        self.assertEqual(evidencias['transmitente_nome[1]']['trecho'], 'MARIA DA SILVA')
        self.assertEqual(evidencias['adquirente_nome[0]']['trecho'], 'PEDRO SANTOS')

    def test_posicao_conta_so_as_partes_que_entraram(self):
        extracao = self._aberta(payload_registro(self.job.job_id))
        extracao.campos.filter(chave='/acts/0/partes/0').update(
            status_revisao='descartado',
        )

        evidencias = prefill_do_ato(extracao, 0, self.documento)['evidencias']

        self.assertEqual(evidencias['transmitente_nome[0]']['trecho'], 'MARIA DA SILVA')
        self.assertNotIn('transmitente_nome[1]', evidencias)

    def test_trecho_sai_mascarado(self):
        payload = payload_registro(self.job.job_id)
        payload['acts'][0]['partes'][0]['nome'] = self._campo(
            'JOÃO DA SILVA', 'JOÃO DA SILVA (CPF 123.456.789-00)',
        )

        evidencias = self._prefill(payload)['evidencias']

        trecho = evidencias['transmitente_nome[0]']['trecho']
        self.assertEqual(trecho, 'JOÃO DA SILVA (CPF ***)')
        self.assertNotIn('123.456.789-00', json.dumps(evidencias))

    def test_baixa_confianca_marca_a_evidencia(self):
        payload = payload_registro(self.job.job_id)
        payload['acts'][0]['data']['confianca'] = 0.4

        evidencias = self._prefill(payload)['evidencias']

        self.assertTrue(evidencias['data']['confianca_baixa'])
        self.assertFalse(evidencias['area']['confianca_baixa'])

    def test_evidencia_so_dos_inputs_preenchidos(self):
        extracao = self._aberta(payload_registro(self.job.job_id))
        extracao.campos.filter(chave='/acts/0/area').update(
            status_revisao='descartado',
        )
        Documento.objects.filter(pk=self.documento.pk).update(livro='7')
        self.documento.refresh_from_db()

        resultado = prefill_do_ato(extracao, 0, self.documento)

        self.assertNotIn('area', resultado['evidencias'])
        self.assertNotIn('livro_documento', resultado['evidencias'])
        self.assertLessEqual(
            {
                nome for nome in resultado['evidencias']
                if '[' not in nome
            },
            set(resultado['form_data']),
        )

    def test_evidencia_da_origem_pela_posicao_zero(self):
        payload = self._registro()
        payload['acts'][0]['origem'] = {
            'tipo_documento': self._campo('transcricao', 'MATRÍCULA Nº 42.718'),
            'numero': self._campo('T366', '42.718'),
            'cartorio': self._campo('CRI de Origem', 'CRI de Guaíra'),
            'livro': self._campo('2', 'Livro 2-RG'),
            'folha': self._campo('123', 'Folha 087'),
        }

        evidencias = self._prefill(payload)['evidencias']

        self.assertEqual(evidencias['numero_origem[0]']['trecho'], '42.718')
        self.assertEqual(evidencias['cartorio_origem_nome[0]']['trecho'], 'CRI de Guaíra')
        self.assertEqual(evidencias['livro_origem[0]']['trecho'], 'Livro 2-RG')
        self.assertEqual(evidencias['folha_origem[0]']['trecho'], 'Folha 087')

    def test_tabela_unica_de_inputs(self):
        self.assertEqual(input_do_campo('/acts/3/data'), 'data')
        self.assertEqual(input_do_campo('/acts/*/data'), 'data')
        self.assertEqual(input_do_campo('/acts/0/forma', 'registro'), 'forma_transacao')
        self.assertEqual(input_do_campo('/acts/0/forma', 'averbacao'), 'forma_averbacao')
        self.assertEqual(
            input_do_campo('/acts/0/partes/4/nome', papel='adquirente'),
            'adquirente_nome',
        )
        self.assertIsNone(input_do_campo('/acts/0/valor_transacao'))
        self.assertIsNone(input_do_campo('/acts/0/partes/0/documento_identificacao/valor'))
        # As chaves da tabela são padrões reais do mapa de destinos (sem
        # erro de digitação que deixaria uma linha sem input).
        for padrao in CHAVE_PARA_INPUT:
            with self.subTest(padrao=padrao):
                self.assertIn(padrao, destinos.DESTINOS)
