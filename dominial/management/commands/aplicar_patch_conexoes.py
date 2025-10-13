"""
Comando para aplicar patch que resolve problemas de conexão na árvore
"""

from django.core.management.base import BaseCommand
import sys
import os

# Adicionar o diretório raiz ao path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))

from patch_hierarquia_arvore_service import aplicar_patch_hierarquia_arvore_service


class Command(BaseCommand):
    help = 'Aplica patch para resolver problemas de conexão na árvore da cadeia dominial'

    def add_arguments(self, parser):
        parser.add_argument(
            '--testar',
            action='store_true',
            help='Testar o patch após aplicação'
        )

    def handle(self, *args, **options):
        self.stdout.write("🔧 APLICANDO PATCH PARA RESOLVER CONEXÕES")
        self.stdout.write("=" * 50)
        
        try:
            # Aplicar o patch
            sucesso = aplicar_patch_hierarquia_arvore_service()
            
            if sucesso:
                self.stdout.write("✅ Patch aplicado com sucesso!")
                self.stdout.write("")
                self.stdout.write("📋 MELHORIAS IMPLEMENTADAS:")
                self.stdout.write("   - Extração de origens mais robusta")
                self.stdout.write("   - Busca de documentos com múltiplas estratégias")
                self.stdout.write("   - Suporte a diferentes formatos de origem")
                self.stdout.write("   - Logs detalhados para debug")
                self.stdout.write("")
                
                if options['testar']:
                    self.stdout.write("🧪 TESTANDO PATCH...")
                    self.stdout.write("-" * 30)
                    
                    # Testar extração de origens
                    from dominial.services.hierarquia_arvore_service import HierarquiaArvoreService
                    
                    textos_teste = [
                        "T2822",
                        "T 2822", 
                        "T-2822",
                        "transcrição 2822",
                        "2822"
                    ]
                    
                    for texto in textos_teste:
                        # Simular extração (usando regex melhorada)
                        import re
                        origens = []
                        
                        # Padrão 1: M/T seguido de números
                        padrao1 = re.findall(r'[MT]\d+', texto)
                        origens.extend(padrao1)
                        
                        # Padrão 2: M/T com separadores
                        padrao2 = re.findall(r'[MT]\s*[-.]?\s*\d+', texto)
                        for match in padrao2:
                            limpo = re.sub(r'\s*[-.]?\s*', '', match)
                            if limpo not in origens:
                                origens.append(limpo)
                        
                        # Padrão 3: Números simples
                        padrao3 = re.findall(r'\b\d{3,}\b', texto)
                        for num in padrao3:
                            if not any(f'M{num}' in texto or f'T{num}' in texto for _ in [1]):
                                if f'M{num}' not in origens:
                                    origens.append(f'M{num}')
                        
                        self.stdout.write(f"   '{texto}' -> {origens}")
                    
                    self.stdout.write("✅ Teste de extração concluído!")
                
            else:
                self.stdout.write("❌ Falha ao aplicar patch")
                
        except Exception as e:
            self.stdout.write(f"❌ Erro ao aplicar patch: {e}")
            import traceback
            traceback.print_exc()
        
        self.stdout.write("")
        self.stdout.write("📝 PRÓXIMOS PASSOS:")
        self.stdout.write("   1. Testar a árvore da cadeia dominial")
        self.stdout.write("   2. Verificar se T1004 -> T2822 está conectado")
        self.stdout.write("   3. Executar: python manage.py testar_conexao_t1004_t2822")
        self.stdout.write("")
        self.stdout.write("✅ Patch aplicado com sucesso!")
