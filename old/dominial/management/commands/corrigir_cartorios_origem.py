from django.core.management.base import BaseCommand
from django.db import transaction
from dominial.models import Lancamento, Documento


class Command(BaseCommand):
    help = 'Corrige os cartórios de origem dos lançamentos baseado nos cartórios reais dos documentos'

    def handle(self, *args, **options):
        self.stdout.write('🔧 Iniciando correção dos cartórios de origem...')
        
        with transaction.atomic():
            # Buscar todos os lançamentos com origem
            lancamentos = Lancamento.objects.filter(
                origem__isnull=False
            ).exclude(origem='').select_related('documento', 'cartorio_origem')
            
            self.stdout.write(f'📊 Total de lançamentos com origem: {lancamentos.count()}')
            
            corrigidos = 0
            erros = 0
            
            for lancamento in lancamentos:
                try:
                    # Separar múltiplas origens
                    origens = [o.strip() for o in lancamento.origem.split(';')]
                    
                    # Buscar o primeiro documento de origem para determinar o cartório
                    cartorio_correto = None
                    
                    for origem_numero in origens:
                        if origem_numero:
                            documento_origem = Documento.objects.filter(
                                numero=origem_numero
                            ).first()
                            
                            if documento_origem:
                                cartorio_correto = documento_origem.cartorio
                                break
                    
                    if cartorio_correto and cartorio_correto != lancamento.cartorio_origem:
                        self.stdout.write(
                            f'🔄 Corrigindo lançamento {lancamento.id} (Doc: {lancamento.documento.numero}): '
                            f'Cartório origem {lancamento.cartorio_origem} → {cartorio_correto}'
                        )
                        
                        lancamento.cartorio_origem = cartorio_correto
                        lancamento.save()
                        corrigidos += 1
                    elif cartorio_correto:
                        self.stdout.write(
                            f'✅ Lançamento {lancamento.id} (Doc: {lancamento.documento.numero}) já correto: '
                            f'Cartório origem {lancamento.cartorio_origem}'
                        )
                    else:
                        self.stdout.write(
                            f'⚠️ Lançamento {lancamento.id} (Doc: {lancamento.documento.numero}): '
                            f'Origem {lancamento.origem} não encontrada'
                        )
                        erros += 1
                        
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(
                            f'❌ Erro ao processar lançamento {lancamento.id}: {str(e)}'
                        )
                    )
                    erros += 1
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'✅ Correção concluída! {corrigidos} lançamentos corrigidos, {erros} erros'
                )
            ) 