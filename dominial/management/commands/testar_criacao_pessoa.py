from django.core.management.base import BaseCommand
from dominial.models import Pessoas

class Command(BaseCommand):
    help = 'Testa a criação de pessoas sem CPF'

    def handle(self, *args, **options):
        self.stdout.write('🧪 Testando criação de pessoas...')
        
        # Teste 1: Criar pessoa sem CPF
        try:
            pessoa1, created1 = Pessoas.objects.get_or_create(
                nome='João Silva',
                defaults={
                    'nome': 'João Silva',
                    'cpf': None,
                    'rg': '',
                    'email': '',
                    'telefone': ''
                }
            )
            
            if created1:
                self.stdout.write(self.style.SUCCESS(f'✅ Pessoa criada: {pessoa1.nome} (ID: {pessoa1.id})'))
            else:
                self.stdout.write(self.style.WARNING(f'⚠️ Pessoa já existia: {pessoa1.nome} (ID: {pessoa1.id})'))
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'❌ Erro ao criar pessoa: {str(e)}'))
            return
        
        # Teste 2: Tentar criar a mesma pessoa novamente
        try:
            pessoa2, created2 = Pessoas.objects.get_or_create(
                nome='João Silva',
                defaults={
                    'nome': 'João Silva',
                    'cpf': None,
                    'rg': '',
                    'email': '',
                    'telefone': ''
                }
            )
            
            if created2:
                self.stdout.write(self.style.ERROR(f'❌ Erro: Pessoa foi criada novamente'))
            else:
                self.stdout.write(self.style.SUCCESS(f'✅ Pessoa não foi duplicada: {pessoa2.nome} (ID: {pessoa2.id})'))
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'❌ Erro no teste de duplicação: {str(e)}'))
        
        # Teste 3: Criar pessoa com nome diferente
        try:
            pessoa3, created3 = Pessoas.objects.get_or_create(
                nome='Maria Santos',
                defaults={
                    'nome': 'Maria Santos',
                    'cpf': None,
                    'rg': '',
                    'email': '',
                    'telefone': ''
                }
            )
            
            if created3:
                self.stdout.write(self.style.SUCCESS(f'✅ Nova pessoa criada: {pessoa3.nome} (ID: {pessoa3.id})'))
            else:
                self.stdout.write(self.style.WARNING(f'⚠️ Pessoa já existia: {pessoa3.nome} (ID: {pessoa3.id})'))
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'❌ Erro ao criar segunda pessoa: {str(e)}'))
        
        # Verificar total de pessoas
        total_pessoas = Pessoas.objects.count()
        self.stdout.write(self.style.SUCCESS(f'📊 Total de pessoas no banco: {total_pessoas}'))
        
        # Verificar pessoas com CPF NULL
        pessoas_sem_cpf = Pessoas.objects.filter(cpf__isnull=True).count()
        self.stdout.write(self.style.SUCCESS(f'📊 Pessoas sem CPF (NULL): {pessoas_sem_cpf}'))
        
        self.stdout.write(self.style.SUCCESS('🎉 Teste concluído!')) 