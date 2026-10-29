"""Testes HTTP da rota de importação da revisão (I-6 / #263).

Mesmo contrato JSON das outras ações do bloco de revisão: 404/405/CSRF em
JSON, 422 para recusas e erros de ato, 409 para conflito de versão e
transição concorrente. O cenário de dados é o sintético da revisão.
"""

import json
from datetime import date

from django.test import Client
from django.utils import timezone

from dominial.models import Lancamento, LancamentoTipo
from ia_ocr import services
from ia_ocr.models import CampoSugerido, ExtracaoSugerida, OcrJob, PaginaOcr
from ia_ocr.revisao import desnormalizar

from .base_texto import TelaTextoBase
from .payloads_extracao import (
    SCHEMA_VERSION, TEXTO_PAGINA_1, payload_registro,
)


class ImportacaoViewBase(TelaTextoBase):
    """Job ``revisado`` pendurado no documento do cenário da tela."""

    def setUp(self):
        super().setUp()
        self.job = OcrJob.objects.create(
            documento_digital=self.arquivo, status='revisado',
        )
        self.pagina = PaginaOcr.objects.create(
            ocr_job=self.job, numero_pagina=1, texto_ocr=TEXTO_PAGINA_1,
        )
        self.tipo_registro = LancamentoTipo.objects.create(tipo='registro')
        self.client.force_login(self.dono)

    @staticmethod
    def _campo(valor, trecho=None):
        campo = {
            'raw': valor, 'normalized': valor, 'confianca': 0.95,
            'requer_revisao': False,
        }
        if trecho:
            campo['evidencia'] = {'pagina': 1, 'trecho': trecho}
        return campo

    def _extracao(self, payload=None):
        payload = payload or payload_registro(self.job.job_id)
        extracao = ExtracaoSugerida.objects.create(
            ocr_job=self.job, schema_version=SCHEMA_VERSION,
            payload=payload, payload_servico=payload, provider='local-model',
        )
        linhas = desnormalizar(extracao, payload, [self.pagina])
        for linha in linhas:
            if linha.tipo_valor in ('parte', 'cartorio'):
                linha.criar_novo = True
        CampoSugerido.objects.bulk_create(linhas)
        extracao.finalizada_em = timezone.now()
        extracao.save(update_fields=['finalizada_em'])
        return extracao

    def post_importar(self, corpo, job=None, cliente=None):
        return (cliente or self.client).post(
            self.url('importar_job_ocr', job),
            data=json.dumps(corpo),
            content_type='application/json',
        )


class ImportarJobOcrAcessoTest(ImportacaoViewBase):
    def test_sem_login_redireciona(self):
        self.client.logout()

        resposta = self.client.post(
            self.url('importar_job_ocr'), data='{}',
            content_type='application/json',
        )

        self.assertEqual(resposta.status_code, 302)

    def test_usuario_sem_acesso_recebe_404_json(self):
        self.client.force_login(self.sem_acesso)

        resposta = self.client.post(
            self.url('importar_job_ocr'), data='{}',
            content_type='application/json',
        )

        self.assertEqual(resposta.status_code, 404)
        self.assertEqual(resposta.json(), {'erro': 'nao_encontrado'})

    def test_get_nao_permitido_em_json(self):
        resposta = self.client.get(self.url('importar_job_ocr'))

        self.assertEqual(resposta.status_code, 405)
        self.assertEqual(resposta.json(), {'erro': 'metodo_nao_permitido'})
        self.assertEqual(resposta['Allow'], 'POST')

    def test_csrf_invalido_e_403_json(self):
        cliente = Client(enforce_csrf_checks=True)
        cliente.force_login(self.dono)

        resposta = cliente.post(
            self.url('importar_job_ocr'),
            data=json.dumps({'versao': 'x', 'atos': ['/acts/0']}),
            content_type='application/json',
        )

        self.assertEqual(resposta.status_code, 403)
        self.assertEqual(resposta.json(), {'erro': 'csrf_invalido'})

    def test_json_quebrado_e_400(self):
        resposta = self.client.post(
            self.url('importar_job_ocr'), data='{invalido',
            content_type='application/json',
        )

        self.assertEqual(resposta.status_code, 400)
        self.assertEqual(resposta.json(), {'erro': 'json_invalido'})

    def test_sem_extracao_e_422(self):
        resposta = self.client.post(
            self.url('importar_job_ocr'),
            data=json.dumps({'versao': 'x', 'atos': ['/acts/0']}),
            content_type='application/json',
        )

        self.assertEqual(resposta.status_code, 422)
        self.assertEqual(resposta.json(), {
            'erro': 'sem_extracao', 'chave': None,
        })


class ImportarJobOcrResultadoTest(ImportacaoViewBase):
    def _corpo(self, extracao, atos=('/acts/0',)):
        return {
            'versao': services.versao_bloco(extracao),
            'atos': list(atos),
        }

    def test_importa_e_devolve_as_linhas(self):
        extracao = self._extracao()

        resposta = self.post_importar(self._corpo(extracao))

        self.assertEqual(resposta.status_code, 200)
        corpo = resposta.json()
        self.assertTrue(corpo['ok'])
        (linha,) = corpo['linhas']
        self.assertEqual(linha['chave'], '/acts/0')
        self.assertEqual(linha['status'], 'criado')
        self.assertEqual(linha['lancamento_id'], Lancamento.objects.get().pk)
        self.assertIn('/editar/', linha['url'])
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, 'importado')

    def test_duplicidade_e_422_com_as_linhas(self):
        extracao = self._extracao()
        Lancamento.objects.create(
            documento=self.documento, tipo=self.tipo_registro,
            numero_lancamento=None, data=date(2020, 2, 15),
        )

        resposta = self.post_importar(self._corpo(extracao))

        self.assertEqual(resposta.status_code, 422)
        corpo = resposta.json()
        self.assertEqual(corpo['erro'], 'importacao_invalida')
        (linha,) = corpo['linhas']
        self.assertEqual(linha['status'], 'erro')
        (erro,) = linha['erros']
        self.assertEqual(erro['codigo'], 'lancamento_duplicado')
        self.assertIn('url', erro['existente'])

    def test_versao_velha_e_409(self):
        extracao = self._extracao()
        versao_velha = services.versao_bloco(extracao)
        CampoSugerido.objects.filter(chave='/acts/0/area').update(
            valor_final='9.99',
        )

        resposta = self.post_importar(
            {'versao': versao_velha, 'atos': ['/acts/0']},
        )

        self.assertEqual(resposta.status_code, 409)
        self.assertEqual(resposta.json(), {'erro': 'conflito_versao', 'chaves': []})

    def test_versao_ausente_e_422(self):
        self._extracao()

        resposta = self.post_importar({'versao': None, 'atos': ['/acts/0']})

        self.assertEqual(resposta.status_code, 422)
        self.assertEqual(resposta.json(), {
            'erro': 'versao_ausente', 'chave': None,
        })

    def test_atos_vazio_e_422(self):
        extracao = self._extracao()

        resposta = self.post_importar(
            {'versao': services.versao_bloco(extracao), 'atos': []},
        )

        self.assertEqual(resposta.status_code, 422)
        self.assertEqual(resposta.json(), {
            'erro': 'nenhum_ato', 'chave': None,
        })

    def test_job_extraido_e_422_estado_invalido(self):
        extracao = self._extracao()
        self.job.status = 'extraido'
        self.job.save(update_fields=['status'])

        resposta = self.post_importar(self._corpo(extracao))

        self.assertEqual(resposta.status_code, 422)
        self.assertEqual(resposta.json(), {
            'erro': 'estado_invalido', 'chave': None,
        })
