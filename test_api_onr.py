#!/usr/bin/env python3
"""
Script de teste para verificar se a API do ONR está funcionando
"""

import requests
import json

def test_api_onr():
    url = 'https://www.registrodeimoveis.org.br/includes/consulta-cartorios.php'
    headers = {
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0',
        'Accept': '*/*',
        'Accept-Language': 'pt-BR,pt;q=0.8,en-US;q=0.5,en;q=0.3',
        'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
        'X-Requested-With': 'XMLHttpRequest',
        'Sec-Fetch-Dest': 'empty',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Site': 'same-origin',
        'Priority': 'u=0',
        'Referer': 'https://www.registrodeimoveis.org.br/cartorios'
    }

    print("Testando API do ONR...")
    
    # Teste 1: Buscar cidades do Paraná
    print("\n1. Testando busca de cidades do Paraná...")
    try:
        response = requests.post(url, headers=headers, data={'estado': 'PR'})
        print(f"Status: {response.status_code}")
        print(f"Headers: {dict(response.headers)}")
        
        if response.status_code == 200:
            cidades = response.json()
            print(f"Cidades encontradas: {len(cidades)}")
            if cidades:
                print(f"Primeiras 5 cidades: {[c.get('value', 'N/A') for c in cidades[:5]]}")
                
                # Teste 2: Buscar cartórios de uma cidade específica
                if cidades:
                    primeira_cidade = cidades[0].get('value')
                    print(f"\n2. Testando busca de cartórios de {primeira_cidade}...")
                    
                    response2 = requests.post(url, headers=headers, data={
                        'estado': 'PR',
                        'cidade': primeira_cidade
                    })
                    print(f"Status: {response2.status_code}")
                    
                    if response2.status_code == 200:
                        cartorios = response2.json()
                        print(f"Cartórios encontrados: {len(cartorios)}")
                        if cartorios:
                            print(f"Primeiro cartório: {cartorios[0]}")
                        else:
                            print("Nenhum cartório encontrado")
                    else:
                        print(f"Erro na resposta: {response2.text}")
            else:
                print("Nenhuma cidade encontrada")
        else:
            print(f"Erro na resposta: {response.text}")
            
    except Exception as e:
        print(f"Erro: {str(e)}")

if __name__ == "__main__":
    test_api_onr() 