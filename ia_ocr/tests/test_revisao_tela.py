"""Tela de revisão de campos (I-5): render, escape, pendências e somente leitura."""

import re

from django.conf import settings
from django.shortcuts import resolve_url
from django.utils import timezone

from ia_ocr import estados, revisao
from ia_ocr.models import CampoSugerido, ExtracaoSugerida, OcrJob

from .base_texto import TelaTextoBase
from .payloads_extracao import (
    PROVIDER, SCHEMA_VERSION, TEXTO_PAGINA_1, payload_averbacao,
)

RAW_MALICIOSO = '<script>alert(1)</script>"><img onerror=1>'


class RevisaoTelaTest(TelaTextoBase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.dono)
        self.documento.tipo.tipo = 'matricula'
        self.documento.tipo.save(update_fields=['tipo'])
        self.job.paginas.filter(numero_pagina=1).update(texto_ocr=TEXTO_PAGINA_1)
        OcrJob.objects.filter(pk=self.job.pk).update(status=estados.EXTRAIDO)
        self.job.refresh_from_db()

    def _extracao(self, payload=None, resolver=False):
        payload = payload or payload_averbacao(self.job.job_id)
        extracao = ExtracaoSugerida.objects.create(
            ocr_job=self.job, schema_version=SCHEMA_VERSION,
            payload=payload, payload_servico=payload, provider=PROVIDER,
        )
        linhas = revisao.desnormalizar(extracao, payload, list(self.job.paginas.all()))
        if resolver:
            for linha in linhas:
                linha.status_revisao = 'aceito'
                if linha.tipo_valor in ('parte', 'cartorio'):
                    linha.criar_novo = True
        CampoSugerido.objects.bulk_create(linhas)
        return extracao

    def _tela(self):
        return self.client.get(self.url('campos_job_ocr'))

    def _botao_finalizar(self, resposta):
        html = resposta.content.decode()
        botao = re.search(r'<button[^>]*data-ocr-finalizar[^>]*>', html)
        self.assertIsNotNone(botao)
        return botao.group(0)

    def test_tela_exige_extraido(self):
        self._extracao()
        OcrJob.objects.filter(pk=self.job.pk).update(status=estados.CONCLUIDO)

        resposta = self._tela()

        self.assertRedirects(resposta, self.url_tela(), fetch_redirect_response=False)
        self.assertTrue(self.mensagens(resposta))

    def test_tela_renderiza_campos_e_versao(self):
        extracao = self._extracao()

        resposta = self._tela()

        self.assertEqual(resposta.status_code, 200)
        self.assertTemplateUsed(resposta, 'ia_ocr/revisao_campos.html')
        self.assertContains(resposta, 'data-ocr-revisao')
        self.assertContains(resposta, f'data-versao="{resposta.context["versao"]}"')
        self.assertContains(resposta, ' data-campo\n', count=extracao.campos.count())
        self.assertContains(resposta, '← Voltar ao processamento')

    def test_tela_escapa_texto_do_ocr(self):
        payload = payload_averbacao(self.job.job_id)
        payload['document']['numero']['raw'] = RAW_MALICIOSO
        self._extracao(payload)

        resposta = self._tela()

        self.assertEqual(resposta.status_code, 200)
        self.assertNotContains(resposta, '<script>alert(1)</script>')
        self.assertNotContains(resposta, '"><img onerror=1>')
        self.assertContains(resposta, '&lt;script&gt;alert(1)&lt;/script&gt;')
        self.assertContains(resposta, '&quot;&gt;&lt;img onerror=1&gt;')

    def test_tela_mostra_pendencias_e_desabilita_finalizar(self):
        extracao = self._extracao()
        self.assertTrue(revisao.pendencias(extracao))

        resposta = self._tela()

        self.assertContains(resposta, 'data-ocr-pendencias')
        self.assertIn('disabled', self._botao_finalizar(resposta))

    def test_tela_sem_pendencia_habilita_finalizar(self):
        extracao = self._extracao(resolver=True)
        self.assertEqual(revisao.pendencias(extracao), [])

        resposta = self._tela()

        self.assertNotContains(resposta, 'data-ocr-pendencias')
        self.assertNotIn('disabled', self._botao_finalizar(resposta))
        self.assertNotContains(resposta, 'data-ocr-somente-leitura')

    def test_tela_somente_leitura_apos_revisado(self):
        extracao = self._extracao(resolver=True)
        ExtracaoSugerida.objects.filter(pk=extracao.pk).update(
            finalizada_em=timezone.now(), finalizada_por=self.dono,
        )
        OcrJob.objects.filter(pk=self.job.pk).update(status=estados.REVISADO)

        resposta = self._tela()

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, 'data-ocr-somente-leitura')
        self.assertIn('disabled', self._botao_finalizar(resposta))
        html = resposta.content.decode()
        valores = re.findall(r'<(?:input|textarea)[^>]*data-campo-valor[^>]*>', html)
        self.assertEqual(len(valores), extracao.campos.count())
        for tag in valores:
            self.assertIn(' disabled', tag)

    def test_tela_exige_login_e_permissao(self):
        self._extracao()
        url = self.url('campos_job_ocr')

        self.client.logout()
        resposta = self.client.get(url)
        self.assertEqual(resposta.status_code, 302)
        self.assertTrue(resposta.url.startswith(
            f'{resolve_url(settings.LOGIN_URL)}?next=',
        ))

        self.client.force_login(self.sem_acesso)
        self.assertEqual(self.client.get(url).status_code, 404)
