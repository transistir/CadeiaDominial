"""Save sobre linha ignorada (Tarefa C #322, #328) — migração VERBATIM de
``ia_ocr/tests/test_revisao_tela.py`` (Etapa 10 do plano de 400 linhas):
mesma classe, mesmos nomes de teste; só mudam os imports.
"""

import json

from ia_ocr import services
from ia_ocr.models import CampoSugerido

from .test_revisao_tela_base import TelaRevisaoBase


class LinhaIgnoradaSaveTest(TelaRevisaoBase):
    """Tarefa C #322 (revisão Opus): decisão sobre linha ignorada não é 500.

    Extração antiga já salvou ``/acts/0/valor_transacao`` ou
    ``/acts/0/detalhes`` (#328); as folhas não têm mais destino (Tarefa C).
    Aba aberta antes do deploy pode reenviar o card: o save recusa com 422
    ``linha_inexistente``, sem gravar nada — e o token da tela segue valendo
    para salvar OUTRO card (o token cobre todas as linhas, inclusive a
    ignorada).
    """

    def _extracao_antiga(self):
        extracao = self._extracao()
        CampoSugerido.objects.create(
            extracao=extracao,
            chave='/acts/0/valor_transacao',
            raw='R$ 150.000,00',
            normalized='150000.00',
            tipo_valor='decimal',
            status_revisao='aceito',
        )
        CampoSugerido.objects.create(
            extracao=extracao,
            chave='/acts/0/detalhes',
            raw='Detalhes antigos do ato',
            normalized='Detalhes antigos do ato',
            tipo_valor='texto',
            status_revisao='aceito',
        )
        return extracao

    def test_post_na_linha_ignorada_e_422_sem_gravar(self):
        # #328 rodada 2 (Opus N-2): a recusa vale para as duas folhas sem
        # destino — valor_transacao (#322) e detalhes (#328).
        extracao = self._extracao_antiga()
        versao = self._tela().context['versao']

        for chave, valor in (
            ('/acts/0/valor_transacao', '150000.00'),
            ('/acts/0/detalhes', 'Detalhes antigos do ato'),
        ):
            with self.subTest(chave=chave):
                salvar = self.client.post(
                    self.url('salvar_bloco_ocr'),
                    data=json.dumps({
                        'versao': versao,
                        'decisoes': [{
                            'chave': chave,
                            'incluir': True, 'conferido': True, 'valor': valor,
                        }],
                    }),
                    content_type='application/json',
                )

                self.assertEqual(salvar.status_code, 422, salvar.content)
                self.assertEqual(salvar.json()['erro'], 'linha_inexistente')
                campo = extracao.campos.get(chave=chave)
                self.assertIsNone(campo.valor_final)
                # Nada foi gravado: o token da tela continua sendo o vigente.
                self.assertEqual(services.versao_bloco(extracao), versao)

    def test_salvar_outro_card_com_o_token_da_tela_e_200(self):
        self._extracao_antiga()
        versao = self._tela().context['versao']

        salvar = self.client.post(
            self.url('salvar_bloco_ocr'),
            data=json.dumps({
                'versao': versao,
                'decisoes': [{
                    'chave': '/document/numero',
                    'incluir': True, 'conferido': True,
                }],
            }),
            content_type='application/json',
        )

        self.assertEqual(salvar.status_code, 200, salvar.content)
