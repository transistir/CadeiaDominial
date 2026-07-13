import re
from dataclasses import dataclass

from ..utils.documento_identidade_utils import normalizar_numero_documento


PADROES_FIM_CADEIA = (
    'Destacamento Público:',
    'Outra:',
    'Sem Origem:',
    'FIM_CADEIA',
)


@dataclass(frozen=True)
class OrigemLancamentoLeitura:
    indice_origem: int
    tipo_documento: str
    numero: str
    numero_normalizado: str
    cartorio: object
    livro: str | None
    folha: str | None
    fonte: str

    @property
    def cartorio_id(self):
        return self.cartorio.pk if self.cartorio else None

    @property
    def codigo(self):
        prefixo = 'M' if self.tipo_documento == 'matricula' else 'T'
        return f'{prefixo}{self.numero_normalizado}'


class LancamentoOrigemLeituraService:
    """Lê estrutura primeiro e usa o texto somente na ausência dela."""

    @classmethod
    def obter_origens(cls, lancamento):
        estruturadas = list(
            lancamento.origens_estruturadas.select_related('cartorio').order_by(
                'indice_origem', 'id'
            )
        )
        if estruturadas:
            return tuple(
                OrigemLancamentoLeitura(
                    indice_origem=origem.indice_origem,
                    tipo_documento=origem.tipo_documento,
                    numero=origem.numero,
                    numero_normalizado=origem.numero_normalizado,
                    cartorio=origem.cartorio,
                    livro=origem.livro,
                    folha=origem.folha,
                    fonte='estruturada',
                )
                for origem in estruturadas
            )
        return cls._obter_fallback_textual(lancamento)

    @classmethod
    def _obter_fallback_textual(cls, lancamento):
        if not lancamento.origem:
            return ()

        resultados = []
        partes = [parte.strip() for parte in lancamento.origem.split(';') if parte.strip()]
        for indice, parte in enumerate(partes):
            if any(padrao in parte for padrao in PADROES_FIM_CADEIA):
                continue
            identidade = cls._extrair_identidade_legada(parte)
            if identidade is None:
                continue
            tipo_documento, numero, numero_normalizado = identidade
            resultados.append(
                OrigemLancamentoLeitura(
                    indice_origem=indice,
                    tipo_documento=tipo_documento,
                    numero=numero,
                    numero_normalizado=numero_normalizado,
                    cartorio=lancamento.cartorio_origem,
                    livro=cls._normalizar_metadado(lancamento.livro_origem),
                    folha=cls._normalizar_metadado(lancamento.folha_origem),
                    fonte='legada',
                )
            )
        return tuple(resultados)

    @staticmethod
    def _extrair_identidade_legada(texto):
        numero = texto.strip()
        prefixado = re.match(r'^([MT])\s*\d', numero, re.IGNORECASE)
        if prefixado:
            tipo_documento = (
                'matricula'
                if prefixado.group(1).upper() == 'M'
                else 'transcricao'
            )
        elif re.fullmatch(r'\d+', numero):
            tipo_documento = 'matricula'
        else:
            codigos = re.findall(r'([MT])\s*(\d+)', numero, re.IGNORECASE)
            if len(codigos) != 1:
                return None
            prefixo, valor = codigos[0]
            tipo_documento = (
                'matricula' if prefixo.upper() == 'M' else 'transcricao'
            )
            numero = f'{prefixo.upper()}{valor}'

        try:
            normalizado = normalizar_numero_documento(numero, tipo_documento)
        except (TypeError, ValueError):
            return None
        return tipo_documento, numero, normalizado

    @staticmethod
    def _normalizar_metadado(valor):
        return valor.strip() if isinstance(valor, str) and valor.strip() else None
