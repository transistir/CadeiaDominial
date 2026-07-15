from django.core.management.base import BaseCommand
from dominial.models import Cartorios
import requests
import logging
import html

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Importa cartórios de uma cidade específica do ONR para o banco de dados'

    def add_arguments(self, parser):
        parser.add_argument('estado', type=str, help='Sigla do estado (ex: AC)')
        parser.add_argument('cidade', type=str, help='Nome da cidade (ex: CRUZEIRO DO SUL)')

    def handle(self, *args, **options):
        estado = options['estado']
        cidade = options['cidade']
        url = 'https://www.registrodeimoveis.org.br/includes/consulta-cartorios.php'
        
        # Headers exatamente como no teste que funcionou
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

        self.stdout.write(f'Buscando cartórios de {cidade} ({estado})...')
        
        try:
            # Primeiro, buscar as cidades do estado
            response = requests.post(url, headers=headers, data={'estado': estado})
            response.raise_for_status()
            cidades = response.json()
            self.stdout.write(f'Cidades encontradas: {cidades}')

            # Depois, buscar os cartórios da cidade específica
            response = requests.post(url, headers=headers, data={
                'estado': estado,
                'cidade': cidade
            })
            response.raise_for_status()
            cartorios = response.json()
            self.stdout.write(f'Resposta dos cartórios: {cartorios}')
            
            total = 0
            for cartorio in cartorios:
                try:
                    cns = cartorio.get('codigo_cns', '')
                    nome = html.unescape(cartorio.get('nome_serventia', ''))
                    email = html.unescape(cartorio.get('publico_email', ''))
                    telefone = html.unescape(cartorio.get('telefone_1', ''))
                    # Montar endereço completo
                    endereco = html.unescape((
                        (cartorio.get('descricao_tipo_logradouro', '') + ' ' if cartorio.get('descricao_tipo_logradouro') else '') +
                        (cartorio.get('endereco_logradouro', '') + ', ' if cartorio.get('endereco_logradouro') else '') +
                        (cartorio.get('endereco_numero', '') + ' ' if cartorio.get('endereco_numero') else '') +
                        (cartorio.get('endereco_complemento', '') + ' ' if cartorio.get('endereco_complemento') else '') +
                        (cartorio.get('endereco_bairro', '') + ' ' if cartorio.get('endereco_bairro') else '') +
                        (cartorio.get('endereco_cep', '') if cartorio.get('endereco_cep') else '')
                    ).strip())

                    if not nome or not cns:
                        self.stdout.write(f'Cartório ignorado por falta de dados: {cartorio}')
                        continue
                    
                    Cartorios.objects.update_or_create(
                        cns=cns,
                        defaults={
                            'nome': nome,
                            'endereco': endereco,
                            'telefone': telefone,
                            'email': email,
                            'estado': estado,
                            'cidade': cidade
                        }
                    )
                    total += 1
                    self.stdout.write(f'Cartório importado: {nome}')
                except Exception as e:
                    logger.error(f'Erro ao salvar cartório: {str(e)}')
                    self.stdout.write(f'Erro ao salvar cartório: {str(e)}')
            
            self.stdout.write(self.style.SUCCESS(f'Importação concluída! Total de cartórios: {total}'))
            
        except Exception as e:
            logger.error(f'Erro ao buscar cartórios de {cidade}: {str(e)}')
            self.stdout.write(self.style.ERROR(f'Erro: {str(e)}')) 