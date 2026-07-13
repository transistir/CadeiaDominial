from django.core.management.base import BaseCommand
from dominial.models import Documento, Lancamento

class Command(BaseCommand):
    help = 'Limpa documentos e lançamentos de teste de um imóvel específico'

    def add_arguments(self, parser):
        parser.add_argument('imovel_id', type=int, help='ID do imóvel para limpar')

    def handle(self, *args, **options):
        imovel_id = options['imovel_id']
        
        # Primeiro remove os lançamentos
        lancamentos = Lancamento.objects.filter(documento__imovel_id=imovel_id)
        num_lancamentos = lancamentos.count()
        lancamentos.delete()
        
        # Depois remove os documentos
        documentos = Documento.objects.filter(imovel_id=imovel_id)
        num_documentos = documentos.count()
        documentos.delete()
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Limpeza concluída: {num_lancamentos} lançamentos e {num_documentos} documentos removidos do imóvel {imovel_id}'
            )
        ) 