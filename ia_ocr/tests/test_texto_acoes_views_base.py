"""Auxiliares compartilhados das ações da tela de texto."""

from .test_ui_card_ocr import _elementos


def _botao(conteudo, atributo):
    achados = _elementos(conteudo, 'button', presentes=(atributo,))
    return achados[0] if achados else None
