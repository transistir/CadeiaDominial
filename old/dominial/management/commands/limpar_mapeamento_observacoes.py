from django.core.management.base import BaseCommand
from dominial.models import Lancamento
import re


class Command(BaseCommand):
    help = 'Limpa o mapeamento de origens que foi salvo incorretamente no campo observações'

    def handle(self, *args, **options):
        # Buscar lançamentos que têm mapeamento nas observações
        lancamentos_com_mapeamento = Lancamento.objects.filter(
            observacoes__contains='[MAPEAMENTO_ORIGENS:'
        )
        
        count = 0
        for lancamento in lancamentos_com_mapeamento:
            # Remover o mapeamento das observações
            observacoes_limpas = re.sub(r'\s*\[MAPEAMENTO_ORIGENS:.*?\]\s*', '', lancamento.observacoes)
            
            # Se as observações ficaram vazias após a limpeza, definir como None
            if not observacoes_limpas.strip():
                observacoes_limpas = None
            
            lancamento.observacoes = observacoes_limpas
            lancamento.save()
            count += 1
            
            self.stdout.write(
                self.style.SUCCESS(f'Lançamento {lancamento.id} limpo: {observacoes_limpas}')
            )
        
        self.stdout.write(
            self.style.SUCCESS(f'Total de {count} lançamentos limpos com sucesso!')
        ) 