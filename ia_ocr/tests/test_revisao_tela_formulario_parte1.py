"""Contrato de apresentação da tela por ato (I-11a, #321) — migração
VERBATIM de ``ia_ocr/tests/test_revisao_tela.py`` (Etapa 10 do plano de
400 linhas).

Parte 1 de 2 do corpo de ``FormularioPorAtoTest`` (613 linhas não cabem
em um arquivo de 400). Classe SIMPLES (sem ``TestCase``); quem coleta é
a fachada em ``test_revisao_tela_formulario.py``. Corpos verbatim.
"""

import copy
import json
import re

from django.test.html import parse_html

from dominial.models import LancamentoTipo
from ia_ocr import revisao
from ia_ocr.models import CampoSugerido, ExtracaoSugerida

from .payloads_extracao import _campo, payload_averbacao, payload_com_closure
from .test_revisao_tela_base import _descendentes, _texto_fora_de_details
from .test_ui_card_ocr import _atributos, _elementos


class FormularioPorAtoTestParte1:
    """Contrato de apresentação I-11a (#321), sem mudar decisões da revisão."""

    def _payload_formulario(self):
        payload = payload_com_closure(self.job.job_id)
        ato = payload['acts'][0]
        for nome, valor in (
            ('numero_lancamento', '1'), ('forma', 'Compra e venda'),
            ('titulo', 'Escritura pública'), ('descricao', 'Descrição do ato'),
            ('detalhes', 'Informação complementar'),
            ('eh_inicio_matricula', False), ('observacoes', 'Observações do ato'),
            ('cartorio_transmissao', 'CRI de Guaíra'),
        ):
            ato[nome] = _campo(valor, 'R-1/42.718')
        ato['origem'] = {
            'numero': _campo('42', 'R-1/42.718'),
            'cartorio': _campo('CRI de Guaíra', 'CRI de Guaíra'),
        }
        return payload

    def test_transmissao_ordem_rotulos_e_bloco_do_ato(self):
        self._extracao(self._payload_formulario())
        resposta = self._tela()
        html = resposta.content.decode()
        ato = _elementos(html, 'section', valores={'data-secao': 'ato'})[0]
        chaves = self._chaves_do_html(str(ato))
        sequencia = [
            f'/acts/0/{nome}' for nome in (
                'cartorio_transmissao', 'livro_transacao', 'folha_transacao',
                'data_transacao', 'origem/cartorio',
            )
        ]
        for chave in sequencia:
            self.assertEqual(chaves.count(chave), 1)
        posicoes = [chaves.index(chave) for chave in sequencia]
        self.assertEqual(posicoes, sorted(posicoes))

        cards = {
            _atributos(card)['data-chave']: card
            for card in _elementos(str(ato), 'article', presentes=('data-campo',))
        }
        outros = _elementos(html, 'section', valores={'data-secao': 'outros'})[0]
        chaves_outros = self._chaves_do_html(str(outros))
        for nome, rotulo in (
            ('livro_transacao', 'Livro da transmissão'),
            ('folha_transacao', 'Folha da transmissão'),
            ('data_transacao', 'Data da transmissão'),
        ):
            chave = f'/acts/0/{nome}'
            with self.subTest(chave=chave):
                label = _descendentes(cards[chave], 'label', 'data-campo-rotulo')[0]
                self.assertEqual(_texto_fora_de_details(label), rotulo)
                self.assertNotIn(chave, chaves_outros)

    def test_transmissao_data_tem_input_date(self):
        self._extracao(self._payload_formulario())
        html = self._tela().content.decode()
        cards = _elementos(html, 'article', valores={
            'data-chave': '/acts/0/data_transacao',
        })
        self.assertEqual(len(cards), 1)
        controles = _descendentes(cards[0], 'input', 'data-campo-valor')
        self.assertEqual(len(controles), 1)
        self.assertEqual(_atributos(controles[0])['type'], 'date')

    def test_formulario_abre_pela_secao_documento(self):
        payload = self._payload_formulario()
        self._extracao(payload)
        resposta = self._tela()
        html = resposta.content.decode()

        self.assertEqual(_texto_fora_de_details(_elementos(html, 'h2')[0]), 'Documento')
        secoes = resposta.context['secoes']
        self.assertEqual(secoes[0]['tipo'], 'documento')
        self.assertEqual([c.chave for c in secoes[0]['campos']], [
            '/document/' + nome for nome in (
                'tipo', 'numero', 'data', 'cartorio', 'livro', 'folha',
                'imovel_descricao', 'area',
            )
        ])
        campos = resposta.context['campos']
        self.assertCountEqual(self._chaves_do_html(html), [c.chave for c in campos])
        antes = [dict(c.__dict__) for c in campos]
        with self.assertNumQueries(0):
            revisao.secoes_da_tela(campos, payload=payload)
        self.assertEqual([c.__dict__ for c in campos], antes)

        # Não reconhecidos usa o payload do serviço; legado usa o salvo.
        desconhecido = copy.deepcopy(payload)
        desconhecido['acts'][0]['rotulo']['normalized'] = 'X-9'
        for servico, salvo in ((desconhecido, payload), ({}, desconhecido)):
            with self.subTest(payload_servico=bool(servico)):
                ExtracaoSugerida.objects.update(payload_servico=servico, payload=salvo)
                html = self._tela().content.decode()
                secao = _elementos(html, 'section', valores={
                    'data-secao': 'nao_reconhecidos',
                })[0]
                self.assertIn('X-9', str(secao))
                self.assertFalse(_descendentes(secao, 'article', 'data-campo'))

    def test_atos_em_ordem_reversa(self):
        payload = self._payload_formulario()
        payload['acts'] = [copy.deepcopy(payload['acts'][0]) for _ in range(3)]
        for ato in payload['acts']:
            ato['rotulo'].update(normalized=None, raw=None)
        extracao = self._extracao(payload)

        def titulos(resposta):
            return [
                _texto_fora_de_details(_elementos(str(secao), 'h2')[0])
                for secao in _elementos(resposta.content.decode(), 'section',
                                       valores={'data-secao': 'ato'})
            ]

        self.assertEqual(titulos(self._tela()), ['Ato 3', 'Ato 2', 'Ato 1'])
        for indice, rotulo in enumerate(('R-1', 'Av-2', 'R-3')):
            extracao.campos.filter(chave=f'/acts/{indice}/rotulo').update(
                normalized=rotulo, raw='Texto bruto diferente',
            )
        resposta = self._tela()
        self.assertEqual(titulos(resposta), ['Ato R-3', 'Ato Av-2', 'Ato R-1'])
        secoes = [s for s in resposta.context['secoes'] if s['tipo'] == 'ato']
        self.assertEqual([s['tipo_display'] for s in secoes], [
            'Registro', 'Averbação', 'Registro',
        ])
        for secao in secoes:
            prefixo = secao['chave_ato']
            total = sum(
                p['chave'] == prefixo or p['chave'].startswith(prefixo + '/')
                for p in resposta.context['pendencias']
            )
            self.assertEqual(secao['pendencias_do_ato'], total)
            self.assertContains(resposta, f'{total} pendência')

    def test_nenhuma_chave_interna_fora_do_detalhe_tecnico(self):
        LancamentoTipo.objects.update_or_create(
            tipo='registro', defaults={'requer_forma': True},
        )
        payload = self._payload_formulario()
        del payload['acts'][0]['forma']
        self._extracao(payload)
        resposta = self._tela()
        self.assertTrue(resposta.context['avisos'])
        self.assertTrue(resposta.context['pendencias'])
        visivel = _texto_fora_de_details(parse_html(resposta.content.decode()))
        for interno in (
            '/document/', '/acts/', 'SEM_DESTINO', 'requer_forma',
            'escolha_pendente', 'dominial.Lancamento',
        ):
            with self.subTest(interno=interno):
                self.assertNotIn(interno, visivel)
        self.assertIn('Campo recomendado não preenchido', visivel)

    def test_rotulo_de_negocio_por_campo(self):
        self._extracao(self._payload_formulario())
        html = self._tela().content.decode()
        cards = {
            _atributos(c)['data-chave']: c
            for c in _elementos(html, 'article', presentes=('data-campo',))
        }
        for chave, esperado in (
            ('/acts/0/tipo_sugerido', 'Tipo do lançamento'),
            ('/acts/0/numero_lancamento', 'Número'),
            ('/acts/0/data', 'Data'), ('/acts/0/area', 'Área (ha)'),
            ('/document/numero', 'Número do documento'),
            ('/acts/0/cartorio_transmissao', 'Cartório da transmissão'),
        ):
            with self.subTest(chave=chave):
                rotulo = _descendentes(cards[chave], 'label', 'data-campo-rotulo')[0]
                self.assertEqual(_texto_fora_de_details(rotulo), esperado)
        visivel = _texto_fora_de_details(parse_html(html))
        self.assertIn('Partes', visivel)
        self.assertIn('Origem', visivel)
        self.assertNotIn('tipo_sugerido', visivel)
        self.assertNotIn('numero_lancamento', visivel)
        self.assertEqual(revisao.rotulo_de_campo('/acts/0/campo_desconhecido'),
                         'Campo desconhecido')

    def test_campo_fora_do_formulario_fica_em_outros_dados(self):
        self._extracao(self._payload_formulario(), resolver=True)
        resposta = self._tela()
        html = resposta.content.decode()
        outros = _elementos(html, 'section', valores={'data-secao': 'outros'})[0]
        self.assertIn('Outros dados lidos', str(outros))
        detalhe = _elementos(str(outros), 'details', valores={'class': 'outros-dados'})[0]
        self.assertNotIn('open', _atributos(detalhe))
        chaves_outros = self._chaves_do_html(str(detalhe))
        for chave in (
            '/acts/0/eh_inicio_matricula', '/acts/0/rotulo',
            '/document/cri_atual',
            '/closure/indicio_fim_cadeia',
        ):
            with self.subTest(chave=chave):
                self.assertIn(chave, chaves_outros)
                self.assertEqual(self._chaves_do_html(html).count(chave), 1)
        ato = next(s for s in resposta.context['secoes'] if s['tipo'] == 'ato')
        self.assertEqual(ato['campos'][0].chave, '/acts/0')
        grupos = list(dict.fromkeys(c.chave.split('/')[3] for c in ato['campos'][1:]))
        self.assertEqual(grupos, [
            'tipo_sugerido', 'numero_lancamento', 'data', 'forma', 'titulo',
            'descricao', 'area', 'partes', 'cartorio_transmissao',
            'livro_transacao', 'folha_transacao', 'data_transacao', 'origem',
            'observacoes',
        ])
        pendentes = {p['chave'] for p in resposta.context['pendencias']}
        for card in _elementos(html, 'article', presentes=('data-campo',)):
            detalhes = _elementos(str(card), 'details', valores={'class': 'campo-detalhe'})
            self.assertEqual(len(detalhes), 1)
            self.assertEqual('open' in _atributos(detalhes[0]),
                             _atributos(card)['data-chave'] in pendentes)
        # O agrupador também acolhe folhas legadas, sem reativá-las no save.
        legados = [
            CampoSugerido(chave='/acts/0/valor_transacao', normalized='150000'),
            CampoSugerido(chave='/acts/0/campo_desconhecido', normalized='extra'),
            CampoSugerido(chave='/acts/0/area/dado_extra', normalized='extra'),
        ]
        secoes = revisao.secoes_da_tela(legados)
        self.assertEqual(secoes[-1]['tipo'], 'outros')
        self.assertEqual([c.chave for c in secoes[-1]['campos']],
                         [c.chave for c in legados])

    def test_ato_descartado_aparece_no_proprio_bloco(self):
        extracao = self._extracao(self._payload_formulario())
        for status in ('sugerido', 'descartado'):
            with self.subTest(status=status):
                extracao.campos.filter(chave='/acts/0').update(status_revisao=status)
                html = self._tela().content.decode()
                secao = _elementos(html, 'section', valores={
                    'data-chave-ato': '/acts/0',
                })[0]
                cards = _descendentes(secao, 'article', 'data-campo')
                self.assertEqual([_atributos(c)['data-chave'] for c in cards[:2]],
                                 ['/acts/0', '/acts/0/tipo_sugerido'])
                incluir = _descendentes(cards[0], 'input', 'data-campo-incluir')
                self.assertEqual(len(incluir), 1)
                self.assertIn('Incluir', _texto_fora_de_details(cards[0]))
                self.assertEqual('checked' in _atributos(incluir[0]),
                                 status != 'descartado')
                self.assertEqual('descartado' in _atributos(secao)['class'].split(),
                                 status == 'descartado')
                outros = _elementos(html, 'section', valores={'data-secao': 'outros'})[0]
                self.assertNotIn('/acts/0', self._chaves_do_html(str(outros)))
                self.assertEqual(self._chaves_do_html(html).count('/acts/0'), 1)

    def test_pendencia_em_outros_abre_o_detalhe(self):
        extracao = self._extracao(self._payload_formulario(), resolver=True)
        # #328: ``detalhes`` nem vira linha — a pendência exemplar em
        # "outros dados" usa outra folha fora do formulário (``rotulo``).
        chave = '/acts/0/rotulo'
        extracao.campos.filter(chave=chave).update(
            status_revisao='sugerido', requer_revisao=True,
        )

        resposta = self._tela()
        html = resposta.content.decode()
        pendencia = next(p for p in resposta.context['pendencias'] if p['chave'] == chave)
        self.assertContains(resposta, f'href="#{pendencia["alvo"]}"')
        outros = _elementos(html, 'details', valores={'class': 'outros-dados'})[0]
        self.assertIn('open', _atributos(outros))
        card = _elementos(str(outros), 'article', valores={'data-chave': chave})[0]
        detalhe = _elementos(str(card), 'details', valores={'class': 'campo-detalhe'})[0]
        self.assertIn('open', _atributos(detalhe))
        controle = _descendentes(card, 'textarea', 'data-campo-valor')[0]
        self.assertEqual(_atributos(controle)['id'], pendencia['alvo'])

    def test_titulo_do_ato_usa_rotulo_da_linha_do_ato(self):
        payload = payload_averbacao(self.job.job_id)
        payload['acts'][0]['rotulo']['normalized'] = 'Av-5'
        payload['acts'] = [copy.deepcopy(payload['acts'][0]) for _ in range(6)]
        extracao = self._extracao(payload)
        chave = '/acts/5'
        extracao.campos.filter(chave=f'{chave}/rotulo').delete()

        def titulo():
            secao = _elementos(self._tela().content.decode(), 'section', valores={
                'data-chave-ato': chave,
            })[0]
            return _texto_fora_de_details(_elementos(str(secao), 'h2')[0])

        self.assertEqual(titulo(), 'Ato Av-5')
        # A folha ganha quando incluída, mas seu descarte devolve a decisão
        # à linha estrutural; descartar ambas usa o número da seção.
        folha = CampoSugerido.objects.create(
            extracao=extracao, chave=f'{chave}/rotulo', tipo_valor='texto',
            normalized='R-9', valor_final='Av-7', status_revisao='editado',
        )
        self.assertEqual(titulo(), 'Ato Av-7')
        folha.status_revisao = 'descartado'
        folha.save(update_fields=['status_revisao'])
        self.assertEqual(titulo(), 'Ato Av-5')
        extracao.campos.filter(chave=chave).update(status_revisao='descartado')
        self.assertEqual(titulo(), 'Ato 6')

    def test_campo_texto_continua_textarea(self):
        payload = self._payload_formulario()
        for nome in ('titulo', 'forma'):
            payload['acts'][0][nome]['normalized'] = 'A\nB'
        extracao = self._extracao(payload)
        resposta = self._tela()
        html = resposta.content.decode()
        decisoes = []
        for nome in ('titulo', 'forma'):
            with self.subTest(campo=nome):
                chave = f'/acts/0/{nome}'
                card = _elementos(html, 'article', valores={'data-chave': chave})[0]
                controles = _descendentes(card, 'textarea', 'data-campo-valor')
                self.assertEqual(len(controles), 1)
                self.assertFalse(_descendentes(card, 'input', 'data-campo-valor'))
                atributos = _atributos(controles[0])
                self.assertEqual(atributos['data-tipo'], 'texto')
                self.assertIn('campo-valor', atributos['class'].split())
                # O parser de HTML normaliza espaços; leia o valor literal
                # para garantir que o formulário conserva a quebra de linha.
                valor = re.search(
                    rf'<textarea\b[^>]*id="{atributos["id"]}"[^>]*>(.*?)</textarea>',
                    html, re.S,
                ).group(1)
                self.assertEqual(valor, 'A\nB')
                decisoes.append({
                    'chave': chave, 'valor': valor, 'incluir': True, 'conferido': True,
                })
        salvar = self.client.post(
            self.url('salvar_bloco_ocr'),
            data=json.dumps({'versao': resposta.context['versao'], 'decisoes': decisoes}),
            content_type='application/json',
        )
        self.assertEqual(salvar.status_code, 200, salvar.content)
        for decisao in decisoes:
            campo = extracao.campos.get(chave=decisao['chave'])
            self.assertEqual(revisao._valor_efetivo(campo), 'A\nB')

