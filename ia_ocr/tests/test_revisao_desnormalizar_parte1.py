"""Desnormalização do payload A3 — parte 1 de 3 do corpo de
``DesnormalizarTest`` (``ia_ocr/tests/test_revisao.py``, Etapa 5,
grupo 3 do plano de 400 linhas). Classe SIMPLES (sem ``TestCase``):
o discovery do Django não a coleta; quem coleta é a fachada em
``test_revisao_desnormalizar.py``. Corpos verbatim.
"""

from dominial.models import LancamentoTipo
from ia_ocr.extracao_schema import validar_payload
from ia_ocr.models import CampoSugerido, ExtracaoSugerida, OcrJob, PaginaOcr

from ia_ocr.revisao import campo_obrigatorio, desnormalizar
from .factories import criar_documento_digital
from .payloads_extracao import (
    SCHEMA_VERSION, TEXTO_PAGINA_1, _campo, payload_averbacao,
    payload_registro,
)


class DesnormalizarTestParte1:
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

        # Uma query por payload resolve os ``LancamentoTipo`` dos atos.
        with self.assertNumQueries(2):
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
        # Tarefa C #322: a folha valor_transacao do schema A3 é ignorada.
        self.assertNotIn('/acts/0/valor_transacao', por_chave)
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

    def test_transmissao_placeholder_unico_por_ato(self):
        payload = payload_registro(self.job.job_id)
        segundo = payload_averbacao(self.job.job_id)['acts'][0]
        segundo['ordem'] = 2
        payload['acts'].append(segundo)

        linhas = self._linhas(payload)

        for indice in range(2):
            for nome, tipo in (
                ('livro_transacao', 'texto'), ('folha_transacao', 'texto'),
                ('data_transacao', 'data'),
            ):
                chave = f'/acts/{indice}/{nome}'
                with self.subTest(chave=chave):
                    encontradas = [linha for linha in linhas if linha.chave == chave]
                    self.assertEqual(len(encontradas), 1)
                    linha = encontradas[0]
                    self.assertIsNone(linha.normalized)
                    self.assertFalse(linha.requer_revisao)
                    self.assertEqual(linha.motivos_revisao, [])
                    self.assertEqual(linha.tipo_valor, tipo)

    def test_transmissao_placeholder_mesmo_sem_tipo(self):
        payload = payload_averbacao(self.job.job_id)
        payload['acts'][0].pop('tipo_sugerido')
        payload['acts'][0].pop('rotulo')

        linhas = self._linhas(payload, validar=False)

        for nome in ('livro_transacao', 'folha_transacao', 'data_transacao'):
            chave = f'/acts/0/{nome}'
            with self.subTest(chave=chave):
                encontradas = [linha for linha in linhas if linha.chave == chave]
                self.assertEqual(len(encontradas), 1)
                self.assertIsNone(encontradas[0].normalized)
                self.assertFalse(encontradas[0].requer_revisao)

    def test_transmissao_folhas_do_payload_sem_duplicatas(self):
        esperados = {
            'livro_transacao': ('10-A', 'texto'),
            'folha_transacao': ('25v', 'texto'),
            'data_transacao': ('2019-12-20', 'data'),
        }
        for caso in ('preenchida', 'nula', 'sem_normalized', 'normalized_nulo'):
            with self.subTest(caso=caso):
                self.extracao.campos.all().delete()
                payload = payload_registro(self.job.job_id)
                for nome, (valor, _tipo) in esperados.items():
                    campo = _campo(valor, 'R-1/42.718')
                    if caso == 'nula':
                        campo = None
                    elif caso == 'sem_normalized':
                        campo.pop('normalized')
                    elif caso == 'normalized_nulo':
                        campo['normalized'] = None
                    payload['acts'][0][nome] = campo

                # Formas degeneradas (folha nula, sem `normalized`...) que o
                # contrato v1.2 nem sempre aceita: aqui só a desnormalização.
                linhas = self._linhas(payload, validar=False)
                for nome in esperados:
                    chave = f'/acts/0/{nome}'
                    self.assertEqual(
                        sum(linha.chave == chave for linha in linhas), 1, chave,
                    )
                CampoSugerido.objects.bulk_create(linhas)

                for nome, (valor, tipo) in esperados.items():
                    chave = f'/acts/0/{nome}'
                    with self.subTest(chave=chave):
                        salvas = self.extracao.campos.filter(chave=chave)
                        self.assertEqual(salvas.count(), 1)
                        linha = salvas.get()
                        if caso == 'preenchida':
                            self.assertEqual(linha.normalized, valor)
                        else:
                            self.assertIsNone(linha.normalized)
                        self.assertEqual(linha.tipo_valor, tipo)
                        if caso in ('nula', 'sem_normalized'):
                            self.assertIsNone(linha.raw)
                            self.assertIsNone(linha.confianca)
                        else:
                            self.assertEqual(linha.confianca, 0.95)
                        # Data explícita sem canônico exige revisão;
                        # placeholder opcional continua sem pendência.
                        revisao = caso == 'normalized_nulo' and tipo == 'data'
                        self.assertEqual(linha.requer_revisao, revisao)
                        self.assertEqual(
                            linha.motivos_revisao,
                            ['normalizacao_invalida'] if revisao else [],
                        )

    # --- #324 (I-11d): campos vazios da origem na revisão ------------------

    def _payload_com_origem(self, **folhas):
        payload = payload_registro(self.job.job_id)
        payload['acts'][0]['origem'] = folhas
        return payload

    def test_origem_preenchida_ganha_placeholders_dos_demais_campos(self):
        payload = self._payload_com_origem(
            numero=_campo('M42.718', 'Nº 42.718', raw='Nº 42.718'),
            cartorio=payload_registro(self.job.job_id)['document']['cartorio'],
        )

        por_chave = self._por_chave(self._linhas(payload))

        for nome, tipo in (
            ('tipo_documento', 'enum'), ('livro', 'texto'),
            ('folha', 'texto'), ('data', 'data'),
        ):
            chave = f'/acts/0/origem/{nome}'
            with self.subTest(chave=chave):
                linha = por_chave[chave]
                self.assertIsNone(linha.raw)
                self.assertIsNone(linha.normalized)
                self.assertIsNone(linha.confianca)
                self.assertFalse(linha.requer_revisao)
                self.assertEqual(linha.motivos_revisao, [])
                self.assertEqual(linha.tipo_valor, tipo)
                self.assertFalse(campo_obrigatorio(chave))
        # O que o payload trouxe continua sendo a folha real, uma só vez.
        numero = por_chave['/acts/0/origem/numero']
        self.assertEqual(numero.normalized, 'M42.718')
        self.assertEqual(numero.confianca, 0.95)
        self.assertEqual(
            por_chave['/acts/0/origem/cartorio'].tipo_valor, 'cartorio',
        )

    def test_origem_placeholder_uma_linha_por_chave(self):
        payload = self._payload_com_origem(
            tipo_documento=_campo('matricula', 'MATRÍCULA Nº 42.718'),
            numero=_campo('M42.718', 'Nº 42.718', raw='Nº 42.718'),
            livro=_campo('2-RG', 'Livro 2-RG', raw='Livro 2-RG'),
            folha=_campo('087', 'Folha 087', raw='Folha 087'),
            data=_campo('2020-01-10', '10 de janeiro de 2020'),
            cartorio=payload_registro(self.job.job_id)['document']['cartorio'],
        )

        linhas = self._linhas(payload)

        chaves = [linha.chave for linha in linhas]
        self.assertEqual(len(chaves), len(set(chaves)))
        origem = {
            linha.chave: linha for linha in linhas if '/origem/' in linha.chave
        }
        self.assertEqual(len(origem), 6)
        # Folhas do payload preservadas: nenhuma virou placeholder vazio.
        for nome in ('tipo_documento', 'numero', 'livro', 'folha', 'data'):
            with self.subTest(nome=nome):
                self.assertIsNotNone(origem[f'/acts/0/origem/{nome}'].normalized)

    def test_ato_sem_origem_nao_ganha_linhas_da_origem(self):
        casos = {
            'sem_chave': payload_averbacao(self.job.job_id),
            'nula': self._payload_com_origem(),
            'vazia': self._payload_com_origem(),
        }
        casos['nula']['acts'][0]['origem'] = None
        for nome, payload in casos.items():
            with self.subTest(caso=nome):
                chaves = [
                    linha.chave for linha in self._linhas(payload)
                    if '/origem' in linha.chave
                ]
                self.assertEqual(chaves, [])

    def test_tipo_que_exige_cartorio_de_origem_ganha_todos_os_campos(self):
        LancamentoTipo.objects.create(
            tipo='registro', requer_cartorio_origem=True,
        )
        # Registro sem bloco ``origem`` no payload: o tipo exige o cartório.
        payload = payload_registro(self.job.job_id)
        self.assertNotIn('origem', payload['acts'][0])

        por_chave = self._por_chave(self._linhas(payload))

        for nome in (
            'cartorio', 'tipo_documento', 'numero', 'livro', 'folha', 'data',
        ):
            with self.subTest(nome=nome):
                linha = por_chave[f'/acts/0/origem/{nome}']
                self.assertIsNone(linha.normalized)
                self.assertFalse(linha.requer_revisao)
