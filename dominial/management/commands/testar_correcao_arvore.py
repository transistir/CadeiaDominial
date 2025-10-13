"""
Comando para testar se a correção da árvore funcionou
"""

from django.core.management.base import BaseCommand
from dominial.models import Documento, Lancamento, Imovel
from dominial.services.hierarquia_arvore_service import HierarquiaArvoreService
import logging

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Testa se a correção da árvore funcionou'

    def add_arguments(self, parser):
        parser.add_argument(
            '--imovel',
            type=str,
            help='Matrícula do imóvel para testar'
        )

    def handle(self, *args, **options):
        imovel_matricula = options.get('imovel')
        
        self.stdout.write("🔍 TESTANDO CORREÇÃO DA ÁRVORE")
        self.stdout.write("=" * 50)
        
        # Testar extração de origens
        self.stdout.write("\n📋 TESTANDO EXTRAÇÃO DE ORIGENS")
        self.stdout.write("-" * 30)
        
        textos_teste = [
            "T2822",
            "T 2822",
            "T-2822",
            "T.2822",
            "transcrição 2822",
            "matrícula 2822",
            "2822",
            "M9712; T2822",
            "T2822; M9716"
        ]
        
        for texto in textos_teste:
            origens = HierarquiaArvoreService._extrair_origens_robusto(texto)
            self.stdout.write(f"   '{texto}' -> {origens}")
        
        # Buscar alguns imóveis para testar
        if imovel_matricula:
            imoveis_teste = [imovel_matricula]
        else:
            # Buscar alguns imóveis para testar
            imoveis = Imovel.objects.all()[:3]
            imoveis_teste = [imovel.matricula for imovel in imoveis]
        
        for matricula in imoveis_teste:
            self.stdout.write(f"\n🌳 TESTANDO ÁRVORE PARA IMÓVEL {matricula}")
            self.stdout.write("-" * 40)
            
            try:
                imovel = Imovel.objects.get(matricula=matricula)
                
                # Construir árvore
                arvore = HierarquiaArvoreService.construir_arvore_cadeia_dominial(imovel)
                
                self.stdout.write(f"✅ Árvore construída com sucesso!")
                self.stdout.write(f"   Documentos: {len(arvore['documentos'])}")
                self.stdout.write(f"   Conexões: {len(arvore['conexoes'])}")
                
                # Mostrar documentos
                self.stdout.write(f"\n📄 DOCUMENTOS:")
                for doc in arvore['documentos']:
                    self.stdout.write(f"   - {doc['numero']} ({doc['tipo_display']}) - Nível {doc['nivel']}")
                
                # Mostrar conexões
                self.stdout.write(f"\n🔗 CONEXÕES:")
                for conexao in arvore['conexoes']:
                    self.stdout.write(f"   - {conexao['from']} -> {conexao['to']} ({conexao['tipo']})")
                
                # Verificar se há lançamentos com origens
                self.stdout.write(f"\n📝 LANÇAMENTOS COM ORIGENS:")
                for doc in arvore['documentos']:
                    documento_obj = Documento.objects.get(id=doc['id'])
                    lancamentos = documento_obj.lancamentos.filter(origem__isnull=False).exclude(origem='')
                    if lancamentos.exists():
                        self.stdout.write(f"   Documento {doc['numero']}:")
                        for lanc in lancamentos:
                            origens_extraidas = HierarquiaArvoreService._extrair_origens_robusto(lanc.origem)
                            self.stdout.write(f"     - Lançamento {lanc.id}: '{lanc.origem}' -> {origens_extraidas}")
                
            except Imovel.DoesNotExist:
                self.stdout.write(f"❌ Imóvel {matricula} não encontrado")
            except Exception as e:
                self.stdout.write(f"❌ Erro ao testar imóvel {matricula}: {e}")
                import traceback
                traceback.print_exc()
        
        self.stdout.write("\n✅ Teste concluído!")
        self.stdout.write("\n📝 PRÓXIMOS PASSOS:")
        self.stdout.write("   1. Verificar se a árvore está mostrando mais conexões")
        self.stdout.write("   2. Verificar se T1004 -> T2822 está conectado (se existirem)")
        self.stdout.write("   3. Testar no frontend a visualização da árvore")
