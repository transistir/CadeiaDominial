#!/usr/bin/env python
import os
import django

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'cadeia_dominial.settings')
django.setup()

from dominial.forms import TIsForm
from dominial.models import TIs

print("=== Teste: Formulário com múltiplos estados ===")

# Testar formulário com múltiplos estados
data = {
    'nome': 'TI Multi-Estado',
    'codigo': 'TI777',
    'etnia': 'Multi',
    'estado': ['AM', 'PA', 'MT'],
    'area': '5000.00'
}

form = TIsForm(data)
print("Válido:", form.is_valid())
print("Erros:", form.errors if not form.is_valid() else "Nenhum erro")

if form.is_valid():
    print("\n=== Salvando TI ===")
    tis_count_before = TIs.objects.count()
    print(f"TIs antes: {tis_count_before}")
    
    tis = form.save()
    print(f"TI salva: {tis.nome}")
    print(f"Estados: {tis.estado}")
    print(f"Área: {tis.area}")
    
    tis_count_after = TIs.objects.count()
    print(f"TIs depois: {tis_count_after}")
    
    # Limpar o teste
    tis.delete()
    print("TI de teste removida")

print("\n=== Teste concluído! ===") 