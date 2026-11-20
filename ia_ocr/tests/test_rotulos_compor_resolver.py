"""Partes por cenário de ``test_rotulos``; coletadas pela fachada."""

from ia_ocr.rotulos import compor_numero_lancamento, resolver_tipo

class ComporNumeroLancamentoTestParte:
    """compor_numero_lancamento: o formato canônico do V1 (#322 rodada 3).

    Decisão de produto (orquestrador, por falta de resposta do cliente): a
    importação grava o MESMO texto do fluxo manual
    (``lancamento_form_service._gerar_numero_lancamento``) — os sete
    consumidores ordenam por ``^(R|AV)\\d+``.
    """

    def test_registro_e_averbacao_com_sigla(self):
        self.assertEqual(
            compor_numero_lancamento('registro', '5', 'M237'), 'R5 M237',
        )
        self.assertEqual(
            compor_numero_lancamento('averbacao', '6', 'M237'), 'AV6 M237',
        )

    def test_sigla_vazia_compoe_sem_ela(self):
        self.assertEqual(compor_numero_lancamento('registro', '5', ''), 'R5')
        self.assertEqual(
            compor_numero_lancamento('averbacao', '6', None), 'AV6',
        )

    def test_inicio_de_matricula_e_so_a_sigla(self):
        self.assertEqual(
            compor_numero_lancamento('inicio_matricula', '5', 'M237'),
            'M237',
        )
        self.assertIsNone(
            compor_numero_lancamento('inicio_matricula', '5', ''),
        )

    def test_sem_numero_do_ato_nao_compoe_prefixo(self):
        # P2-5 na gravação: sem número do ato não há o que prefixar.
        self.assertIsNone(compor_numero_lancamento('registro', None, 'M237'))
        self.assertIsNone(compor_numero_lancamento('averbacao', '', 'M237'))

    def test_tipo_fora_dos_tres_devolve_o_numero(self):
        # Mesmo fallback do fluxo manual: número como veio.
        self.assertEqual(
            compor_numero_lancamento('transcricao', '5', 'M237'), '5',
        )
        self.assertIsNone(compor_numero_lancamento(None, None, 'M237'))


class ResolverTipoTestParte:
    """Precedência de resolução de tipo do ato (#322 rodada 7)."""

    def test_tipo_explicito_vence_rotulo_e_sugestao(self):
        tipo, divergencia, origem = resolver_tipo('averbacao', 'R-1', 'registro')
        self.assertEqual(tipo, 'averbacao')
        self.assertFalse(divergencia)
        self.assertEqual(origem, 'explicito')

    def test_rotulo_vence_sugestao_com_divergencia(self):
        tipo, divergencia, origem = resolver_tipo(None, 'R-1', 'averbacao')
        self.assertEqual(tipo, 'registro')
        self.assertTrue(divergencia)
        self.assertEqual(origem, 'rotulo')

    def test_rotulo_concorda_com_sugestao_sem_divergencia(self):
        tipo, divergencia, origem = resolver_tipo(None, 'R-1', 'registro')
        self.assertEqual(tipo, 'registro')
        self.assertFalse(divergencia)
        self.assertEqual(origem, 'rotulo')

    def test_sugestao_vence_sem_rotulo_nem_edicao(self):
        tipo, divergencia, origem = resolver_tipo(None, None, 'averbacao')
        self.assertEqual(tipo, 'averbacao')
        self.assertFalse(divergencia)
        self.assertEqual(origem, 'sugerido')

    def test_rotulo_matricula_nao_define_tipo(self):
        tipo, divergencia, origem = resolver_tipo(None, 'M-3-14511', 'registro')
        self.assertEqual(tipo, 'registro')
        self.assertFalse(divergencia)
        self.assertEqual(origem, 'sugerido')

    def test_tipo_explicito_invalido_ignorado(self):
        tipo, divergencia, origem = resolver_tipo('tipo_invalido', 'R-1', 'averbacao')
        self.assertEqual(tipo, 'registro')
        self.assertTrue(divergencia)
        self.assertEqual(origem, 'rotulo')

    def test_tudo_vazio_devolve_nenhum(self):
        tipo, divergencia, origem = resolver_tipo(None, None, None)
        self.assertIsNone(tipo)
        self.assertFalse(divergencia)
        self.assertEqual(origem, 'nenhum')

    def test_tipo_limpo_e_decisao_antes_de_rotulo_e_sugestao(self):
        # P2-1 (#322/PR #327): '' explícito (revisor limpou o <select>)
        # é decisão de "sem tipo" — cairia no rótulo/sugestão e o tipo
        # apagado seria importado sem aviso.
        self.assertEqual(
            resolver_tipo('', 'Av-5', 'averbacao'), (None, False, 'limpo'),
        )

    def test_tipo_ausente_mantem_a_precedencia_antiga(self):
        # None continua "sem decisão": rótulo e sugestão decidem como antes.
        self.assertEqual(
            resolver_tipo(None, 'Av-5', 'averbacao'),
            ('averbacao', False, 'rotulo'),
        )

