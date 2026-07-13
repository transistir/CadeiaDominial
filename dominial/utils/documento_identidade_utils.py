"""Utilitários puros para a identidade de documentos registrais."""

from dataclasses import dataclass


TIPOS_DOCUMENTO = frozenset({'matricula', 'transcricao'})
PREFIXOS_POR_TIPO = {
    'matricula': 'M',
    'transcricao': 'T',
}


@dataclass(frozen=True, slots=True)
class DocumentoIdentidade:
    """Valor imutável que representa a identidade registral de um documento."""

    tipo: str
    numero_normalizado: str
    cartorio_id: int

    def __post_init__(self):
        if not isinstance(self.tipo, str):
            raise TypeError('O tipo do documento deve ser um texto.')
        if not isinstance(self.cartorio_id, int) or isinstance(self.cartorio_id, bool):
            raise TypeError('O ID do cartório deve ser um número inteiro.')
        if self.cartorio_id <= 0:
            raise ValueError('O ID do cartório deve ser maior que zero.')

        tipo_normalizado = self.tipo.strip().lower()
        numero_normalizado = normalizar_numero_documento(
            self.numero_normalizado,
            tipo_normalizado,
        )

        object.__setattr__(self, 'tipo', tipo_normalizado)
        object.__setattr__(self, 'numero_normalizado', numero_normalizado)


def normalizar_numero_documento(numero, tipo):
    """Retorna o número sem o prefixo de apresentação do tipo informado.

    A função é deliberadamente conservadora: preserva zeros à esquerda,
    pontuação e espaços internos que possam ter significado registral. Apenas
    espaços externos e o prefixo ``M``/``T`` compatível são removidos.

    Raises:
        ValueError: quando tipo/número são inválidos ou o prefixo contradiz o
            tipo estruturado informado.
        TypeError: quando número ou tipo não são textos.
    """
    if not isinstance(tipo, str):
        raise TypeError('O tipo do documento deve ser um texto.')
    if not isinstance(numero, str):
        raise TypeError('O número do documento deve ser um texto.')

    tipo_normalizado = tipo.strip().lower()
    if tipo_normalizado not in TIPOS_DOCUMENTO:
        raise ValueError(f'Tipo de documento inválido: {tipo!r}.')

    numero_normalizado = numero.strip()
    if not numero_normalizado:
        raise ValueError('O número do documento não pode ser vazio.')

    primeiro_caractere = numero_normalizado[0].upper()
    prefixo_esperado = PREFIXOS_POR_TIPO[tipo_normalizado]
    prefixos_conhecidos = set(PREFIXOS_POR_TIPO.values())

    if primeiro_caractere in prefixos_conhecidos:
        if primeiro_caractere != prefixo_esperado:
            raise ValueError(
                f'O prefixo {primeiro_caractere!r} é incompatível com o tipo '
                f'{tipo_normalizado!r}.'
            )
        numero_normalizado = numero_normalizado[1:].strip()

    if not numero_normalizado:
        raise ValueError('O número do documento não pode conter apenas o prefixo.')

    return numero_normalizado
