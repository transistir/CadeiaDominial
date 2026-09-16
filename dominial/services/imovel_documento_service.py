"""Sincronização de cartório entre Imovel e seu documento principal (#210).

Bug original: editar `Imovel.cartorio` deixava o `Documento` principal
(tipo=matrícula/transcrição, mesmo número) no cartório antigo. Como a cadeia
dominial resolve documentos por (tipo, numero_normalizado, cartorio), a
matrícula principal sumia da cadeia quando os dois ficavam em cartórios
diferentes.

Escopo deliberadamente reduzido (auditoria rejeitou uma versão anterior de
3.180 linhas): sincroniza SOMENTE o cartório. Tipo/número do documento
principal continuam fora daqui (issue #212).
"""

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from ..models import Documento, Lancamento, LancamentoOrigem
from .lancamento_origem_leitura_service import LancamentoOrigemLeituraService


class ImovelDocumentoService:
    """Mantém `Documento.cartorio` do documento principal alinhado a `Imovel.cartorio`."""

    @staticmethod
    def _buscar_candidatos(imovel):
        return list(
            Documento.objects.filter(
                imovel=imovel,
                tipo__tipo=imovel.tipo_documento_principal,
                numero_normalizado=imovel.matricula_normalizada,
            ).select_related('tipo', 'cartorio')
        )

    @staticmethod
    def _lancamentos_legados_ambiguos(documento, cartorio_antigo):
        """Lançamentos cuja origem só existe como texto livre (sem
        `LancamentoOrigem` estruturado) e que hoje resolvem para a
        identidade antiga do documento. Não há campo estruturado para
        migrar automaticamente, então precisam ser reportados.
        """
        candidatos = (
            Lancamento.objects.filter(origem__isnull=False)
            .exclude(origem='')
            .exclude(id__in=LancamentoOrigem.objects.values_list('lancamento_id', flat=True))
            .select_related('documento', 'cartorio_origem')
        )

        ambiguos = []
        for lancamento in candidatos:
            for origem in LancamentoOrigemLeituraService.obter_origens(lancamento):
                if (
                    origem.fonte == 'legada'
                    and origem.tipo_documento == documento.tipo.tipo
                    and origem.numero_normalizado == documento.numero_normalizado
                    and origem.cartorio_id == cartorio_antigo.id
                ):
                    ambiguos.append(lancamento)
                    break
        return ambiguos

    @staticmethod
    def validar_troca_cartorio(imovel, novo_cartorio):
        """Validação somente-leitura (nenhuma escrita).

        Levanta `ValidationError` quando a troca de cartório não pode ser
        feita com segurança (documento ambíguo, colisão de identidade no
        cartório destino, ou referência textual legada que não pode ser
        migrada). Retorna a lista de candidatos (0 ou 1 documento).
        """
        candidatos = ImovelDocumentoService._buscar_candidatos(imovel)

        if len(candidatos) > 1:
            ids = ', '.join(str(doc.id) for doc in candidatos)
            raise ValidationError(
                f'Existem {len(candidatos)} documentos para a identidade '
                f'{imovel.get_tipo_documento_principal_display()} "{imovel.matricula}" '
                f'deste imóvel (documentos IDs: {ids}). Corrija a duplicidade antes '
                'de trocar o cartório do imóvel.'
            )

        if len(candidatos) == 1:
            documento = candidatos[0]
            if documento.cartorio_id == novo_cartorio.id:
                # Já alinhado ao destino: nada a validar ou migrar.
                return candidatos

            colisao = (
                Documento.objects.filter(
                    tipo__tipo=documento.tipo.tipo,
                    numero_normalizado=documento.numero_normalizado,
                    cartorio=novo_cartorio,
                )
                .exclude(pk=documento.pk)
                .first()
            )
            if colisao:
                raise ValidationError(
                    f'Já existe um documento (ID {colisao.id}) com esta identidade '
                    f'no cartório "{novo_cartorio.nome}". Resolva a colisão antes de '
                    'trocar o cartório do imóvel.'
                )

            legados = ImovelDocumentoService._lancamentos_legados_ambiguos(
                documento, documento.cartorio,
            )
            if legados:
                ids = ', '.join(str(lancamento.id) for lancamento in legados)
                raise ValidationError(
                    'Existem lançamentos com origem textual legada (não estruturada) '
                    f'que referenciam esta identidade e não podem ser migrados '
                    f'automaticamente (lançamentos IDs: {ids}). Estruture a origem '
                    'desses lançamentos antes de trocar o cartório.'
                )

        return candidatos

    @staticmethod
    def sincronizar_cartorio_documento_principal(imovel):
        """Alinha o cartório do documento principal ao `imovel.cartorio` atual.

        Deve ser chamada logo após `imovel.save()`, dentro da mesma
        `transaction.atomic()` do chamador (admin, form ou view). Retorna uma
        mensagem de aviso quando não há documento principal (0 candidatos) —
        o save do imóvel é permitido mesmo assim. Levanta `ValidationError`
        em caso de ambiguidade ou colisão de identidade.
        """
        novo_cartorio = imovel.cartorio
        candidatos = ImovelDocumentoService.validar_troca_cartorio(imovel, novo_cartorio)

        if not candidatos:
            return (
                f'Nenhum documento {imovel.get_tipo_documento_principal_display()} '
                f'"{imovel.matricula}" foi encontrado para vincular ao novo cartório. '
                'A matrícula não aparecerá na cadeia dominial até que o documento '
                'correspondente seja criado ou corrigido.'
            )

        documento = candidatos[0]
        if documento.cartorio_id == novo_cartorio.id:
            return None

        try:
            with transaction.atomic():
                # Revalida dentro da transação (select_for_update trava as
                # linhas em bancos que suportam, ex.: Postgres) para lidar
                # com uma troca concorrente entre a validação e a escrita.
                try:
                    documento_atual = Documento.objects.select_for_update().get(pk=documento.pk)
                except Documento.DoesNotExist as erro:
                    raise ValidationError(
                        'O documento principal foi removido durante a troca de '
                        'cartório. Tente novamente.'
                    ) from erro

                candidatos_atuais = list(
                    Documento.objects.select_for_update().filter(
                        imovel=imovel,
                        tipo__tipo=imovel.tipo_documento_principal,
                        numero_normalizado=imovel.matricula_normalizada,
                    )
                )
                if len(candidatos_atuais) != 1 or candidatos_atuais[0].pk != documento_atual.pk:
                    raise ValidationError(
                        'A situação mudou, tente novamente.'
                    )

                cartorio_antigo = documento_atual.cartorio

                colisao_atual = (
                    Documento.objects.select_for_update()
                    .filter(
                        tipo__tipo=documento_atual.tipo.tipo,
                        numero_normalizado=documento_atual.numero_normalizado,
                        cartorio=novo_cartorio,
                    )
                    .exclude(pk=documento_atual.pk)
                    .first()
                )
                if colisao_atual:
                    raise ValidationError(
                        'Outra alteração concorrente já ocupou esta identidade no '
                        'cartório destino. Tente novamente.'
                    )

                documento_atual.cartorio = novo_cartorio
                documento_atual.save(update_fields=['cartorio'])

                LancamentoOrigem.objects.filter(
                    tipo_documento=imovel.tipo_documento_principal,
                    numero_normalizado=imovel.matricula_normalizada,
                    cartorio=cartorio_antigo,
                ).update(cartorio=novo_cartorio)
        except IntegrityError as erro:
            raise ValidationError(
                'Conflito ao trocar o cartório do documento principal (alteração '
                'concorrente). Tente novamente.'
            ) from erro

        return None
