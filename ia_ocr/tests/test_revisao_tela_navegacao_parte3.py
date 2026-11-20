"""Tela de revisão de campos (I-5) — migração VERBATIM de
``ia_ocr/tests/test_revisao_tela.py`` (Etapa 10 do plano de 400 linhas):
parte 3 de 3 do corpo de ``RevisaoTelaTest``; classe SIMPLES (sem
``TestCase``), coletada só pela fachada em
``test_revisao_tela_navegacao.py``. Corpos verbatim.
"""

import json

from dominial.models import Cartorios, LancamentoTipo, Pessoas
from ia_ocr import revisao, views
from ia_ocr.models import CampoSugerido
from ia_ocr.revisao import IndiceCartorios, IndicePessoas, enriquecer_payload

from .payloads_extracao import _campo, payload_registro
from .test_revisao_tela_base import _decisao_do_card
from .test_ui_card_ocr import _atributos, _elementos


class RevisaoTelaTestParte3:
    def test_mascara_preserva_valor_sem_milhar_e_processo_longo(self):
        mascarar = views._mascarar_evidencia
        trecho = (
            'Valor 1500000,00, processo 000123456789, '
            'CNS 123456789012345.'
        )
        self.assertEqual(mascarar(trecho), trecho)

    def _titulos_da_evidencia(self, campo, trecho):
        CampoSugerido.objects.filter(pk=campo.pk).update(
            evidencia_trecho=trecho, evidencia_pagina=1,
        )
        html = self._tela().content.decode()
        trechos = _elementos(
            html, 'span', presentes=('title',),
            valores={'class': 'campo-trecho'},
        )
        return [_atributos(span)['title'] for span in trechos]

    def test_tela_mascara_title_dos_casos_com_rotulo(self):
        extracao = self._extracao()
        campo = extracao.campos.get(chave='/document/numero')
        for trecho, esperado in self.CASOS_MASCARADOS:
            with self.subTest(trecho=trecho):
                self.assertIn(
                    esperado, self._titulos_da_evidencia(campo, trecho),
                )

    def test_tela_preserva_title_dos_casos_sem_rotulo(self):
        extracao = self._extracao()
        campo = extracao.campos.get(chave='/document/numero')
        for trecho in self.CASOS_INTACTOS:
            with self.subTest(trecho=trecho):
                self.assertIn(
                    trecho, self._titulos_da_evidencia(campo, trecho),
                )

    def test_evidencia_mascarada_nao_altera_valor_do_campo(self):
        extracao = self._extracao(payload_registro(self.job.job_id))
        chave = '/acts/0/partes/0/documento_identificacao/valor'
        campo = extracao.campos.get(chave=chave)
        CampoSugerido.objects.filter(pk=campo.pk).update(
            evidencia_trecho='CPF 123.456.789-00', evidencia_pagina=1,
        )

        resposta = self._tela()
        html = resposta.content.decode()

        self.assertEqual(self._valor_do_card(html, chave), '12345678900')
        campo.refresh_from_db()
        self.assertEqual(campo.normalized, '12345678900')
        trechos = _elementos(
            html, 'span', presentes=('title',),
            valores={'class': 'campo-trecho'},
        )
        self.assertIn(
            'CPF ***', [_atributos(trecho)['title'] for trecho in trechos],
        )

    def test_valor_transacao_do_payload_nao_vira_card_e_finaliza(self):
        """Tarefa C #322: o campo não existe no formulário de lançamento."""
        extracao = self._extracao(
            payload_registro(self.job.job_id), resolver=True,
        )
        self.assertEqual(revisao.pendencias(extracao), [])
        self.assertNotIn(
            '/acts/0/valor_transacao', self._chaves_na_tela(),
        )

        finalizar = self.client.post(
            self.url('finalizar_revisao_ocr'),
            data=json.dumps({'versao': self._tela().context['versao']}),
            content_type='application/json',
        )
        self.assertEqual(finalizar.status_code, 200, finalizar.content)

    def test_linha_antiga_de_valor_transacao_nao_aparece_na_tela(self):
        """Tarefa C #322: extração antiga com a linha salva — sem card."""
        extracao = self._extracao(
            payload_registro(self.job.job_id), resolver=True,
        )
        CampoSugerido.objects.create(
            extracao=extracao,
            chave='/acts/0/valor_transacao',
            raw='R$ 150.000,00',
            normalized='150000.00',
            tipo_valor='decimal',
            status_revisao='sugerido',
            requer_revisao=True,
        )

        self.assertNotIn(
            '/acts/0/valor_transacao', self._chaves_na_tela(),
        )

        finalizar = self.client.post(
            self.url('finalizar_revisao_ocr'),
            data=json.dumps({'versao': self._tela().context['versao']}),
            content_type='application/json',
        )
        self.assertEqual(finalizar.status_code, 200, finalizar.content)

    def test_detalhes_do_payload_nao_vira_card_e_finaliza(self):
        """#328: o campo não existe no formulário de lançamento."""
        payload = payload_registro(self.job.job_id)
        payload['acts'][0]['detalhes'] = _campo(
            'Detalhes do ato', 'Escritura Pública de Compra e Venda',
        )
        extracao = self._extracao(payload, resolver=True)
        self.assertEqual(revisao.pendencias(extracao), [])
        self.assertNotIn('/acts/0/detalhes', self._chaves_na_tela())

        finalizar = self.client.post(
            self.url('finalizar_revisao_ocr'),
            data=json.dumps({'versao': self._tela().context['versao']}),
            content_type='application/json',
        )
        self.assertEqual(finalizar.status_code, 200, finalizar.content)

    def test_linha_antiga_de_detalhes_nao_aparece_na_tela(self):
        """#328: extração antiga com a linha salva — sem card."""
        extracao = self._extracao(
            payload_registro(self.job.job_id), resolver=True,
        )
        CampoSugerido.objects.create(
            extracao=extracao,
            chave='/acts/0/detalhes',
            raw='Detalhes antigos',
            normalized='Detalhes antigos',
            tipo_valor='texto',
            status_revisao='sugerido',
            requer_revisao=True,
        )

        self.assertNotIn('/acts/0/detalhes', self._chaves_na_tela())

        finalizar = self.client.post(
            self.url('finalizar_revisao_ocr'),
            data=json.dumps({'versao': self._tela().context['versao']}),
            content_type='application/json',
        )
        self.assertEqual(finalizar.status_code, 200, finalizar.content)

    def test_obrigatorio_vazio_continua_bloqueando_finalizacao(self):
        extracao = self._extracao(
            payload_registro(self.job.job_id), resolver=True,
        )
        chave = '/document/data'

        salvar = self.client.post(
            self.url('salvar_bloco_ocr'),
            data=json.dumps({
                'versao': self._tela().context['versao'],
                'decisoes': [{
                    'chave': chave, 'incluir': True, 'valor': '',
                }],
            }),
            content_type='application/json',
        )
        self.assertEqual(salvar.status_code, 200, salvar.content)

        finalizar = self.client.post(
            self.url('finalizar_revisao_ocr'),
            data=json.dumps({'versao': salvar.json()['versao']}),
            content_type='application/json',
        )

        self.assertEqual(finalizar.status_code, 422, finalizar.content)
        self.assertIn(
            {
                'chave': chave,
                'motivo': 'obrigatorio_ausente',
                'bloqueante': True,
            },
            finalizar.json()['pendencias'],
        )
        self.assertFalse(any(
            pendencia['chave'] == chave
            and pendencia['motivo'] == 'valor_incompativel_destino'
            for pendencia in finalizar.json()['pendencias']
        ))

    def test_enum_obrigatorio_vazio_bloqueia_finalizacao(self):
        payload = payload_registro(self.job.job_id)
        payload['acts'][0]['origem'] = {
            'tipo_documento': dict(payload['document']['tipo']),
        }
        extracao = self._extracao(payload, resolver=True)
        chave = '/acts/0/origem/tipo_documento'
        self.assertFalse(any(
            pendencia['chave'] == chave
            for pendencia in revisao.pendencias(extracao)
        ))

        salvar = self.client.post(
            self.url('salvar_bloco_ocr'),
            data=json.dumps({
                'versao': self._tela().context['versao'],
                'decisoes': [{
                    'chave': chave, 'incluir': True, 'valor': '',
                }],
            }),
            content_type='application/json',
        )
        self.assertEqual(salvar.status_code, 200, salvar.content)
        self.assertEqual(
            extracao.campos.get(chave=chave).valor_final, '',
        )

        finalizar = self.client.post(
            self.url('finalizar_revisao_ocr'),
            data=json.dumps({'versao': salvar.json()['versao']}),
            content_type='application/json',
        )

        self.assertEqual(finalizar.status_code, 422, finalizar.content)
        self.assertIn(
            {
                'chave': chave,
                'motivo': 'valor_incompativel_destino',
                'bloqueante': True,
            },
            finalizar.json()['pendencias'],
        )

    def test_decimal_so_espacos_salva_como_vazio(self):
        extracao = self._extracao(
            payload_registro(self.job.job_id), resolver=True,
        )
        # Tarefa C #322: valor_transacao não é mais linha de revisão.
        for chave in ('/acts/0/area',):
            with self.subTest(chave=chave):
                salvar = self.client.post(
                    self.url('salvar_bloco_ocr'),
                    data=json.dumps({
                        'versao': self._tela().context['versao'],
                        'decisoes': [{
                            'chave': chave, 'incluir': True, 'valor': '   ',
                        }],
                    }),
                    content_type='application/json',
                )

                self.assertEqual(salvar.status_code, 200, salvar.content)
                self.assertEqual(
                    extracao.campos.get(chave=chave).valor_final, '',
                )

    def test_descartar_campo_exigido_pelo_tipo_nao_estoura(self):
        LancamentoTipo.objects.create(
            tipo='averbacao', requer_descricao=True, requer_observacao=False,
        )
        extracao = self._extracao()

        salvar = self.client.post(
            self.url('salvar_bloco_ocr'),
            data=json.dumps({
                'versao': self._tela().context['versao'],
                'decisoes': [{'chave': '/acts/0/descricao', 'incluir': False}],
            }),
            content_type='application/json',
        )

        self.assertEqual(salvar.status_code, 200, salvar.content)
        campo = extracao.campos.get(chave='/acts/0/descricao')
        self.assertEqual(campo.status_revisao, 'descartado')

    def test_mudar_tipo_com_titulo_descartado_nao_estoura(self):
        LancamentoTipo.objects.create(
            tipo='registro', requer_titulo=True,
            requer_cartorio_origem=False, requer_observacao=False,
        )
        extracao = self._extracao()
        CampoSugerido.objects.create(
            extracao=extracao,
            chave='/acts/0/titulo',
            raw='Título antigo',
            normalized='Título antigo',
            tipo_valor='texto',
            status_revisao='descartado',
        )

        salvar = self.client.post(
            self.url('salvar_bloco_ocr'),
            data=json.dumps({
                'versao': self._tela().context['versao'],
                'decisoes': [{
                    'chave': '/acts/0/tipo_sugerido',
                    'incluir': True, 'valor': 'registro',
                }],
            }),
            content_type='application/json',
        )

        self.assertEqual(salvar.status_code, 200, salvar.content)
        campo = extracao.campos.get(chave='/acts/0/titulo')
        self.assertEqual(campo.status_revisao, 'descartado')

    def test_finaliza_usando_apenas_os_controles_renderizados(self):
        # Cartório do documento: match único; cri_atual: dois homônimos;
        # JOÃO por CPF; MARIA e PEDRO sem cadastro (único caminho: criar).
        Cartorios.objects.create(nome='CRI de Guaíra', cns='E2E-1', estado='PR')
        homonimos = [
            Cartorios.objects.create(
                nome='Cartório de Registro de Imóveis de Guaíra',
                cns=f'E2E-{indice}', estado='PR',
            )
            for indice in (2, 3)
        ]
        Pessoas.objects.create(nome='JOÃO DA SILVA', cpf='12345678900')
        payload = enriquecer_payload(
            payload_registro(self.job.job_id), IndicePessoas(), IndiceCartorios(),
        )
        self._extracao(payload)

        html = self._tela().content.decode()
        toolbar = _elementos(html, 'div', presentes=('data-ocr-toolbar',))[0]
        versao = _atributos(toolbar)['data-versao']
        decisoes = [
            decisao for card in _elementos(html, 'article', presentes=('data-campo',))
            if (decisao := _decisao_do_card(card)) is not None
        ]
        escolhas = {d['chave']: d['escolha'] for d in decisoes if 'escolha' in d}
        self.assertEqual(
            escolhas['/document/cri_atual']['cartorio_id'], homonimos[0].pk,
        )
        self.assertTrue(escolhas['/acts/0/partes/2']['criar_novo'])

        salvar = self.client.post(
            self.url('salvar_bloco_ocr'),
            data=json.dumps({'versao': versao, 'decisoes': decisoes}),
            content_type='application/json',
        )
        self.assertEqual(salvar.status_code, 200, salvar.content)

        finalizar = self.client.post(
            self.url('finalizar_revisao_ocr'),
            data=json.dumps({'versao': salvar.json()['versao']}),
            content_type='application/json',
        )
        self.assertEqual(finalizar.status_code, 200, finalizar.content)
        self.assertIn('redirect', finalizar.json())

