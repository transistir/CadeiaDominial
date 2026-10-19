"""Views da extração e revisão com backend falso e documentos sintéticos."""

import json
import uuid
from unittest import mock

from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import resolve_url
from django.test import Client, override_settings
from django.urls import reverse

from dominial.models import Pessoas
from ia_ocr import estados, revisao, services
from ia_ocr.estados import TransicaoInvalida
from ia_ocr.extracao_backends import ExtracaoBackendError
from ia_ocr.models import OcrJob

from .base_texto import TelaTextoBase
from .payloads_extracao import (
    TEXTO_PAGINA_1, payload_averbacao, payload_registro,
)


@override_settings(EXTRACAO_HTTP_TIMEOUT_SECONDS=30)
class ExtracaoViewsTest(TelaTextoBase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.dono)
        self.documento.tipo.tipo = 'matricula'
        self.documento.tipo.save(update_fields=['tipo'])
        self.backend = mock.Mock(spec=['extrair'])
        self.backend.extrair.return_value = {
            'extracao': payload_averbacao(self.job.job_id),
            'dpi': 300,
            'paginas': [
                {
                    'pagina': pagina.numero_pagina,
                    'texto_corrigido': (
                        TEXTO_PAGINA_1 if pagina.numero_pagina == 1 else pagina.texto_ocr
                    ),
                }
                for pagina in self.job.paginas.all()
            ],
        }
        backend_patch = mock.patch(
            'ia_ocr.services.get_extracao_backend', return_value=self.backend,
        )
        backend_patch.start()
        self.addCleanup(backend_patch.stop)

    def _extracao(self, payload=None):
        if payload is not None:
            self.backend.extrair.return_value['extracao'] = payload
        return services.solicitar_extracao(self.job, self.dono)

    def _post_json(self, nome, dados, client=None):
        return (client or self.client).post(
            self.url(nome), data=json.dumps(dados), content_type='application/json',
        )

    def _url_documento(self):
        return reverse('documento_detalhado', kwargs={
            'tis_id': self.ti.pk,
            'imovel_id': self.imovel.pk,
            'documento_id': self.documento.pk,
        })

    def _resolver_pendencias(self, extracao):
        decisoes = {}
        for campo in extracao.campos.all():
            decisao = {'incluir': True, 'conferido': True}
            if campo.tipo_valor in ('cartorio', 'parte'):
                decisao['escolha'] = {'criar_novo': True}
            decisoes[campo.chave] = decisao
        services.salvar_bloco(
            extracao, decisoes, self.dono, services.versao_bloco(extracao),
        )
        self.assertEqual(revisao.pendencias(extracao), [])

    def test_get_extrair_recusa_405(self):
        resposta = self.client.get(self.url('extrair_campos_ocr'))

        self.assertEqual(resposta.status_code, 405)
        self.assertEqual(resposta['Allow'], 'POST')
        self.backend.extrair.assert_not_called()

    def test_post_sem_login_redireciona(self):
        self.client.logout()
        for nome in ('extrair_campos_ocr', 'salvar_bloco_ocr', 'finalizar_revisao_ocr'):
            with self.subTest(endpoint=nome):
                resposta = self._post_json(nome, {})

                self.assertEqual(resposta.status_code, 302)
                self.assertTrue(resposta.url.startswith(
                    f'{resolve_url(settings.LOGIN_URL)}?next=',
                ))
                self.assertIn(self.url(nome), resposta.url)
        self.backend.extrair.assert_not_called()

    def test_documento_de_outro_usuario_404(self):
        self.client.force_login(self.sem_acesso)
        for nome in ('extrair_campos_ocr', 'salvar_bloco_ocr', 'finalizar_revisao_ocr'):
            with self.subTest(endpoint=nome):
                resposta = self._post_json(nome, {})

                self.assertEqual(resposta.status_code, 404)
                if nome != 'extrair_campos_ocr':
                    self.assertEqual(resposta.json(), {'erro': 'nao_encontrado'})
                    inexistente = self.client.post(
                        self.url(nome, job_id=uuid.uuid4()),
                        data='{}', content_type='application/json',
                    )
                    self.assertEqual(inexistente.status_code, 404)
                    self.assertEqual(inexistente.json(), resposta.json())
        self.assertEqual(self.client.get(self.url('campos_job_ocr')).status_code, 404)
        self.backend.extrair.assert_not_called()
        self.assertFalse(self.job.extracoes.exists())

    def test_extrair_guarda_concluido(self):
        OcrJob.objects.filter(pk=self.job.pk).update(status=estados.EM_EXECUCAO)

        resposta = self.client.post(self.url('extrair_campos_ocr'))

        self.assertRedirects(resposta, self.url_tela(), fetch_redirect_response=False)
        self.assertIn((
            'error', 'Este processamento não permite extrair campos no estado atual.',
        ), self.mensagens(resposta))
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, estados.EM_EXECUCAO)
        self.assertFalse(self.job.extracoes.exists())
        self.backend.extrair.assert_not_called()

    def test_extrair_sucesso_redireciona_e_transiciona(self):
        resposta = self.client.post(self.url('extrair_campos_ocr'))

        self.assertRedirects(
            resposta, self.url('campos_job_ocr'), fetch_redirect_response=False,
        )
        self.assertIn((
            'success', 'Extração concluída. Revise os campos.',
        ), self.mensagens(resposta))
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, estados.EXTRAIDO)
        self.assertEqual(self.job.dpi, 300)
        self.assertTrue(self.job.extracao_vigente().campos.exists())
        self.assertEqual(self.job.extracao_vigente().solicitada_por, self.dono)
        transicao = self.job.transicoes.get()
        self.assertEqual(transicao.de_status, estados.CONCLUIDO)
        self.assertEqual(transicao.para_status, estados.EXTRAIDO)
        self.assertEqual(transicao.usuario, self.dono)
        self.backend.extrair.assert_called_once()

    def test_extrair_erros_exibem_mensagens_seguras(self):
        indisponivel = 'O serviço de extração não respondeu. Tente novamente em instantes.'
        casos = (
            (
                services.ExtracaoRecusada('sem_texto_ocr'),
                'O OCR ainda não devolveu texto para todas as páginas.',
            ),
            (
                services.ExtracaoRecusada('extracao_desatualizada'),
                'A extração mudou. Recarregue a tela.',
            ),
            (
                services.ExtracaoConcorrente(),
                'Já existe uma extração em andamento para este documento.',
            ),
            (services.ExtracaoIndisponivel(), indisponivel),
            (ExtracaoBackendError('FALHA', 'detalhe que não deve aparecer'), indisponivel),
            (
                TransicaoInvalida('detalhe interno', code='estado_invalido'),
                'Este processamento não permite extrair campos no estado atual.',
            ),
        )
        for erro, mensagem in casos:
            with self.subTest(erro=type(erro).__name__), mock.patch(
                'ia_ocr.views.services.solicitar_extracao', side_effect=erro,
            ):
                resposta = self.client.post(self.url('extrair_campos_ocr'))

                self.assertRedirects(resposta, self.url_tela(), fetch_redirect_response=False)
                self.assertEqual(self.mensagens(resposta)[-1], ('error', mensagem))

    def test_salvar_bloco_ok_e_versao_nova(self):
        extracao = self._extracao()
        versao = services.versao_bloco(extracao)

        resposta = self._post_json('salvar_bloco_ocr', {
            'versao': versao,
            'decisoes': [{
                'chave': '/document/data', 'incluir': True, 'valor': '2020-01-11',
            }],
        })

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.json(), {
            'ok': True,
            'versao': services.versao_bloco(extracao),
            'partes_invalidadas': [],
            'pendencias': [
                {'chave': item['chave'], 'motivo': item['motivo']}
                for item in revisao.pendencias(extracao)
            ],
        })
        self.assertNotEqual(resposta.json()['versao'], versao)
        campo = extracao.campos.get(chave='/document/data')
        self.assertEqual(campo.valor_final, '2020-01-11')
        self.assertEqual(campo.revisado_por, self.dono)
        self.assertIsNotNone(campo.revisado_em)

    def test_identidade_corrigida_devolve_partes_invalidadas(self):
        extracao = self._extracao(payload_registro(self.job.job_id))
        chave_parte = '/acts/0/partes/0'

        corrigida = self._post_json('salvar_bloco_ocr', {
            'versao': services.versao_bloco(extracao),
            'decisoes': [
                {
                    'chave': f'{chave_parte}/nome',
                    'incluir': True, 'conferido': True,
                    'valor': 'JOÃO DA SILVA CORRIGIDO',
                },
                {
                    'chave': f'{chave_parte}/documento_identificacao/valor',
                    'incluir': True, 'conferido': True,
                    'valor': '11122233344',
                },
            ],
        })

        self.assertEqual(corrigida.status_code, 200, corrigida.content)
        self.assertEqual(
            corrigida.json()['partes_invalidadas'], [chave_parte],
        )

        sem_identidade = self._post_json('salvar_bloco_ocr', {
            'versao': corrigida.json()['versao'],
            'decisoes': [{
                'chave': '/document/numero', 'incluir': True, 'valor': '43.000',
            }],
        })

        self.assertEqual(sem_identidade.status_code, 200, sem_identidade.content)
        self.assertEqual(sem_identidade.json()['partes_invalidadas'], [])

    def test_escolha_antiga_recusada_apos_identidade_mudar(self):
        pessoa_a = Pessoas.objects.create(
            nome='JOÃO DA SILVA', cpf='12345678900',
        )
        pessoa_b = Pessoas.objects.create(
            nome='MARIA DA SILVA', cpf='98765432100',
        )
        extracao = self._extracao(payload_registro(self.job.job_id))
        chave = '/acts/0/partes/0'
        parte = extracao.campos.get(chave=chave)
        # O match único já vem escolhido: é a pessoa A que a tela exibe.
        self.assertEqual(parte.pessoa_escolhida_id, pessoa_a.pk)
        self.assertEqual(parte.match_candidatos, [pessoa_a.pk])

        corrigida = self._post_json('salvar_bloco_ocr', {
            'versao': services.versao_bloco(extracao),
            'decisoes': [
                {
                    'chave': f'{chave}/nome',
                    'incluir': True, 'conferido': True,
                    'valor': 'MARIA DA SILVA',
                },
                {
                    'chave': f'{chave}/documento_identificacao/valor',
                    'incluir': True, 'conferido': True,
                    'valor': '98765432100',
                },
            ],
        })

        self.assertEqual(corrigida.status_code, 200, corrigida.content)
        self.assertEqual(corrigida.json()['partes_invalidadas'], [chave])
        parte.refresh_from_db()
        self.assertIsNone(parte.pessoa_escolhida_id)
        self.assertEqual(parte.match_candidatos, [pessoa_b.pk])

        # Janela do reload diferido: o select ainda poderia mandar A, mas o
        # servidor não pode regravar a escolha que ele mesmo invalidou.
        antiga = self._post_json('salvar_bloco_ocr', {
            'versao': corrigida.json()['versao'],
            'decisoes': [{
                'chave': chave, 'incluir': True, 'conferido': True,
                'escolha': {
                    'pessoa_id': pessoa_a.pk, 'criar_novo': False,
                },
            }],
        })

        self.assertEqual(antiga.status_code, 422, antiga.content)
        self.assertEqual(antiga.json(), {
            'erro': 'escolha_invalida', 'chave': chave,
        })
        parte.refresh_from_db()
        self.assertIsNone(parte.pessoa_escolhida_id)

    def test_duas_partes_invalidadas_no_mesmo_bloco(self):
        pessoa_a = Pessoas.objects.create(
            nome='JOÃO DA SILVA', cpf='12345678900',
        )
        pessoa_b = Pessoas.objects.create(
            nome='MARIA DA SILVA', cpf='98765432100',
        )
        extracao = self._extracao(payload_registro(self.job.job_id))
        chave_0 = '/acts/0/partes/0'
        chave_1 = '/acts/0/partes/1'
        self.assertEqual(
            extracao.campos.get(chave=chave_0).pessoa_escolhida_id,
            pessoa_a.pk,
        )
        self.assertEqual(
            extracao.campos.get(chave=chave_1).pessoa_escolhida_id,
            pessoa_b.pk,
        )

        resposta = self._post_json('salvar_bloco_ocr', {
            'versao': services.versao_bloco(extracao),
            'decisoes': [
                {
                    'chave': f'{chave_0}/nome',
                    'incluir': True, 'conferido': True,
                    'valor': 'MARIA DA SILVA',
                },
                {
                    'chave': f'{chave_0}/documento_identificacao/valor',
                    'incluir': True, 'conferido': True,
                    'valor': '98765432100',
                },
                {
                    'chave': f'{chave_1}/nome',
                    'incluir': True, 'conferido': True,
                    'valor': 'JOÃO DA SILVA',
                },
                {
                    'chave': f'{chave_1}/documento_identificacao/valor',
                    'incluir': True, 'conferido': True,
                    'valor': '12345678900',
                },
            ],
        })

        self.assertEqual(resposta.status_code, 200, resposta.content)
        self.assertCountEqual(
            resposta.json()['partes_invalidadas'], [chave_0, chave_1],
        )

    def test_tipo_documento_invalido_e_recusado(self):
        extracao = self._extracao()

        resposta = self._post_json('salvar_bloco_ocr', {
            'versao': services.versao_bloco(extracao),
            'decisoes': [{
                'chave': '/document/tipo', 'incluir': True, 'valor': 'matriculaa',
            }],
        })

        self.assertEqual(resposta.status_code, 422, resposta.content)
        self.assertEqual(resposta.json()['erro'], 'valor_invalido')
        self.assertEqual(resposta.json()['chave'], '/document/tipo')

    def test_origem_tipo_documento_invalido_e_recusado(self):
        payload = payload_registro(self.job.job_id)
        payload['acts'][0]['origem'] = {
            'tipo_documento': dict(payload['document']['tipo']),
        }
        extracao = self._extracao(payload)
        chave = '/acts/0/origem/tipo_documento'
        self.assertTrue(extracao.campos.filter(chave=chave).exists())

        resposta = self._post_json('salvar_bloco_ocr', {
            'versao': services.versao_bloco(extracao),
            'decisoes': [{
                'chave': chave, 'incluir': True, 'valor': 'matriculaa',
            }],
        })

        self.assertEqual(resposta.status_code, 422, resposta.content)
        self.assertEqual(resposta.json()['erro'], 'valor_invalido')
        self.assertEqual(resposta.json()['chave'], chave)

    def test_escolha_de_pessoa_em_linha_de_cartorio_e_recusada(self):
        pessoa = Pessoas.objects.create(nome='FULANO DE TAL')
        extracao = self._extracao()

        resposta = self._post_json('salvar_bloco_ocr', {
            'versao': services.versao_bloco(extracao),
            'decisoes': [{
                'chave': '/document/cartorio', 'incluir': True,
                'escolha': {'pessoa_id': pessoa.pk, 'criar_novo': False},
            }],
        })

        self.assertEqual(resposta.status_code, 422, resposta.content)
        self.assertEqual(resposta.json(), {
            'erro': 'escolha_incompativel', 'chave': '/document/cartorio',
        })

    def test_salvar_devolve_pendencias_restantes(self):
        extracao = self._extracao()
        antes = revisao.pendencias(extracao)
        self.assertTrue(antes)

        resposta = self._post_json('salvar_bloco_ocr', {
            'versao': services.versao_bloco(extracao),
            'decisoes': [{
                'chave': '/document/numero', 'incluir': True, 'conferido': True,
            }],
        })

        self.assertEqual(resposta.status_code, 200, resposta.content)
        devolvidas = resposta.json()['pendencias']
        self.assertEqual(
            devolvidas,
            [
                {'chave': item['chave'], 'motivo': item['motivo']}
                for item in revisao.pendencias(extracao)
            ],
        )
        self.assertTrue(devolvidas)
        self.assertIn(antes[0]['chave'], [item['chave'] for item in devolvidas])

    def test_salvar_ultima_pendencia_devolve_lista_vazia(self):
        extracao = self._extracao()

        def decisao_da(chave):
            campo = extracao.campos.get(chave=chave)
            decisao = {'incluir': True, 'conferido': True}
            if campo.tipo_valor in ('cartorio', 'parte'):
                decisao['escolha'] = {'criar_novo': True}
            return decisao

        # Resolve tudo menos uma pendência pelo serviço; só a última passa
        # pela view, que é quem devolve o estado restante para a tela.
        restantes = revisao.pendencias(extracao)
        for _ in range(extracao.campos.count()):
            if len(restantes) <= 1:
                break
            chave = restantes[0]['chave']
            services.salvar_bloco(
                extracao, {chave: decisao_da(chave)},
                self.dono, services.versao_bloco(extracao),
            )
            restantes = revisao.pendencias(extracao)
        self.assertEqual(len(restantes), 1)

        ultima = restantes[0]['chave']
        resposta = self._post_json('salvar_bloco_ocr', {
            'versao': services.versao_bloco(extracao),
            'decisoes': [{'chave': ultima, **decisao_da(ultima)}],
        })

        self.assertEqual(resposta.status_code, 200, resposta.content)
        self.assertEqual(resposta.json()['pendencias'], [])
        self.assertEqual(revisao.pendencias(extracao), [])

    def test_salvar_bloco_conflito_409_com_chaves(self):
        extracao = self._extracao()
        versao = services.versao_bloco(extracao)
        linha = extracao.campos.get(chave='/document/data')
        versao_linha = revisao.versao_linha(linha)
        services.salvar_bloco(extracao, {
            linha.chave: {'incluir': True, 'valor': '2020-01-11'},
        }, self.dono, versao)

        resposta = self._post_json('salvar_bloco_ocr', {
            'versao': versao,
            'decisoes': [{
                'chave': linha.chave, 'incluir': True,
                'valor': '2020-01-12', 'versao': versao_linha,
            }],
        })

        self.assertEqual(resposta.status_code, 409)
        self.assertEqual(resposta.json(), {
            'erro': 'conflito_versao', 'chaves': [linha.chave],
        })
        linha.refresh_from_db()
        self.assertEqual(linha.valor_final, '2020-01-11')

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
        for status, _rotulo in estados.STATUS_CHOICES:
            if status in (estados.EXTRAIDO, estados.REVISADO):
                continue
            with self.subTest(status=status):
                OcrJob.objects.filter(pk=self.job.pk).update(status=status)

                resposta = self.client.get(self.url('campos_job_ocr'))

                self.assertRedirects(resposta, self.url_tela(), fetch_redirect_response=False)
                self.assertEqual(self.mensagens(resposta)[-1][0], 'info')

    def test_campos_contexto_da_extracao_vigente_e_somente_leitura(self):
        self._extracao()
        vigente = self._extracao()
        for status, dpi in ((estados.EXTRAIDO, 300), (estados.REVISADO, None)):
            with self.subTest(status=status), mock.patch(
                'ia_ocr.views.render', return_value=HttpResponse(),
            ) as renderizar:
                OcrJob.objects.filter(pk=self.job.pk).update(status=status, dpi=dpi)

                resposta = self.client.get(self.url('campos_job_ocr'))

                self.assertEqual(resposta.status_code, 200)
                self.assertEqual(renderizar.call_args.args[1], 'ia_ocr/revisao_campos.html')
                contexto = renderizar.call_args.args[2]
                self.assertEqual(contexto['extracao'], vigente)
                chaves = [campo.chave for campo in contexto['campos']]
                self.assertEqual(chaves, sorted(chaves))
                agrupados = [
                    campo for grupo in contexto['por_destino'].values() for campo in grupo
                ]
                self.assertCountEqual(agrupados, contexto['campos'])
                self.assertEqual(
                    contexto['por_destino']['dominial.Documento.data'],
                    [vigente.campos.get(chave='/document/data')],
                )
                self.assertEqual(contexto['pendencias'], revisao.pendencias(vigente))
                self.assertEqual(contexto['avisos'], revisao.avisos(vigente))
                self.assertEqual(contexto['versao'], services.versao_bloco(vigente))
                self.assertEqual(contexto['somente_leitura'], status == estados.REVISADO)
                self.assertEqual(contexto['dpi'], dpi or 200)
                self.assertEqual(contexto['url_salvar'], self.url('salvar_bloco_ocr'))
                self.assertEqual(contexto['url_finalizar'], self.url('finalizar_revisao_ocr'))
                self.assertEqual(contexto['url_texto'], self.url_tela())
                self.assertEqual(contexto['url_documento'], self._url_documento())

    def test_campos_versao_vem_da_mesma_lista_exibida(self):
        extracao = self._extracao()
        pendencias = revisao.pendencias

        def outro_revisor_grava_durante_o_get(*args, **kwargs):
            # Commit concorrente depois de a view já ter lido as linhas.
            services.salvar_bloco(extracao, {
                '/document/livro': {'incluir': False},
            }, self.dono, services.versao_bloco(extracao))
            return pendencias(*args, **kwargs)

        with mock.patch(
            'ia_ocr.views.render', return_value=HttpResponse(),
        ) as renderizar, mock.patch(
            'ia_ocr.views.revisao.pendencias',
            side_effect=outro_revisor_grava_durante_o_get,
        ):
            resposta = self.client.get(self.url('campos_job_ocr'))

        self.assertEqual(resposta.status_code, 200)
        contexto = renderizar.call_args.args[2]
        exibido = {campo.chave: campo for campo in contexto['campos']}
        self.assertNotEqual(exibido['/document/livro'].status_revisao, 'descartado')
        self.assertEqual(
            contexto['versao'],
            services.versao_bloco(extracao, campos=contexto['campos']),
        )
        self.assertNotEqual(contexto['versao'], services.versao_bloco(extracao))
        # Com o token da tela, a gravação seguinte esbarra no save do outro.
        resposta = self._post_json('salvar_bloco_ocr', {
            'versao': contexto['versao'],
            'decisoes': [{'chave': '/document/livro', 'incluir': True}],
        })
        self.assertEqual(resposta.status_code, 409)
