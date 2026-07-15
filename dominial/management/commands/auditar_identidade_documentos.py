"""Audita identidades registrais sem alterar dados."""

import json
from collections import defaultdict

from django.core.management.base import BaseCommand, CommandError

from dominial.models import Documento
from dominial.utils.documento_identidade_utils import normalizar_numero_documento


class Command(BaseCommand):
    help = (
        'Audita documentos sem alterar dados e informa conflitos pela identidade '
        'tipo, número normalizado e cartório.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--json',
            action='store_true',
            dest='usar_json',
            help='Emite um objeto JSON adequado para automação.',
        )
        parser.add_argument(
            '--fail-on-conflict',
            action='store_true',
            help='Encerra com erro quando houver conflito ou registro inválido.',
        )

    def handle(self, *args, **options):
        grupos = defaultdict(list)
        invalidos = []
        sem_cartorio = []
        documentos = Documento.objects.select_related(
            'tipo',
            'cartorio',
            'imovel',
        ).order_by('pk')

        total = 0
        for documento in documentos:
            total += 1
            if not documento.cartorio_id:
                sem_cartorio.append(self._dados_documento(documento))
                continue

            try:
                numero_normalizado = normalizar_numero_documento(
                    documento.numero,
                    documento.tipo.tipo,
                )
            except (TypeError, ValueError) as erro:
                item = self._dados_documento(documento)
                item['erro'] = str(erro)
                invalidos.append(item)
                continue

            chave = (
                documento.tipo.tipo,
                numero_normalizado,
                documento.cartorio_id,
            )
            grupos[chave].append(documento)

        conflitos = []
        for chave, candidatos in sorted(grupos.items(), key=lambda item: item[0]):
            if len(candidatos) < 2:
                continue
            tipo, numero_normalizado, cartorio_id = chave
            conflitos.append({
                'tipo': tipo,
                'numero_normalizado': numero_normalizado,
                'cartorio_id': cartorio_id,
                'documentos': [
                    self._dados_documento(documento)
                    for documento in candidatos
                ],
            })

        relatorio = {
            'somente_leitura': True,
            'total_documentos': total,
            'total_grupos_conflitantes': len(conflitos),
            'total_documentos_conflitantes': sum(
                len(conflito['documentos']) for conflito in conflitos
            ),
            'total_invalidos': len(invalidos),
            'total_sem_cartorio': len(sem_cartorio),
            'conflitos': conflitos,
            'invalidos': invalidos,
            'sem_cartorio': sem_cartorio,
        }

        if options['usar_json']:
            self.stdout.write(json.dumps(relatorio, ensure_ascii=False, sort_keys=True))
        else:
            self._escrever_relatorio(relatorio)

        tem_impedimentos = bool(conflitos or invalidos or sem_cartorio)
        if options['fail_on_conflict'] and tem_impedimentos:
            raise CommandError(
                'A auditoria encontrou impedimentos para aplicar as constraints.'
            )

    @staticmethod
    def _dados_documento(documento):
        return {
            'id': documento.pk,
            'tipo': documento.tipo.tipo,
            'numero': documento.numero,
            'cartorio_id': documento.cartorio_id,
            'imovel_id': documento.imovel_id,
        }

    def _escrever_relatorio(self, relatorio):
        self.stdout.write('AUDITORIA DE IDENTIDADE DOS DOCUMENTOS (SOMENTE LEITURA)')
        self.stdout.write(f"Documentos: {relatorio['total_documentos']}")
        self.stdout.write(
            f"Grupos conflitantes: {relatorio['total_grupos_conflitantes']}"
        )
        self.stdout.write(
            f"Documentos conflitantes: {relatorio['total_documentos_conflitantes']}"
        )
        self.stdout.write(f"Inválidos: {relatorio['total_invalidos']}")
        self.stdout.write(f"Sem cartório: {relatorio['total_sem_cartorio']}")

        for conflito in relatorio['conflitos']:
            ids = ', '.join(str(item['id']) for item in conflito['documentos'])
            self.stdout.write(
                'CONFLITO '
                f"tipo={conflito['tipo']} "
                f"numero={conflito['numero_normalizado']} "
                f"cartorio_id={conflito['cartorio_id']} "
                f"documentos=[{ids}]"
            )

        for invalido in relatorio['invalidos']:
            self.stdout.write(
                f"INVALIDO documento_id={invalido['id']} erro={invalido['erro']}"
            )

        for item in relatorio['sem_cartorio']:
            self.stdout.write(f"SEM_CARTORIO documento_id={item['id']}")
