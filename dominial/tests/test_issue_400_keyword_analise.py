"""
Issue #400 — o badge de palavra-chave não pode ser criado por texto do
sistema. ``buscar_keyword`` ignora blocos analíticos (§5, regra 4): só o
texto documental dispara ATENÇÃO/PENDENTE.
"""

from datetime import date

from django.test import SimpleTestCase

from dominial.services.keyword_alerta_service import buscar_keyword
from dominial.services.observacoes_analise import registrar_analise


DATA = date(2026, 11, 25)


class BuscarKeywordIgnoraAnaliseTest(SimpleTestCase):
    def test_analise_com_pendente_nao_dispara(self):
        texto = '[ANÁLISE — fulano — 2026-11-25] PENDENTE de certidão'
        self.assertIsNone(buscar_keyword(texto))

    def test_analise_com_atencao_nao_dispara(self):
        texto = '[ANÁLISE — fulano — 2026-11-25] ATENÇÃO à divergência de área'
        self.assertIsNone(buscar_keyword(texto))

    def test_documental_com_pendente_continua_disparando(self):
        resultado = buscar_keyword('Certidão pendente de averbação')

        self.assertIsNotNone(resultado)
        self.assertEqual(resultado['label'], 'PENDENTE')
        self.assertEqual(resultado['priority'], 3)

    def test_documental_com_atencao_continua_disparando(self):
        resultado = buscar_keyword('Atenção: conferir área remanescente')

        self.assertIsNotNone(resultado)
        self.assertEqual(resultado['label'], 'ATENÇÃO')
        self.assertEqual(resultado['priority'], 2)

    def test_misto_devolve_a_prioridade_do_documental(self):
        texto = registrar_analise(
            'Documento com atenção na área',
            'PENDENTE de certidão',
            'fulano',
            DATA,
        )

        resultado = buscar_keyword(texto)

        self.assertIsNotNone(resultado)
        # O analítico (PENDENTE, prioridade 3) não pode rebaixar o
        # documental (ATENÇÃO, prioridade 2).
        self.assertEqual(resultado['label'], 'ATENÇÃO')
        self.assertEqual(resultado['priority'], 2)

    def test_acento_e_caixa_continuam_funcionando(self):
        self.assertEqual(buscar_keyword('ATENCAO')['label'], 'ATENÇÃO')
        self.assertEqual(buscar_keyword('pEnDeNtE')['label'], 'PENDENTE')

    def test_documental_que_contem_analise_como_palavra_nao_e_removido(self):
        # "análise" no texto documental não é marcador: o texto segue valendo.
        resultado = buscar_keyword('Análise pendente do setor jurídico')

        self.assertIsNotNone(resultado)
        self.assertEqual(resultado['label'], 'PENDENTE')
