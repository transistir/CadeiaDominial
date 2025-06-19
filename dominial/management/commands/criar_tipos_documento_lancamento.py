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

        # Criar tipos de lançamento
        tipos_lancamento = [
            ('transacao', 'Transação', True, False),
            ('averbacao', 'Averbação', False, True),
            ('matricula_cadeia', 'Matrícula de Cadeia', False, False),
            ('registro', 'Registro', True, False)
        ]

        for codigo, nome, requer_transmissao, requer_detalhes in tipos_lancamento:
            LancamentoTipo.objects.get_or_create(
                tipo=codigo,
                defaults={
                    'tipo': codigo,
                    'requer_transmissao': requer_transmissao,
                    'requer_detalhes': requer_detalhes
                }
            )
            self.stdout.write(f'Tipo de lançamento "{nome}" criado/atualizado')

        self.stdout.write(self.style.SUCCESS('Tipos de documento e lançamento criados com sucesso!')) 