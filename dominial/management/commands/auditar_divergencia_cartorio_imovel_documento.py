"""Audita divergências entre `Imovel.cartorio` e o documento principal (#210).

Somente leitura: não altera nenhum dado. Classifica cada imóvel em um de
três estados possíveis quanto ao seu documento principal (mesmo tipo e
número normalizado da matrícula do imóvel, ignorando cartório):

- divergente: existe exatamente um candidato, mas em cartório diferente;
- ausente: nenhum documento candidato foi encontrado;
- ambíguo: existe mais de um documento candidato.
"""

from django.core.management.base import BaseCommand

from dominial.models import Documento, Imovel


class Command(BaseCommand):
    help = (
        'Audita, sem alterar dados, divergências entre o cartório do imóvel e '
        'o cartório do seu documento principal (#210).'
    )

    def handle(self, *args, **options):
        divergentes = []
        ausentes = []
        ambiguos = []

        imoveis = Imovel.objects.select_related('cartorio').order_by('pk')
        for imovel in imoveis:
            candidatos = list(
                Documento.objects.filter(
                    imovel=imovel,
                    tipo__tipo=imovel.tipo_documento_principal,
                    numero_normalizado=imovel.matricula_normalizada,
                ).select_related('cartorio')
            )

            if len(candidatos) > 1:
                ambiguos.append((imovel, candidatos))
            elif len(candidatos) == 0:
                ausentes.append(imovel)
            elif candidatos[0].cartorio_id != imovel.cartorio_id:
                divergentes.append((imovel, candidatos[0]))

        self.stdout.write('=== Divergentes (imóvel e documento em cartórios diferentes) ===')
        for imovel, documento in divergentes:
            self.stdout.write(
                f'  Imóvel {imovel.id} ({imovel.get_sigla_formatada()}): '
                f'imóvel no cartório "{imovel.cartorio.nome}" (ID {imovel.cartorio_id}), '
                f'documento {documento.id} no cartório "{documento.cartorio.nome}" '
                f'(ID {documento.cartorio_id}).'
            )

        self.stdout.write('')
        self.stdout.write('=== Ausentes (nenhum documento principal candidato) ===')
        for imovel in ausentes:
            self.stdout.write(
                f'  Imóvel {imovel.id} ({imovel.get_sigla_formatada()}) no cartório '
                f'"{imovel.cartorio.nome}": nenhum documento correspondente encontrado.'
            )

        self.stdout.write('')
        self.stdout.write('=== Ambíguos (mais de um documento candidato) ===')
        for imovel, candidatos in ambiguos:
            ids = ', '.join(str(doc.id) for doc in candidatos)
            self.stdout.write(
                f'  Imóvel {imovel.id} ({imovel.get_sigla_formatada()}): '
                f'{len(candidatos)} documentos candidatos (IDs: {ids}).'
            )

        self.stdout.write('')
        self.stdout.write(
            f'Total: {len(divergentes)} divergente(s), {len(ausentes)} ausente(s), '
            f'{len(ambiguos)} ambíguo(s).'
        )
