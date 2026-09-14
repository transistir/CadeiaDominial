"""Audita divergências de cartório entre imóveis e documentos principais."""

import csv

from django.core.management.base import BaseCommand
from django.db.models import F

from dominial.models import Documento


CAMPOS = (
    'imovel_id',
    'documento_id',
    'tipo',
    'numero_normalizado',
    'cartorio_imovel_id',
    'cartorio_documento_id',
)
PREFIXOS_FORMULA = ('=', '+', '-', '@', '\t', '\r')


def neutralizar_formula(valor):
    if isinstance(valor, str) and valor.startswith(PREFIXOS_FORMULA):
        return f"'{valor}"
    return valor


class Command(BaseCommand):
    help = (
        'Lista, sem alterar dados, documentos principais cujo cartório diverge '
        'do cartório do imóvel.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--csv',
            action='store_true',
            dest='usar_csv',
            help='Emite CSV no stdout em vez da tabela de texto.',
        )

    def handle(self, *args, **options):
        documentos = Documento.objects.filter(
            tipo__tipo=F('imovel__tipo_documento_principal'),
            numero_normalizado=F('imovel__matricula_normalizada'),
        ).exclude(
            cartorio_id=F('imovel__cartorio_id'),
        ).select_related('tipo', 'imovel').order_by('imovel_id', 'pk')

        linhas = [self._linha(documento) for documento in documentos]
        if options['usar_csv']:
            self._escrever_csv(linhas)
        else:
            self._escrever_tabela(linhas)

    @staticmethod
    def _linha(documento):
        return {
            'imovel_id': documento.imovel_id,
            'documento_id': documento.pk,
            'tipo': documento.tipo.tipo,
            'numero_normalizado': documento.numero_normalizado,
            'cartorio_imovel_id': documento.imovel.cartorio_id,
            'cartorio_documento_id': documento.cartorio_id,
        }

    def _escrever_csv(self, linhas):
        escritor = csv.DictWriter(self.stdout, fieldnames=CAMPOS)
        escritor.writeheader()
        escritor.writerows(
            {
                campo: neutralizar_formula(valor)
                for campo, valor in linha.items()
            }
            for linha in linhas
        )

    def _escrever_tabela(self, linhas):
        self.stdout.write(
            'IMOVEL_ID | DOCUMENTO_ID | TIPO | NUMERO_NORMALIZADO | '
            'CARTORIO_IMOVEL_ID | CARTORIO_DOCUMENTO_ID'
        )
        for linha in linhas:
            self.stdout.write(
                f"{linha['imovel_id']} | {linha['documento_id']} | "
                f"{linha['tipo']} | {linha['numero_normalizado']} | "
                f"{linha['cartorio_imovel_id']} | "
                f"{linha['cartorio_documento_id']}"
            )
        self.stdout.write(f'Total de divergências: {len(linhas)}')
