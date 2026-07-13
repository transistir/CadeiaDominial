"""Resolução central e inequívoca de documentos pela identidade registral."""

from dataclasses import dataclass
from typing import Literal

from ..models import Documento
from ..utils.documento_identidade_utils import (
    DocumentoIdentidade,
    normalizar_numero_documento,
)


StatusResolucao = Literal['nao_encontrado', 'encontrado', 'ambiguo']


@dataclass(frozen=True, slots=True)
class ResultadoResolucaoDocumento:
    status: StatusResolucao
    identidade: DocumentoIdentidade
    documento: Documento | None = None
    candidatos: tuple[Documento, ...] = ()

    def __post_init__(self):
        if self.status == 'encontrado' and self.documento is None:
            raise ValueError('Uma resolução encontrada deve conter o documento.')
        if self.status != 'encontrado' and self.documento is not None:
            raise ValueError('Somente uma resolução encontrada pode conter documento.')
        if self.status == 'ambiguo' and len(self.candidatos) < 2:
            raise ValueError('Uma resolução ambígua deve conter ao menos dois candidatos.')


class DocumentoIdentidadeService:
    """Localiza documentos sem reduzir sua identidade ao número."""

    @staticmethod
    def resolver(identidade: DocumentoIdentidade) -> ResultadoResolucaoDocumento:
        if not isinstance(identidade, DocumentoIdentidade):
            raise TypeError('A resolução exige um DocumentoIdentidade completo.')

        # O filtro estrutural sempre restringe tipo e cartório. A comparação do
        # número acontece em Python temporariamente para aceitar dados legados
        # armazenados como "M123" e dados canônicos armazenados como "123".
        documentos_estruturalmente_compativeis = Documento.objects.filter(
            tipo__tipo=identidade.tipo,
            cartorio_id=identidade.cartorio_id,
        ).select_related('tipo', 'cartorio', 'imovel').order_by('pk')

        candidatos = tuple(
            documento
            for documento in documentos_estruturalmente_compativeis
            if normalizar_numero_documento(documento.numero, identidade.tipo)
            == identidade.numero_normalizado
        )

        if not candidatos:
            return ResultadoResolucaoDocumento(
                status='nao_encontrado',
                identidade=identidade,
            )
        if len(candidatos) > 1:
            return ResultadoResolucaoDocumento(
                status='ambiguo',
                identidade=identidade,
                candidatos=candidatos,
            )
        return ResultadoResolucaoDocumento(
            status='encontrado',
            identidade=identidade,
            documento=candidatos[0],
            candidatos=candidatos,
        )

    @staticmethod
    def resolver_por_dados(tipo, numero, cartorio_id) -> ResultadoResolucaoDocumento:
        return DocumentoIdentidadeService.resolver(
            DocumentoIdentidade(
                tipo=tipo,
                numero_normalizado=numero,
                cartorio_id=cartorio_id,
            )
        )
