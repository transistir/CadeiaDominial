import re
from dataclasses import dataclass

from django.db.models import Prefetch

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

    ATRIBUTO_PREFETCH = '_origens_estruturadas_prefetch'

    @classmethod
    def prefetch_linhas(cls):
        """``Prefetch`` para carregar em lote as linhas de vários lançamentos."""
        # Import tardio evita o ciclo models -> utils -> services -> utils.
        from ..models import LancamentoOrigem

        return Prefetch(
            'origens_estruturadas',
            queryset=LancamentoOrigem.objects.select_related('cartorio').order_by(
                'indice_origem', 'id'
            ),
            to_attr=cls.ATRIBUTO_PREFETCH,
        )

    @classmethod
    def linhas_estruturadas(cls, lancamento):
        """Linhas ``LancamentoOrigem`` do lançamento: do prefetch, se houver."""
        prefetched = getattr(lancamento, cls.ATRIBUTO_PREFETCH, None)
        if prefetched is not None:
            return prefetched
        return list(
            lancamento.origens_estruturadas.select_related('cartorio').order_by(
                'indice_origem', 'id'
            )
        )

    @classmethod
    def obter_origens(cls, lancamento):
        estruturadas = cls.linhas_estruturadas(lancamento)
        if estruturadas:
            return tuple(
                OrigemLancamentoLeitura(
                    indice_origem=origem.indice_origem,
                    tipo_documento=origem.tipo_documento,
                    numero=origem.numero,
                    numero_normalizado=origem.numero_normalizado,
                    cartorio=origem.cartorio,
                    livro=cls._normalizar_metadado(origem.livro),
                    folha=cls._normalizar_metadado(origem.folha),
                    fonte='estruturada',
                )
                for origem in estruturadas
            )
        return cls._obter_fallback_textual(lancamento)

    @classmethod
    def _obter_fallback_textual(cls, lancamento):
        if not lancamento.origem:
            return ()

        # Mesmo fallback já usado no caminho de escrita
        # (LancamentoOrigemService._buscar_dados_origem): sem
        # `cartorio_origem` explícito, assume o cartório do próprio
        # documento do lançamento, em vez de ficar sem cartório (o que faria
        # consumidores que exigem identidade completa ignorarem a origem
        # silenciosamente). Achado da revisão automatizada do PR (Qodo,
        # 2026-07-14).
        cartorio_fallback = (
            lancamento.cartorio_origem
            or (lancamento.documento.cartorio if lancamento.documento_id else None)
        )

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
                    cartorio=cartorio_fallback,
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
        if valor is None or valor == "None":
            return None
        return valor.strip() if isinstance(valor, str) and valor.strip() else None
