"""Regressões do pacote 2a: decisões de cadastro e tipo efetivo do ato."""

from copy import deepcopy
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from dominial.models import Cartorios, Pessoas
from ia_ocr import estados, revisao, services, valores
from ia_ocr.models import CampoSugerido, ExtracaoSugerida, OcrJob, PaginaOcr

from .factories import criar_documento_digital, criar_usuario
from .payloads_extracao import PROVIDER, SCHEMA_VERSION, TEXTO_PAGINA_1, payload_registro


class RevisaoSemanticaTest(TestCase):
    def setUp(self):
        self.usuario = criar_usuario()
        self.joao = Pessoas.objects.create(nome='JOÃO DA SILVA', cpf='12345678900')
        self.maria = Pessoas.objects.create(nome='MARIA DA SILVA', cpf='98765432100')
        self.cartorio = Cartorios.objects.create(nome='CRI de Guaíra', estado='SP')
        self.job = OcrJob.objects.create(
            documento_digital=criar_documento_digital(upload_por=self.usuario),
            status=estados.EXTRAIDO, criado_por=self.usuario,
        )
        pagina = PaginaOcr.objects.create(
            ocr_job=self.job, numero_pagina=1, texto_ocr=TEXTO_PAGINA_1,
        )
        payload = payload_registro(self.job.job_id)
        cartorio = payload['document']['cartorio']
        payload['document']['cri_atual'] = deepcopy(cartorio)
        ato = payload['acts'][0]
        ato['origem'] = {'cartorio': deepcopy(cartorio)}
        ato['cartorio_transmissao'] = deepcopy(cartorio)
        ato['titulo'] = dict(ato['rotulo'], normalized='Compra e venda')
        enriquecido = revisao.enriquecer_payload(
            payload, revisao.IndicePessoas(), revisao.IndiceCartorios(),
        )
        self.extracao = ExtracaoSugerida.objects.create(
            ocr_job=self.job, schema_version=SCHEMA_VERSION,
            payload=enriquecido, payload_servico=payload, provider=PROVIDER,
        )
        CampoSugerido.objects.bulk_create(
            revisao.desnormalizar(self.extracao, enriquecido, [pagina]),
        )
        decisoes = {}
        for campo in self.extracao.campos.all():
            decisao = {'incluir': True, 'conferido': True}
            if campo.tipo_valor == 'parte' and not campo.pessoa_escolhida_id:
                decisao['escolha'] = {'criar_novo': True}
            decisoes[campo.chave] = decisao
        self._salvar(decisoes)
        self.assertEqual(revisao.pendencias(self.extracao), [])
        self.parte = self.extracao.campos.get(chave='/acts/0/partes/0')
        self.assertEqual(self.parte.pessoa_escolhida_id, self.joao.pk)

    def _salvar(self, decisoes):
        return services.salvar_bloco(
            self.extracao, decisoes, self.usuario,
            services.versao_bloco(self.extracao),
        )

    def _escolher(self, pessoa_id):
        self._salvar({self.parte.chave: {
            'incluir': True, 'conferido': True,
            'escolha': {'pessoa_escolhida_id': pessoa_id},
        }})
        self.parte.refresh_from_db()

    def _assert_escolha_pendente(self, candidatos):
        self.parte.refresh_from_db()
        self.assertIsNone(self.parte.pessoa_escolhida_id)
        self.assertEqual(self.parte.match_candidatos, candidatos)
        self.assertFalse(self.parte.criar_novo)
        pendencia = {
            'chave': self.parte.chave, 'motivo': 'escolha_pendente',
            'bloqueante': True,
        }
        self.assertIn(pendencia, revisao.pendencias(self.extracao))
        with self.assertRaises(services.RevisaoIncompleta) as erro:
            services.finalizar_revisao(self.extracao, self.usuario)
        self.assertIn(pendencia, erro.exception.pendencias)
        self.extracao.refresh_from_db()
        self.job.refresh_from_db()
        self.assertIsNone(self.extracao.finalizada_em)
        self.assertEqual(self.job.status, estados.EXTRAIDO)

    def test_criar_cartorios_rejeita_candidato_unico_e_preserva_intencao_no_dto(self):
        chaves = (
            '/document/cartorio', '/document/cri_atual',
            '/acts/0/origem/cartorio', '/acts/0/cartorio_transmissao',
        )
        for chave in chaves:
            self.assertEqual(
                self.extracao.campos.get(chave=chave).match_candidatos,
                [self.cartorio.pk],
            )
        self._salvar({chave: {
            'incluir': True, 'conferido': True, 'escolha': {'criar_novo': True},
        } for chave in chaves})
        self.assertEqual(revisao.pendencias(self.extracao), [])
        finalizada = services.finalizar_revisao(self.extracao, self.usuario)
        dados = revisao.dados_revisados(finalizada)

        for dto, campo in (
            (dados.documento, 'cartorio'), (dados.documento, 'cri_atual'),
            (dados.atos[0], 'cartorio_origem'),
            (dados.atos[0], 'cartorio_transmissao'),
        ):
            with self.subTest(campo=campo):
                self.assertIsNone(getattr(dto, f'{campo}_id'))
                self.assertTrue(getattr(dto, f'{campo}_criar_novo'))
        self.assertIsNone(dados.atos[0].origem['cartorio_id'])
        self.assertTrue(dados.atos[0].origem['cartorio_criar_novo'])

    def test_criar_cartorio_prevalece_sobre_id_residual(self):
        self.extracao.campos.filter(chave='/document/cartorio').update(criar_novo=True)
        finalizada = services.finalizar_revisao(self.extracao, self.usuario)
        documento = revisao.dados_revisados(finalizada).documento
        self.assertIsNone(documento.cartorio_id)
        self.assertTrue(documento.cartorio_criar_novo)

    def test_tipo_invalido_persistido_bloqueia_finalizacao(self):
        chave = '/acts/0/tipo_sugerido'
        for origem in ('normalized', 'valor_final'):
            with self.subTest(origem=origem):
                self.extracao.campos.filter(chave=chave).update(**{origem: 'registroo'})
                with self.assertRaises(services.RevisaoIncompleta) as erro:
                    services.finalizar_revisao(self.extracao, self.usuario)
                self.assertIn({
                    'chave': chave, 'motivo': valores.MOTIVO_INCOMPATIVEL,
                    'bloqueante': True,
                }, erro.exception.pendencias)
                self.extracao.campos.filter(chave=chave).update(
                    normalized='registro', valor_final=None,
                )

    def test_corrigir_nome_e_cpf_exige_nova_escolha_antes_de_finalizar(self):
        self._escolher(self.joao.pk)
        antes = revisao.versao_linha(self.parte)
        inicio = timezone.now()
        self._salvar({
            f'{self.parte.chave}/nome': {'incluir': True, 'valor': 'MARIA DA SILVA'},
            f'{self.parte.chave}/documento_identificacao/valor': {
                'incluir': True, 'valor': '98765432100',
            },
        })
        self._assert_escolha_pendente([self.maria.pk])
        self.assertNotEqual(revisao.versao_linha(self.parte), antes)
        self.assertEqual(self.parte.revisado_por, self.usuario)
        self.assertGreaterEqual(self.parte.revisado_em, inicio)
        outra = self.extracao.campos.get(chave='/acts/0/partes/1')
        self.assertEqual(outra.pessoa_escolhida_id, self.maria.pk)

        self._escolher(self.maria.pk)
        self.assertEqual(revisao.pendencias(self.extracao), [])
        finalizada = services.finalizar_revisao(self.extracao, self.usuario)
        parte = revisao.dados_revisados(finalizada).atos[0].partes[0]
        self.assertEqual((parte.nome, parte.cpf, parte.pessoa_id), (
            'MARIA DA SILVA', '98765432100', self.maria.pk,
        ))

    def test_correcao_de_identidade_recomputa_candidatos_e_exige_nova_escolha(self):
        outra = self.extracao.campos.get(chave='/acts/0/partes/1')
        with patch('ia_ocr.services.IndicePessoas', wraps=revisao.IndicePessoas) as indice:
            self._salvar({
                f'{self.parte.chave}/nome': {'incluir': True, 'valor': self.maria.nome},
                f'{self.parte.chave}/documento_identificacao/valor': {
                    'incluir': True, 'valor': self.maria.cpf,
                },
                f'{outra.chave}/nome': {'incluir': True, 'valor': self.joao.nome},
                f'{outra.chave}/documento_identificacao/valor': {
                    'incluir': True, 'valor': self.joao.cpf,
                },
            })
        self._assert_escolha_pendente([self.maria.pk])
        outra.refresh_from_db()
        self.assertIsNone(outra.pessoa_escolhida_id)
        self.assertEqual(outra.match_candidatos, [self.joao.pk])
        self.assertFalse(outra.criar_novo)
        indice.assert_called_once_with()

    def test_escolher_a_pessoa_recomputada_finaliza(self):
        self._salvar({
            f'{self.parte.chave}/nome': {'incluir': True, 'valor': self.maria.nome},
            f'{self.parte.chave}/documento_identificacao/valor': {
                'incluir': True, 'valor': self.maria.cpf,
            },
        })
        self._assert_escolha_pendente([self.maria.pk])
        self._escolher(self.parte.match_candidatos[0])
        self.assertEqual(revisao.pendencias(self.extracao), [])

        finalizada = services.finalizar_revisao(self.extracao, self.usuario)
        parte = revisao.dados_revisados(finalizada).atos[0].partes[0]
        self.assertEqual(parte.pessoa_id, self.maria.pk)
        self.assertEqual((parte.nome, parte.cpf), (self.maria.nome, self.maria.cpf))

    def test_cada_campo_de_identidade_invalida_match_automatico(self):
        for sufixo, valor, candidatos in (
            ('nome', 'MARIA DA SILVA', [self.joao.pk]),
            ('documento_identificacao/valor', '98765432100', [self.maria.pk]),
            ('documento_identificacao/tipo', 'RG', [self.maria.pk]),
        ):
            with self.subTest(sufixo=sufixo):
                # A tela só oferece quem está em match_candidatos: recomputar
                # antes de escolher mantém o cenário do select real.
                self.extracao.campos.filter(pk=self.parte.pk).update(
                    match_candidatos=[self.joao.pk],
                )
                self._escolher(self.joao.pk)
                self._salvar({f'{self.parte.chave}/{sufixo}': {
                    'incluir': True, 'valor': valor,
                }})
                self._assert_escolha_pendente(candidatos)

    def test_escolha_no_mesmo_bloco_nao_sobrevive_a_correcao_em_qualquer_ordem(self):
        for escolha_primeiro, nome in ((True, 'MARIA DA SILVA'), (False, 'JOÃO DA SILVA')):
            with self.subTest(escolha_primeiro=escolha_primeiro):
                itens = [
                    (self.parte.chave, {
                        'incluir': True, 'conferido': True,
                        'escolha': {'pessoa_escolhida_id': self.joao.pk},
                    }),
                    (f'{self.parte.chave}/nome', {'incluir': True, 'valor': nome}),
                ]
                self._salvar(dict(itens if escolha_primeiro else reversed(itens)))
                self._assert_escolha_pendente([self.joao.pk])

    def test_reenvio_sem_mudar_identidade_preserva_escolha(self):
        antes = revisao.versao_linha(self.parte)
        with patch('ia_ocr.services.IndicePessoas', wraps=revisao.IndicePessoas) as indice:
            self._salvar({
                f'{self.parte.chave}/nome': {
                    'incluir': True, 'conferido': True, 'valor': 'JOÃO DA SILVA',
                },
                f'{self.parte.chave}/documento_identificacao/valor': {
                    'incluir': True, 'conferido': True, 'valor': '12345678900',
                },
                '/document/livro': {'incluir': True, 'valor': '3-A'},
            })
        indice.assert_not_called()
        self.parte.refresh_from_db()
        self.assertEqual(self.parte.pessoa_escolhida_id, self.joao.pk)
        self.assertEqual(self.parte.match_candidatos, [self.joao.pk])
        self.assertEqual(revisao.versao_linha(self.parte), antes)

    def test_correcao_invalida_tambem_decisao_anterior_de_criar_pessoa(self):
        self._salvar({self.parte.chave: {
            'incluir': True, 'conferido': True, 'escolha': {'criar_novo': True},
        }})
        self._salvar({f'{self.parte.chave}/nome': {
            'incluir': True, 'valor': 'MARIA DA SILVA',
        }})
        self._assert_escolha_pendente([self.joao.pk])
