"""
Utilitários para formatação de dados
"""


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