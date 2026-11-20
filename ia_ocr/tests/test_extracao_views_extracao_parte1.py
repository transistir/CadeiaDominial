"""Parte 1 de 3 do corpo de ``ExtracaoViewsTest`` — migração VERBATIM de
``ia_ocr/tests/test_extracao_views.py`` (Etapa 12 do plano de 400 linhas).

Classe SIMPLES (sem ``TestCase``); quem coleta é a fachada em
``test_extracao_views_extracao.py``. As constantes de módulo (``V1_1``,
``MENSAGEM_*``) só são usadas nesta parte.
"""

import json
import uuid
from unittest import mock

from django.conf import settings
from django.shortcuts import resolve_url
from django.urls import reverse

from ia_ocr import estados, revisao, services
from ia_ocr.estados import TransicaoInvalida
from ia_ocr.extracao_backends import ExtracaoBackendError
from ia_ocr.extracao_schema import PayloadExtracaoInvalido
from ia_ocr.models import OcrJob

from .payloads_extracao import TEXTO_PAGINA_1, _campo, payload_averbacao

V1_1 = 'umbelino-extracao-matricula-v1.1'
MENSAGEM_INDISPONIVEL = (
    'O serviço de extração não respondeu. Tente novamente em instantes.'
)
MENSAGEM_FORMATO_INESPERADO = (
    'A extração veio em formato inesperado. Avise o suporte.'
)
MENSAGEM_INCOMPATIVEL = (
    'O serviço de extração não aceitou o formato desta versão. '
    'Avise o suporte.'
)


class ExtracaoViewsTestParte1:
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
            resposta, self.url('revisar_job_ocr'), fetch_redirect_response=False,
        )
        self.assertIn((
            'success', 'Extração concluída. Revise cada ato no formulário.',
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

    def test_extrair_auto_sem_extracao_cria_e_redireciona_campos(self):
        resposta = self.client.post(
            self.url('extrair_campos_ocr'), {'extrair_auto': '1'},
        )

        self.assertRedirects(
            resposta, self.url('revisar_job_ocr'), fetch_redirect_response=False,
        )
        self.assertIn((
            'success', 'Extração concluída. Revise cada ato no formulário.',
        ), self.mensagens(resposta))
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, estados.EXTRAIDO)
        self.assertEqual(self.job.extracoes.count(), 1)
        self.backend.extrair.assert_called_once()

    def test_extrair_auto_com_vigente_redireciona_campos_sem_nova_extracao(self):
        # Greptile P1 (PR #319): o POST atrasado da segunda aba não cria
        # extração vigente nova — volta para os campos com aviso, sem erro.
        vigente = self._extracao()

        resposta = self.client.post(
            self.url('extrair_campos_ocr'), {'extrair_auto': '1'},
        )

        self.assertRedirects(
            resposta, self.url('revisar_job_ocr'), fetch_redirect_response=False,
        )
        self.assertIn(
            ('info', 'Os campos já foram extraídos.'), self.mensagens(resposta),
        )
        self.job.refresh_from_db()
        self.assertEqual(self.job.extracoes.count(), 1)
        self.assertEqual(self.job.extracao_vigente(), vigente)
        self.backend.extrair.assert_called_once()

    def test_extrair_manual_sem_flag_com_vigente_reeextrai(self):
        vigente = self._extracao()

        resposta = self.client.post(self.url('extrair_campos_ocr'))

        self.assertRedirects(
            resposta, self.url('revisar_job_ocr'), fetch_redirect_response=False,
        )
        self.assertIn((
            'success', 'Extração concluída. Revise cada ato no formulário.',
        ), self.mensagens(resposta))
        self.job.refresh_from_db()
        self.assertEqual(self.job.extracoes.count(), 2)
        self.assertNotEqual(self.job.extracao_vigente(), vigente)

    def test_extrair_erros_exibem_mensagens_seguras(self):
        indisponivel = MENSAGEM_INDISPONIVEL
        inesperado = MENSAGEM_FORMATO_INESPERADO
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
            (services.ExtracaoIncompativel(), MENSAGEM_INCOMPATIVEL),
            (
                services.ExtracaoPayloadInvalido(
                    'propriedade_extra', '$.acts[0].data_transacao',
                ),
                inesperado,
            ),
            # O serviço converte, mas a view cobre também a exceção crua da
            # validação — como já faz com ExtracaoBackendError.
            (
                PayloadExtracaoInvalido(
                    'propriedade_extra', '$.acts[0].data_transacao',
                ),
                inesperado,
            ),
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

    def test_extrair_payload_fora_do_contrato_mostra_formato_inesperado(self):
        """Serviço respondeu, mas o payload (declarado v1.1) traz
        `data_transacao`: mensagem própria, sem código/caminho/valor na tela,
        e nada é gravado."""
        payload = payload_averbacao(self.job.job_id)
        payload['schema_version'] = V1_1
        payload['acts'][0]['data_transacao'] = _campo('2019-12-20', 'Av-1/42.718')
        self.backend.extrair.return_value['extracao'] = payload

        resposta = self.client.post(self.url('extrair_campos_ocr'))

        self.assertRedirects(resposta, self.url_tela(), fetch_redirect_response=False)
        self.assertEqual(
            self.mensagens(resposta)[-1], ('error', MENSAGEM_FORMATO_INESPERADO),
        )
        texto = ' '.join(mensagem for _nivel, mensagem in self.mensagens(resposta))
        for interno in ('propriedade_extra', 'data_transacao', '$.acts'):
            self.assertNotIn(interno, texto)
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, estados.CONCLUIDO)
        self.assertFalse(self.job.extracoes.exists())

    def test_extrair_falha_de_transporte_mantem_a_mensagem_de_indisponivel(self):
        """O que é falha da chamada (não do conteúdo) segue com a mensagem
        antiga, sem vazar o detalhe do backend."""
        self.backend.extrair.side_effect = ExtracaoBackendError(
            'EXTRACAO_INDISPONIVEL', 'detalhe que não deve aparecer',
        )

        resposta = self.client.post(self.url('extrair_campos_ocr'))

        self.assertRedirects(resposta, self.url_tela(), fetch_redirect_response=False)
        self.assertEqual(
            self.mensagens(resposta)[-1], ('error', MENSAGEM_INDISPONIVEL),
        )
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, estados.CONCLUIDO)
        self.assertFalse(self.job.extracoes.exists())

    def test_extrair_incompativel_mostra_mensagem_propria_e_limpa_reserva(self):
        """422 do serviço: mensagem própria (não a de 'não respondeu', que
        mentiria — o serviço respondeu) e a reserva da extração volta a
        NULL, como em toda falha do fluxo."""
        self.backend.extrair.side_effect = ExtracaoBackendError(
            'EXTRACAO_INCOMPATIVEL', 'detalhe que não deve aparecer',
        )

        resposta = self.client.post(self.url('extrair_campos_ocr'))

        self.assertRedirects(resposta, self.url_tela(), fetch_redirect_response=False)
        self.assertEqual(
            self.mensagens(resposta)[-1], ('error', MENSAGEM_INCOMPATIVEL),
        )
        texto = ' '.join(mensagem for _nivel, mensagem in self.mensagens(resposta))
        self.assertNotIn('EXTRACAO_INCOMPATIVEL', texto)
        self.assertNotIn('detalhe que não deve aparecer', texto)
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, estados.CONCLUIDO)
        self.assertFalse(self.job.extracoes.exists())
        self.assertIsNone(self.job.extracao_reserva)
        self.assertIsNone(self.job.extracao_reservada_ate)

    def test_extrair_aceita_payload_v1_2_com_transmissao_do_ato(self):
        """O incidente de ponta a ponta: o serviço responde v1.2 com
        livro/folha/data da transmissão e o clique em 'Extrair campos' chega
        à revisão em vez de 'O serviço de extração não respondeu'."""
        payload = payload_averbacao(self.job.job_id)
        ato = payload['acts'][0]
        ato['livro_transacao'] = _campo('10-A', 'Av-1/42.718')
        ato['folha_transacao'] = _campo('25v', 'Av-1/42.718')
        ato['data_transacao'] = _campo('2019-12-20', 'Av-1/42.718')
        self.backend.extrair.return_value['extracao'] = payload

        resposta = self.client.post(self.url('extrair_campos_ocr'))

        self.assertRedirects(
            resposta, self.url('revisar_job_ocr'), fetch_redirect_response=False,
        )
        self.assertIn(
            ('success', 'Extração concluída. Revise cada ato no formulário.'),
            self.mensagens(resposta),
        )
        extracao = self.job.extracao_vigente()
        self.assertEqual(
            extracao.campos.get(chave='/acts/0/livro_transacao').normalized, '10-A',
        )
        self.assertEqual(
            extracao.campos.get(chave='/acts/0/data_transacao').normalized,
            '2019-12-20',
        )
