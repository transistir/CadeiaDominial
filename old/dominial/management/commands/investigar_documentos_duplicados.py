from django.core.management.base import BaseCommand
from dominial.models import Documento
from django.db.models import Count


class Command(BaseCommand):
    help = 'Investiga documentos duplicados no banco de dados'

    def add_arguments(self, parser):
        parser.add_argument(
            '--numero',
            type=str,
            help='Número específico do documento para investigar (ex: M794)'
        )
        parser.add_argument(
            '--corrigir',
            action='store_true',
            help='Corrigir automaticamente documentos duplicados (manter o mais antigo)'
        )

    def handle(self, *args, **options):
        numero_especifico = options.get('numero')
        corrigir = options.get('corrigir')
        
        self.stdout.write("🔍 INVESTIGANDO DOCUMENTOS DUPLICADOS")
        self.stdout.write("=" * 50)
        
        if numero_especifico:
            self.investigar_documento_especifico(numero_especifico, corrigir)
        else:
            self.investigar_todos_duplicados(corrigir)
    
    def investigar_documento_especifico(self, numero, corrigir=False):
        """Investiga um documento específico"""
        self.stdout.write(f"\n🔍 VERIFICANDO DOCUMENTO {numero}:")
        self.stdout.write("-" * 30)
        
        docs = Documento.objects.filter(numero=numero).select_related(
            'cartorio', 'imovel', 'tipo'
        ).order_by('id')
        
        if not docs.exists():
            self.stdout.write(f"❌ Nenhum documento {numero} encontrado")
            return
        
        self.stdout.write(f"📄 Encontrados {docs.count()} documentos com número {numero}:")
        
        for i, doc in enumerate(docs, 1):
            self.stdout.write(f"   {i}. ID: {doc.id} | Data: {doc.data} | Tipo: {doc.tipo.tipo}")
            self.stdout.write(f"      Cartório: {doc.cartorio.nome}")
            self.stdout.write(f"      Imóvel: {doc.imovel.matricula} ({doc.imovel.nome})")
            self.stdout.write(f"      Livro: {doc.livro} | Folha: {doc.folha}")
            self.stdout.write("")
        
        # Verificar se são duplicados (mesmo cartório)
        cartorios = docs.values_list('cartorio_id', flat=True).distinct()
        if len(cartorios) == 1:
            self.stdout.write(f"⚠️ Documentos duplicados no mesmo cartório!")
            if corrigir:
                self.corrigir_duplicados(docs)
        else:
            self.stdout.write(f"✅ Documentos em cartórios diferentes (não são duplicados)")
    
    def investigar_todos_duplicados(self, corrigir=False):
        """Investiga todos os documentos duplicados"""
        # Buscar documentos com mesmo número e cartório
        duplicatas = Documento.objects.values('numero', 'cartorio').annotate(
            count=Count('id')
        ).filter(count__gt=1).order_by('-count', 'numero')
        
        if not duplicatas.exists():
            self.stdout.write("✅ Nenhum documento duplicado encontrado!")
            return
        
        self.stdout.write(f"⚠️ Encontrados {duplicatas.count()} grupos de documentos duplicados:")
        self.stdout.write("")
        
        for duplicata in duplicatas:
            numero = duplicata['numero']
            cartorio_id = duplicata['cartorio']
            count = duplicata['count']
            
            self.stdout.write(f"📄 Número: '{numero}' | Cartório ID: {cartorio_id} | Total: {count}")
            
            # Buscar todos os documentos com este número e cartório
            docs = Documento.objects.filter(
                numero=numero, 
                cartorio_id=cartorio_id
            ).select_related('cartorio', 'imovel', 'tipo').order_by('id')
            
            for i, doc in enumerate(docs, 1):
                self.stdout.write(f"   {i}. ID: {doc.id} | Data: {doc.data} | Tipo: {doc.tipo.tipo}")
                self.stdout.write(f"      Cartório: {doc.cartorio.nome}")
                self.stdout.write(f"      Imóvel: {doc.imovel.matricula} ({doc.imovel.nome})")
                self.stdout.write(f"      Livro: {doc.livro} | Folha: {doc.folha}")
                self.stdout.write("")
            
            if corrigir:
                self.corrigir_duplicados(docs)
            
            self.stdout.write("-" * 50)
    
    def corrigir_duplicados(self, docs):
        """Corrige documentos duplicados mantendo o mais antigo"""
        from django.db import transaction
        
        self.stdout.write("🛠️ CORRIGINDO DUPLICADOS...")
        
        # Ordenar por data (mais antigo primeiro)
        docs_ordenados = sorted(docs, key=lambda x: x.data)
        manter = docs_ordenados[0]  # Mais antigo
        remover = docs_ordenados[1:]  # Restante
        
        self.stdout.write(f"   ✅ Mantendo: ID {manter.id} (Data: {manter.data})")
        
        with transaction.atomic():
            for doc in remover:
                self.stdout.write(f"   🗑️ Removendo: ID {doc.id} (Data: {doc.data})")
                doc.delete()
        
        self.stdout.write("✅ Duplicados corrigidos!")
        self.stdout.write("")

    def verificar_constraints(self):
        """Verifica se as constraints estão funcionando"""
        self.stdout.write("\n🔍 VERIFICANDO CONSTRAINTS:")
        self.stdout.write("-" * 30)
        
        # Verificar constraint unique_together
        self.stdout.write("📋 Constraint unique_together: ('numero', 'cartorio')")
        
        # Buscar violações da constraint
        violacoes = Documento.objects.values('numero', 'cartorio').annotate(
            count=Count('id')
        ).filter(count__gt=1)
        
        if violacoes.exists():
            self.stdout.write(f"⚠️ {violacoes.count()} violações da constraint encontradas")
            for violacao in violacoes:
                self.stdout.write(f"   - Número: '{violacao['numero']}' | Cartório: {violacao['cartorio']} | Count: {violacao['count']}")
        else:
            self.stdout.write("✅ Nenhuma violação da constraint encontrada") 