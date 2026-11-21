"""Cenários de entrada/tela, nada-grava e rascunho — migração VERBATIM de
``ia_ocr/tests/test_revisao_formulario_view.py`` (Etapa 12 do plano de
400 linhas). Corpos e nomes de classes preservados.
"""

import json
import re
from copy import deepcopy

from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from ia_ocr.models import CampoSugerido

from .test_revisao_formulario_view_base import (
    RevisaoFormularioBase, post_do_html,
)


class EntradaETelaTest(RevisaoFormularioBase):
    def test_entrada_leva_ao_primeiro_ato_pendente(self):
        resposta = self.client.get(self.url_entrada())

        self.assertRedirects(resposta, self.url_ato(0), fetch_redirect_response=False)

    def test_campos_redireciona_para_a_revisao(self):
        """#341 fase 3: a tela de cards se aposenta — `campos/` entra na revisão."""
        resposta = self.client.get(reverse('campos_job_ocr', kwargs=self.kwargs()))

        self.assertRedirects(
            resposta, self.url_entrada(), fetch_redirect_response=False,
        )

    def test_rotas_da_tela_de_cards_aposentadas_dao_404(self):
        """#341 fase 4: `campos/salvar|finalizar|importar/` saem do tree.

        O POST JSON que a tela de cards enviava vira 404 — aba velha aberta no
        servidor de testes não grava nada; `campos/` segue redirecionando.
        """
        entrada = self.url_entrada()  # .../ocr-job/<uuid>/revisar/
        for caminho in ('campos/salvar/', 'campos/finalizar/', 'campos/importar/'):
            resposta = self.client.post(
                entrada.replace('revisar/', caminho),
                data='{}', content_type='application/json',
            )
            self.assertEqual(resposta.status_code, 404, caminho)
        self.assertRedirects(
            self.client.get(entrada.replace('revisar/', 'campos/')),
            self.url_entrada(), fetch_redirect_response=False,
        )

    def test_formulario_do_ato_vem_preenchido(self):
        resposta = self.client.get(self.url_ato(0))

        self.assertEqual(resposta.status_code, 200)
        self.assertTemplateUsed(resposta, 'dominial/lancamento_form.html')
        html = resposta.content.decode()
        self.assertIn('Revisão da extração · ato 1 de 3', html)
        self.assertIn('📄 Revisar Lançamento', html)
        self.assertRegex(html, r'<input[^>]*name="numero_lancamento_simples"[^>]*value="1"')
        self.assertRegex(html, r'<input[^>]*name="data"[^>]*value="2020-02-15"')
        self.assertRegex(
            html,
            r'<option value="%s"[^>]*selected' % self.tipo_registro.pk,
        )
        for nome in ('JOÃO DA SILVA', 'MARIA DA SILVA', 'PEDRO SANTOS'):
            self.assertIn(f'value="{nome}"', html)

    def test_sidebar_lista_os_atos_com_estado(self):
        html = self.client.get(self.url_ato(1)).content.decode()

        self.assertIn('ia-revisao-sidebar', html)
        for rotulo in ('1. R1', '2. Av1', '3. R2'):
            self.assertIn(rotulo, html)
        # Ato 2 em edição; os outros dois pendentes, com o destino da aba.
        self.assertEqual(html.count('ia-ato-pendente'), 2 + 1)  # 2 abas + css
        self.assertIn(f'data-ir-para="0"', html)
        self.assertIn(f'data-ir-para="2"', html)
        # O script do formulário cita a classe no seletor; nenhuma ABA a usa.
        self.assertNotRegex(html, r'class="[^"]*js-lancamento-resumo')

    def test_evidencias_e_js_so_na_revisao(self):
        html = self.client.get(self.url_ato(0)).content.decode()

        self.assertIn('id="ia-evidencias"', html)
        self.assertIn('ocr_revisao_formulario.js', html)
        self.assertIn('data-url-texto=', html)

    def test_nenhuma_chave_tecnica_na_tela(self):
        html = self.client.get(self.url_ato(0)).content.decode()
        banner = html[html.index('id="ia-revisao-banner"'):]
        banner = banner[:banner.index('</section>')]

        self.assertNotIn('/acts/', banner)

    def test_evidencia_vai_mascarada_para_o_json(self):
        CampoSugerido.objects.filter(
            extracao=self.extracao, chave='/acts/0/descricao',
        ).delete()
        CampoSugerido.objects.filter(
            extracao=self.extracao, chave='/acts/0/observacoes',
        ).delete()
        CampoSugerido.objects.filter(
            extracao=self.extracao, chave='/acts/0/data',
        ).update(evidencia_trecho='compra, CPF 123.456.789-00 em 15/02/2020')

        html = self.client.get(self.url_ato(0)).content.decode()

        self.assertNotIn('123.456.789-00', html)
        self.assertIn('CPF ***', html)

    def test_json_de_evidencias_traz_pagina_trecho_e_posicao_das_partes(self):
        html = self.client.get(self.url_ato(0)).content.decode()

        bruto = re.search(
            r'<script id="ia-evidencias" type="application/json">(.*?)</script>',
            html, re.S,
        ).group(1)
        evidencias = json.loads(bruto)

        self.assertEqual(evidencias['data'], {
            'pagina': 1, 'trecho': '15 de fevereiro de 2020',
            'confianca_baixa': False,
        })
        self.assertEqual(evidencias['transmitente_nome[1]']['trecho'], 'MARIA DA SILVA')
        self.assertEqual(evidencias['adquirente_nome[0]']['trecho'], 'PEDRO SANTOS')
        # Nada de chave técnica de linha como nome de campo.
        self.assertFalse([nome for nome in evidencias if '/' in nome])

    def test_novo_lancamento_manual_nao_tem_nada_da_revisao(self):
        resposta = self.client.get(reverse('novo_lancamento_documento', kwargs={
            'tis_id': self.imovel.terra_indigena_id.pk,
            'imovel_id': self.imovel.pk, 'documento_id': self.documento.pk,
        }))

        html = resposta.content.decode()
        self.assertEqual(resposta.status_code, 200)
        for marca in ('ia-evidencias', 'ia-revisao-sidebar', 'ia-revisao-banner',
                      'ocr_revisao_formulario.js', 'data-ir-para'):
            self.assertNotIn(marca, html)
        self.assertIn('lancamento-sidebar', html + 'lancamento-sidebar')

    def test_consultas_do_get_nao_crescem_com_o_numero_de_atos(self):
        with CaptureQueriesContext(connection) as com_tres:
            self.assertEqual(self.client.get(self.url_ato(0)).status_code, 200)
        payload = self._payload_de_tres_atos()
        payload['acts'] += deepcopy(payload['acts'])
        self.job.extracoes.all().delete()
        self.extracao = self._aberta(payload)

        with CaptureQueriesContext(connection) as com_seis:
            resposta = self.client.get(self.url_ato(0))

        self.assertEqual(resposta.status_code, 200)
        self.assertIn('ato 1 de 6', resposta.content.decode())
        self.assertEqual(len(com_seis), len(com_tres))

    def test_ato_inexistente_e_404(self):
        self.assertEqual(self.client.get(self.url_ato(9)).status_code, 404)

    def test_job_ainda_sem_extracao_volta_para_o_texto(self):
        self.job.status = 'concluido'
        self.job.save(update_fields=['status'])

        resposta = self.client.get(self.url_ato(0))

        self.assertRedirects(
            resposta, reverse('texto_job_ocr', kwargs=self.kwargs()),
            fetch_redirect_response=False,
        )

    def test_job_importado_volta_para_o_documento(self):
        self.job.status = 'importado'
        self.job.save(update_fields=['status'])

        resposta = self.client.get(self.url_entrada())

        self.assertRedirects(resposta, self.url_documento(), fetch_redirect_response=False)


class NadaGravaTest(RevisaoFormularioBase):
    def _escritas(self, consultas):
        return [
            consulta['sql'] for consulta in consultas
            if consulta['sql'].lstrip().upper().startswith(
                ('INSERT', 'UPDATE', 'DELETE'),
            )
        ]

    def test_get_e_navegacao_so_escrevem_na_sessao(self):
        antes = self.contagens()
        status_antes = self.job.status
        revisado_antes = list(
            CampoSugerido.objects.filter(extracao=self.extracao)
            .order_by('pk').values_list('pk', 'revisado_em', 'status_revisao'),
        )

        with CaptureQueriesContext(connection) as consultas:
            self.client.get(self.url_entrada())
            for indice in (0, 1, 2, 1, 0):
                resposta = self.client.get(self.url_ato(indice))
                self.assertEqual(resposta.status_code, 200)
            # Navegar com o que foi digitado: POST com ``_ir_para``.
            pagina = self.client.get(self.url_ato(0))
            navegacao = self.client.post(
                self.url_ato(0),
                post_do_html(pagina, _ir_para='2', observacoes='anotação minha'),
            )
            self.assertRedirects(
                navegacao, self.url_ato(2), fetch_redirect_response=False,
            )
            self.client.get(self.url_ato(2))

        escritas = self._escritas(consultas.captured_queries)
        self.assertTrue(escritas, 'o rascunho deve escrever a sessão')
        for sql in escritas:
            self.assertIn('django_session', sql)
        self.assertEqual(self.contagens(), antes)
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, status_antes)
        self.assertEqual(
            list(
                CampoSugerido.objects.filter(extracao=self.extracao)
                .order_by('pk').values_list('pk', 'revisado_em', 'status_revisao'),
            ),
            revisado_antes,
        )

    def test_get_sozinho_nao_escreve_nem_a_sessao(self):
        with CaptureQueriesContext(connection) as consultas:
            self.client.get(self.url_ato(1))

        self.assertEqual(self._escritas(consultas.captured_queries), [])


class RascunhoTest(RevisaoFormularioBase):
    def test_edicao_sobrevive_a_ida_e_volta(self):
        pagina = self.client.get(self.url_ato(0))
        post = post_do_html(
            pagina, _ir_para='1', forma_transacao='Doação rascunhada',
            observacoes='nota do revisor',
        )
        # Segunda linha de origem digitada à mão: volta pelo mesmo caminho do
        # re-render de erro do formulário manual.
        post['origem_completa[]'] = ['M123', 'T45']
        post['cartorio_origem_nome[]'] = ['', '']
        post['cartorio_origem[]'] = ['', '']
        post['livro_origem[]'] = ['2', '3']
        post['folha_origem[]'] = ['10', '11']
        self.client.post(self.url_ato(0), post)

        self.client.get(self.url_ato(1))
        volta = self.client.get(self.url_ato(0))

        html = volta.content.decode()
        self.assertRegex(html, r'name="forma_transacao"[^>]*value="Doação rascunhada"')
        self.assertIn('nota do revisor', html)
        self.assertIn('value="M123"', html)
        self.assertIn('value="T45"', html)
        self.assertIn('Suas alterações não salvas deste ato foram restauradas.', html)

    def test_rascunho_e_por_ato(self):
        pagina = self.client.get(self.url_ato(0))
        self.client.post(
            self.url_ato(0), post_do_html(pagina, _ir_para='1', observacoes='só do ato 1'),
        )

        outro = self.client.get(self.url_ato(2)).content.decode()

        self.assertNotIn('só do ato 1', outro)

    def test_destino_invalido_fica_no_mesmo_ato(self):
        pagina = self.client.get(self.url_ato(0))

        resposta = self.client.post(
            self.url_ato(0), post_do_html(pagina, _ir_para='99'),
        )

        self.assertRedirects(resposta, self.url_ato(0), fetch_redirect_response=False)

    def test_rascunho_nao_guarda_o_token_csrf_nem_o_destino(self):
        pagina = self.client.get(self.url_ato(0))
        self.client.post(
            self.url_ato(0),
            {**post_do_html(pagina, _ir_para='1'), 'csrfmiddlewaretoken': 'x'},
        )

        guardado = self.client.session['ia_ocr_rascunhos'][str(self.extracao.pk)]['0']

        self.assertNotIn('csrfmiddlewaretoken', guardado)
        self.assertNotIn('_ir_para', guardado)

    def test_so_os_ultimos_documentos_ficam_na_sessao(self):
        from ia_ocr import revisao_ato

        sessao = self.client.session
        sessao[revisao_ato.CHAVE_SESSAO] = {
            str(numero): {'0': {'data': ['2020-01-01']}} for numero in (901, 902, 903)
        }
        sessao.save()

        pagina = self.client.get(self.url_ato(0))
        self.client.post(self.url_ato(0), post_do_html(pagina, _ir_para='1'))

        guardados = list(self.client.session[revisao_ato.CHAVE_SESSAO])
        self.assertEqual(guardados, ['902', '903', str(self.extracao.pk)])


class SidebarDecrescenteTest(RevisaoFormularioBase):
    """A sidebar da revisão vem do MAIOR ato para o menor (decisão do dono,
    #370, 21/11) — só EXIBIÇÃO: índice, estado, navegação e contagem ficam
    como estavam, e o formulário segue na ordem natural.
    """

    def _abas_da_sidebar(self, html):
        sidebar = html[html.index('ia-revisao-sidebar'):]
        return re.findall(
            r'>(\d+)\. (R\d+|Av\d+)', sidebar[:sidebar.index('</aside>')],
        )

    def test_sidebar_vem_do_maior_para_o_menor(self):
        html = self.client.get(self.url_ato(0)).content.decode()

        self.assertEqual(
            self._abas_da_sidebar(html),
            [('3', 'R2'), ('2', 'Av1'), ('1', 'R1')],
        )

    def test_ato_atual_fica_marcado_na_posicao_dele(self):
        html = self.client.get(self.url_ato(1)).content.decode()

        self.assertEqual(
            self._abas_da_sidebar(html),
            [('3', 'R2'), ('2', 'Av1'), ('1', 'R1')],
        )
        em_edicao = re.search(
            r'aria-current="step"\s+title="Ato em edição">(\d+)\. (\S+)', html,
        )
        self.assertEqual(em_edicao.groups(), ('2', 'Av1'))

    def test_links_guardam_o_data_ir_para_do_indice_de_cada_ato(self):
        html = self.client.get(self.url_ato(0)).content.decode()

        sidebar = html[html.index('ia-revisao-sidebar'):]
        self.assertEqual(
            re.findall(
                r'data-ir-para="(\d+)"', sidebar[:sidebar.index('</aside>')],
            ),
            ['2', '1'],
        )

    def test_navegacao_por_ir_para_continua_no_ato_1(self):
        pagina = self.client.get(self.url_ato(1))

        resposta = self.client.post(
            self.url_ato(1), post_do_html(pagina, _ir_para='0'),
        )

        self.assertRedirects(resposta, self.url_ato(0), fetch_redirect_response=False)

    def test_contador_salvos_total_fica_como_antes(self):
        self.salvar(0)  # R-1 — o ÚLTIMO da sidebar agora

        html = self.client.get(self.url_ato(2)).content.decode()

        self.assertIn('ato 3 de 3', html)
        self.assertIn('1 de 3 salvo', html)
        self.assertEqual(
            self._abas_da_sidebar(html),
            [('3', 'R2'), ('2', 'Av1'), ('1', 'R1')],
        )
        self.assertIn('✔ salvo', html)
