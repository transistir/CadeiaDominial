"""Card do tipo sugerido como <select> (Tarefa B, #322/PR #327) — migração
VERBATIM de ``ia_ocr/tests/test_revisao_tela.py`` (Etapa 10 do plano de
400 linhas).

Parte 1 de 2 do corpo de ``TipoSugeridoSelectTest`` (410 linhas não
cabem em um arquivo de 400). Classe SIMPLES (sem ``TestCase``); quem
coleta é a fachada em ``test_revisao_tela_tipo_sugerido.py``. Corpos
verbatim.
"""

import json
import re

from dominial.models import LancamentoTipo
from ia_ocr import rotulos

from .payloads_extracao import payload_registro


class TipoSugeridoSelectTestParte1:
    """Tarefa B (#322/PR #327): o card do tipo é <select>, como o formulário.

    As opções DESENHADAS e o enum ACEITO no save vêm da MESMA fonte — o
    contrato A3 (``rotulos.TIPOS_SUGERIDOS``; revisão Opus, MUST-FIX #322).
    O rótulo de exibição vem do cadastro (``LancamentoTipo``) quando a
    linha existe e de ``TIPO_CHOICES`` quando não vem; valor efetivo fora
    do enum ganha opção extra selecionada em vez de cair na vazia. Valor
    fora do enum enviado no POST continua sendo recusado com 422.
    """

    def setUp(self):
        super().setUp()
        # Produção tem as 3 linhas de LancamentoTipo; a suíte não semeia.
        for tipo in ('averbacao', 'registro', 'inicio_matricula'):
            LancamentoTipo.objects.get_or_create(tipo=tipo)

    def _card(self, html):
        achado = re.search(
            r'<article[^>]*data-chave="/acts/0/tipo_sugerido".*?</article>',
            html, re.S,
        )
        self.assertIsNotNone(achado)
        return achado.group(0)

    def _tag_select(self, html):
        tags = [
            tag for tag in re.findall(r'<select[^>]*>', self._card(html))
            if 'data-campo-valor' in tag
        ]
        self.assertEqual(len(tags), 1, tags)
        return tags[0]

    def _salvar_tipo(self, decisao):
        return self.client.post(
            self.url('salvar_bloco_ocr'),
            data=json.dumps({
                'versao': self._tela().context['versao'],
                'decisoes': [{
                    'chave': '/acts/0/tipo_sugerido', 'incluir': True,
                    **decisao,
                }],
            }),
            content_type='application/json',
        )

    def test_card_do_tipo_e_select_com_as_opcoes_do_contrato(self):
        self._extracao()

        html = self._tela().content.decode()
        card = self._card(html)

        self.assertIn('data-tipo="enum"', self._tag_select(html))
        self.assertIn('<option value=""></option>', card)
        # Uma opção por código do contrato, com o display do cadastro.
        for codigo in rotulos.TIPOS_SUGERIDOS:
            self.assertIn(f'<option value="{codigo}"', card)
        for _codigo, display in LancamentoTipo.TIPO_CHOICES:
            self.assertIn(f'>{display}</option>', card)
        # Selecionado = tipo_exibido da view (aqui o rótulo 'Av-1' resolve
        # 'averbacao', concordando com a sugestão).
        self.assertIn('<option value="averbacao" selected>', card)
        # O select é o único editor da chave: nada de input de texto.
        self.assertIsNone(re.search(r'<input[^>]*type="text"', card))
        self.assertNotIn('<textarea', card)

    def test_post_cada_opcao_desenhada_e_aceito(self):
        # MUST-FIX (revisão Opus): nenhum valor que o select oferece pode
        # dar 422 — opções e enum vêm da mesma fonte.
        extracao = self._extracao()

        for codigo in rotulos.TIPOS_SUGERIDOS:
            with self.subTest(codigo=codigo):
                salvar = self._salvar_tipo(
                    {'conferido': True, 'valor': codigo},
                )
                self.assertEqual(salvar.status_code, 200, salvar.content)
                campo = extracao.campos.get(chave='/acts/0/tipo_sugerido')
                self.assertEqual(
                    campo.valor_final if campo.valor_final is not None
                    else campo.normalized,
                    codigo,
                )

    def test_normalizado_sem_linha_no_cadastro_nao_perde_o_valor(self):
        # MUST-FIX (revisão Opus): 'inicio_matricula' está no contrato mas
        # sem linha no cadastro — antes, nenhuma opção era marcada, o
        # navegador enviava a vazia e o save apagava a sugestão. Agora a
        # opção sai de TIPO_CHOICES, selecionada, e o valor sobrevive.
        # P2-2 (#322/PR #327): com o tipo exibido resolvido pelo ato, o
        # rótulo 'Av-1' é neutralizado para a SUGESTÃO decidir — senão o
        # card mostraria 'averbacao' (o que a importação usaria) em vez
        # da sugestão 'inicio_matricula' que este teste exercita.
        extracao = self._extracao()
        extracao.campos.filter(chave='/acts/0/tipo_sugerido').update(
            normalized='inicio_matricula',
        )
        extracao.campos.filter(
            chave__in=('/acts/0', '/acts/0/rotulo'),
        ).update(normalized=None, raw=None, valor_final=None)
        LancamentoTipo.objects.filter(tipo='inicio_matricula').delete()

        html = self._tela().content.decode()
        card = self._card(html)
        self.assertIn('<option value="inicio_matricula" selected>', card)
        self.assertIn('>Início de Matrícula</option>', card)

        salvar = self._salvar_tipo(
            {'conferido': True, 'valor': 'inicio_matricula'},
        )
        self.assertEqual(salvar.status_code, 200, salvar.content)
        campo = extracao.campos.get(chave='/acts/0/tipo_sugerido')
        # O design envia o MESMO valor do normalized: valor_final fica None
        # por desenho e a decisão vive em escolha_explicita.
        self.assertIsNone(campo.valor_final)
        self.assertTrue(campo.escolha_explicita)
        self.assertEqual(
            campo.valor_final if campo.valor_final is not None
            else campo.normalized,
            'inicio_matricula',
        )

        # Save seguinte conferindo sem valor: o efetivo permanece.
        salvar = self._salvar_tipo({'conferido': True})
        self.assertEqual(salvar.status_code, 200, salvar.content)
        campo = extracao.campos.get(chave='/acts/0/tipo_sugerido')
        self.assertEqual(
            campo.valor_final if campo.valor_final is not None
            else campo.normalized,
            'inicio_matricula',
        )

    def test_select_seleciona_valor_final_revisado(self):
        extracao = self._extracao()
        extracao.campos.filter(chave='/acts/0/tipo_sugerido').update(
            valor_final='registro', status_revisao='editado',
        )

        html = self._tela().content.decode()

        self.assertIn('<option value="registro" selected>', self._card(html))
        self.assertNotIn(
            '<option value="averbacao" selected>', self._card(html),
        )

    def test_select_mostra_o_tipo_resolvido_do_ato(self):
        # P2-2 (#322/PR #327): rótulo 'Av-5' × sugestão 'registro' sem
        # decisão do revisor — o card mostra o MESMO tipo que pendências,
        # prévia e importação resolvem (o rótulo vence), não o normalized
        # cru: o card não pode exibir um tipo e a importação usar outro.
        payload = payload_registro(self.job.job_id)
        payload['acts'][0]['rotulo'] = {
            'raw': 'Av-5', 'normalized': 'Av-5', 'confianca': 0.95,
            'requer_revisao': False,
        }
        self._extracao(payload)

        html = self._tela().content.decode()
        card = self._card(html)

        self.assertIn('<option value="averbacao" selected>', card)
        self.assertNotIn('<option value="registro" selected>', card)

    def test_select_com_linha_descartada_mostra_o_tipo_do_rotulo(self):
        # P2 (#322/PR #327, rodada 10): linha de tipo DESCARTADA com edição
        # preservada ('registro') — ``_contexto_revisao`` remove a linha e
        # o resolvedor usa o rótulo 'Av-5'. A cópia antiga da precedência
        # na view mostrava o ``valor_final`` morto; o card tem que exibir
        # o que a importação usa ('averbacao'), nunca 'registro'.
        payload = payload_registro(self.job.job_id)
        payload['acts'][0]['rotulo'] = {
            'raw': 'Av-5', 'normalized': 'Av-5', 'confianca': 0.95,
            'requer_revisao': False,
        }
        extracao = self._extracao(payload)
        extracao.campos.filter(chave='/acts/0/tipo_sugerido').update(
            status_revisao='descartado', valor_final='registro',
        )

        html = self._tela().content.decode()
        card = self._card(html)

        self.assertIn('<option value="averbacao" selected>', card)
        self.assertNotIn('<option value="registro" selected>', card)

