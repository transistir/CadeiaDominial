from django.core.management.base import BaseCommand
from dominial.models import LancamentoTipo

class Command(BaseCommand):
    help = 'Cria os tipos de lançamento necessários para o sistema'

    def handle(self, *args, **options):
        tipos_lancamento = [
            {
                'tipo': 'averbacao',
                'requer_forma': True,
                'requer_descricao': True,
                'requer_observacao': True,
                'requer_titulo': False,
                'requer_cartorio_origem': False,
                'requer_livro_origem': False,
                'requer_folha_origem': False,
                'requer_data_origem': False,
            },
            {
                'tipo': 'registro',
                'requer_forma': True,
                'requer_titulo': True,
                'requer_cartorio_origem': True,
                'requer_livro_origem': True,
                'requer_folha_origem': True,
                'requer_data_origem': True,
                'requer_observacao': True,
                'requer_descricao': False,
            },
            {
                'tipo': 'inicio_matricula',
                'requer_forma': True,
                'requer_descricao': True,
                'requer_observacao': True,
                'requer_titulo': False,
                'requer_cartorio_origem': False,
                'requer_livro_origem': False,
                'requer_folha_origem': False,
                'requer_data_origem': False,
            },
        ]

        # Primeiro, excluir todos os tipos existentes
        LancamentoTipo.objects.all().delete()
        self.stdout.write(
            self.style.WARNING('Todos os tipos de lançamento existentes foram removidos.')
        )

        # Criar apenas os tipos necessários
        for tipo_data in tipos_lancamento:
            tipo = LancamentoTipo.objects.create(**tipo_data)
            self.stdout.write(
                self.style.SUCCESS(f'Tipo de lançamento "{tipo.get_tipo_display()}" criado com sucesso!')
            )

        self.stdout.write(
            self.style.SUCCESS('Tipos de lançamento configurados: Registro, Averbação e Início de Matrícula')
        ) 