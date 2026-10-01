from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from dominial.models import Imovel, UserImovel, UserTI


class Command(BaseCommand):
    help = (
        'Migra atribuições legadas por imóvel para atribuições por TI. '
        'Executa em dry-run por padrão.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--aplicar',
            action='store_true',
            help='Aplica a migração. Sem esta opção, apenas exibe a prévia.',
        )
        parser.add_argument(
            '--como-usuario',
            metavar='USERNAME',
            help='Usuário a registrar no campo atribuido_por.',
        )

    def handle(self, *args, **options):
        atribuido_por = self._obter_atribuidor(options.get('como_usuario'))
        linhas = list(
            UserImovel.objects.select_related(
                'user', 'imovel__terra_indigena_id'
            ).order_by(
                'user__username',
                'imovel__terra_indigena_id__nome',
                'imovel__terra_indigena_id_id',
                'id',
            )
        )
        relatorio = self._montar_relatorio(linhas)

        self._emitir_relatorio(relatorio, aplicar=options['aplicar'])

        if not options['aplicar']:
            return

        with transaction.atomic():
            UserTI.objects.bulk_create(
                [
                    UserTI(
                        user_id=item['user_id'],
                        tis_id=item['tis_id'],
                        atribuido_por=atribuido_por,
                    )
                    for item in relatorio['pares_a_criar']
                ],
                ignore_conflicts=True,
            )
            UserImovel.objects.filter(pk__in=relatorio['userimovel_ids']).delete()

        self.stdout.write(self.style.SUCCESS('Migração aplicada.'))

    @staticmethod
    def _obter_atribuidor(username):
        if not username:
            return None

        User = get_user_model()
        try:
            return User.objects.get(username=username)
        except User.DoesNotExist as exc:
            raise CommandError(f'Usuário "{username}" não encontrado.') from exc

    @staticmethod
    def _montar_relatorio(linhas):
        pares = {}
        for linha in linhas:
            chave = (linha.user_id, linha.imovel.terra_indigena_id_id)
            pares.setdefault(
                chave,
                {
                    'user_id': linha.user_id,
                    'user': linha.user,
                    'username': linha.user.username,
                    'tis_id': linha.imovel.terra_indigena_id_id,
                    'tis_nome': linha.imovel.terra_indigena_id.nome,
                },
            )

        pares_existentes = set(
            UserTI.objects.filter(
                user_id__in={user_id for user_id, _tis_id in pares},
                tis_id__in={tis_id for _user_id, tis_id in pares},
            ).values_list('user_id', 'tis_id')
        )

        itens = []
        for chave, item in pares.items():
            total_ti = Imovel.objects.filter(
                terra_indigena_id_id=item['tis_id']
            ).count()
            visiveis_hoje = Imovel.objects.for_user(item['user']).filter(
                terra_indigena_id_id=item['tis_id']
            ).count()
            itens.append(
                {
                    **item,
                    'visiveis_hoje': visiveis_hoje,
                    'total_ti': total_ti,
                    'delta': total_ti - visiveis_hoje,
                }
            )

        return {
            'itens': itens,
            'pares_a_criar': [
                item for chave, item in pares.items() if chave not in pares_existentes
            ],
            'userimovel_ids': [linha.pk for linha in linhas],
            'delta_total': sum(item['delta'] for item in itens),
        }

    def _emitir_relatorio(self, relatorio, *, aplicar):
        modo = 'APLICAÇÃO' if aplicar else 'DRY-RUN — nenhuma alteração será feita'
        self.stdout.write(f'MODO: {modo}')
        self.stdout.write(
            'usuario | TI | imóveis que vê hoje | passará a ver (hoje) | delta'
        )
        self.stdout.write(
            '--------|----|---------------------|----------------------|------'
        )
        for item in relatorio['itens']:
            self.stdout.write(
                f"{item['username']} | {item['tis_nome']} | "
                f"{item['visiveis_hoje']} de {item['total_ti']} | "
                f"{item['total_ti']} | {item['delta']:+d}"
            )

        self.stdout.write(
            f"TOTAL: {len(relatorio['pares_a_criar'])} UserTI a criar, "
            f"{len(relatorio['userimovel_ids'])} UserImovel a remover, "
            f"{relatorio['delta_total']} imóveis a mais visíveis hoje."
        )
        self.stdout.write(
            self.style.WARNING(
                'ATENÇÃO: após a conversão, estes usuários também verão TODO '
                'imóvel FUTURO destas TIs.'
            )
        )
