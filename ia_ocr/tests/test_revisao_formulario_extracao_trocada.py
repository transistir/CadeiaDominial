"""Cenário M2 (#341): extração trocada no meio da revisão — migração VERBATIM
de ``ia_ocr/tests/test_revisao_formulario_view.py`` (Etapa 12 do plano de
400 linhas). Corpos e nomes de classes preservados.
"""

from django.db import connection

from dominial.models import Lancamento
from ia_ocr.models import CampoSugerido

from .test_revisao_formulario_view_base import (
    RevisaoFormularioBase, post_do_html,
)


class ExtracaoTrocadaTest(RevisaoFormularioBase):
    """M2 (#341): POST de página renderizada sobre outra extração não grava.

    A reextração troca a vigente no meio da revisão; o navegador segue com o
    formulário da ANTIGA aberto. Sem o hidden ``extracao_id`` validado sob
    trava, o POST gravava os dados da extração antiga e marcava como
    importado o ato da MESMA posição na nova.
    """

    def _reextrair(self):
        """Extração nova (R9) no lugar da vigente, como a reextração faria."""
        payload = self._payload_de_tres_atos()
        payload['acts'][0]['rotulo'] = self._campo('R-9', 'R-9/M237')
        payload['acts'][0]['observacoes'] = self._campo(
            'lido pela reextração', 'reextraído',
        )
        return self._aberta(payload)

    def test_post_da_pagina_antiga_nao_grava_nem_marca_ato_da_extracao_nova(self):
        pagina = self.client.get(self.url_ato(0))
        post = post_do_html(pagina)
        self.assertEqual(post['extracao_id'], [str(self.extracao.pk)])
        nova = self._reextrair()
        antes = self.contagens()

        resposta = self.client.post(self.url_ato(0), post)

        self.assertRedirects(
            resposta, self.url_entrada(), fetch_redirect_response=False,
        )
        self.assertTrue(any(
            'A extração deste documento mudou' in texto
            for texto in self.mensagens(resposta)
        ))
        self.assertEqual(self.contagens(), antes)
        # O ato 0 da extração NOVA segue pendente — nada marcado como importado.
        from ia_ocr import revisao_ato

        atos = revisao_ato.atos_da_revisao(nova)
        self.assertEqual(atos[0]['estado'], revisao_ato.ESTADO_PENDENTE)
        self.assertEqual(
            CampoSugerido.objects.filter(
                extracao=nova, status_revisao='importado',
            ).count(),
            0,
        )

    def test_save_revalida_hidden_dentro_da_transacao_autoritativa(self):
        """Mesmo se a checagem preliminar não vir a troca, o save recusa."""
        from unittest import mock

        pagina = self.client.get(self.url_ato(0))  # HTML da R1
        post = post_do_html(pagina)
        nova = self._reextrair()  # vigente agora começa por R9
        antes = self.contagens()

        # Simula a janela entre a guarda preliminar e o save. Sem a validação
        # do hidden dentro de ``revisao_ato.salvar_ato``, os dados R1 seriam
        # gravados e o ato R9 da extração nova seria marcado como importado.
        with mock.patch(
            'ia_ocr.views._extracao_trocada_no_post', return_value=None,
        ):
            resposta = self.client.post(self.url_ato(0), post)

        self.assertRedirects(
            resposta, self.url_entrada(), fetch_redirect_response=False,
        )
        self.assertTrue(any(
            'A extração deste documento mudou' in texto
            for texto in self.mensagens(resposta)
        ))
        self.assertEqual(self.contagens(), antes)
        self.assertEqual(
            CampoSugerido.objects.filter(
                extracao=nova, status_revisao='importado',
            ).count(),
            0,
        )

    def test_navegacao_guarda_rascunho_dentro_da_transacao_da_trava(self):
        """A trava não pode ser solta entre validar o hidden e o rascunho."""
        from unittest import mock

        from ia_ocr import revisao_ato

        pagina = self.client.get(self.url_ato(0))
        profundidade_externa = len(connection.atomic_blocks)
        profundidades = []
        guardar_real = revisao_ato.guardar_rascunho

        def observar_transacao(*args, **kwargs):
            profundidades.append(len(connection.atomic_blocks))
            return guardar_real(*args, **kwargs)

        with mock.patch.object(
            revisao_ato, 'guardar_rascunho', side_effect=observar_transacao,
        ):
            resposta = self.client.post(self.url_ato(0), post_do_html(
                pagina, _ir_para='1', observacoes='rascunho atual',
            ))

        self.assertRedirects(
            resposta, self.url_ato(1), fetch_redirect_response=False,
        )
        self.assertEqual(len(profundidades), 1)
        self.assertGreater(profundidades[0], profundidade_externa)

    def test_navegacao_da_pagina_antiga_nao_guarda_rascunho(self):
        pagina = self.client.get(self.url_ato(0))
        self._reextrair()

        resposta = self.client.post(self.url_ato(0), post_do_html(
            pagina, _ir_para='1', observacoes='digitado na página antiga',
        ))

        self.assertRedirects(
            resposta, self.url_entrada(), fetch_redirect_response=False,
        )
        # O digitado era da extração antiga: nada guardado na sessão — nem
        # sob a nova (onde envenenaria o ato 0), nem sob a antiga.
        self.assertEqual(self.client.session.get('ia_ocr_rascunhos') or {}, {})

    def test_post_sem_a_identidade_da_extracao_e_recusado(self):
        pagina = self.client.get(self.url_ato(0))
        post = post_do_html(pagina)
        del post['extracao_id']
        antes = self.contagens()

        resposta = self.client.post(self.url_ato(0), post)

        self.assertRedirects(
            resposta, self.url_entrada(), fetch_redirect_response=False,
        )
        self.assertTrue(any(
            'A extração deste documento mudou' in texto
            for texto in self.mensagens(resposta)
        ))
        self.assertEqual(self.contagens(), antes)

    def test_post_da_pagina_da_extracao_atual_salva_normalmente(self):
        nova = self._reextrair()

        pagina = self.client.get(self.url_ato(0))
        post = post_do_html(pagina)
        self.assertEqual(post['extracao_id'], [str(nova.pk)])

        resposta = self.client.post(self.url_ato(0), post)

        self.assertEqual(resposta.status_code, 302, self.mensagens(resposta))
        self.assertEqual(
            Lancamento.objects.filter(documento=self.documento).count(), 1,
        )
