from django.core.management.base import BaseCommand
from dominial.models import DocumentoTipo, LancamentoTipo

class Command(BaseCommand):
    help = 'Cria os tipos de documento e lançamento padrão'

    def handle(self, *args, **options):
        # Criar tipos de documento
        tipos_documento = [
            ('transmissao', 'Transmissão'),
            ('matricula', 'Matrícula')
        ]
        
        for codigo, nome in tipos_documento:
            DocumentoTipo.objects.get_or_create(
                tipo=codigo,
                defaults={'tipo': codigo}
            )
            self.stdout.write(self.style.SUCCESS(f'Tipo de documento "{nome}" criado com sucesso'))

        # Criar tipos de lançamento
        tipos_lancamento = [
            ('registro', 'Registro'),
            ('averbacao', 'Averbação')
        ]
        
        for codigo, nome in tipos_lancamento:
            LancamentoTipo.objects.get_or_create(
                tipo=codigo,
                defaults={'tipo': codigo}
            )
            self.stdout.write(self.style.SUCCESS(f'Tipo de lançamento "{nome}" criado com sucesso')) 