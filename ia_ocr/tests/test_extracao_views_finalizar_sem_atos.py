"""``FinalizarSemAtosViewsTest`` (issue #262) — migração VERBATIM de
``ia_ocr/tests/test_extracao_views.py`` (Etapa 12 do plano de 400 linhas).

Classe inteira neste arquivo; nome e ids de teste preservados.
"""

import json

from django.test import override_settings
from django.urls import reverse

from ia_ocr import estados, revisao, services
from ia_ocr.models import CampoSugerido, ExtracaoSugerida, OcrJob

from .base_texto import TelaTextoBase
from .payloads_extracao import (
    PROVIDER, SCHEMA_VERSION, TEXTO_PAGINA_1, payload_averbacao,
)


class FinalizarSemAtosViewsTest(TelaTextoBase):
    """Issue #262: POST finalizar aceita sem_atos só sob flag e tipo booleano."""

    def setUp(self):
        super().setUp()
        self.client.force_login(self.dono)
        self.documento.tipo.tipo = 'matricula'
        self.documento.tipo.save(update_fields=['tipo'])
        self.job.paginas.filter(numero_pagina=1).update(texto_ocr=TEXTO_PAGINA_1)
        OcrJob.objects.filter(pk=self.job.pk).update(status=estados.EXTRAIDO)
        self.job.refresh_from_db()

    def _extracao_sem_atos(self):
        payload = payload_averbacao(self.job.job_id)
        payload['acts'] = []
        extracao = ExtracaoSugerida.objects.create(
            ocr_job=self.job, schema_version=SCHEMA_VERSION,
            payload=payload, payload_servico=payload, provider=PROVIDER,
            solicitada_por=self.dono,
        )
        CampoSugerido.objects.bulk_create(
            revisao.desnormalizar(extracao, payload, list(self.job.paginas.all())),
        )
        # Sem atos, o cabeçalho ainda precisa das escolhas de cartório.
        extracao.campos.filter(tipo_valor='cartorio').update(criar_novo=True)
        self.assertEqual(revisao.pendencias(extracao), [{
            'chave': '/acts', 'motivo': 'nenhum_ato', 'bloqueante': True,
        }])
        return extracao

    def _url_documento(self):
        return reverse('documento_detalhado', kwargs={
            'tis_id': self.ti.pk,
            'imovel_id': self.imovel.pk,
            'documento_id': self.documento.pk,
        })

    def _post_finalizar(self, dados):
        return self.client.post(
            self.url('finalizar_revisao_ocr'),
            data=json.dumps(dados), content_type='application/json',
        )

    def _post_salvar(self, dados):
        return self.client.post(
            self.url('salvar_bloco_ocr'),
            data=json.dumps(dados), content_type='application/json',
        )

    @override_settings(OCR_PERMITIR_FINALIZAR_SEM_ATOS=True)
    def test_salvar_bloco_devolve_elegibilidade_sem_atos(self):
        # Issue #262: com acts=[] pendencias() é sempre nenhum_ato; a tela
        # precisa da elegibilidade separada para não mentir após um bloqueio.
        extracao = self._extracao_sem_atos()

        resposta = self._post_salvar({
            'versao': services.versao_bloco(extracao),
            'decisoes': [],
        })

        self.assertEqual(resposta.status_code, 200, resposta.content)
        self.assertIs(resposta.json()['sem_atos_elegivel'], True)

        # Obrigatório não se descarta pela API; o dado legado vem do banco.
        extracao.campos.filter(chave='/document/data').update(
            status_revisao='descartado',
        )
        bloqueio = self._post_salvar({
            'versao': services.versao_bloco(extracao),
            'decisoes': [],
        })

        self.assertEqual(bloqueio.status_code, 200, bloqueio.content)
        self.assertIs(bloqueio.json()['sem_atos_elegivel'], False)

    @override_settings(OCR_PERMITIR_FINALIZAR_SEM_ATOS=True)
    def test_salvar_data_vazia_cria_bloqueio_real(self):
        extracao = self._extracao_sem_atos()

        resposta = self._post_salvar({
            'versao': services.versao_bloco(extracao),
            'decisoes': [{
                'chave': '/document/data', 'incluir': True, 'valor': '',
            }],
        })

        self.assertEqual(resposta.status_code, 200, resposta.content)
        self.assertIs(resposta.json()['sem_atos_elegivel'], False)
        self.assertIn(
            {'chave': '/document/data', 'motivo': 'obrigatorio_ausente'},
            resposta.json()['pendencias'],
        )

    def test_incluir_false_sem_valor_preserva_correcao_obrigatoria(self):
        extracao = self._extracao_sem_atos()
        campo = extracao.campos.get(chave='/document/data')
        campo.valor_final = '2020-01-11'
        campo.status_revisao = 'editado'
        campo.save()

        resposta = self._post_salvar({
            'versao': services.versao_bloco(extracao),
            'decisoes': [{'chave': '/document/data', 'incluir': False}],
        })

        self.assertEqual(resposta.status_code, 200, resposta.content)
        campo.refresh_from_db()
        self.assertEqual(campo.valor_final, '2020-01-11')
        self.assertEqual(campo.status_revisao, 'editado')

    def test_incluir_false_valor_null_explicito_volta_ao_ocr(self):
        extracao = self._extracao_sem_atos()
        campo = extracao.campos.get(chave='/document/data')
        normalizado = campo.normalized
        campo.valor_final = '2020-01-11'
        campo.status_revisao = 'editado'
        campo.save()

        resposta = self._post_salvar({
            'versao': services.versao_bloco(extracao),
            'decisoes': [
                {'chave': '/document/data', 'incluir': False, 'valor': None},
            ],
        })

        self.assertEqual(resposta.status_code, 200, resposta.content)
        campo.refresh_from_db()
        # Sem valor_final o valor efetivo volta a ser o normalizado do OCR.
        self.assertIsNone(campo.valor_final)
        self.assertEqual(campo.normalized, normalizado)

    @override_settings(OCR_PERMITIR_FINALIZAR_SEM_ATOS=True)
    def test_flag_ligada_sem_atos_200_com_redirect(self):
        extracao = self._extracao_sem_atos()

        resposta = self._post_finalizar({
            'versao': services.versao_bloco(extracao),
            'sem_atos': True,
        })

        self.assertEqual(resposta.status_code, 200, resposta.content)
        self.assertEqual(resposta.json(), {
            'ok': True, 'redirect': self._url_documento(),
        })
        extracao.refresh_from_db()
        self.job.refresh_from_db()
        self.assertIsNotNone(extracao.finalizada_em)
        self.assertEqual(extracao.finalizada_por, self.dono)
        self.assertEqual(self.job.status, estados.REVISADO)
        self.assertEqual(
            self.job.transicoes.get(para_status=estados.REVISADO).motivo,
            'revisao_finalizada_sem_atos',
        )

    @override_settings(OCR_PERMITIR_FINALIZAR_SEM_ATOS=False)
    def test_flag_desligada_sem_atos_422(self):
        extracao = self._extracao_sem_atos()

        resposta = self._post_finalizar({
            'versao': services.versao_bloco(extracao),
            'sem_atos': True,
        })

        self.assertEqual(resposta.status_code, 422)
        self.assertEqual(resposta.json()['erro'], 'revisao_incompleta')
        self.assertEqual(resposta.json()['pendencias'], [{
            'chave': '/acts', 'motivo': 'nenhum_ato', 'bloqueante': True,
        }])
        extracao.refresh_from_db()
        self.job.refresh_from_db()
        self.assertIsNone(extracao.finalizada_em)
        self.assertEqual(self.job.status, estados.EXTRAIDO)

    @override_settings(OCR_PERMITIR_FINALIZAR_SEM_ATOS=True)
    def test_campo_obrigatorio_pendente_sem_atos_422(self):
        # Issue #262: confirmar "sem atos" não pode ignorar campo obrigatório
        # do documento que continua pendente.
        payload = payload_averbacao(self.job.job_id)
        payload['acts'] = []
        payload['document'].pop('data')
        extracao = ExtracaoSugerida.objects.create(
            ocr_job=self.job, schema_version=SCHEMA_VERSION,
            payload=payload, payload_servico=payload, provider=PROVIDER,
            solicitada_por=self.dono,
        )
        CampoSugerido.objects.bulk_create(
            revisao.desnormalizar(extracao, payload, list(self.job.paginas.all())),
        )

        resposta = self._post_finalizar({
            'versao': services.versao_bloco(extracao),
            'sem_atos': True,
        })

        self.assertEqual(resposta.status_code, 422, resposta.content)
        self.assertEqual(resposta.json()['erro'], 'revisao_incompleta')
        extracao.refresh_from_db()
        self.job.refresh_from_db()
        self.assertIsNone(extracao.finalizada_em)
        self.assertEqual(self.job.status, estados.EXTRAIDO)

    @override_settings(OCR_PERMITIR_FINALIZAR_SEM_ATOS=True)
    def test_sem_atos_string_e_corpo_invalido(self):
        extracao = self._extracao_sem_atos()

        resposta = self._post_finalizar({
            'versao': services.versao_bloco(extracao),
            'sem_atos': 'true',
        })

        self.assertEqual(resposta.status_code, 422)
        self.assertEqual(resposta.json(), {
            'erro': 'corpo_invalido', 'chave': None,
        })
        extracao.refresh_from_db()
        self.job.refresh_from_db()
        self.assertIsNone(extracao.finalizada_em)
        self.assertEqual(self.job.status, estados.EXTRAIDO)

    def _descartar_data(self, extracao):
        # Obrigatório não se descarta pela API (incluir é coagido); o dado
        # legado descartado é simulado direto no banco.
        extracao.campos.filter(chave='/document/data').update(
            status_revisao='descartado',
        )
        self.assertIn(
            {
                'chave': '/document/data',
                'motivo': 'obrigatorio_ausente',
                'bloqueante': True,
            },
            revisao.pendencias_sem_atos(extracao),
        )

    @override_settings(OCR_PERMITIR_FINALIZAR_SEM_ATOS=True)
    def test_get_com_bloqueio_de_campo_nao_oferece_sem_atos(self):
        # Issue #262: o bloqueio de campo fica escondido atrás de nenhum_ato,
        # mas a confirmação só é oferecida quando ele é a ÚNICA pendência.
        # #341 fase 3: quem oferece é a revisão por formulário; com o
        # bloqueio, a entrada da revisão nem chega a oferecê-la.
        extracao = self._extracao_sem_atos()
        self._descartar_data(extracao)
        self.assertFalse(services.pode_finalizar_sem_atos(extracao))

        resposta = self.client.get(self.url('campos_job_ocr'), follow=True)

        self.assertEqual(resposta.redirect_chain[-1][0], self.url_tela())
        self.assertEqual(resposta.status_code, 200)
        self.assertIn(
            ('info', 'A extração não trouxe nenhum ato para revisar.'),
            self.mensagens(resposta),
        )

    @override_settings(OCR_PERMITIR_FINALIZAR_SEM_ATOS=True)
    def test_post_sem_atos_com_bloqueio_de_campo_422_explica(self):
        # Issue #262: o 422 não pode dizer só "nenhum_ato" quando há campo
        # obrigatório pendente.
        extracao = self._extracao_sem_atos()
        self._descartar_data(extracao)

        resposta = self._post_finalizar({
            'versao': services.versao_bloco(extracao),
            'sem_atos': True,
        })

        self.assertEqual(resposta.status_code, 422, resposta.content)
        self.assertEqual(resposta.json()['erro'], 'revisao_incompleta')
        chaves = [item['chave'] for item in resposta.json()['pendencias']]
        self.assertIn('/acts', chaves)
        self.assertIn('/document/data', chaves)
        extracao.refresh_from_db()
        self.job.refresh_from_db()
        self.assertIsNone(extracao.finalizada_em)
        self.assertEqual(self.job.status, estados.EXTRAIDO)

    @override_settings(OCR_PERMITIR_FINALIZAR_SEM_ATOS=False)
    def test_flag_desligada_mescla_bloqueio_de_campo_na_tela_e_no_422(self):
        # Issue #262: a mesclagem de bloqueios de campo não depende da flag;
        # sem atos e com flag desligada, a entrada da revisão volta à tela do
        # texto e o 422 lista /acts e a chave do campo descartado.
        extracao = self._extracao_sem_atos()
        self._descartar_data(extracao)

        resposta = self.client.get(self.url('campos_job_ocr'), follow=True)

        self.assertEqual(resposta.redirect_chain[-1][0], self.url_tela())
        self.assertEqual(resposta.status_code, 200)
        self.assertIn(
            ('info', 'A extração não trouxe nenhum ato para revisar.'),
            self.mensagens(resposta),
        )

        resposta = self._post_finalizar({
            'versao': services.versao_bloco(extracao),
            'sem_atos': True,
        })

        self.assertEqual(resposta.status_code, 422, resposta.content)
        self.assertEqual(resposta.json()['erro'], 'revisao_incompleta')
        chaves = [item['chave'] for item in resposta.json()['pendencias']]
        self.assertIn('/acts', chaves)
        self.assertIn('/document/data', chaves)
        extracao.refresh_from_db()
        self.job.refresh_from_db()
        self.assertIsNone(extracao.finalizada_em)
        self.assertEqual(self.job.status, estados.EXTRAIDO)

    @override_settings(OCR_PERMITIR_FINALIZAR_SEM_ATOS=True)
    def test_atos_descartados_pelo_revisor_nao_liberam_finalizacao(self):
        # Issue #262 (S2): a paliativa só vale quando o SERVIÇO devolveu
        # acts: []. Se o revisor descartou todos os atos, finalizar sem atos
        # é falso e o payload do serviço precisa barrar.
        payload = payload_averbacao(self.job.job_id)
        self.assertTrue(payload['acts'])
        extracao = ExtracaoSugerida.objects.create(
            ocr_job=self.job, schema_version=SCHEMA_VERSION,
            payload=payload, payload_servico=payload, provider=PROVIDER,
            solicitada_por=self.dono,
        )
        CampoSugerido.objects.bulk_create(
            revisao.desnormalizar(extracao, payload, list(self.job.paginas.all())),
        )
        extracao.campos.filter(tipo_valor='ato').update(
            status_revisao='descartado',
        )
        self.assertEqual(revisao.pendencias(extracao), [{
            'chave': '/acts', 'motivo': 'nenhum_ato', 'bloqueante': True,
        }])

        resposta = self.client.get(self.url('campos_job_ocr'), follow=True)

        # #341 fase 3: atos descartados não aparecem na revisão (a saída é
        # a mesma mensagem de "nenhum ato") e não liberam a finalização.
        self.assertEqual(resposta.redirect_chain[-1][0], self.url_tela())
        self.assertIn(
            ('info', 'A extração não trouxe nenhum ato para revisar.'),
            self.mensagens(resposta),
        )

        resposta = self._post_finalizar({
            'versao': services.versao_bloco(extracao),
            'sem_atos': True,
        })

        self.assertEqual(resposta.status_code, 422, resposta.content)
        self.assertEqual(resposta.json()['erro'], 'revisao_incompleta')
        extracao.refresh_from_db()
        self.assertIsNone(extracao.finalizada_em)

    @override_settings(OCR_PERMITIR_FINALIZAR_SEM_ATOS=True)
    def test_get_somente_leitura_nao_perde_title(self):
        # Issue #262: job já REVISADO não reabre a confirmação sem atos —
        # `finalizar_revisao` só parte de `extraido`, então a entrada da
        # revisão (#341) nem oferece o botão: volta à tela do texto.
        self._extracao_sem_atos()
        OcrJob.objects.filter(pk=self.job.pk).update(status=estados.REVISADO)

        resposta = self.client.get(self.url('campos_job_ocr'), follow=True)

        self.assertEqual(resposta.redirect_chain[-1][0], self.url_tela())
        self.assertEqual(resposta.status_code, 200)
        self.assertNotIn('revisao_sem_atos.html', [
            t.name for t in resposta.templates
        ])
        self.assertIn(
            ('info', 'A extração não trouxe nenhum ato para revisar.'),
            self.mensagens(resposta),
        )
