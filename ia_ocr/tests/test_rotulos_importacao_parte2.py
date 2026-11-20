"""Parte 2 de 3 do corpo de ``RotulosImportacaoTest`` — migração VERBATIM.

Classe simples, sem ``TestCase``; quem coleta é a fachada em
``test_rotulos_importacao.py``.

Os testes de integração com o motor em lote (``importar``, ``resumo``,
``ImportacaoInvalida``) saíram com o motor, aposentado na fase 4 da #341.
Fica o caso que exercita os helpers MANTIDOS direto
(``_linhas_por_chave``, ``_rotulo_efetivo``, ``_resolver_tipo_e_numero``):
linha descartada não decide o tipo.
"""

from ia_ocr import importacao as modulo_importacao, revisao
from ia_ocr.rotulos import analisar_rotulo


class RotulosImportacaoTestParte2:
    def test_rotulo_efetivo_ignora_so_a_linha_descartada(self):
        # Rodada 6: a ordem vale candidato a candidato. Linha ESTRUTURAL
        # descartada → a FOLHA ativa ainda decide; descartar a folha
        # também → os dois candidatos são pulados e o leitor devolve
        # ``None`` sem exceção — o ``tipo_sugerido`` volta a decidir
        # (comportamento anterior à rodada 4).
        extracao = self._extracao(self._payload(
            rotulo='R-5', tipo='averbacao', numero='R-5',
        ))
        linhas = modulo_importacao._linhas_por_chave(extracao)
        (marcado,) = revisao.dados_revisados(extracao).atos
        estrutural = linhas['/acts/0']
        folha = linhas['/acts/0/rotulo']

        revisao.aplicar_linha(
            estrutural, incluir=False, usuario=self.usuario,
        )
        estrutural.save()
        efetivo = modulo_importacao._rotulo_efetivo('/acts/0', linhas)
        self.assertEqual(efetivo, 'R-5')
        tipo, _, _ = modulo_importacao._resolver_tipo_e_numero(
            marcado, analisar_rotulo(efetivo), self.documento,
        )
        self.assertEqual(tipo.tipo, 'registro')

        revisao.aplicar_linha(folha, incluir=False, usuario=self.usuario)
        folha.save()
        efetivo = modulo_importacao._rotulo_efetivo('/acts/0', linhas)
        self.assertIsNone(efetivo)
        tipo, _, _ = modulo_importacao._resolver_tipo_e_numero(
            marcado, analisar_rotulo(efetivo), self.documento,
        )
        self.assertEqual(tipo.tipo, 'averbacao')
