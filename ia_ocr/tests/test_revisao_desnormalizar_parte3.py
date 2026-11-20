"""Desnormalização do payload A3 — parte 3 de 3 do corpo de
``DesnormalizarTest`` (``ia_ocr/tests/test_revisao.py``, Etapa 5,
grupo 3 do plano de 400 linhas). Classe SIMPLES (sem ``TestCase``):
o discovery do Django não a coleta; quem coleta é a fachada em
``test_revisao_desnormalizar.py``. Corpos verbatim.
"""

from ia_ocr.revisao import aplicar_linha
from .payloads_extracao import payload_registro


class DesnormalizarTestParte3:
    def test_evidencia_usa_texto_corrigido(self):
        """Trecho é conferido contra o texto vigente: o corrigido (#290).

        O OCR puro é só fallback (página sem ``texto_corrigido`` — coberto
        pelos demais testes): com correção aplicada, trecho que só existe
        no OCR original é ``trecho_ausente``.
        """
        self.pagina.texto_corrigido = (
            'Texto revisado pelo serviço. MATRÍCULA Nº 42.718.'
        )
        self.pagina.save(update_fields=['texto_corrigido'])

        payload = payload_registro(self.job.job_id)
        # Só existe no texto corrigido → evidência íntegra.
        payload['document']['tipo']['evidencia'] = {
            'pagina': 1, 'trecho': 'Texto revisado pelo serviço.',
        }
        # Só existe no OCR puro → não vale mais contra o texto corrigido.
        payload['document']['data']['evidencia'] = {
            'pagina': 1, 'trecho': '10 de janeiro de 2020',
        }

        por_chave = self._por_chave(self._linhas(payload))

        do_corrigido = por_chave['/document/tipo']
        self.assertEqual(
            do_corrigido.evidencia_trecho, 'Texto revisado pelo serviço.'
        )
        self.assertNotIn('trecho_ausente', do_corrigido.motivos_revisao)

        so_do_ocr = por_chave['/document/data']
        self.assertEqual(so_do_ocr.evidencia_trecho, '')
        self.assertIn('trecho_ausente', so_do_ocr.motivos_revisao)
        self.assertTrue(so_do_ocr.requer_revisao)

    def test_bbox_guardado(self):
        # bbox ainda não está no schema A3 vendorizado (o evidence tem
        # additionalProperties: false) e desnormalizar não valida: os
        # payloads aqui pulam o validar_payload.
        payload = payload_registro(self.job.job_id)
        payload['document']['numero']['evidencia'] = {
            'pagina': 1, 'trecho': 'Nº 42.718', 'bbox': [10, 20, 300, 40],
        }
        payload['acts'][0]['evidencia'] = {
            'pagina': 1, 'trecho': 'R-1/42.718', 'bbox': [1.5, 2, 3, 4.5],
        }
        payload['acts'][0]['partes'][0]['evidencia'] = {
            'pagina': 1, 'trecho': 'JOÃO DA SILVA', 'bbox': [0, 0, 100, 20],
        }

        por_chave = self._por_chave(self._linhas(payload, validar=False))

        campo = por_chave['/document/numero']
        self.assertEqual(campo.evidencia_bbox, [10, 20, 300, 40])
        self.assertEqual(campo.evidencia_trecho, 'Nº 42.718')
        # bbox íntegro não é pendência: linha segue limpa.
        self.assertEqual(campo.motivos_revisao, [])
        self.assertFalse(campo.requer_revisao)

        # Linhas estruturais (ato e parte) também carregam o bbox.
        self.assertEqual(por_chave['/acts/0'].evidencia_bbox, [1.5, 2, 3, 4.5])
        self.assertEqual(
            por_chave['/acts/0/partes/0'].evidencia_bbox, [0, 0, 100, 20]
        )

        # Evidência sem bbox (e placeholder) → None, sem pendência.
        self.assertIsNone(por_chave['/document/data'].evidencia_bbox)
        self.assertNotIn(
            'trecho_ausente', por_chave['/document/data'].motivos_revisao
        )

    def test_bbox_invalido_vira_none(self):
        invalidos = (
            [10, 20, 30],            # 3 números
            [10, 20, 30, 40, 50],    # 5 números
            [10, 20, '30', 40],      # string no meio
            [True, 20, 30, 40],      # bool não é número
            '10,20,30,40',           # não é lista
            {'x0': 10},              # não é lista
            None,                    # null explícito
        )
        for bbox in invalidos:
            with self.subTest(bbox=bbox):
                payload = payload_registro(self.job.job_id)
                payload['document']['numero']['evidencia'] = {
                    'pagina': 1, 'trecho': 'Nº 42.718', 'bbox': bbox,
                }

                numero = self._por_chave(
                    self._linhas(payload, validar=False)
                )['/document/numero']

                self.assertIsNone(numero.evidencia_bbox)
                # bbox malformado NÃO é pendência: página e trecho seguem
                # íntegros e a linha não vai para revisão por causa dele.
                self.assertEqual(numero.evidencia_pagina, 1)
                self.assertEqual(numero.evidencia_trecho, 'Nº 42.718')
                self.assertEqual(numero.motivos_revisao, [])
                self.assertFalse(numero.requer_revisao)

    def test_select_ja_vem_com_um_candidato(self):
        payload = payload_registro(self.job.job_id)
        payload['document']['cartorio']['match_sugerido'] = {
            'cartorio_id': 7, 'candidatos': [],
        }
        payload['document']['cri_atual']['match_sugerido'] = {
            'cartorio_id': None, 'candidatos': [3, 4],
        }
        payload['acts'][0]['partes'][0]['match_pessoa_id'] = 11
        payload['acts'][0]['partes'][1]['match_pessoa_id'] = None

        por_chave = self._por_chave(self._linhas(payload, validar=False))

        cartorio = por_chave['/document/cartorio']
        self.assertEqual(cartorio.match_candidatos, [7])
        self.assertEqual(cartorio.cartorio_escolhido_id, 7)
        # Vários candidatos: o revisor escolhe; nada vem pré-escolhido.
        cri_atual = por_chave['/document/cri_atual']
        self.assertEqual(cri_atual.match_candidatos, [3, 4])
        self.assertIsNone(cri_atual.cartorio_escolhido_id)
        parte = por_chave['/acts/0/partes/0']
        self.assertEqual(parte.match_candidatos, [11])
        self.assertEqual(parte.pessoa_escolhida_id, 11)
        self.assertIsNone(parte.cartorio_escolhido_id)
        sem_match = por_chave['/acts/0/partes/1']
        self.assertEqual(sem_match.match_candidatos, [])
        self.assertIsNone(sem_match.pessoa_escolhida_id)
        # Sem enriquecimento (PEDRO SANTOS): nenhum id inventado.
        self.assertEqual(por_chave['/acts/0/partes/2'].match_candidatos, [])
        self.assertIsNone(por_chave['/acts/0/partes/2'].pessoa_escolhida_id)

    def test_criar_novo_marca_escolha(self):
        payload = payload_registro(self.job.job_id)
        payload['acts'][0]['partes'][2]['match_pessoa_id'] = None

        parte = self._por_chave(
            self._linhas(payload, validar=False)
        )['/acts/0/partes/2']
        self.assertEqual(parte.match_candidatos, [])
        self.assertFalse(parte.criar_novo)

        aplicar_linha(
            parte, incluir=True, conferido=True,
            escolha={'pessoa_escolhida_id': None, 'criar_novo': True},
        )

        self.assertTrue(parte.criar_novo)
        self.assertIsNone(parte.pessoa_escolhida_id)
        self.assertEqual(parte.status_revisao, 'aceito')

    def test_parte_homonima_vem_com_candidatos(self):
        payload = payload_registro(self.job.job_id)
        payload['acts'][0]['partes'][0]['match_pessoa_id'] = None
        payload['acts'][0]['partes'][0]['match_pessoa_candidatos'] = [11, 12]

        parte = self._por_chave(
            self._linhas(payload, validar=False)
        )['/acts/0/partes/0']

        self.assertEqual(parte.match_candidatos, [11, 12])
        self.assertIsNone(parte.pessoa_escolhida_id)

    def test_escolha_e_criar_novo_sao_exclusivos(self):
        payload = payload_registro(self.job.job_id)
        payload['acts'][0]['partes'][0]['match_pessoa_id'] = None
        payload['acts'][0]['partes'][0]['match_pessoa_candidatos'] = [11, 12]
        payload['document']['cri_atual']['match_sugerido'] = {
            'cartorio_id': None, 'candidatos': [3, 4],
        }
        por_chave = self._por_chave(self._linhas(payload, validar=False))
        parte = por_chave['/acts/0/partes/0']
        cri_atual = por_chave['/document/cri_atual']

        # Escolher depois de "criar novo" desmarca o "criar novo".
        aplicar_linha(parte, incluir=True, escolha={'criar_novo': True})
        aplicar_linha(parte, incluir=True, escolha={'pessoa_escolhida_id': 12})
        self.assertEqual(parte.pessoa_escolhida_id, 12)
        self.assertFalse(parte.criar_novo)

        # "Criar novo" depois de escolher zera a escolha.
        aplicar_linha(parte, incluir=True, escolha={'criar_novo': True})
        self.assertTrue(parte.criar_novo)
        self.assertIsNone(parte.pessoa_escolhida_id)

        aplicar_linha(
            cri_atual, incluir=True, escolha={'cartorio_escolhido_id': 4},
        )
        aplicar_linha(cri_atual, incluir=True, escolha={'criar_novo': True})
        self.assertTrue(cri_atual.criar_novo)
        self.assertIsNone(cri_atual.cartorio_escolhido_id)
        aplicar_linha(
            cri_atual, incluir=True, escolha={'cartorio_escolhido_id': 3},
        )
        self.assertEqual(cri_atual.cartorio_escolhido_id, 3)
        self.assertFalse(cri_atual.criar_novo)

        # As duas coisas na mesma escolha: "criar novo" vence.
        aplicar_linha(
            parte, incluir=True,
            escolha={'pessoa_escolhida_id': 11, 'criar_novo': True},
        )
        self.assertTrue(parte.criar_novo)
        self.assertIsNone(parte.pessoa_escolhida_id)
