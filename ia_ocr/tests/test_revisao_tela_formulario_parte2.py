"""Contrato de apresentação da tela por ato (I-11a, #321) — migração
VERBATIM de ``ia_ocr/tests/test_revisao_tela.py`` (Etapa 10 do plano de
400 linhas): parte 2 de 2 do corpo de ``FormularioPorAtoTest``; classe
SIMPLES (sem ``TestCase``), coletada só pela fachada em
``test_revisao_tela_formulario.py``. Corpos verbatim.
"""

import json
import re

from django.test import override_settings

from ia_ocr import revisao, rotulos

from .payloads_extracao import _campo, payload_averbacao
from .test_revisao_tela_base import (
    _descendentes, _texto_fora_de_details, _valor_do_select,
)
from .test_ui_card_ocr import _atributos, _elementos


class FormularioPorAtoTestParte2:
    @override_settings(OCR_PERMITIR_FINALIZAR_SEM_ATOS=True)
    def test_pendencia_aponta_para_campo_existente(self):
        def conferir_links(resposta):
            html = resposta.content.decode()
            bloco = _elementos(html, 'section', presentes=('data-ocr-pendencias',))[0]
            links = _descendentes(bloco, 'a', 'href')
            self.assertTrue(links)
            self.assertEqual(len(links), len(resposta.context['pendencias']))
            ids = re.findall(r'\bid="([^"]+)"', html)
            for link in links:
                alvo = _atributos(link)['href'].removeprefix('#')
                self.assertEqual(ids.count(alvo), 1, alvo)
                controles = [
                    elemento for tag in ('input', 'select', 'textarea')
                    for elemento in _elementos(html, tag, valores={'id': alvo})
                ]
                self.assertEqual(len(controles), 1, alvo)

        self._extracao(self._payload_formulario())
        conferir_links(self._tela())
        payload = payload_averbacao(self.job.job_id)
        payload['acts'] = []
        self._extracao(payload, resolver=True)
        resposta = self._tela()
        conferir_links(resposta)
        self.assertContains(resposta, 'href="#campo-sem-atos"')
        with self.settings(OCR_PERMITIR_FINALIZAR_SEM_ATOS=False):
            self.assertNotContains(self._tela(), 'href="#campo-sem-atos"')
        for chave, acao in (
            ('/acts/0/tipo_sugerido', 'informe o tipo do lançamento'),
            ('/document/data', 'informe a data'),
            ('/document/cartorio', 'escolha o cartório'),
        ):
            descricao = revisao.descrever_pendencia({
                'chave': chave, 'motivo': 'obrigatorio_ausente',
            })
            self.assertEqual(descricao['acao'], acao)

    def test_bloco_do_tipo_intacto(self):
        payload = self._payload_formulario()
        # Sugestão divergente: a opção selecionada vem do resolvedor (#327).
        payload['acts'][0]['rotulo']['normalized'] = 'Av-1'
        self._extracao(payload)
        resposta = self._tela()
        card = _elementos(resposta.content.decode(), 'article', valores={
            'data-chave': '/acts/0/tipo_sugerido',
        })[0]
        selects = _descendentes(card, 'select', 'data-campo-valor')
        self.assertEqual(len(selects), 1)
        select = selects[0]
        self.assertEqual(_atributos(select)['data-tipo'], 'enum')
        self.assertEqual(_atributos(select)['id'], 'campo-acts0tipo_sugerido')
        opcoes = _descendentes(select, 'option', 'value')
        self.assertEqual([_atributos(o)['value'] for o in opcoes],
                         ['', *rotulos.TIPOS_SUGERIDOS])
        self.assertEqual([_texto_fora_de_details(o) for o in opcoes[1:]],
                         [o['display'] for o in resposta.context['opcoes_tipo_sugerido']])
        selecionadas = [o for o in opcoes if 'selected' in _atributos(o)]
        self.assertEqual(len(selecionadas), 1)
        self.assertEqual(_atributos(selecionadas[0])['value'], 'averbacao')
        campo = next(c for c in resposta.context['campos'] if c.eh_tipo_sugerido)
        self.assertEqual(_valor_do_select(select), campo.tipo_exibido)
        self.assertFalse(_descendentes(card, 'input', 'data-campo-valor'))

    # --- #324 (I-11d): origem sem livro/folha ------------------------------

    @staticmethod
    def _card_da_origem(html, chave):
        return next(
            card for card in _elementos(
                html, 'article', presentes=('data-campo',),
            )
            if _atributos(card)['data-chave'] == chave
        )

    def test_origem_sem_livro_e_folha_campo_vazio_editavel_com_selo(self):
        self._extracao(self._payload_formulario(), resolver=True)
        html = self._tela().content.decode()

        for nome in ('livro', 'folha'):
            chave = f'/acts/0/origem/{nome}'
            with self.subTest(chave=chave):
                card = self._card_da_origem(html, chave)
                (entrada,) = _descendentes(card, 'textarea', 'data-campo-valor')
                atributos = _atributos(entrada)
                self.assertNotIn('disabled', atributos)
                self.assertNotIn('readonly', atributos)
                # Nunca pré-preenchido: o revisor informa ou segue sem.
                self.assertEqual(''.join(
                    filho for filho in entrada.children
                    if isinstance(filho, str)
                ).strip(), '')
                (selo,) = _descendentes(card, 'span', 'data-campo-nao-consta')
                self.assertEqual(
                    _texto_fora_de_details(selo).strip(),
                    'não consta no documento',
                )
                self.assertEqual(
                    atributos['aria-describedby'], _atributos(selo)['id'],
                )
        # O selo é só de livro/folha: número lido, data e tipo não o ganham.
        for nome in ('numero', 'data', 'tipo_documento', 'cartorio'):
            with self.subTest(sem_selo=nome):
                card = self._card_da_origem(html, f'/acts/0/origem/{nome}')
                self.assertEqual(
                    _descendentes(card, 'span', 'data-campo-nao-consta'), [],
                )

    def test_aviso_da_origem_tem_rotulo_proprio_e_nao_bloqueia(self):
        self._extracao(self._payload_formulario(), resolver=True)
        resposta = self._tela()
        html = resposta.content.decode()

        self.assertEqual(
            sorted(
                item['motivo'] for item in resposta.context['avisos']
                if item['motivo'].endswith('_nao_consta')
            ),
            ['folha_origem_nao_consta', 'livro_origem_nao_consta'],
        )
        self.assertFalse([
            item for item in resposta.context['pendencias']
            if item['motivo'].endswith('_nao_consta')
        ])
        bloco = _elementos(html, 'section', presentes=('data-ocr-avisos',))[0]
        visivel = _texto_fora_de_details(bloco)
        self.assertIn('Livro da origem não consta no documento', visivel)
        self.assertIn('Folha da origem não consta no documento', visivel)
        for interno in (
            'livro_origem_nao_consta', 'folha_origem_nao_consta', '/acts/',
        ):
            with self.subTest(interno=interno):
                self.assertNotIn(interno, visivel)
        # Só o aviso da origem: nada de "recomendado não preenchido" no lugar.
        self.assertNotIn('Campo recomendado não preenchido', visivel)
        botao = re.search(r'<button[^>]*data-ocr-finalizar[^>]*>', html).group(0)
        self.assertEqual(
            'disabled' in botao, bool(resposta.context['pendencias']),
        )

    def test_selo_some_quando_o_documento_traz_livro_e_folha(self):
        payload = self._payload_formulario()
        payload['acts'][0]['origem']['livro'] = _campo('3-A', 'R-1/42.718')
        payload['acts'][0]['origem']['folha'] = _campo('12', 'R-1/42.718')
        self._extracao(payload, resolver=True)
        resposta = self._tela()
        html = resposta.content.decode()

        self.assertFalse([
            item for item in resposta.context['avisos']
            if item['motivo'].endswith('_nao_consta')
        ])
        self.assertNotIn('data-campo-nao-consta', html)

    # --- #324 (PR #343, P2): o save devolve os avisos RECALCULADOS ----------
    # Os avisos e os selos "não consta no documento" só eram calculados na
    # abertura da página: preencher livro/folha deixava o aviso na tela, e
    # mudar o número da origem podia esconder ou criar um. A resposta do save
    # traz a lista do estado recém-salvo, da MESMA fonte da abertura.

    CHAVES_LIVRO_FOLHA = ('/acts/0/origem/livro', '/acts/0/origem/folha')

    def _salvar_decisoes(self, decisoes):
        return self.client.post(
            self.url('salvar_bloco_ocr'),
            data=json.dumps({
                'versao': self._tela().context['versao'],
                'decisoes': [
                    {'chave': chave, 'incluir': True, 'valor': valor}
                    for chave, valor in decisoes.items()
                ],
            }),
            content_type='application/json',
        )

    @staticmethod
    def _chaves_dos_avisos(avisos):
        return sorted((item['chave'], item['motivo']) for item in avisos)

    def test_salvar_livro_e_folha_da_origem_tira_os_avisos_do_ato(self):
        self._extracao(self._payload_formulario(), resolver=True)
        abertura = self._tela().context['avisos']
        self.assertEqual(
            sorted(
                item['chave'] for item in abertura
                if item['motivo'].endswith('_nao_consta')
            ),
            sorted(self.CHAVES_LIVRO_FOLHA),
        )

        resposta = self._salvar_decisoes({
            '/acts/0/origem/livro': '3-A', '/acts/0/origem/folha': '12',
        })

        self.assertEqual(resposta.status_code, 200, resposta.content)
        avisos = resposta.json()['avisos']
        # Os avisos de livro/folha DAQUELE ato saíram da resposta, e com eles
        # o selo (nenhum item "não consta" sobrou).
        self.assertFalse([
            item for item in avisos if item['chave'] in self.CHAVES_LIVRO_FOLHA
        ])
        self.assertFalse([item for item in avisos if item['nao_consta']])
        # É o MESMO cálculo da abertura: reabrir a tela mostra a mesma lista.
        self.assertEqual(
            self._chaves_dos_avisos(avisos),
            self._chaves_dos_avisos(self._tela().context['avisos']),
        )

    def test_salvar_so_o_livro_mantem_o_aviso_da_folha(self):
        self._extracao(self._payload_formulario(), resolver=True)

        resposta = self._salvar_decisoes({'/acts/0/origem/livro': '3-A'})

        self.assertEqual(resposta.status_code, 200, resposta.content)
        (aviso,) = [
            item for item in resposta.json()['avisos'] if item['nao_consta']
        ]
        self.assertEqual(aviso, {
            'chave': '/acts/0/origem/folha',
            'motivo': 'folha_origem_nao_consta',
            'local': 'Ato 1 — folha',
            'rotulo': 'Folha da origem não consta no documento',
            'nao_consta': True,
        })

    def test_esvaziar_o_livro_depois_de_salvo_volta_o_aviso(self):
        payload = self._payload_formulario()
        payload['acts'][0]['origem']['livro'] = _campo('3-A', 'R-1/42.718')
        self._extracao(payload, resolver=True)
        self.assertFalse([
            item for item in self._tela().context['avisos']
            if item['chave'] == '/acts/0/origem/livro'
        ])

        resposta = self._salvar_decisoes({'/acts/0/origem/livro': ''})

        self.assertEqual(resposta.status_code, 200, resposta.content)
        self.assertEqual(
            [
                (item['chave'], item['motivo'], item['nao_consta'])
                for item in resposta.json()['avisos']
                if item['chave'] == '/acts/0/origem/livro'
            ],
            [('/acts/0/origem/livro', 'livro_origem_nao_consta', True)],
        )

    def test_preencher_o_numero_da_origem_cria_os_avisos_de_livro_e_folha(self):
        """Sem número não há documento de origem citado: nada a avisar."""
        payload = self._payload_formulario()
        del payload['acts'][0]['origem']['numero']
        self._extracao(payload, resolver=True)
        self.assertFalse([
            item for item in self._tela().context['avisos']
            if item['motivo'].endswith('_nao_consta')
        ])

        resposta = self._salvar_decisoes({'/acts/0/origem/numero': '42'})

        self.assertEqual(resposta.status_code, 200, resposta.content)
        self.assertEqual(
            sorted(
                item['chave'] for item in resposta.json()['avisos']
                if item['nao_consta']
            ),
            sorted(self.CHAVES_LIVRO_FOLHA),
        )

    def test_apagar_o_numero_da_origem_esconde_os_avisos_de_livro_e_folha(self):
        self._extracao(self._payload_formulario(), resolver=True)
        self.assertTrue([
            item for item in self._tela().context['avisos']
            if item['motivo'].endswith('_nao_consta')
        ])

        resposta = self._salvar_decisoes({'/acts/0/origem/numero': ''})

        self.assertEqual(resposta.status_code, 200, resposta.content)
        self.assertFalse([
            item for item in resposta.json()['avisos'] if item['nao_consta']
        ])
