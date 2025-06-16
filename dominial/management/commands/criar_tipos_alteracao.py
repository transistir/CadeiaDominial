from django.core.management.base import BaseCommand
from dominial.models import AlteracoesTipo

class Command(BaseCommand):
    help = 'Cria os tipos de alteração padrão'

    def handle(self, *args, **kwargs):
        tipos = [
            'registro',
            'averbacao',
            'nao_classificado'
        ]
        
        for tipo in tipos:
            AlteracoesTipo.objects.get_or_create(tipo=tipo)
            self.stdout.write(self.style.SUCCESS(f'Tipo de alteração "{tipo}" criado com sucesso!')) 