"""Parte 3 de 3 do corpo de ``ExtracaoViewsTest`` — migração VERBATIM de
``ia_ocr/tests/test_extracao_views.py`` (Etapa 12 do plano de 400 linhas).

Classe SIMPLES (sem ``TestCase``); quem coleta é a fachada em
``test_extracao_views_extracao.py``. Corpos verbatim.
"""

import json
from unittest import mock

from django.conf import settings
from django.test import Client
from django.urls import reverse

from ia_ocr import estados, revisao, services
from ia_ocr.estados import TransicaoInvalida
from ia_ocr.models import OcrJob


class ExtracaoViewsTestParte3:
    def test_salvar_em_extracao_substituta_com_mesmo_estado_e_conflito(self):
        antiga = self._extracao()
        versao_antiga = services.versao_bloco(antiga)
        # A reextração recria as linhas no mesmo estado das da antiga.
        nova = self._extracao()
        self.assertEqual(
            [revisao.versao_linha(campo) for campo in nova.campos.order_by('chave')],
            [revisao.versao_linha(campo) for campo in antiga.campos.order_by('chave')],
        )

        resposta = self._post_json('salvar_bloco_ocr', {
            'versao': versao_antiga,
            'decisoes': [{
                'chave': '/document/data', 'incluir': True, 'valor': '2020-01-11',
            }],
        })

        self.assertEqual(resposta.status_code, 409)
        self.assertEqual(resposta.json(), {
            'erro': 'conflito_versao', 'chaves': ['/document/data'],
        })
        linha = nova.campos.get(chave='/document/data')
        self.assertIsNone(linha.valor_final)
        self.assertIsNone(linha.revisado_em)

    def test_resposta_do_save_usa_a_versao_da_transacao(self):
        extracao = self._extracao()
        salvar_bloco = services.salvar_bloco
        versao_no_commit = []

        def outro_revisor_grava_depois_do_commit(*args, **kwargs):
            resultado = salvar_bloco(*args, **kwargs)
            versao_no_commit.append(services.versao_bloco(extracao))
            salvar_bloco(extracao, {
                '/document/livro': {'incluir': False},
            }, self.dono, versao_no_commit[0])
            return resultado

        with mock.patch(
            'ia_ocr.views.services.salvar_bloco',
            side_effect=outro_revisor_grava_depois_do_commit,
        ):
            resposta = self._post_json('salvar_bloco_ocr', {
                'versao': services.versao_bloco(extracao),
                'decisoes': [{
                    'chave': '/document/data', 'incluir': True, 'valor': '2020-01-11',
                }],
            })

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.json()['versao'], versao_no_commit[0])
        # Com esse token, a página não passa por cima da gravação do outro.
        resposta = self._post_json('salvar_bloco_ocr', {
            'versao': resposta.json()['versao'],
            'decisoes': [{'chave': '/document/livro', 'incluir': True}],
        })
        self.assertEqual(resposta.status_code, 409)
        self.assertEqual(
            extracao.campos.get(chave='/document/livro').status_revisao, 'descartado',
        )

    def test_salvar_bloco_json_invalido_400(self):
        for nome in ('salvar_bloco_ocr', 'finalizar_revisao_ocr'):
            for corpo in (b'{', b'', b'\xff'):
                with self.subTest(endpoint=nome, corpo=corpo):
                    resposta = self.client.post(
                        self.url(nome), data=corpo, content_type='application/json',
                    )

                    self.assertEqual(resposta.status_code, 400)
                    self.assertEqual(resposta.json(), {'erro': 'json_invalido'})

    def test_salvar_valor_invalido_422_com_chave_e_sem_gravacao_parcial(self):
        extracao = self._extracao()
        versao = services.versao_bloco(extracao)

        resposta = self._post_json('salvar_bloco_ocr', {
            'versao': versao,
            'decisoes': [
                {'chave': '/document/numero', 'incluir': True, 'valor': '42.719'},
                {'chave': '/document/data', 'incluir': True, 'valor': 'data-invalida'},
            ],
        })

        self.assertEqual(resposta.status_code, 422)
        self.assertEqual(resposta.json(), {
            'erro': 'valor_invalido', 'chave': '/document/data',
        })
        self.assertEqual(services.versao_bloco(extracao), versao)

    def test_salvar_corpo_malformado_422(self):
        extracao = self._extracao()
        versao = services.versao_bloco(extracao)
        corpos = [None, [], {}, {'versao': versao, 'decisoes': {}}, {
            'versao': versao, 'decisoes': [{'chave': '/document/data'}],
        }, {
            'versao': versao,
            'decisoes': [{'chave': '/document/data', 'incluir': True, 'valor': 123}],
        }]
        for corpo in corpos:
            with self.subTest(corpo=corpo):
                resposta = self._post_json('salvar_bloco_ocr', corpo)

                self.assertEqual(resposta.status_code, 422)
                self.assertIn('erro', resposta.json())
                self.assertIn('chave', resposta.json())
                self.assertEqual(services.versao_bloco(extracao), versao)

    def test_salvar_tipo_ato_invalido_422_sem_gravacao_parcial(self):
        extracao = self._extracao()
        versao = services.versao_bloco(extracao)

        resposta = self._post_json('salvar_bloco_ocr', {
            'versao': versao,
            'decisoes': [
                {'chave': '/document/numero', 'incluir': True, 'valor': '42.719'},
                {'chave': '/acts/0/tipo_sugerido', 'incluir': True,
                 'valor': 'registroo'},
            ],
        })

        self.assertEqual(resposta.status_code, 422)
        self.assertEqual(resposta.json(), {
            'erro': 'valor_invalido', 'chave': '/acts/0/tipo_sugerido',
        })
        self.assertEqual(services.versao_bloco(extracao), versao)

    def test_finalizar_com_pendencia_422(self):
        extracao = self._extracao()
        pendencias = revisao.pendencias(extracao)
        self.assertTrue(pendencias)

        resposta = self._post_json('finalizar_revisao_ocr', {
            'versao': services.versao_bloco(extracao),
        })

        self.assertEqual(resposta.status_code, 422)
        self.assertEqual(resposta.json(), {
            'erro': 'revisao_incompleta', 'pendencias': pendencias,
        })
        extracao.refresh_from_db()
        self.job.refresh_from_db()
        self.assertIsNone(extracao.finalizada_em)
        self.assertEqual(self.job.status, estados.EXTRAIDO)

    def test_finalizar_ok_200_com_redirect(self):
        extracao = self._extracao()
        self._resolver_pendencias(extracao)

        resposta = self._post_json('finalizar_revisao_ocr', {
            'versao': services.versao_bloco(extracao),
        })

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.json(), {'ok': True, 'redirect': self._url_documento()})
        self.job.refresh_from_db()
        extracao.refresh_from_db()
        self.assertEqual(self.job.status, estados.REVISADO)
        self.assertEqual(extracao.finalizada_por, self.dono)
        self.assertIsNotNone(extracao.finalizada_em)
        self.assertEqual(self.job.transicoes.get(para_status=estados.REVISADO).usuario, self.dono)

    def test_finalizar_com_versao_obsoleta_e_409_e_nao_finaliza(self):
        extracao = self._extracao()
        self._resolver_pendencias(extracao)
        versao_a = services.versao_bloco(extracao)
        # Com a página em A, outra aba grava uma correção (B).
        services.salvar_bloco(extracao, {
            '/document/data': {'incluir': True, 'valor': '2020-01-11'},
        }, self.dono, versao_a)
        self.assertEqual(revisao.pendencias(extracao), [])

        resposta = self._post_json('finalizar_revisao_ocr', {'versao': versao_a})

        self.assertEqual(resposta.status_code, 409)
        self.assertEqual(resposta.json(), {'erro': 'conflito_versao', 'chaves': []})
        extracao.refresh_from_db()
        self.job.refresh_from_db()
        self.assertIsNone(extracao.finalizada_em)
        self.assertIsNone(extracao.finalizada_por)
        self.assertEqual(self.job.status, estados.EXTRAIDO)
        self.assertFalse(self.job.transicoes.filter(para_status=estados.REVISADO).exists())

    def test_finalizar_sem_versao_na_view_e_422(self):
        extracao = self._extracao()
        self._resolver_pendencias(extracao)

        for corpo in ({}, {'versao': None}, {'versao': 123}, {'versao': ['x']}):
            with self.subTest(corpo=corpo):
                resposta = self._post_json('finalizar_revisao_ocr', corpo)

                self.assertEqual(resposta.status_code, 422)
                self.assertEqual(resposta.json(), {
                    'erro': 'versao_ausente', 'chave': None,
                })
        extracao.refresh_from_db()
        self.job.refresh_from_db()
        self.assertIsNone(extracao.finalizada_em)
        self.assertEqual(self.job.status, estados.EXTRAIDO)

    def test_salvar_exige_csrf(self):
        extracao = self._extracao()
        dados = {'versao': services.versao_bloco(extracao), 'decisoes': []}
        self.assertEqual(self._post_json('salvar_bloco_ocr', dados).status_code, 200)
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.dono)

        for nome in ('salvar_bloco_ocr', 'finalizar_revisao_ocr'):
            with self.subTest(endpoint=nome):
                resposta = self._post_json(nome, dados, client=client)

                self.assertEqual(resposta.status_code, 403)
                self.assertEqual(resposta.json(), {'erro': 'csrf_invalido'})
        token = 'a' * 32
        client.cookies[settings.CSRF_COOKIE_NAME] = token
        resposta = client.post(
            self.url('salvar_bloco_ocr'), data=json.dumps(dados),
            content_type='application/json', **{settings.CSRF_HEADER_NAME: token},
        )
        self.assertEqual(resposta.status_code, 200)

    def test_endpoints_json_recusam_get_com_405(self):
        for nome in ('salvar_bloco_ocr', 'finalizar_revisao_ocr'):
            with self.subTest(endpoint=nome):
                resposta = self.client.get(self.url(nome))

                self.assertEqual(resposta.status_code, 405)
                self.assertEqual(resposta['Allow'], 'POST')
                self.assertEqual(resposta.json(), {'erro': 'metodo_nao_permitido'})

    def test_endpoints_json_transicao_invalida_409(self):
        extracao = self._extracao()
        for nome, servico in (
            ('salvar_bloco_ocr', 'salvar_bloco'),
            ('finalizar_revisao_ocr', 'finalizar_revisao'),
        ):
            with self.subTest(endpoint=nome), mock.patch(
                f'ia_ocr.views.services.{servico}',
                side_effect=TransicaoInvalida('detalhe interno', code='estado_invalido'),
            ):
                resposta = self._post_json(nome, {
                    'versao': services.versao_bloco(extracao), 'decisoes': [],
                })

                self.assertEqual(resposta.status_code, 409)
                self.assertEqual(resposta.json(), {'erro': 'estado_invalido'})

    def test_campos_exige_extraido_ou_revisado(self):
        # #341 fase 3: `campos/` virou encaminhamento; quem recusa o estado
        # é a entrada da revisão — de volta à tela do texto (que, sem texto
        # pronto, segue para o upload) ou ao documento quando a revisão já
        # foi concluída (importado).
        upload = reverse('upload_documento_digital', kwargs={
            'tis_id': self.ti.pk, 'imovel_id': self.imovel.pk,
            'documento_id': self.documento.pk,
        })
        destinos = {
            'pendente': upload,
            'em_execucao': upload,
            'falhou': upload,
            'concluido': self.url_tela(),
            'texto_confirmado': self.url_tela(),
            'importado': self._url_documento(),
        }
        for status, _rotulo in estados.STATUS_CHOICES:
            if status in (estados.EXTRAIDO, estados.REVISADO):
                continue
            with self.subTest(status=status):
                OcrJob.objects.filter(pk=self.job.pk).update(status=status)

                resposta = self.client.get(self.url('campos_job_ocr'), follow=True)

                self.assertEqual(resposta.status_code, 200)
                self.assertEqual(
                    resposta.redirect_chain[0],
                    (self.url('revisar_job_ocr'), 302),
                )
                self.assertEqual(resposta.redirect_chain[-1][0], destinos[status])
                self.assertEqual(self.mensagens(resposta)[-1][0], 'info')

    def test_campos_contexto_da_extracao_vigente_e_somente_leitura(self):
        # #341 fase 3: a tela de cards se aposentou e `campos/` só encaminha
        # à revisão por formulário — em EXTRAIDO e em REVISADO igualmente
        # (quem diferencia os estados é a entrada da revisão).
        self._extracao()
        vigente = self._extracao()
        for status, dpi in ((estados.EXTRAIDO, 300), (estados.REVISADO, None)):
            with self.subTest(status=status):
                OcrJob.objects.filter(pk=self.job.pk).update(status=status, dpi=dpi)

                resposta = self.client.get(self.url('campos_job_ocr'))

                self.assertRedirects(
                    resposta, self.url('revisar_job_ocr'),
                    fetch_redirect_response=False,
                )
                self.assertEqual(self.job.extracao_vigente(), vigente)

    def test_campos_versao_vem_da_mesma_lista_exibida(self):
        # #341 fase 3: a tela de cards se foi; o token de versão que o
        # revisor carrega continua protegendo a gravação — um save do outro
        # revisor entre a leitura e o POST recusa o token velho com 409.
        extracao = self._extracao()
        tela_versao = services.versao_bloco(extracao)
        services.salvar_bloco(extracao, {
            '/document/livro': {'incluir': False},
        }, self.dono, tela_versao)

        resposta = self._post_json('salvar_bloco_ocr', {
            'versao': tela_versao,
            'decisoes': [{'chave': '/document/livro', 'incluir': True}],
        })

        self.assertEqual(resposta.status_code, 409)
