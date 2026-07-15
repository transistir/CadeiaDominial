"""
Utilitários para validações de dados
"""


def validar_cpf(cpf):
    """
    Valida um CPF brasileiro.
    """
    # Remove caracteres não numéricos
    cpf = ''.join(filter(str.isdigit, cpf))
    
    # Verifica se tem 11 dígitos
    if len(cpf) != 11:
        return False
    
    # Verifica se todos os dígitos são iguais
    if cpf == cpf[0] * 11:
        return False
    
    # Calcula o primeiro dígito verificador
    soma = sum(int(cpf[i]) * (10 - i) for i in range(9))
    resto = soma % 11
    digito1 = 0 if resto < 2 else 11 - resto
    
    # Calcula o segundo dígito verificador
    soma = sum(int(cpf[i]) * (11 - i) for i in range(10))
    resto = soma % 11
    digito2 = 0 if resto < 2 else 11 - resto
    
    # Verifica se os dígitos calculados são iguais aos do CPF
    return cpf[-2:] == f"{digito1}{digito2}"


def validar_matricula(matricula):
    """
    Valida um número de matrícula.
    """
    # TODO: Implementar validação específica de matrícula
    # Por enquanto, apenas verifica se não está vazio
    return bool(matricula and matricula.strip())


def validar_sncr(sncr):
    """
    Valida um número SNCR (Sistema Nacional de Cadastro Rural).
    """
    # TODO: Implementar validação específica de SNCR
    # Por enquanto, apenas verifica se não está vazio
    return bool(sncr and sncr.strip()) 