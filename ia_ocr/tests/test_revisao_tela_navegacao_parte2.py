"""Tela de revisão de campos (I-5) — migração VERBATIM de
``ia_ocr/tests/test_revisao_tela.py`` (Etapa 10 do plano de 400 linhas):
parte 2 de 3 do corpo de ``RevisaoTelaTest``; classe SIMPLES (sem
``TestCase``), coletada só pela fachada em
``test_revisao_tela_navegacao.py``. Corpos verbatim.
"""

import json

from dominial.models import Cartorios
from ia_ocr import revisao, views

from .payloads_extracao import payload_averbacao, payload_registro


class RevisaoTelaTestParte2:
    def test_criar_novo_cartorio_opcional_sem_nome_gera_pendencia(self):
        extracao = self._extracao(resolver=True)
        self.assertEqual(revisao.pendencias(extracao), [])
        chave = '/document/cri_atual'

        salvar = self.client.post(
            self.url('salvar_bloco_ocr'),
            data=json.dumps({
                'versao': self._tela().context['versao'],
                'decisoes': [{
                    'chave': chave, 'incluir': True, 'valor': '',
                    'escolha': {'criar_novo': True},
                }],
            }),
            content_type='application/json',
        )

        self.assertEqual(salvar.status_code, 200, salvar.content)
        self.assertIn(
            {'chave': chave, 'motivo': 'criar_novo_sem_nome',
             'bloqueante': True},
            revisao.pendencias(extracao),
        )

        salvar = self.client.post(
            self.url('salvar_bloco_ocr'),
            data=json.dumps({
                'versao': salvar.json()['versao'],
                'decisoes': [{
                    'chave': chave, 'incluir': True, 'valor': 'Cartório Novo',
                    'escolha': {'criar_novo': True},
                }],
            }),
            content_type='application/json',
        )

        self.assertEqual(salvar.status_code, 200, salvar.content)
        self.assertFalse(any(
            pendencia['motivo'] == 'criar_novo_sem_nome'
            for pendencia in revisao.pendencias(extracao)
        ))

    def test_escolher_cartorio_existente_zera_nome(self):
        cartorio = Cartorios.objects.create(
            nome='Cartório Existente', cns='E2E-novo', estado='PR',
        )
        extracao = self._extracao_com_cartorio_nulo()
        # A tela só oferece match_candidatos: o cartório foi criado depois da
        # extração, então simula a lista recomputada que o select exibiria.
        extracao.campos.filter(chave='/document/cartorio').update(
            match_candidatos=[cartorio.pk],
        )

        salvar = self._salvar_cartorio({
            'valor': 'Cartório Digitado',
            'escolha': {'cartorio_id': cartorio.pk, 'criar_novo': False},
        })

        self.assertEqual(salvar.status_code, 200, salvar.content)
        campo = extracao.campos.get(chave='/document/cartorio')
        self.assertIsNone(campo.valor_final)
        self.assertEqual(campo.cartorio_escolhido_id, cartorio.pk)
        self.assertFalse(any(
            pendencia['chave'] == '/document/cartorio'
            and pendencia['motivo'] == 'obrigatorio_ausente'
            for pendencia in revisao.pendencias(extracao)
        ))

        finalizar = self.client.post(
            self.url('finalizar_revisao_ocr'),
            data=json.dumps({'versao': salvar.json()['versao']}),
            content_type='application/json',
        )
        self.assertEqual(finalizar.status_code, 200, finalizar.content)
        extracao.refresh_from_db()
        dados = revisao.dados_revisados(extracao)
        self.assertEqual(dados.documento.cartorio_id, cartorio.pk)

    def test_cartorio_digitado_acima_do_limite_e_422(self):
        self._extracao_com_cartorio_nulo()

        salvar = self._salvar_cartorio({
            'valor': 'x' * 10001, 'escolha': {'criar_novo': True},
        })

        self.assertEqual(salvar.status_code, 422, salvar.content)
        self.assertEqual(salvar.json()['erro'], 'valor_invalido')
        self.assertEqual(salvar.json()['chave'], '/document/cartorio')

    def test_cartorio_nome_no_limite_de_200_e_aceito(self):
        extracao = self._extracao_com_cartorio_nulo()

        salvar = self._salvar_cartorio({
            'valor': 'x' * 200, 'escolha': {'criar_novo': True},
        })

        self.assertEqual(salvar.status_code, 200, salvar.content)
        campo = extracao.campos.get(chave='/document/cartorio')
        self.assertEqual(campo.valor_final, 'x' * 200)

    def test_cartorio_nome_acima_de_200_e_422(self):
        self._extracao_com_cartorio_nulo()

        salvar = self._salvar_cartorio({
            'valor': 'x' * 201, 'escolha': {'criar_novo': True},
        })

        self.assertEqual(salvar.status_code, 422, salvar.content)
        self.assertEqual(salvar.json()['erro'], 'valor_invalido')
        self.assertEqual(salvar.json()['chave'], '/document/cartorio')

    def test_cartorio_nome_acima_de_200_bloqueia_finalizacao(self):
        extracao = self._extracao_com_cartorio_nulo()
        extracao.campos.filter(chave='/document/cartorio').update(
            normalized='x' * 201, status_revisao='editado', criar_novo=True,
        )
        versao = self._tela().context['versao']

        finalizar = self.client.post(
            self.url('finalizar_revisao_ocr'),
            data=json.dumps({'versao': versao}),
            content_type='application/json',
        )

        self.assertEqual(finalizar.status_code, 422, finalizar.content)
        self.assertIn(
            {
                'chave': '/document/cartorio',
                'motivo': 'valor_acima_do_limite_destino',
                'bloqueante': True,
            },
            finalizar.json()['pendencias'],
        )

    def _extracao_com_cartorio_ocr_longo(self, cartorio_pk=None):
        """OCR traz nome acima de 200; opcionalmente com candidato existente."""
        extracao = self._extracao(resolver=True)
        extracao.campos.filter(chave='/document/cartorio').update(
            normalized='x' * 250,
            match_candidatos=[cartorio_pk] if cartorio_pk else [],
            status_revisao='sugerido',
            criar_novo=False,
        )
        return extracao

    def test_cartorio_existente_escolhido_aceita_nome_longo_do_ocr(self):
        cartorio = Cartorios.objects.create(
            nome='Cartório Existente', cns='E2E-longo', estado='PR',
        )
        extracao = self._extracao_com_cartorio_ocr_longo(cartorio.pk)

        salvar = self._salvar_cartorio({
            'escolha': {'cartorio_id': cartorio.pk, 'criar_novo': False},
        })

        self.assertEqual(salvar.status_code, 200, salvar.content)
        campo = extracao.campos.get(chave='/document/cartorio')
        self.assertEqual(campo.cartorio_escolhido_id, cartorio.pk)
        self.assertFalse(any(
            pendencia['chave'] == '/document/cartorio'
            for pendencia in revisao.pendencias(extracao)
        ))

    def test_cartorio_existente_escolhido_finaliza_com_nome_longo_do_ocr(self):
        cartorio = Cartorios.objects.create(
            nome='Cartório Existente', cns='E2E-longo', estado='PR',
        )
        self._extracao_com_cartorio_ocr_longo(cartorio.pk)

        salvar = self._salvar_cartorio({
            'escolha': {'cartorio_id': cartorio.pk, 'criar_novo': False},
        })
        self.assertEqual(salvar.status_code, 200, salvar.content)

        finalizar = self.client.post(
            self.url('finalizar_revisao_ocr'),
            data=json.dumps({'versao': salvar.json()['versao']}),
            content_type='application/json',
        )

        self.assertEqual(finalizar.status_code, 200, finalizar.content)

    def test_cartorio_nome_longo_do_ocr_sem_escolha_e_422(self):
        self._extracao_com_cartorio_ocr_longo()

        salvar = self._salvar_cartorio({'escolha': {'criar_novo': False}})

        self.assertEqual(salvar.status_code, 422, salvar.content)
        self.assertEqual(salvar.json()['erro'], 'valor_invalido')
        self.assertEqual(salvar.json()['chave'], '/document/cartorio')

    @staticmethod
    def _campo_sintetico(valor):
        return {
            'raw': valor, 'normalized': valor, 'confianca': 0.95,
            'requer_revisao': False, 'evidencia': None,
        }

    def _extracao_com_rg_longo(self, comprimento):
        """OCR sugere documento de identificação RG acima do limite da parte."""
        payload = payload_registro(self.job.job_id)
        payload['acts'][0]['partes'][2]['documento_identificacao'] = {
            'tipo': self._campo_sintetico('RG'),
            'valor': self._campo_sintetico('x' * comprimento),
        }
        return self._extracao(payload, resolver=True)

    def test_rg_acima_de_20_e_422_no_save_com_a_chave(self):
        chave = '/acts/0/partes/2/documento_identificacao/valor'
        self._extracao_com_rg_longo(21)

        salvar = self.client.post(
            self.url('salvar_bloco_ocr'),
            data=json.dumps({
                'versao': self._tela().context['versao'],
                'decisoes': [{'chave': chave, 'incluir': True,
                              'conferido': True}],
            }),
            content_type='application/json',
        )

        self.assertEqual(salvar.status_code, 422, salvar.content)
        self.assertEqual(salvar.json()['erro'], 'valor_invalido')
        self.assertEqual(salvar.json()['chave'], chave)

    def test_rg_acima_de_20_bloqueia_a_finalizacao(self):
        chave = '/acts/0/partes/2/documento_identificacao/valor'
        self._extracao_com_rg_longo(21)

        finalizar = self.client.post(
            self.url('finalizar_revisao_ocr'),
            data=json.dumps({'versao': self._tela().context['versao']}),
            content_type='application/json',
        )

        self.assertEqual(finalizar.status_code, 422, finalizar.content)
        self.assertIn({
            'chave': chave, 'motivo': 'valor_acima_do_limite_destino',
            'bloqueante': True,
        }, finalizar.json()['pendencias'])

    def test_evidencia_mascara_documentos_com_7_ou_mais_digitos(self):
        payload = payload_averbacao(self.job.job_id)
        payload['document']['numero']['evidencia'] = {
            'pagina': 1,
            'trecho': 'Transmitente: JOÃO DA SILVA (CPF 123.456.789-00).',
        }
        extracao = self._extracao(payload)

        resposta = self._tela()

        self.assertContains(resposta, 'CPF ***')
        self.assertNotContains(resposta, '123.456.789-00')
        self.assertEqual(
            extracao.campos.get(chave='/document/numero').evidencia_trecho,
            'Transmitente: JOÃO DA SILVA (CPF 123.456.789-00).',
        )

    CASOS_MASCARADOS = (
        ('RG 123456', 'RG ***'),
        ('RG 123456,', 'RG ***,'),
        ('RG 1234567.', 'RG ***.'),
        ('RG 1.234.567', 'RG ***'),
        ('RG 12.345.678', 'RG ***'),
        ('RG 12.345.678-9', 'RG ***'),
        ('R.G. 12.345.678-9', 'R.G. ***'),
        ('RG nº 1.234.567', 'RG nº ***'),
        ('RG n.º 123456', 'RG n.º ***'),
        ('RG nº 123456', 'RG nº ***'),
        ('RG nº. 123456', 'RG nº. ***'),
        ('RG n° 123456', 'RG n° ***'),
        ('RG 12 345 678-9', 'RG ***'),
        ('RG n.º 1.234.567', 'RG n.º ***'),
        ('RG nº. 1234567', 'RG nº. ***'),
        ('12.345.678-9', '***'),
        ('12.345.678-X', '***'),
        ('CPF 123.456.789-00', 'CPF ***'),
        ('CPF 123 456 789 00', 'CPF ***'),
        ('CPF 12345678900', 'CPF ***'),
    )

    CASOS_INTACTOS = (
        'MATRÍCULA Nº 142718 FICHA 01',
        'matrícula 123456',
        'com 123456 apenas',
        'R$ 1500000',
        'R$ 15000000',
        'valor R$ 15000000,00',
        '15000000',
        'R$ 1.500.000,00',
        '1500000,00',
        '250000 m²',
        'CNS 123456789012345',
        '10/01/2020',
        '2020-01-10',
        '0001234-56.2020.8.16.0001',
    )

    def test_mascara_cpf_e_rg_sem_apagar_seis_digitos(self):
        mascarar = views._mascarar_evidencia
        self.assertEqual(
            mascarar('CPF 123.456.789-00 e RG 12.345.678-9'),
            'CPF *** e RG ***',
        )
        self.assertEqual(
            mascarar('Trecho sem documento, com 123456 apenas'),
            'Trecho sem documento, com 123456 apenas',
        )

    def test_mascara_rg_pelo_rotulo(self):
        mascarar = views._mascarar_evidencia
        for trecho, esperado in self.CASOS_MASCARADOS:
            with self.subTest(trecho=trecho):
                self.assertEqual(mascarar(trecho), esperado)

    def test_mascara_preserva_numeros_sem_rotulo(self):
        mascarar = views._mascarar_evidencia
        for trecho in self.CASOS_INTACTOS:
            with self.subTest(trecho=trecho):
                self.assertEqual(mascarar(trecho), trecho)

    def test_mascara_preserva_data_iso_valor_cns_e_processo(self):
        mascarar = views._mascarar_evidencia
        trecho = (
            'Data 10/01/2020, ISO 2020-01-10, valor R$ 1.500.000,00, '
            'CNS 123456789012345, processo 0001234-56.2020.8.16.0001.'
        )
        self.assertEqual(mascarar(trecho), trecho)

    def test_mascara_cpf_e_rg_com_pontuacao_final(self):
        mascarar = views._mascarar_evidencia
        self.assertEqual(
            mascarar('CPF 12345678900 e RG 1234567-X, matrícula 123456.'),
            'CPF *** e RG ***, matrícula 123456.',
        )

    def test_mascara_rg_seguido_de_pontuacao(self):
        mascarar = views._mascarar_evidencia
        self.assertEqual(mascarar('RG 123456.'), 'RG ***.')
        self.assertEqual(
            mascarar('RG 123456, emitido pelo oficial'),
            'RG ***, emitido pelo oficial',
        )

    def test_mascara_preserva_pontuacao_de_numero_maior(self):
        mascarar = views._mascarar_evidencia
        trecho = (
            'Valor 1.500.000,00 e 1500000,00, datas 10/01/2020 e '
            '2020-01-10, CNS 123456789012345'
        )
        self.assertEqual(mascarar(trecho), trecho)

    def test_mascara_cpf_com_espacos_contiguo_e_rg_curto(self):
        mascarar = views._mascarar_evidencia
        self.assertEqual(
            mascarar('CPF 123 456 789 00 e CPF 12345678900.'),
            'CPF *** e CPF ***.',
        )
        self.assertEqual(
            mascarar('RG 123456 e RG 123456789.'),
            'RG *** e RG ***.',
        )

