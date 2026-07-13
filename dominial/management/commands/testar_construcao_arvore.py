from django.core.management.base import BaseCommand
from dominial.models import Documento, Lancamento, Imovel
from dominial.services.hierarquia_arvore_service import HierarquiaArvoreService
import json


class Command(BaseCommand):
    help = 'Testa a construção da árvore da cadeia dominial para identificar problemas'

    def add_arguments(self, parser):
        parser.add_argument(
            '--imovel',
            type=str,
            help='Matrícula do imóvel para testar'
        )
        parser.add_argument(
            '--debug',
            action='store_true',
            help='Mostrar informações detalhadas de debug'
        )

    def handle(self, *args, **options):
        imovel_matricula = options.get('imovel', 'M19905')
        debug = options.get('debug', False)
        
        self.stdout.write("🔍 TESTANDO CONSTRUÇÃO DA ÁRVORE DA CADEIA DOMINIAL")
        self.stdout.write("=" * 70)
        
        # Buscar o imóvel
        try:
            imovel = Imovel.objects.get(matricula=imovel_matricula)
            self.stdout.write(f"📄 Imóvel encontrado: {imovel.matricula} - {imovel.nome}")
        except Imovel.DoesNotExist:
            self.stdout.write(f"❌ Imóvel não encontrado: {imovel_matricula}")
            return
        
        # Construir a árvore
        self.stdout.write(f"\n🔧 Construindo árvore para imóvel {imovel.matricula}...")
        
        try:
            arvore = HierarquiaArvoreService.construir_arvore_cadeia_dominial(imovel)
            self.stdout.write("✅ Árvore construída com sucesso!")
        except Exception as e:
            self.stdout.write(f"❌ Erro ao construir árvore: {str(e)}")
            import traceback
            traceback.print_exc()
            return
        
        # Analisar documentos
        self.stdout.write(f"\n📊 ANÁLISE DOS DOCUMENTOS")
        self.stdout.write("-" * 50)
        self.stdout.write(f"Total de documentos: {len(arvore['documentos'])}")
        
        for i, doc in enumerate(arvore['documentos'], 1):
            self.stdout.write(f"\n   Documento {i}:")
            self.stdout.write(f"      Número: {doc['numero']}")
            self.stdout.write(f"      Tipo: {doc['tipo_display']}")
            self.stdout.write(f"      Imóvel: {doc.get('imovel_matricula', 'N/A')}")
            self.stdout.write(f"      Nível: {doc['nivel']}")
            self.stdout.write(f"      Importado: {doc['is_importado']}")
            self.stdout.write(f"      Compartilhado: {doc['is_compartilhado']}")
        
        # Analisar conexões
        self.stdout.write(f"\n🔗 ANÁLISE DAS CONEXÕES")
        self.stdout.write("-" * 50)
        self.stdout.write(f"Total de conexões: {len(arvore['conexoes'])}")
        
        # Agrupar conexões por tipo
        conexoes_por_tipo = {}
        for con in arvore['conexoes']:
            tipo = con['tipo']
            if tipo not in conexoes_por_tipo:
                conexoes_por_tipo[tipo] = []
            conexoes_por_tipo[tipo].append(con)
        
        for tipo, conexoes in conexoes_por_tipo.items():
            self.stdout.write(f"\n   Tipo: {tipo} ({len(conexoes)} conexões)")
            for con in conexoes:
                self.stdout.write(
                    f"      {con['from_numero']} (ID {con['from']}) → "
                    f"{con['to_numero']} (ID {con['to']})"
                )
        
        # Verificar conexões problemáticas específicas
        self.stdout.write(f"\n⚠️ VERIFICANDO CONEXÕES PROBLEMÁTICAS")
        self.stdout.write("-" * 50)
        
        # Buscar conexões que envolvem M9712, M9716, M19905
        matriculas_problematicas = ['M9712', 'M9716', 'M19905']
        
        for matricula in matriculas_problematicas:
            conexoes_from = [c for c in arvore['conexoes'] if c['from_numero'] == matricula]
            conexoes_to = [c for c in arvore['conexoes'] if c['to_numero'] == matricula]
            
            self.stdout.write(f"\n   Matrícula {matricula}:")
            self.stdout.write(f"      Conexões de saída (origem): {len(conexoes_from)}")
            for con in conexoes_from:
                self.stdout.write(f"         {con['from_numero']} → {con['to_numero']} ({con['tipo']})")
            
            self.stdout.write(f"      Conexões de entrada (destino): {len(conexoes_to)}")
            for con in conexoes_to:
                self.stdout.write(f"         {con['from_numero']} → {con['to_numero']} ({con['tipo']})")
        
        # Verificar se há conexão incorreta M9712 → M19905
        conexao_incorreta = [
            c for c in arvore['conexoes']
            if c['from_numero'] == 'M9712' and c['to_numero'] == 'M19905'
        ]
        if conexao_incorreta:
            self.stdout.write(f"\n❌ PROBLEMA ENCONTRADO!")
            self.stdout.write(f"   Conexão incorreta: M9712 → M19905")
            self.stdout.write(f"   Tipo: {conexao_incorreta[0]['tipo']}")
            self.stdout.write(f"   Esta conexão não deveria existir!")
        else:
            self.stdout.write(f"\n✅ Nenhuma conexão incorreta encontrada")
        
        # Mostrar estrutura esperada vs encontrada
        self.stdout.write(f"\n📋 ESTRUTURA DA CADEIA DOMINIAL")
        self.stdout.write("-" * 50)
        
        # Estrutura esperada
        self.stdout.write(f"   Estrutura esperada:")
        self.stdout.write(f"      M9712 → M9716 → M19905")
        
        # Estrutura encontrada
        self.stdout.write(f"   Estrutura encontrada:")
        for con in arvore['conexoes']:
            if con['from_numero'] in matriculas_problematicas or con['to_numero'] in matriculas_problematicas:
                self.stdout.write(f"      {con['from_numero']} → {con['to_numero']} ({con['tipo']})")
        
        if debug:
            self.stdout.write(f"\n🔍 DADOS COMPLETOS DA ÁRVORE (DEBUG)")
            self.stdout.write("-" * 50)
            self.stdout.write(json.dumps(arvore, indent=2, default=str))
