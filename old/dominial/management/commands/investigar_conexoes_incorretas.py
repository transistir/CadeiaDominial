from django.core.management.base import BaseCommand
from dominial.models import Documento, Lancamento
from django.db.models import Q
import re


class Command(BaseCommand):
    help = 'Investiga conexões incorretas na cadeia dominial'

    def add_arguments(self, parser):
        parser.add_argument(
            '--matriculas',
            nargs='+',
            type=str,
            help='Matrículas específicas para investigar'
        )
        parser.add_argument(
            '--corrigir',
            action='store_true',
            help='Corrigir automaticamente as conexões incorretas'
        )

    def handle(self, *args, **options):
        matriculas = options.get('matriculas', ['M9716', 'M9712', 'M19905'])
        corrigir = options.get('corrigir', False)
        
        self.stdout.write("🔍 INVESTIGANDO CONEXÕES INCORRETAS NA CADEIA DOMINIAL")
        self.stdout.write("=" * 70)
        
        # Analisar cada matrícula
        for matricula in matriculas:
            self.analisar_matricula(matricula)
        
        # Buscar conexões problemáticas
        self.buscar_conexoes_problematicas()
        
        if corrigir:
            self.corrigir_conexoes_incorretas()

    def analisar_matricula(self, matricula):
        """Analisa uma matrícula específica"""
        self.stdout.write(f"\n📄 ANALISANDO MATRÍCULA: {matricula}")
        self.stdout.write("-" * 50)
        
        documentos = Documento.objects.filter(numero=matricula).select_related(
            'cartorio', 'imovel', 'tipo'
        ).prefetch_related('lancamentos')
        
        if not documentos.exists():
            self.stdout.write(f"❌ Nenhum documento encontrado: {matricula}")
            return
        
        for doc in documentos:
            self.stdout.write(f"   Documento ID: {doc.id}")
            self.stdout.write(f"   Tipo: {doc.tipo.get_tipo_display()}")
            self.stdout.write(f"   Imóvel: {doc.imovel.matricula}")
            self.stdout.write(f"   Cartório: {doc.cartorio.nome}")
            self.stdout.write(f"   Origem do documento: '{doc.origem}'")
            
            # Verificar lançamentos
            lancamentos = doc.lancamentos.all()
            self.stdout.write(f"   Total de lançamentos: {lancamentos.count()}")
            
            for i, lanc in enumerate(lancamentos, 1):
                self.stdout.write(f"     Lançamento {i}:")
                self.stdout.write(f"       ID: {lanc.id}")
                self.stdout.write(f"       Tipo: {lanc.tipo.get_tipo_display()}")
                self.stdout.write(f"       Número: {lanc.numero_lancamento}")
                self.stdout.write(f"       Origem: '{lanc.origem}'")
                self.stdout.write(f"       Data: {lanc.data}")

    def buscar_conexoes_problematicas(self):
        """Busca conexões problemáticas entre as matrículas"""
        self.stdout.write(f"\n🔍 BUSCANDO CONEXÕES PROBLEMÁTICAS")
        self.stdout.write("=" * 50)
        
        # Buscar lançamentos que referenciam M9712
        lancamentos_m9712 = Lancamento.objects.filter(
            origem__icontains='M9712'
        ).select_related('documento', 'documento__imovel')
        
        self.stdout.write(f"Lançamentos que referenciam M9712: {lancamentos_m9712.count()}")
        
        for lanc in lancamentos_m9712:
            self.stdout.write(f"   Lançamento ID: {lanc.id}")
            self.stdout.write(f"   Documento: {lanc.documento.numero}")
            self.stdout.write(f"   Imóvel: {lanc.documento.imovel.matricula}")
            self.stdout.write(f"   Origem: '{lanc.origem}'")
            self.stdout.write(f"   Tipo: {lanc.tipo.get_tipo_display()}")
            self.stdout.write()
        
        # Buscar lançamentos que referenciam M9716
        lancamentos_m9716 = Lancamento.objects.filter(
            origem__icontains='M9716'
        ).select_related('documento', 'documento__imovel')
        
        self.stdout.write(f"Lançamentos que referenciam M9716: {lancamentos_m9716.count()}")
        
        for lanc in lancamentos_m9716:
            self.stdout.write(f"   Lançamento ID: {lanc.id}")
            self.stdout.write(f"   Documento: {lanc.documento.numero}")
            self.stdout.write(f"   Imóvel: {lanc.documento.imovel.matricula}")
            self.stdout.write(f"   Origem: '{lanc.origem}'")
            self.stdout.write(f"   Tipo: {lanc.tipo.get_tipo_display()}")
            self.stdout.write()
        
        # Buscar lançamentos que referenciam M19905
        lancamentos_m19905 = Lancamento.objects.filter(
            origem__icontains='M19905'
        ).select_related('documento', 'documento__imovel')
        
        self.stdout.write(f"Lançamentos que referenciam M19905: {lancamentos_m19905.count()}")
        
        for lanc in lancamentos_m19905:
            self.stdout.write(f"   Lançamento ID: {lanc.id}")
            self.stdout.write(f"   Documento: {lanc.documento.numero}")
            self.stdout.write(f"   Imóvel: {lanc.documento.imovel.matricula}")
            self.stdout.write(f"   Origem: '{lanc.origem}'")
            self.stdout.write(f"   Tipo: {lanc.tipo.get_tipo_display()}")
            self.stdout.write()

    def corrigir_conexoes_incorretas(self):
        """Corrige conexões incorretas identificadas"""
        self.stdout.write(f"\n🔧 CORRIGINDO CONEXÕES INCORRETAS")
        self.stdout.write("=" * 50)
        
        # Baseado na análise, o problema é que M9712 está sendo conectada incorretamente à M19905
        # quando deveria apenas ser origem da M9716
        
        # Buscar lançamentos que têm M9712 como origem mas não deveriam
        lancamentos_problematicos = Lancamento.objects.filter(
            origem__icontains='M9712'
        ).exclude(
            documento__numero='M9716'  # Excluir a conexão correta M9712 -> M9716
        )
        
        self.stdout.write(f"Lançamentos com conexão incorreta para M9712: {lancamentos_problematicos.count()}")
        
        for lanc in lancamentos_problematicos:
            self.stdout.write(f"   Corrigindo lançamento ID: {lanc.id}")
            self.stdout.write(f"   Documento: {lanc.documento.numero}")
            self.stdout.write(f"   Origem atual: '{lanc.origem}'")
            
            # Remover M9712 da origem se não for a conexão correta
            if lanc.origem:
                origens = [o.strip() for o in lanc.origem.split(';') if o.strip()]
                origens_corrigidas = [o for o in origens if o != 'M9712']
                
                if len(origens_corrigidas) != len(origens):
                    nova_origem = '; '.join(origens_corrigidas) if origens_corrigidas else ''
                    lanc.origem = nova_origem
                    lanc.save()
                    self.stdout.write(f"   Origem corrigida: '{nova_origem}'")
                    self.stdout.write(f"   ✅ Corrigido!")
                else:
                    self.stdout.write(f"   ⚠️ Não foi necessário corrigir")
            self.stdout.write()
