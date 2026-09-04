"""
Utilitários para formatação de dados
"""

import unicodedata


_PREFIXO_CRI = "cartorio de registro de imoveis"


def _remover_acentos_preservando_posicao(texto):
    """
    Remove acentos mantendo o mapeamento de posição: cada caractere do texto
    de entrada vira exatamente um caractere no resultado. Assim o índice de
    fim de um prefixo casado no texto sem acento vale também no texto de
    entrada (evitando o descasamento de comprimento de uma normalização NFKD
    ingênua).

    Espera receber texto já em NFC — ver `abreviar_cartorio`. Sequências
    combinantes (base + marca) que sobrarem são tratadas como uma unidade:
    a marca combinante isolada é mantida na saída (preservando a posição),
    mas o `.startswith` do prefixo já terá casado pelo caractere base.
    """
    resultado = []
    for caractere in texto:
        base = ''.join(
            c
            for c in unicodedata.normalize("NFKD", caractere)
            if not unicodedata.combining(c)
        )
        resultado.append(base if len(base) == 1 else caractere)
    return ''.join(resultado)


def abreviar_cartorio(nome):
    """
    Substitui o prefixo "Cartório de Registro de Imóveis" pela sigla "CRI".

    Usado APENAS nas exportações (Excel e PDF completo) — a UI de cadastro
    mantém o nome por extenso (issue #50).

    - Falsy (None, "") retorna inalterado.
    - Só o prefixo exato casa (variantes como "do Registro" não são tocadas).
    - NFC e NFD do mesmo texto produzem o mesmo resultado (o texto é
      normalizado para NFC antes de comparar).
    - Exige fronteira de palavra após "Imóveis" (fim da string ou caractere
      não-alfabético): "...ImóveisXYZ" NÃO é abreviado.
    - A caixa e os acentos do restante do nome são preservados.
    """
    if not nome:
        return nome

    nome_nfc = unicodedata.normalize("NFC", nome)
    normalizado = _remover_acentos_preservando_posicao(nome_nfc).lower()
    if not normalizado.startswith(_PREFIXO_CRI):
        return nome

    fim = len(_PREFIXO_CRI)
    if fim < len(normalizado) and normalizado[fim].isalpha():
        # Sem fronteira de palavra depois de "Imóveis" — não abrevia.
        return nome

    resto = nome_nfc[fim:].lstrip()
    return f"CRI {resto}".rstrip()


def formatar_cpf(cpf):
    """
    Formata um CPF no padrão XXX.XXX.XXX-XX
    """
    if not cpf:
        return ""
    
    # Remove caracteres não numéricos
    cpf = ''.join(filter(str.isdigit, cpf))
    
    # Verifica se tem 11 dígitos
    if len(cpf) != 11:
        return cpf
    
    # Formata o CPF
    return f"{cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]}"


def formatar_telefone(telefone):
    """
    Formata um telefone no padrão (XX) XXXXX-XXXX
    """
    if not telefone:
        return ""
    
    # Remove caracteres não numéricos
    telefone = ''.join(filter(str.isdigit, telefone))
    
    # Verifica se tem 10 ou 11 dígitos
    if len(telefone) == 10:
        return f"({telefone[:2]}) {telefone[2:6]}-{telefone[6:]}"
    elif len(telefone) == 11:
        return f"({telefone[:2]}) {telefone[2:7]}-{telefone[7:]}"
    else:
        return telefone


def formatar_valor_monetario(valor):
    """
    Formata um valor monetário no padrão brasileiro
    """
    if valor is None:
        return "R$ 0,00"
    
    try:
        return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except (ValueError, TypeError):
        return "R$ 0,00"


def formatar_area(area):
    """
    Formata uma área em hectares
    """
    if area is None:
        return "0,00 ha"

    try:
        return f"{area:,.2f} ha".replace(",", "X").replace(".", ",").replace("X", ".")
    except (ValueError, TypeError):
        return "0,00 ha"


def normalizar_texto_opcional(valor, padrao=None):
    """Substitui valores textuais ausentes ou o sentinela legado 'None'."""
    if valor is None:
        return padrao

    if isinstance(valor, str):
        valor_comparacao = valor.strip()
        if not valor_comparacao or valor_comparacao == "None":
            return padrao

    return valor