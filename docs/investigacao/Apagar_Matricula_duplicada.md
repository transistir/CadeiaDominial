docker-compose exec web python manage.py shell

## Primeiro listar as duplicadas
```
from dominial.models import Imovel, Documento
imovel = Imovel.objects.get(id=5)
docs = Documento.objects.filter(imovel=imovel)
from collections import Counter
numeros = [doc.numero for doc in docs]
contagem = Counter(numeros)
duplicados = [num for num, count in contagem.items() if count > 1]
print(f"Documentos duplicados ({len(duplicados)}): {duplicados}")
for num in duplicados:
    docs_duplicados = docs.filter(numero=num)
    print(f"\nNúmero: {num} (total: {docs_duplicados.count()})")
    for doc in docs_duplicados:
        print(f"  - ID: {doc.id} | Tipo: {doc.tipo} | Data: {doc.data}")
```
## Depois listar para ver qual é qual
```
        for doc in Documento.objects.filter(imovel=imovel, numero='M9393'):
    print(f"ID: {doc.id} | Data: {doc.data} | Lançamentos: {doc.lancamentos.count()} | Livro: {doc.livro} | Folha: {doc.folha}")
```
e então escolher o id e apagar
```
    from dominial.models.documento_models import Documento
doc = Documento.objects.get(id=119)
doc.delete()
```