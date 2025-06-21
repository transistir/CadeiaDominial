import requests

def test_onr_request():
    url = 'https://www.registrodeimoveis.org.br/cartorios'
    response = requests.get(url)
    return response.status_code == 200

if __name__ == '__main__':
    test_onr_request() 