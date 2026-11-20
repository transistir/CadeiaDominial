"""Máscaras de PII (CPF/RG) da revisão OCR.

Movidas de ``ia_ocr/views/campos.py`` (#341 fase 3): a máscara é usada
pela tela de revisão E pelo pré-preenchimento do formulário
(``formulario/texto.py``), que não devia depender do pacote de views —
o import tardio de lá virou import de topo, do dono. Os nomes continuam
acessíveis via ``ia_ocr.views`` (reexport no ``__init__`` do pacote),
que é como os testes existentes os resolvem.
"""
import re


def _mascarar_cpf(cpf):
    digitos = re.sub(r'\D', '', cpf or '')
    return f'CPF ***.***.***-{digitos[-2:]}' if len(digitos) >= 2 else 'CPF ***'


_CPF = re.compile(r'\b\d{3}[.\s]?\d{3}[.\s]?\d{3}[-.\s]?\d{2}\b')
_RG = re.compile(r'\b\d{1,2}\.\d{3}\.\d{3}-?[\dXx]\b')
_RG_ROTULO = re.compile(
    r'(?i)(\bR\.?G\.?(?:\s*n\.?\s*[º°o]?\.?)?\s*[:\-]?\s*)'
    r'\d(?:[.\-/\s]?\d){4,11}(?:[-\s]?[\dXx])?'
)


def _mascarar_evidencia(trecho):
    """Esconde CPF/RG no trecho exibido; datas, valores e CNS ficam intactos."""
    if not trecho:
        return trecho
    mascarado = _CPF.sub('***', trecho)
    mascarado = _RG.sub('***', mascarado)
    return _RG_ROTULO.sub(r'\1***', mascarado)


def _mascarar_rg(rg):
    digitos = re.sub(r'\D', '', rg or '')
    return f'RG ***{digitos[-2:]}' if len(digitos) >= 2 else 'RG ***'
