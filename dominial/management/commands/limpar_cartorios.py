from django.core.management.base import BaseCommand
from dominial.models import Cartorios
from django.db import transaction

class Command(BaseCommand):
    help = 'Limpa todos os cartórios do banco de dados'

    def add_arguments(self, parser):
        parser.add_argument(
            '--confirmar',
            action='store_true',
            help='Confirma a exclusão de todos os cartórios',
        )

    def handle(self, *args, **options):
        if not options['confirmar']:
            self.stdout.write(
                self.style.WARNING('ATENÇÃO: Esta operação irá excluir TODOS os cartórios do banco de dados.')
            )
            self.stdout.write(
                self.style.WARNING('Para confirmar, execute o comando com a flag --confirmar')
            )
            self.stdout.write(
                self.style.WARNING('Exemplo: python manage.py limpar_cartorios --confirmar')
            )
            return

        try:
            with transaction.atomic():
                total = Cartorios.objects.count()
                Cartorios.objects.all().delete()
                self.stdout.write(
                    self.style.SUCCESS(f'Todos os cartórios foram excluídos com sucesso! Total: {total}')
                )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Erro ao excluir cartórios: {str(e)}')
            ) 