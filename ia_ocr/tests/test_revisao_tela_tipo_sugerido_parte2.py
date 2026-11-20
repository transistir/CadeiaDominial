"""Card do tipo sugerido como <select> (Tarefa B, #322/PR #327) — migração
VERBATIM de ``ia_ocr/tests/test_revisao_tela.py`` (Etapa 10 do plano de
400 linhas): parte 2 de 2 do corpo de ``TipoSugeridoSelectTest``; classe
SIMPLES (sem ``TestCase``), coletada só pela fachada em
``test_revisao_tela_tipo_sugerido.py``. Corpos verbatim.
"""

import json
import re

from django.utils import timezone

from ia_ocr import estados
from ia_ocr.models import ExtracaoSugerida, OcrJob

from .payloads_extracao import payload_averbacao, payload_registro


class TipoSugeridoSelectTestParte2:
    def test_select_com_ato_descartado_preserva_o_tipo_salvo(self):
        # P2 Greptile / P3-1 Opus (#322/PR #327, rodada 11): aqui é o ATO
        # (/acts/0) que está descartado, não a linha de tipo. O card do
        # tipo CONTINUA na tela — a view só filtra LINHAS_IGNORADAS, o
        # template desenha o card com a classe ``descartado`` e o checkbox
        # de reinclusão. Rodada 12: ``resolucoes_de_tipo`` devolve a
        # entrada do ato descartado (MESMO resolvedor, contexto que ignora
        # só o descarte do próprio ato), então o select marca a escolha
        # explícita salva — antes dela, o select vinha EM BRANCO com tipo
        # salvo e o JS enviava valor='' no "Conferido" da reinclusão,
        # apagando o tipo (origem 'limpo').
        extracao = self._extracao()
        extracao.campos.filter(chave='/acts/0').update(
            status_revisao='descartado',
        )
        extracao.campos.filter(chave='/acts/0/tipo_sugerido').update(
            valor_final='averbacao', status_revisao='editado',
        )

        html = self._tela().content.decode()
        card = self._card(html)

        self.assertIn('<option value="averbacao" selected>', card)

    def test_select_com_ato_descartado_e_tipo_limpo_continua_vazio(self):
        # Rodada 11→12: no ato descartado o '' gravado É a decisão de
        # "sem tipo" — o resolvedor devolve origem 'limpo' (não cai no
        # normalized 'averbacao' nem no rótulo) e o select fica sem opção
        # marcada, como no ato presente.
        extracao = self._extracao()
        extracao.campos.filter(chave='/acts/0').update(
            status_revisao='descartado',
        )
        extracao.campos.filter(chave='/acts/0/tipo_sugerido').update(
            valor_final='', status_revisao='editado',
        )

        html = self._tela().content.decode()
        card = self._card(html)

        self.assertIn('<option value=""></option>', card)
        self.assertIsNone(re.search(r'<option[^>]*\sselected', card))

    def test_select_com_ato_descartado_mostra_o_tipo_do_rotulo(self):
        # Rodada 12 (review Opus r11, caso a): ato descartado SEM escolha
        # do revisor (normalized 'registro', valor_final nulo, sem flag) e
        # rótulo divergente 'Av-5'. O fallback da rodada 11 copiava a
        # precedência na view e exibia o normalized cru ('registro'); ao
        # reincluir e conferir, o JS enviaria esse valor, a flag viraria
        # True e a importação gravaria 'registro' — o rótulo deixaria de
        # vencer sem aviso. O card marca o que o MESMO resolvedor devolve
        # no contexto que ignora só o descarte do próprio ato.
        payload = payload_registro(self.job.job_id)
        payload['acts'][0]['rotulo'] = {
            'raw': 'Av-5', 'normalized': 'Av-5', 'confianca': 0.95,
            'requer_revisao': False,
        }
        extracao = self._extracao(payload)
        extracao.campos.filter(chave='/acts/0').update(
            status_revisao='descartado',
        )

        html = self._tela().content.decode()
        card = self._card(html)

        self.assertIn('<option value="averbacao" selected>', card)
        self.assertNotIn('<option value="registro" selected>', card)

    def test_select_com_ato_e_linha_de_tipo_descartados_mostra_o_rotulo(self):
        # Rodada 12 (review Opus r11, caso c): além do ato, a linha de
        # tipo está descartada com edição preservada ('registro'). O
        # descarte da linha de DENTRO continua valendo no contexto do ato
        # descartado — o resolvedor pula o valor_final morto e usa o
        # rótulo 'Av-5', a mesma semântica do ato presente com a linha de
        # tipo descartada.
        payload = payload_registro(self.job.job_id)
        payload['acts'][0]['rotulo'] = {
            'raw': 'Av-5', 'normalized': 'Av-5', 'confianca': 0.95,
            'requer_revisao': False,
        }
        extracao = self._extracao(payload)
        extracao.campos.filter(chave='/acts/0').update(
            status_revisao='descartado',
        )
        extracao.campos.filter(chave='/acts/0/tipo_sugerido').update(
            status_revisao='descartado', valor_final='registro',
        )

        html = self._tela().content.decode()
        card = self._card(html)

        self.assertIn('<option value="averbacao" selected>', card)
        self.assertNotIn('<option value="registro" selected>', card)

    def test_select_com_ato_descartado_e_valor_fora_do_contrato_mostra_o_resolvido(self):
        # Rodada 12 (review Opus r11, caso b): valor explícito FORA do
        # contrato (estado do backfill da 0009: flag marcada, valor_final
        # nulo, normalized 'transcricao') com rótulo 'R-3'. O fallback
        # exibia 'transcricao' — não marca opção do contrato nenhuma e
        # ainda ganhava opção extra; o 'Conferido' da reinclusão enviaria
        # '' e apagaria o tipo. O resolvedor cai no rótulo: marca
        # 'registro', sem opção extra de um valor que o save recusaria.
        payload = payload_averbacao(self.job.job_id)
        payload['acts'][0]['rotulo'] = {
            'raw': 'R-3', 'normalized': 'R-3', 'confianca': 0.95,
            'requer_revisao': False,
        }
        extracao = self._extracao(payload)
        extracao.campos.filter(chave='/acts/0').update(
            status_revisao='descartado',
        )
        extracao.campos.filter(chave='/acts/0/tipo_sugerido').update(
            normalized='transcricao', escolha_explicita=True,
            status_revisao='aceito', valor_final=None,
        )

        html = self._tela().content.decode()
        card = self._card(html)

        self.assertIn('<option value="registro" selected>', card)
        self.assertNotIn('transcricao', card)

    def test_select_com_valor_explicito_fora_do_contrato_mostra_o_resolvido(self):
        # P2 (#322/PR #327, rodada 10): 'transcricao' fora de
        # TIPOS_SUGERIDOS com escolha_explicita=True — estado que o
        # backfill da 0009 pode criar a partir de 'aceito'/'importado'
        # legados. O resolvedor NÃO usa esse valor (cai no rótulo), e o
        # card mostra o que a importação usa; sem opção extra de um tipo
        # que o próprio save recusaria com 422.
        payload = payload_registro(self.job.job_id)
        payload['acts'][0]['rotulo'] = {
            'raw': 'Av-5', 'normalized': 'Av-5', 'confianca': 0.95,
            'requer_revisao': False,
        }
        extracao = self._extracao(payload)
        extracao.campos.filter(chave='/acts/0/tipo_sugerido').update(
            normalized='transcricao', escolha_explicita=True,
            status_revisao='aceito', valor_final=None,
        )

        html = self._tela().content.decode()
        card = self._card(html)

        self.assertIn('<option value="averbacao" selected>', card)
        self.assertNotIn('transcricao', card)

    def test_select_com_tipo_limpo_nao_seleciona_opcao_nenhuma(self):
        # P2-1 + P2-2 (#322/PR #327): ``valor_final=''`` é tipo APAGADO —
        # decisão válida; nenhuma opção marcada (o navegador enviaria a
        # vazia) e a pendência de ``tipo_sugerido`` volta a bloquear.
        extracao = self._extracao()
        extracao.campos.filter(chave='/acts/0/tipo_sugerido').update(
            valor_final='', status_revisao='editado',
        )

        html = self._tela().content.decode()
        card = self._card(html)

        self.assertIn('<option value=""></option>', card)
        self.assertIsNone(re.search(r'<option[^>]*\sselected', card))

    def test_somente_leitura_desabilita_o_select(self):
        extracao = self._extracao()
        ExtracaoSugerida.objects.filter(pk=extracao.pk).update(
            finalizada_em=timezone.now(), finalizada_por=self.dono,
        )
        OcrJob.objects.filter(pk=self.job.pk).update(status=estados.REVISADO)

        html = self._tela().content.decode()

        self.assertIn(' disabled', self._tag_select(html))

    def test_post_registro_diferente_salva_valor_final(self):
        # SHOULD-FIX (revisão Opus): o POST com valor DIFERENTE do
        # normalized prova o salvamento — o sugerido aqui é 'averbacao'.
        extracao = self._extracao()

        salvar = self._salvar_tipo({'conferido': True, 'valor': 'registro'})

        self.assertEqual(salvar.status_code, 200, salvar.content)
        campo = extracao.campos.get(chave='/acts/0/tipo_sugerido')
        self.assertEqual(campo.valor_final, 'registro')
        self.assertEqual(campo.status_revisao, 'editado')
        self.assertTrue(campo.escolha_explicita)

    def test_post_mesmo_valor_marca_escolha_explicita(self):
        # Caso separado (SHOULD-FIX, revisão Opus): valor IGUAL ao sugerido
        # deixa o ``valor_final`` nulo, mas a flag marca que o revisor
        # passou pelo card — e é ela que vence o rótulo na importação.
        extracao = self._extracao()

        salvar = self._salvar_tipo({'conferido': True, 'valor': 'averbacao'})

        self.assertEqual(salvar.status_code, 200, salvar.content)
        campo = extracao.campos.get(chave='/acts/0/tipo_sugerido')
        self.assertIsNone(campo.valor_final)
        self.assertEqual(campo.status_revisao, 'aceito')
        self.assertTrue(campo.escolha_explicita)

    def test_post_fora_do_enum_e_422_sem_gravar(self):
        extracao = self._extracao()

        salvar = self.client.post(
            self.url('salvar_bloco_ocr'),
            data=json.dumps({
                'versao': self._tela().context['versao'],
                'decisoes': [{
                    'chave': '/acts/0/tipo_sugerido',
                    'incluir': True, 'conferido': True,
                    'valor': 'compra_e_venda',
                }],
            }),
            content_type='application/json',
        )

        self.assertEqual(salvar.status_code, 422, salvar.content)
        self.assertEqual(salvar.json()['erro'], 'valor_invalido')
        self.assertEqual(salvar.json()['chave'], '/acts/0/tipo_sugerido')
        # Sem refresh redundante: ``campos.get`` relê do banco (nit revisão).
        campo = extracao.campos.get(chave='/acts/0/tipo_sugerido')
        self.assertEqual(campo.normalized, 'averbacao')
        self.assertIsNone(campo.valor_final)
        self.assertEqual(campo.status_revisao, 'sugerido')
