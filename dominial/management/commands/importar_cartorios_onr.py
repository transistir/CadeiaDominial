from django.core.management.base import BaseCommand
from dominial.models import Cartorios
import requests
import json
import time

class Command(BaseCommand):
    help = 'Importa cartórios do site da ONR'

    def handle(self, *args, **options):
        self.stdout.write('Iniciando importação de cartórios...')
        
        # Headers para simular um navegador
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'application/json, text/javascript, */*; q=0.01',
            'Accept-Language': 'pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7',
            'X-Requested-With': 'XMLHttpRequest',
            'Referer': 'https://www.registrodeimoveis.org.br/cartorios',
        }

        # URL base
        base_url = 'https://www.registrodeimoveis.org.br'
        
        # Testando apenas com o Acre
        estados = {'AC': 'Acre'}

        try:
            # Para cada estado
            for uf, nome_estado in estados.items():
                self.stdout.write(f'Processando estado: {nome_estado} ({uf})')
                
                # Fazendo requisição para obter as cidades do estado
                cidades_url = f'{base_url}/cartorios/cidades/{uf}'
                self.stdout.write(f'URL das cidades: {cidades_url}')
                
                response = requests.get(cidades_url, headers=headers)
                self.stdout.write(f'Status da resposta: {response.status_code}')
                self.stdout.write(f'Conteúdo da resposta: {response.text[:500]}')
                
                if response.status_code == 200:
                    try:
                        cidades = response.json()
                        self.stdout.write(f'Cidades encontradas: {cidades}')
                    except json.JSONDecodeError:
                        self.stdout.write(self.style.ERROR('Erro ao decodificar JSON da resposta'))
                        continue
                    
                    # Para cada cidade
                    for cidade in cidades:
                        self.stdout.write(f'  Processando cidade: {cidade}')
                        
                        # Fazendo requisição para obter os cartórios da cidade
                        cartorios_url = f'{base_url}/cartorios/buscar'
                        params = {
                            'estado': uf,
                            'cidade': cidade
                        }
                        
                        self.stdout.write(f'URL dos cartórios: {cartorios_url}?estado={uf}&cidade={cidade}')
                        response = requests.get(cartorios_url, params=params, headers=headers)
                        self.stdout.write(f'Status da resposta: {response.status_code}')
                        self.stdout.write(f'Conteúdo da resposta: {response.text[:500]}')
                        
                        if response.status_code == 200:
                            try:
                                cartorios = response.json()
                                self.stdout.write(f'Cartórios encontrados: {cartorios}')
                            except json.JSONDecodeError:
                                self.stdout.write(self.style.ERROR('Erro ao decodificar JSON da resposta'))
                                continue
                            
                            # Salvando cada cartório no banco
                            for cartorio in cartorios:
                                try:
                                    Cartorios.objects.create(
                                        nome=cartorio.get('nome', ''),
                                        cns=cartorio.get('cns', ''),
                                        endereco=cartorio.get('endereco', ''),
                                        telefone=cartorio.get('telefone', ''),
                                        email=cartorio.get('email', '')
                                    )
                                    self.stdout.write(f'    Cartório salvo: {cartorio.get("nome")}')
                                except Exception as e:
                                    self.stdout.write(self.style.ERROR(f'    Erro ao salvar cartório: {str(e)}'))
                        
                        # Pausa para não sobrecarregar o servidor
                        time.sleep(1)
                
                # Pausa entre estados
                time.sleep(2)
            
            self.stdout.write(self.style.SUCCESS('Importação concluída com sucesso!'))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Erro inesperado: {str(e)}')) 