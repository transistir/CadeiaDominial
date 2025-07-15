from dominial.models import Documento

print("=== VERIFICAÇÃO DE DOCUMENTOS ===\n")

# Verificar se os documentos existem
try:
    doc1 = Documento.objects.get(id=92)
    print(f"✅ Documento 92 encontrado:")
    print(f"  Número: '{doc1.numero}'")
    print(f"  Cartório: {doc1.cartorio.nome}")
    print(f"  Data: {doc1.data}")
except Documento.DoesNotExist:
    print("❌ Documento 92 não encontrado")

try:
    doc2 = Documento.objects.get(id=84)
    print(f"\n✅ Documento 84 encontrado:")
    print(f"  Número: '{doc2.numero}'")
    print(f"  Cartório: {doc2.cartorio.nome}")
    print(f"  Data: {doc2.data}")
except Documento.DoesNotExist:
    print("\n❌ Documento 84 não encontrado")

# Verificar se ambos existem para comparar
try:
    doc1 = Documento.objects.get(id=92)
    doc2 = Documento.objects.get(id=84)
    
    print(f"\n=== COMPARAÇÃO ===")
    print(f"Números são iguais? {doc1.numero == doc2.numero}")
    print(f"Tipo do número 1: {type(doc1.numero)}")
    print(f"Tipo do número 2: {type(doc2.numero)}")
    print(f"Comprimento número 1: {len(str(doc1.numero))}")
    print(f"Comprimento número 2: {len(str(doc2.numero))}")
    
    # Verificar se há outros documentos com o mesmo número
    mesmo_numero = Documento.objects.filter(numero=doc1.numero)
    print(f"\nTotal de documentos com número '{doc1.numero}': {mesmo_numero.count()}")
    for doc in mesmo_numero:
        print(f"  - ID: {doc.id}, Cartório: {doc.cartorio.nome}, Data: {doc.data}")
        
except Exception as e:
    print(f"\n❌ Erro ao comparar: {e}")

# Mostrar alguns documentos para verificar
print(f"\n=== ÚLTIMOS 5 DOCUMENTOS ===")
ultimos_docs = Documento.objects.all().order_by('-id')[:5]
for doc in ultimos_docs:
    print(f"ID: {doc.id}, Número: '{doc.numero}', Cartório: {doc.cartorio.nome}")