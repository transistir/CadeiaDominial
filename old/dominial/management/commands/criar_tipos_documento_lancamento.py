from django.core.management.base import BaseCommand
from dominial.models import DocumentoTipo, LancamentoTipo

class Command(BaseCommand):
    help = 'Cria os tipos de documento e lançamento com as regras corretas'

    def handle(self, *args, **kwargs):
        # Criar tipos de documento
        tipos_documento = [
            ('transcricao', 'Transcrição'),
            ('matricula', 'Matrícula')
        ]

        for codigo, nome in tipos_documento:
            DocumentoTipo.objects.get_or_create(
                tipo=codigo,
                defaults={'tipo': codigo}
            )
            self.stdout.write(f'Tipo de documento "{nome}" criado/atualizado')

        # Criar tipos de lançamento (apenas os corretos)
        tipos_lancamento = [
            {
                'tipo': 'averbacao',
                'requer_transmissao': True,
                'requer_detalhes': False,
                'requer_titulo': False,
                'requer_cartorio_origem': False,
                'requer_livro_origem': False,
                'requer_folha_origem': False,
                'requer_data_origem': False,
                'requer_forma': True,
                'requer_descricao': True,
                'requer_observacao': True
            },
            {
                'tipo': 'registro',
                'requer_transmissao': True,
                'requer_detalhes': False,
                'requer_titulo': True,
                'requer_cartorio_origem': True,
                'requer_livro_origem': True,
                'requer_folha_origem': True,
                'requer_data_origem': True,
                'requer_forma': True,
                'requer_descricao': False,
                'requer_observacao': True
            },
            {
                'tipo': 'inicio_matricula',
                'requer_transmissao': False,
                'requer_detalhes': False,
                'requer_titulo': False,
                'requer_cartorio_origem': False,
                'requer_livro_origem': False,
                'requer_folha_origem': False,
                'requer_data_origem': False,
                'requer_forma': True,
                'requer_descricao': True,
                'requer_observacao': True
            }
        ]

        for tipo_data in tipos_lancamento:
            tipo, created = LancamentoTipo.objects.get_or_create(
                tipo=tipo_data['tipo'],
                defaults=tipo_data
            )
            
            if created:
                self.stdout.write(
                    self.style.SUCCESS(f'Tipo de lançamento "{tipo.get_tipo_display()}" criado com sucesso!')
                )
            else:
                self.stdout.write(
                    self.style.WARNING(f'Tipo de lançamento "{tipo.get_tipo_display()}" já existe.')
                )

        self.stdout.write(self.style.SUCCESS('Tipos de documento e lançamento criados com sucesso!')) 