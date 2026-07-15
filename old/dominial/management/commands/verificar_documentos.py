from django.core.management.base import BaseCommand
from dominial.models import Documento


class Command(BaseCommand):
    help = 'Verificar documentos específicos por ID'

    def add_arguments(self, parser):
        parser.add_argument('--ids', nargs='+', type=int, help='IDs dos documentos para verificar')

    def handle(self, *args, **options):
        ids = options.get('ids', [92, 84])
        
        self.stdout.write("=== VERIFICAÇÃO DE DOCUMENTOS ===\n")
        
        for doc_id in ids:
            try:
                doc = Documento.objects.get(id=doc_id)
                self.stdout.write(f"✅ Documento {doc_id} encontrado:")
                self.stdout.write(f"  Número: '{doc.numero}'")
                self.stdout.write(f"  Cartório: {doc.cartorio.nome}")
                self.stdout.write(f"  Data: {doc.data}")
                self.stdout.write(f"  Tipo: {type(doc.numero)}")
                self.stdout.write("")
            except Documento.DoesNotExist:
                self.stdout.write(f"❌ Documento {doc_id} não encontrado\n")
        
        # Verificar se há documentos com números iguais
        if len(ids) >= 2:
            try:
                doc1 = Documento.objects.get(id=ids[0])
                doc2 = Documento.objects.get(id=ids[1])
                
                self.stdout.write("=== COMPARAÇÃO ===")
                self.stdout.write(f"Números são iguais? {doc1.numero == doc2.numero}")
                self.stdout.write(f"Tipo do número 1: {type(doc1.numero)}")
                self.stdout.write(f"Tipo do número 2: {type(doc2.numero)}")
                self.stdout.write("")
                
                # Verificar se há outros documentos com o mesmo número
                mesmo_numero = Documento.objects.filter(numero=doc1.numero)
                self.stdout.write(f"Total de documentos com número '{doc1.numero}': {mesmo_numero.count()}")
                for doc in mesmo_numero:
                    self.stdout.write(f"  - ID: {doc.id}, Cartório: {doc.cartorio.nome}, Data: {doc.data}")
                    
            except Exception as e:
                self.stdout.write(f"❌ Erro ao comparar: {e}")
        
        # Mostrar alguns documentos para verificar
        self.stdout.write("\n=== ÚLTIMOS 5 DOCUMENTOS ===")
        ultimos_docs = Documento.objects.all().order_by('-id')[:5]
        for doc in ultimos_docs:
            self.stdout.write(f"ID: {doc.id}, Número: '{doc.numero}', Cartório: {doc.cartorio.nome}") 