import requests

url = 'https://www.registrodeimoveis.org.br/includes/consulta-cartorios.php'
headers = {
    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0',
    'Accept': '*/*',
    'Accept-Language': 'pt-BR,pt;q=0.8,en-US;q=0.5,en;q=0.3',
    'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
    'X-Requested-With': 'XMLHttpRequest',
    'Referer': 'https://www.registrodeimoveis.org.br/cartorios',
}
data = 'estado=AC'

response = requests.post(url, headers=headers, data=data)
self.assertEqual(response.status_code, 200)

response = self.client.post('/dominial/verificar-cartorios/', data={'estado': 'SP'})
self.assertEqual(response.status_code, 200)
data = response.json()
self.assertIn('existem_cartorios', data) 