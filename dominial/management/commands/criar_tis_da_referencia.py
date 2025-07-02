from django.core.management.base import BaseCommand
from dominial.models import TerraIndigenaReferencia, TIs

class Command(BaseCommand):
    help = 'Cria TIs automaticamente a partir das terras indígenas de referência existentes'

    def add_arguments(self, parser):
        parser.add_argument(
            '--codigo',
            type=str,
            help='Código específico da terra indígena para criar TI',
        )

    def handle(self, *args, **options):
        codigo_especifico = options['codigo']
        
        if codigo_especifico:
            self.stdout.write(f'Criando TI para código específico: {codigo_especifico}')
            self.criar_ti_especifica(codigo_especifico)
        else:
            self.stdout.write('Criando TIs para todas as terras indígenas de referência...')
            self.criar_todas_tis()
    
    def criar_ti_especifica(self, codigo):
        """Cria TI para um código específico"""
        try:
            terra_referencia = TerraIndigenaReferencia.objects.get(codigo=codigo)
            
            if TIs.objects.filter(codigo=codigo).exists():
                self.stdout.write(self.style.WARNING(f'TI com código {codigo} já existe'))
                return
            
            tis = TIs.objects.create(
                terra_referencia=terra_referencia,
                nome=terra_referencia.nome,
                codigo=terra_referencia.codigo,
                etnia=terra_referencia.etnia or 'Não informada'
            )
            
            self.stdout.write(self.style.SUCCESS(f'TI criada: {tis.nome} ({codigo})'))
            
        except TerraIndigenaReferencia.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'Referência com código {codigo} não encontrada'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Erro ao criar TI: {str(e)}'))
    
    def criar_todas_tis(self):
        """Cria TIs para todas as referências que ainda não têm TI"""
        referencias = TerraIndigenaReferencia.objects.all()
        contador_criadas = 0
        contador_existentes = 0
        
        for referencia in referencias:
            try:
                if TIs.objects.filter(codigo=referencia.codigo).exists():
                    contador_existentes += 1
                    continue
                
                tis = TIs.objects.create(
                    terra_referencia=referencia,
                    nome=referencia.nome,
                    codigo=referencia.codigo,
                    etnia=referencia.etnia or 'Não informada'
                )
                
                contador_criadas += 1
                self.stdout.write(f'TI criada: {tis.nome} ({referencia.codigo})')
                
            except Exception as e:
                self.stdout.write(self.style.WARNING(f'Erro ao criar TI para {referencia.nome}: {str(e)}'))
                continue
        
        self.stdout.write(self.style.SUCCESS(f'Processo concluído!'))
        self.stdout.write(f'TIs criadas: {contador_criadas}')
        self.stdout.write(f'TIs já existentes: {contador_existentes}') 