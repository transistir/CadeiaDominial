"""Erro público do pré-preenchimento."""

class AtoInexistente(LookupError):
    """O índice não é de um ato incluído da revisão (inexistente ou descartado)."""

    def __init__(self, chave):
        self.chave = chave
        super().__init__(chave)
