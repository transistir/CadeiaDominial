"""Testes da desnormalização do payload A3 em CampoSugerido (I-5, §18).

Um teste por comportamento: chaves JSON Pointer + tipo_valor, placeholders
dos obrigatórios ausentes, baixa confiança forçando revisão, closure sempre
em revisão e evidência (página inexistente / trecho ausente). As linhas
voltam sem pk e ``desnormalizar`` não toca o banco (assertNumQueries(0)).
"""

from django.test import TestCase

from ia_ocr.extracao_schema import validar_payload
from ia_ocr.models import CampoSugerido, ExtracaoSugerida, OcrJob, PaginaOcr
from ia_ocr.revisao import desnormalizar

from .factories import criar_documento_digital
from .payloads_extracao import (
    SCHEMA_VERSION,
    TEXTO_PAGINA_1,
    payload_averbacao,
    payload_com_closure,
    payload_registro,
)


class DesnormalizarTest(TestCase):
    def setUp(self):
        self.job = OcrJob.objects.create(
            documento_digital=criar_documento_digital()
        )
        self.pagina = PaginaOcr.objects.create(
            ocr_job=self.job, numero_pagina=1, texto_ocr=TEXTO_PAGINA_1
        )
        self.paginas = [self.pagina]
        self.extracao = ExtracaoSugerida.objects.create(
            ocr_job=self.job,
            schema_version=SCHEMA_VERSION,
            payload={},
            payload_servico={},
            provider='local-model',
        )

    def _linhas(self, payload, validar=True):
        if validar:
            # As fixtures nascem válidas no A3 contra as páginas do job.
            validar_payload(payload, self.job.job_id, [1])
        return desnormalizar(self.extracao, payload, self.paginas)

    @staticmethod
    def _por_chave(linhas):
        return {linha.chave: linha for linha in linhas}

    def test_chaves_json_pointer_e_tipo_valor(self):
        registro = payload_registro(self.job.job_id)
        averbacao = payload_averbacao(self.job.job_id)
        validar_payload(registro, self.job.job_id, [1])
        validar_payload(averbacao, self.job.job_id, [1])

        with self.assertNumQueries(0):
            linhas = desnormalizar(self.extracao, registro, self.paginas)
            linhas_averbacao = desnormalizar(
                self.extracao, averbacao, self.paginas
            )

        por_chave = self._por_chave(linhas)
        self.assertEqual(len(por_chave), len(linhas))  # chaves únicas
        for linha in linhas:
            self.assertIsInstance(linha, CampoSugerido)
            self.assertIsNone(linha.pk)  # nada salvo
            self.assertEqual(linha.extracao, self.extracao)

        data = por_chave['/document/data']
        self.assertEqual(data.tipo_valor, 'data')
        self.assertEqual(data.raw, '10 de janeiro de 2020')
        self.assertEqual(data.normalized, '2020-01-10')
        self.assertEqual(data.confianca, 0.95)
        # Payload limpo: sem motivos, sem revisão, evidência íntegra.
        self.assertEqual(data.motivos_revisao, [])
        self.assertFalse(data.requer_revisao)
        self.assertEqual(data.evidencia_pagina, 1)
        self.assertEqual(data.evidencia_trecho, '10 de janeiro de 2020')

        nome = por_chave['/acts/0/partes/1/nome']
        self.assertEqual(nome.tipo_valor, 'texto')
        self.assertEqual(nome.normalized, 'MARIA DA SILVA')

        self.assertEqual(por_chave['/document/tipo'].tipo_valor, 'enum')
        self.assertEqual(por_chave['/document/cartorio'].tipo_valor, 'cartorio')
        self.assertEqual(
            por_chave['/acts/0/valor_transacao'].tipo_valor, 'decimal'
        )
        self.assertEqual(por_chave['/acts/0/area'].tipo_valor, 'area')
        self.assertEqual(
            por_chave['/acts/0/partes/0/documento_identificacao/valor']
            .normalized,
            '12345678900',
        )

        ato = por_chave['/acts/0']
        self.assertEqual(ato.tipo_valor, 'ato')
        self.assertEqual(ato.normalized, 'R-1')

        parte = por_chave['/acts/0/partes/2']
        self.assertEqual(parte.tipo_valor, 'parte')
        self.assertEqual(parte.normalized, 'adquirente')

        # closure=None → nenhuma linha /closure no registro.
        self.assertFalse(
            [chave for chave in por_chave if chave.startswith('/closure')]
        )

        # Averbação: descrição presente, sem origem e sem partes.
        por_chave_av = self._por_chave(linhas_averbacao)
        self.assertEqual(por_chave_av['/acts/0'].normalized, 'Av-1')
        self.assertEqual(por_chave_av['/acts/0/descricao'].tipo_valor, 'texto')
        self.assertFalse(
            [chave for chave in por_chave_av if '/origem' in chave]
        )
        self.assertFalse(
            [chave for chave in por_chave_av if '/partes' in chave]
        )

    def test_placeholders_dos_obrigatorios(self):
        completo = self._por_chave(self._linhas(payload_registro(self.job.job_id)))
        obrigatorios = (
            ('/document/tipo', 'enum'),
            ('/document/data', 'data'),
            ('/document/cartorio', 'cartorio'),
            ('/acts/0/tipo_sugerido', 'enum'),
            ('/acts/0/data', 'data'),
        )
        for chave, _tipo in obrigatorios:
            # Presentes no payload: folhas reais (com confiança), não placeholder.
            self.assertIsNotNone(completo[chave].confianca, chave)

        payload = payload_registro(self.job.job_id)
        del payload['document']['tipo']
        del payload['document']['data']
        del payload['document']['cartorio']
        del payload['acts'][0]['tipo_sugerido']
        del payload['acts'][0]['data']

        linhas = self._linhas(payload, validar=False)
        por_chave = self._por_chave(linhas)
        self.assertEqual(len(por_chave), len(linhas))  # sem chave duplicada

        for chave, tipo in obrigatorios:
            with self.subTest(chave=chave):
                linha = por_chave[chave]
                self.assertIsNone(linha.raw)
                self.assertIsNone(linha.normalized)
                self.assertIsNone(linha.confianca)
                self.assertTrue(linha.requer_revisao)
                self.assertEqual(linha.tipo_valor, tipo)
                self.assertIsNone(linha.evidencia_pagina)

    def test_baixa_confianca_forca_revisao(self):
        payload = payload_registro(self.job.job_id)
        numero = payload['document']['numero']
        numero['confianca'] = 0.42
        numero['requer_revisao'] = False  # payload diz que não precisa
        payload['document']['livro']['confianca'] = 0.70  # fronteira: não é baixa
        payload['acts'][0]['partes'][0]['confianca'] = 0.5  # linha de parte

        por_chave = self._por_chave(self._linhas(payload))

        baixa = por_chave['/document/numero']
        self.assertEqual(baixa.confianca, 0.42)
        self.assertIn('baixa_confianca', baixa.motivos_revisao)
        self.assertTrue(baixa.requer_revisao)  # forçada apesar do False

        fronteira = por_chave['/document/livro']
        self.assertNotIn('baixa_confianca', fronteira.motivos_revisao)
        self.assertFalse(fronteira.requer_revisao)

        parte = por_chave['/acts/0/partes/0']
        self.assertIn('baixa_confianca', parte.motivos_revisao)
        self.assertTrue(parte.requer_revisao)

    def test_closure_sempre_requer_revisao(self):
        payload = payload_com_closure(self.job.job_id)
        for campo in payload['closure'].values():
            campo['requer_revisao'] = False  # mesmo negando, closure revisa
            campo['confianca'] = 0.99

        linhas = self._linhas(payload)
        closure = [l for l in linhas if l.chave.startswith('/closure')]
        self.assertEqual(
            {l.chave for l in closure},
            {
                '/closure/indicio_fim_cadeia',
                '/closure/origem_publica_sugerida',
                '/closure/classificacao_sugerida',
            },
        )
        for linha in closure:
            with self.subTest(chave=linha.chave):
                self.assertIn('closure', linha.motivos_revisao)
                self.assertTrue(linha.requer_revisao)

        indicio = self._por_chave(linhas)['/closure/indicio_fim_cadeia']
        self.assertEqual(indicio.normalized, 'true')  # booleano canônico

    def test_evidencia_pagina_inexistente_e_trecho_ausente(self):
        payload = payload_registro(self.job.job_id)
        payload['document']['numero']['evidencia'] = {
            'pagina': 99,  # fora das páginas do job
            'trecho': 'Nº 42.718',
        }
        payload['document']['livro']['evidencia'] = {
            'pagina': 1,
            'trecho': 'trecho que não está no OCR',
        }
        payload['document']['folha']['evidencia'] = None  # A3 admite nula

        por_chave = self._por_chave(self._linhas(payload))

        inexistente = por_chave['/document/numero']
        self.assertIsNone(inexistente.evidencia_pagina)
        self.assertEqual(inexistente.evidencia_trecho, '')
        self.assertIn('evidencia_invalida', inexistente.motivos_revisao)
        self.assertTrue(inexistente.requer_revisao)

        ausente = por_chave['/document/livro']
        self.assertEqual(ausente.evidencia_pagina, 1)
        self.assertEqual(ausente.evidencia_trecho, '')
        self.assertIn('trecho_ausente', ausente.motivos_revisao)
        self.assertTrue(ausente.requer_revisao)

        nula = por_chave['/document/folha']
        self.assertIsNone(nula.evidencia_pagina)
        self.assertEqual(nula.evidencia_trecho, '')
        self.assertNotIn('evidencia_invalida', nula.motivos_revisao)
        self.assertNotIn('trecho_ausente', nula.motivos_revisao)

    def test_normalized_null_permanece_null(self):
        payload = payload_registro(self.job.job_id)
        payload['document']['data']['normalized'] = None

        data = self._por_chave(self._linhas(payload))['/document/data']

        # null ≠ vazio: o campo fica None, não '', e a pendência é explícita.
        self.assertIsNone(data.normalized)
        self.assertTrue(data.requer_revisao)
        self.assertIn('normalizacao_invalida', data.motivos_revisao)
        self.assertEqual(data.raw, '10 de janeiro de 2020')  # raw preservado

    def test_unidade_area(self):
        payload = payload_registro(self.job.job_id)
        payload['acts'][0]['area']['unidade'] = 'm2'

        area = self._por_chave(self._linhas(payload))['/acts/0/area']

        self.assertIn('unidade_area', area.motivos_revisao)
        self.assertTrue(area.requer_revisao)
        # O valor canônico permanece: converter unidade é decisão humana.
        self.assertEqual(area.normalized, '12.50')

    def test_normalizacao_invalida_em_decimal(self):
        payload = payload_registro(self.job.job_id)
        payload['acts'][0]['valor_transacao']['normalized'] = 'abc'

        valor = self._por_chave(self._linhas(payload))['/acts/0/valor_transacao']

        self.assertIsNone(valor.normalized)
        self.assertTrue(valor.requer_revisao)
        self.assertIn('normalizacao_invalida', valor.motivos_revisao)
        self.assertEqual(valor.raw, 'R$ 150.000,00')  # raw preservado
