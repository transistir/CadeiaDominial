import requests

def test_onr_request():
    url = 'https://www.registrodeimoveis.org.br/cartorios'
    response = requests.get(url)
    print('Status:', response.status_code)
    print('HTML:', response.text[:2000])

if __name__ == '__main__':
    test_onr_request() 