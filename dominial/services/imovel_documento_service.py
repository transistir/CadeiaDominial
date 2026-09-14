"""Mantém alinhados o cartório do imóvel e o de seu documento principal."""

from django.core.exceptions import ValidationError

from ..models import Documento, Lancamento
from .cache_service import CacheService


class ImovelDocumentoService:
    """Resolve e sincroniza o documento que representa a identidade do imóvel."""

    @staticmethod
    def candidatos_documento_principal(imovel):
        if not imovel.pk:
            return Documento.objects.none()
        return Documento.objects.filter(
            imovel_id=imovel.pk,
            tipo__tipo=imovel.tipo_documento_principal,
            numero_normalizado=imovel.matricula_normalizada,
        ).select_related('tipo', 'cartorio').order_by('pk')

    @classmethod
    def obter_documento_principal(cls, imovel):
        candidatos = list(cls.candidatos_documento_principal(imovel))
        tipo = imovel.get_tipo_documento_principal_display()
        numero = imovel.matricula_normalizada

        if not candidatos:
            raise ValidationError(
                'Não é possível alterar o cartório do imóvel '
                f'ID {imovel.pk}: nenhum documento principal foi encontrado '
                f'para {tipo} {numero}. Corrija os documentos vinculados antes '
                'de tentar novamente.'
            )
        if len(candidatos) > 1:
            ids = ', '.join(str(documento.pk) for documento in candidatos)
            raise ValidationError(
                'Não é possível alterar o cartório do imóvel '
                f'ID {imovel.pk}: há {len(candidatos)} documentos principais '
                f'candidatos para {tipo} {numero} (IDs: {ids}). Corrija a '
                'ambiguidade antes de tentar novamente.'
            )
        return candidatos[0]

    @staticmethod
    def validar_destino(documento, novo_cartorio):
        conflitos = Documento.objects.filter(
            tipo_id=documento.tipo_id,
            numero_normalizado=documento.numero_normalizado,
            cartorio_id=novo_cartorio.pk,
        ).exclude(pk=documento.pk).order_by('pk')
        ids = list(conflitos.values_list('pk', flat=True))
        if ids:
            ids_formatados = ', '.join(str(documento_id) for documento_id in ids)
            raise ValidationError(
                'Não é possível alterar o cartório do imóvel: o cartório de '
                'destino já possui documento com a mesma identidade '
                f'(IDs: {ids_formatados}).'
            )

    @classmethod
    def validar_alteracao_cartorio(cls, imovel, novo_cartorio):
        if not imovel.pk or not novo_cartorio:
            return None
        if imovel.cartorio_id == novo_cartorio.pk:
            return None
        documento = cls.obter_documento_principal(imovel)
        cls.validar_destino(documento, novo_cartorio)
        return documento

    @classmethod
    def sincronizar_cartorio_documento_principal(cls, imovel):
        documento = cls.obter_documento_principal(imovel)
        cls.validar_destino(documento, imovel.cartorio)
        imoveis_consumidores = Lancamento.objects.filter(
            documento_origem__imovel=imovel,
        ).values_list('documento__imovel_id', flat=True).distinct()
        if documento.cartorio_id != imovel.cartorio_id:
            documento.cartorio_id = imovel.cartorio_id
            documento.save(update_fields=['cartorio'])
        # Best-effort: LocMemCache não propaga invalidações entre workers; um
        # backend compartilhado continua sendo dívida técnica para issue separada.
        imoveis_afetados = {imovel.pk, *imoveis_consumidores}
        for imovel_id in sorted(imoveis_afetados):
            CacheService.invalidate_tronco_principal(imovel_id)
        return documento
