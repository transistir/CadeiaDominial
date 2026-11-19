"""Erros de controle da importação: recusa do lote e rollback do ato."""


class ImportacaoInvalida(Exception):
    """Um ou mais atos não puderam ser gravados (HTTP 422)."""

    code = 'importacao_invalida'

    def __init__(self, linhas):
        self.linhas = list(linhas)
        super().__init__(self.code)


class _AtoInvalido(Exception):
    """Controle interno: força o savepoint do ato a rodar rollback.

    Devolver erros "normalmente" do ``_importar_ato`` deixava o savepoint
    COMITAR o que o ato inválido já tinha gravado (lançamento parcial,
    pessoas, cartórios) — o rollback só vinha no final, tarde demais para
    os atos seguintes (#263 rodada 2). Levantada DENTRO do atomic do ato,
    ela desfaz o savepoint na hora; o loop captura fora e acumula.
    """

    def __init__(self, erros):
        self.erros = erros
        super().__init__('ato invalido')
