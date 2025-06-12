import requests
import pytest

def test_conexao_api_cnj():
    """Testa a conexão básica com a API do CNJ"""
    # CNS de teste (exemplo)
    cns = "123456"
    url = f"https://www.cnj.jus.br/corregedoria/justica_aberta/?d=consulta_extra&a=consulta_extra&f=seiApostila&cns={cns}"
    
    try:
        response = requests.get(url)
        assert response.status_code == 200
        print(f"Status Code: {response.status_code}")
        print(f"Conteúdo: {response.text[:200]}...")  # Mostra os primeiros 200 caracteres
    except requests.exceptions.RequestException as e:
        pytest.fail(f"Erro na conexão: {str(e)}")

if __name__ == "__main__":
    test_conexao_api_cnj() 