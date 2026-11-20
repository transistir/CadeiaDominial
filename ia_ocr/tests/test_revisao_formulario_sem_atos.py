"""Conclusão sem atos pela revisão por formulário (#341 fase 3, #262).

Com a aposentadoria da tela de cards, a saída "sem atos" do I-5/#262 deixa
de ser o JSON de ``campos/finalizar/`` e vira um formulário HTML na revisão
nova: ``revisar/`` renderiza ``revisao_sem_atos.html`` quando a extração do
serviço veio sem atos e ``services.pode_finalizar_sem_atos`` destrava, e o
POST em ``revisar/sem-atos/`` chama ``services.finalizar_revisao`` com
``confirmar_sem_atos=True`` e volta ao documento.

Contrato do serviço (``FinalizarSemAtosTest``): a finalização audita
``EXTRAIDO → REVISADO`` com motivo ``revisao_finalizada_sem_atos`` — não
cria ``ImportacaoIA`` nem vai a ``IMPORTADO`` (não há ato algum a importar).
"""

from django.test import override_settings
from django.urls import reverse

from dominial.models import Cartorios
from ia_ocr import estados, revisao, services
from ia_ocr.models import CampoSugerido, ExtracaoSugerida, ImportacaoIA

from .payloads_extracao import PROVIDER, SCHEMA_VERSION, payload_averbacao
from .test_revisao_formulario_view_base import RevisaoFormularioBase


class RevisarSemAtosBase(RevisaoFormularioBase):
    """Mesma montagem da revisão, com a extração do serviço sem atos."""

    def setUp(self):
        super().setUp()
        self.job.extracoes.all().delete()
        self.extracao = self._sem_atos()

    def _sem_atos(self):
        payload = payload_averbacao(self.job.job_id)
        payload['acts'] = []
        extracao = ExtracaoSugerida.objects.create(
            ocr_job=self.job, schema_version=SCHEMA_VERSION,
            payload=payload, payload_servico=payload, provider=PROVIDER,
            solicitada_por=self.usuario,
        )
        CampoSugerido.objects.bulk_create(
            revisao.desnormalizar(extracao, payload, [self.pagina]),
        )
        # Sem atos, o cabeçalho ainda precisa das escolhas de cartório.
        extracao.campos.filter(tipo_valor='cartorio').update(criar_novo=True)
        self.assertEqual(revisao.pendencias(extracao), [{
            'chave': '/acts', 'motivo': 'nenhum_ato', 'bloqueante': True,
        }])
        return extracao

    def url_sem_atos(self):
        return reverse('revisar_sem_atos_ocr', kwargs=self.kwargs())

    def _assert_nao_finalizada(self):
        self.extracao.refresh_from_db()
        self.job.refresh_from_db()
        self.assertIsNone(self.extracao.finalizada_em)
        self.assertEqual(self.job.status, estados.EXTRAIDO)
        self.assertFalse(self.job.transicoes.exists())


@override_settings(OCR_PERMITIR_FINALIZAR_SEM_ATOS=True)
class RevisarSemAtosTest(RevisarSemAtosBase):
    def test_get_sem_atos_renderiza_a_confirmacao(self):
        resposta = self.client.get(self.url_entrada())

        self.assertEqual(resposta.status_code, 200)
        self.assertTemplateUsed(resposta, 'ia_ocr/revisao_sem_atos.html')
        html = resposta.content.decode()
        self.assertIn('Concluir sem atos', html)
        # O POST vai para a rota nova, com o token que o serviço valida.
        self.assertIn(reverse('revisar_sem_atos_ocr', kwargs=self.kwargs()), html)
        self.assertIn(f'value="{services.versao_bloco(self.extracao)}"', html)

    def test_post_conclui_e_redireciona_ao_documento(self):
        resposta = self.client.post(self.url_sem_atos(), {
            'versao': services.versao_bloco(self.extracao),
        })

        self.assertRedirects(
            resposta, self.url_documento(), fetch_redirect_response=False,
        )
        self.extracao.refresh_from_db()
        self.job.refresh_from_db()
        self.assertIsNotNone(self.extracao.finalizada_em)
        # Contrato do serviço: REVISADO com motivo próprio — sem atos não há
        # importação, então nada vira IMPORTADO nem cria ImportacaoIA.
        self.assertEqual(self.job.status, estados.REVISADO)
        self.assertFalse(ImportacaoIA.objects.exists())
        transicao = self.job.transicoes.get()
        self.assertEqual(transicao.de_status, estados.EXTRAIDO)
        self.assertEqual(transicao.para_status, estados.REVISADO)
        self.assertEqual(transicao.motivo, 'revisao_finalizada_sem_atos')
        mensagens = ' '.join(self.mensagens(resposta))
        self.assertIn('sem atos', mensagens)

    def test_post_com_versao_velha_e_recusado(self):
        versao = services.versao_bloco(self.extracao)
        # Outro revisor mexe numa linha depois de a página ter sido renderizada.
        self.extracao.campos.filter(chave='/document/data').update(
            status_revisao='aceito',
        )

        resposta = self.client.post(self.url_sem_atos(), {'versao': versao})

        self.assertRedirects(
            resposta, self.url_entrada(), fetch_redirect_response=False,
        )
        self._assert_nao_finalizada()

    def test_post_sem_versao_e_recusado(self):
        resposta = self.client.post(self.url_sem_atos(), {})

        self.assertEqual(resposta.status_code, 400)
        self._assert_nao_finalizada()

    def test_get_com_atos_nao_cai_na_tela_sem_atos(self):
        self.job.extracoes.all().delete()
        self.extracao = self._aberta(payload_averbacao(self.job.job_id))

        resposta = self.client.get(self.url_entrada())

        self.assertEqual(resposta.status_code, 302)
        self.assertRedirects(
            resposta, self.url_ato(0), fetch_redirect_response=False,
        )

    def test_escolha_de_cabecalho_nao_afeta_job_com_atos(self):
        # Guarda do review (Opus): a rota sem atos é só do caso sem atos.
        self.job.extracoes.all().delete()
        self.extracao = self._aberta(payload_averbacao(self.job.job_id))

        resposta = self.client.post(self.url_sem_atos(), {
            'versao': services.versao_bloco(self.extracao),
        })

        self.assertEqual(resposta.status_code, 404)
        self._assert_nao_finalizada()

    def test_get_com_bloqueio_de_campo_nao_renderiza_a_confirmacao(self):
        # A paliativa só vale quando a ÚNICA pendência é nenhum_ato.
        self.extracao.campos.filter(chave='/document/data').update(
            status_revisao='descartado',
        )
        self.assertFalse(services.pode_finalizar_sem_atos(self.extracao))

        resposta = self.client.get(self.url_entrada())

        self.assertEqual(resposta.status_code, 302)
        self.assertRedirects(
            resposta,
            reverse('texto_job_ocr', kwargs=self.kwargs()),
            fetch_redirect_response=False,
        )

    def test_get_sem_flag_mantem_o_comportamento_de_hoje(self):
        with override_settings(OCR_PERMITIR_FINALIZAR_SEM_ATOS=False):
            resposta = self.client.get(self.url_entrada())

        self.assertEqual(resposta.status_code, 302)
        self.assertRedirects(
            resposta,
            reverse('texto_job_ocr', kwargs=self.kwargs()),
            fetch_redirect_response=False,
        )
        self.assertIn(
            'não trouxe nenhum ato', ' '.join(self.mensagens(resposta)),
        )

    def test_get_de_job_ja_revisado_nao_reoferece_a_confirmacao(self):
        services.finalizar_revisao(
            self.extracao, self.usuario, confirmar_sem_atos=True,
        )

        resposta = self.client.get(self.url_entrada())

        self.assertEqual(resposta.status_code, 302)
        self.assertNotIn('revisao_sem_atos.html', [
            t.name for t in resposta.templates
        ])


@override_settings(OCR_PERMITIR_FINALIZAR_SEM_ATOS=True)
class RevisarSemAtosComEscolhaPendenteTest(RevisarSemAtosBase):
    """MUST-FIX do review Codex da #341: cabeçalho sem correspondência.

    ``acts: []`` com ``/document/cartorio`` (ou ``cri_atual``) SEM escolha:
    ``pode_finalizar_sem_atos`` recusa e — sem a tela de cards, aposentada
    na fase 4 — não havia controle nenhum para resolver a pendência; o job
    ficava preso em ``extraido`` para sempre. A confirmação passa a oferecer
    o formulário dessas escolhas (e só delas).
    """

    def setUp(self):
        super().setUp()
        self.cartorio = Cartorios.objects.create(
            nome='CRI de Guaíra', cns='CNS-42', estado='PR',
        )
        # Desfaz o ``update(criar_novo=True)`` do setUp: é o cenário do bug —
        # nenhum cadastro escolhido, só candidatos possíveis.
        self.extracao.campos.filter(tipo_valor='cartorio').update(
            criar_novo=False, match_candidatos=[self.cartorio.pk],
        )
        self.extracao.refresh_from_db()
        self.assertFalse(services.pode_finalizar_sem_atos(self.extracao))

    def post_escolhas(self, **extra):
        dados = {'versao': services.versao_bloco(self.extracao)}
        dados.update(extra)
        return self.client.post(self.url_sem_atos(), dados)

    def test_sem_atos_com_cartorio_sem_match_oferece_escolha(self):
        resposta = self.client.get(self.url_entrada())

        self.assertEqual(resposta.status_code, 200)
        self.assertTemplateUsed(resposta, 'ia_ocr/revisao_sem_atos.html')
        html = resposta.content.decode()
        self.assertIn('name="escolha:/document/cartorio"', html)
        self.assertIn('name="escolha:/document/cri_atual"', html)
        self.assertIn(f'value="{self.cartorio.pk}"', html)
        self.assertIn('value="criar_novo"', html)
        self.assertIn('name="criar_novo:/document/cartorio"', html)
        self.assertIn('name="nome:/document/cartorio"', html)
        self.assertIn(f'value="{services.versao_bloco(self.extracao)}"', html)

    def test_escolher_cartorio_existente_conclui_sem_atos(self):
        antes = self.contagens()
        resposta = self.post_escolhas(**{
            'escolha:/document/cartorio': str(self.cartorio.pk),
            'escolha:/document/cri_atual': str(self.cartorio.pk),
        })

        self.assertRedirects(
            resposta, self.url_documento(), fetch_redirect_response=False,
        )
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, estados.REVISADO)
        transicao = self.job.transicoes.get()
        self.assertEqual(transicao.de_status, estados.EXTRAIDO)
        self.assertEqual(transicao.para_status, estados.REVISADO)
        self.assertEqual(transicao.motivo, 'revisao_finalizada_sem_atos')
        self.assertFalse(ImportacaoIA.objects.exists())
        # Sem atos não há o que importar: nenhuma linha de lançamento/documento.
        depois = self.contagens()
        for modelo, quantidade in antes.items():
            if modelo == 'OcrJobTransicao':
                continue
            self.assertEqual(depois[modelo], quantidade, modelo)
        campo = self.extracao.campos.get(chave='/document/cartorio')
        self.assertEqual(campo.cartorio_escolhido_id, self.cartorio.pk)
        self.assertFalse(campo.criar_novo)

    def test_criar_novo_sem_nome_nao_conclui(self):
        resposta = self.post_escolhas(**{
            'criar_novo:/document/cartorio': 'on',
            'nome:/document/cartorio': '   ',
            'escolha:/document/cri_atual': str(self.cartorio.pk),
        })

        self.assertRedirects(
            resposta, self.url_entrada(), fetch_redirect_response=False,
        )
        self.assertIn('Nada foi gravado', ' '.join(self.mensagens(resposta)))
        self._assert_nao_finalizada()
        campo = self.extracao.campos.get(chave='/document/cartorio')
        self.assertFalse(campo.criar_novo)
        self.assertIsNone(campo.cartorio_escolhido_id)

    def test_pendencia_que_a_pagina_nao_resolve_mantem_o_redirect(self):
        # Além das escolhas, um campo de outro tipo pede revisão: a página
        # não resolve isso, então vale o ramo antigo (mensagem + texto).
        self.extracao.campos.filter(chave='/document/data').update(
            requer_revisao=True,
        )

        resposta = self.client.get(self.url_entrada())

        self.assertEqual(resposta.status_code, 302)
        self.assertRedirects(
            resposta,
            reverse('texto_job_ocr', kwargs=self.kwargs()),
            fetch_redirect_response=False,
        )
        self.assertNotIn('revisao_sem_atos.html', [
            t.name for t in resposta.templates
        ])
