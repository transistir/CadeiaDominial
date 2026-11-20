"""Desnormalização do payload A3 — parte 2 de 3 do corpo de
``DesnormalizarTest`` (``ia_ocr/tests/test_revisao.py``, Etapa 5,
grupo 3 do plano de 400 linhas). Classe SIMPLES (sem ``TestCase``):
o discovery do Django não a coleta; quem coleta é a fachada em
``test_revisao_desnormalizar.py``. Corpos verbatim.
"""

from ia_ocr.revisao import linha_ignorada
from .payloads_extracao import (
    _campo, payload_averbacao, payload_com_closure, payload_registro,
)


class DesnormalizarTestParte2:
    def test_transmissao_do_contrato_v1_2_validada_e_desnormalizada(self):
        """Payload v1.2 com livro/folha/data da transmissão em cada ato passa
        pela validação do contrato novo (`validar=True`) e vira UMA linha por
        chave /acts/N/* — com o valor lido do PRÓPRIO ato, não com o
        placeholder vazio e sem cruzar valores entre atos."""
        payload = payload_registro(self.job.job_id)
        self.assertEqual(
            payload['schema_version'], 'umbelino-extracao-matricula-v1.2',
        )
        segundo = payload_averbacao(self.job.job_id)['acts'][0]
        segundo['ordem'] = 2
        payload['acts'].append(segundo)
        # índice do ato → (trecho de evidência, {folha: (valor, tipo_valor)})
        esperados = {
            0: ('R-1/42.718', {
                'livro_transacao': ('10-A', 'texto'),
                'folha_transacao': ('25v', 'texto'),
                'data_transacao': ('2019-12-20', 'data'),
            }),
            1: ('Av-1/42.718', {
                'livro_transacao': ('11-B', 'texto'),
                'folha_transacao': ('7', 'texto'),
                'data_transacao': ('2021-03-20', 'data'),
            }),
        }
        for indice, (trecho, folhas) in esperados.items():
            for nome, (valor, _tipo) in folhas.items():
                payload['acts'][indice][nome] = _campo(valor, trecho)

        linhas = self._linhas(payload)  # valida pelo contrato declarado (v1.2)

        for indice, (trecho, folhas) in esperados.items():
            for nome, (valor, tipo) in folhas.items():
                chave = f'/acts/{indice}/{nome}'
                with self.subTest(chave=chave):
                    encontradas = [linha for linha in linhas if linha.chave == chave]
                    self.assertEqual(len(encontradas), 1)
                    linha = encontradas[0]
                    self.assertEqual(linha.normalized, valor)
                    self.assertEqual(linha.raw, valor)
                    self.assertEqual(linha.tipo_valor, tipo)
                    self.assertEqual(linha.confianca, 0.95)
                    self.assertFalse(linha.requer_revisao)
                    self.assertEqual(linha.motivos_revisao, [])
                    self.assertEqual(linha.evidencia_trecho, trecho)

    def test_transmissao_payload_v1_1_de_servico_antigo_segue_com_placeholders(self):
        """Serviço ainda no v1.1: o payload valida pelo contrato antigo e as
        três folhas de transmissão nascem como placeholders vazios editáveis."""
        payload = payload_registro(self.job.job_id)
        payload['schema_version'] = 'umbelino-extracao-matricula-v1.1'

        linhas = self._linhas(payload)  # valida pelo contrato declarado (v1.1)

        for nome in ('livro_transacao', 'folha_transacao', 'data_transacao'):
            chave = f'/acts/0/{nome}'
            with self.subTest(chave=chave):
                encontradas = [linha for linha in linhas if linha.chave == chave]
                self.assertEqual(len(encontradas), 1)
                self.assertIsNone(encontradas[0].normalized)
                self.assertIsNone(encontradas[0].confianca)
                self.assertFalse(encontradas[0].requer_revisao)

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
                # P1-2 (rodada 7): o rótulo 'R-1' resolve o tipo — o
                # tipo_sugerido ausente não é pendência de revisão.
                self.assertEqual(
                    linha.requer_revisao, chave != '/acts/0/tipo_sugerido',
                )
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

    def test_normalizacao_invalida_em_area(self):
        payload = payload_registro(self.job.job_id)
        payload['acts'][0]['area']['normalized'] = 'abc'

        area = self._por_chave(self._linhas(payload))['/acts/0/area']

        self.assertIsNone(area.normalized)
        self.assertTrue(area.requer_revisao)
        self.assertIn('normalizacao_invalida', area.motivos_revisao)
        self.assertEqual(area.raw, '12,50 ha')  # raw preservado

    def test_valor_transacao_do_payload_nao_gera_linha(self):
        """Tarefa C #322: o formulário de lançamento não tem valor_transacao.

        O schema A3 (Umbelino v1.1) continua mandando a folha — o payload
        segue com ela, mas nenhuma linha de revisão é criada, nem com
        normalização inválida.
        """
        payload = payload_registro(self.job.job_id)
        self.assertIn('valor_transacao', payload['acts'][0])
        payload['acts'][0]['valor_transacao']['normalized'] = 'abc'

        linhas = self._por_chave(self._linhas(payload))

        self.assertNotIn('/acts/0/valor_transacao', linhas)

    def test_detalhes_do_payload_nao_gera_linha(self):
        """#328: o formulário de lançamento não tem detalhes.

        O schema A3 (Umbelino v1.1) continua mandando a folha — o payload
        aceita, mas nenhuma linha de revisão é criada (o app não tem onde
        mostrar nem para onde importar o campo).
        """
        payload = payload_registro(self.job.job_id)
        payload['acts'][0]['detalhes'] = _campo(
            'Detalhes do ato', 'Escritura Pública de Compra e Venda',
        )

        linhas = self._por_chave(self._linhas(payload))

        self.assertNotIn('/acts/0/detalhes', linhas)

    def test_fronteiras_da_linha_ignorada(self):
        """#328 rodada 2 (Opus N-3): a regex derivada mantém a fronteira.

        Só a FOLHA do ato é ignorada — índice real (um ou vários dígitos)
        ou o ponteiro de padrão ``*`` (nit #322, cobertura §25). Homônima
        em outra profundidade, prefixo (``detalhes_x``) e caminho maior
        não são alcançados.
        """
        de_ato = (
            '/acts/0/detalhes', '/acts/10/detalhes', '/acts/*/detalhes',
            '/acts/0/valor_transacao',
        )
        for chave in de_ato:
            with self.subTest(ignorada=chave):
                self.assertTrue(linha_ignorada(chave))

        fora_do_ato = (
            '/document/detalhes', '/acts/0/partes/0/detalhes',
            '/acts/0/detalhes_x', '/acts/0/valor_transacao_x',
            '/actss/0/detalhes',
        )
        for chave in fora_do_ato:
            with self.subTest(ignorada=chave):
                self.assertFalse(linha_ignorada(chave))
