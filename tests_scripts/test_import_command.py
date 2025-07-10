#!/usr/bin/env python3
"""
Script para testar o comando de importação diretamente
"""

import os
import sys
import django

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'cadeia_dominial.settings')
django.setup()

from django.core.management import call_command
from dominial.models import Cartorios

def test_import_command():
    estado = 'DF'  # Testar com DF que tem poucas cidades
    
    print(f"Testando importação de cartórios de imóveis para {estado}...")
    
    # Contar cartórios antes
    cartorios_antes = Cartorios.objects.filter(estado=estado).count()
    print(f"Cartórios antes da importação: {cartorios_antes}")
    
    try:
        # Executar comando
        print("Executando comando...")
        call_command('importar_cartorios_estado', estado)
        
        # Contar cartórios depois
        cartorios_depois = Cartorios.objects.filter(estado=estado).count()
        cartorios_importados = cartorios_depois - cartorios_antes
        
        print(f"Cartórios após importação: {cartorios_depois}")
        print(f"Cartórios importados: {cartorios_importados}")
        
        # Mostrar alguns cartórios importados
        if cartorios_importados > 0:
            print("\nPrimeiros cartórios importados:")
            for cartorio in Cartorios.objects.filter(estado=estado).order_by('-id')[:5]:
                print(f"  - {cartorio.nome} ({cartorio.cidade})")
        
    except Exception as e:
        print(f"Erro: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_import_command() 