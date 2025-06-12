from django.core.management.base import BaseCommand
from dominial.models import Cartorios
import requests
import time
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Importa cartórios do ONR para o banco de dados'

    def handle(self, *args, **options):
        estados = [
            ('AC', 'Acre'), ('AL', 'Alagoas'), ('AM', 'Amazonas'), ('AP', 'Amapá'),
            ('BA', 'Bahia'), ('CE', 'Ceará'), ('DF', 'Distrito Federal'),
            ('ES', 'Espírito Santo'), ('GO', 'Goiás'), ('MA', 'Maranhão'),
            ('MG', 'Minas Gerais'), ('MS', 'Mato Grosso do Sul'), ('MT', 'Mato Grosso'),
            ('PA', 'Pará'), ('PB', 'Paraíba'), ('PE', 'Pernambuco'), ('PI', 'Piauí'),
            ('PR', 'Paraná'), ('RJ', 'Rio de Janeiro'), ('RN', 'Rio Grande do Norte'),
            ('RO', 'Rondônia'), ('RR', 'Roraima'), ('RS', 'Rio Grande do Sul'),
            ('SC', 'Santa Catarina'), ('SE', 'Sergipe'), ('SP', 'São Paulo'),
            ('TO', 'Tocantins')
        ]

        url = 'https://www.registrodeimoveis.org.br/includes/consulta-cartorios.php'
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'X-Requested-With': 'XMLHttpRequest',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }

        total_cartorios = 0

        for sigla, nome in estados:
            self.stdout.write(f'Processando {nome}...')
            
            # Buscar cidades do estado
            try:
                response = requests.post(url, headers=headers, data={'estado': sigla})
                response.raise_for_status()
                cidades = response.json()
                
                for cidade in cidades:
                    self.stdout.write(f'  Buscando cartórios de {cidade}...')
                    
                    # Buscar cartórios da cidade
                    try:
                        response = requests.post(url, headers=headers, data={
                            'estado': sigla,
                            'cidade': cidade
                        })
                        response.raise_for_status()
                        cartorios = response.json()
                        
                        for cartorio in cartorios:
                            try:
                                # Criar ou atualizar cartório no banco
                                Cartorios.objects.update_or_create(
                                    cns=cartorio.get('cns'),
                                    defaults={
                                        'nome': cartorio.get('nome'),
                                        'endereco': cartorio.get('endereco'),
                                        'telefone': cartorio.get('telefone'),
                                        'email': cartorio.get('email'),
                                        'estado': sigla,
                                        'cidade': cidade
                                    }
                                )
                                total_cartorios += 1
                            except Exception as e:
                                logger.error(f'Erro ao salvar cartório: {str(e)}')
                        
                        # Pausa para não sobrecarregar o servidor
                        time.sleep(1)
                        
                    except Exception as e:
                        logger.error(f'Erro ao buscar cartórios de {cidade}: {str(e)}')
                        continue
                
            except Exception as e:
                logger.error(f'Erro ao buscar cidades de {nome}: {str(e)}')
                continue
            
            # Pausa maior entre estados
            time.sleep(2)
        
        self.stdout.write(self.style.SUCCESS(f'Importação concluída! Total de cartórios: {total_cartorios}')) 