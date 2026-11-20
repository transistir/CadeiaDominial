"""Parte 2 de 3 do corpo de ``ExtracaoViewsTest`` — migração VERBATIM de
``ia_ocr/tests/test_extracao_views.py`` (Etapa 12 do plano de 400 linhas).

Classe SIMPLES (sem ``TestCase``); quem coleta é a fachada em
``test_extracao_views_extracao.py``. Corpos verbatim.
"""

from dominial.managers import documentos_for_user
from dominial.models import LancamentoTipo, Pessoas
from ia_ocr import revisao, services

from .payloads_extracao import payload_averbacao, payload_registro


class ExtracaoViewsTestParte2:
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
            'campos_novos': [],
            'pendencias': [
                {'chave': item['chave'], 'motivo': item['motivo']}
                for item in revisao.pendencias(extracao)
            ],
            'sem_atos_elegivel': False,
            # #324: os avisos recalculados do estado recém-salvo, da mesma
            # fonte da abertura da tela (revisao.avisos + descrever_aviso).
            'avisos': [
                {
                    'chave': item['chave'], 'motivo': item['motivo'],
                    'local': item['local'], 'rotulo': item['rotulo'],
                    'nao_consta': item['motivo'].endswith('_origem_nao_consta'),
                }
                for item in map(
                    revisao.descrever_aviso,
                    revisao.avisos(
                        extracao,
                        documentos_queryset=documentos_for_user(self.dono),
                    ),
                )
            ],
        })
        self.assertNotEqual(resposta.json()['versao'], versao)
        campo = extracao.campos.get(chave='/document/data')
        self.assertEqual(campo.valor_final, '2020-01-11')
        self.assertEqual(campo.revisado_por, self.dono)
        self.assertIsNotNone(campo.revisado_em)

    def test_mudar_tipo_devolve_campos_novos_sem_repetir_no_segundo_save(self):
        LancamentoTipo.objects.create(
            tipo='averbacao', requer_descricao=True, requer_observacao=False,
        )
        LancamentoTipo.objects.create(
            tipo='registro', requer_titulo=True,
            requer_cartorio_origem=True, requer_observacao=False,
        )
        extracao = self._extracao(payload_averbacao(self.job.job_id))

        resposta = self._post_json('salvar_bloco_ocr', {
            'versao': services.versao_bloco(extracao),
            'decisoes': [{
                'chave': '/acts/0/tipo_sugerido',
                'incluir': True, 'valor': 'registro',
            }],
        })

        self.assertEqual(resposta.status_code, 200, resposta.content)
        # #324 rodada 2: título + cartório de origem + as 5 linhas da origem.
        self.assertEqual(
            sorted(resposta.json()['campos_novos']),
            [
                '/acts/0/origem/cartorio', '/acts/0/origem/data',
                '/acts/0/origem/folha', '/acts/0/origem/livro',
                '/acts/0/origem/numero', '/acts/0/origem/tipo_documento',
                '/acts/0/titulo',
            ],
        )

        repetido = self._post_json('salvar_bloco_ocr', {
            'versao': resposta.json()['versao'],
            'decisoes': [{
                'chave': '/acts/0/tipo_sugerido',
                'incluir': True, 'valor': 'registro',
            }],
        })

        self.assertEqual(repetido.status_code, 200, repetido.content)
        self.assertEqual(repetido.json()['campos_novos'], [])

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
