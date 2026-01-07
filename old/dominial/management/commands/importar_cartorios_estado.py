from django.core.management.base import BaseCommand
from dominial.models import Cartorios
import requests
import logging
import time
import html
import random

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Importa cartórios de registro de imóveis de um estado do ONR para o banco de dados'

    def add_arguments(self, parser):
        parser.add_argument('estado', type=str, help='Sigla do estado (ex: AC)')

    def is_cartorio_imoveis(self, nome):
        """
        Verifica se o cartório é de registro de imóveis
        """
        nome_lower = nome.lower()
        keywords = [
            'imovel', 'imoveis', 'imóveis', 'imobiliario', 'imobiliária', 
            'registro de imóveis', 'registro de imoveis'
        ]
        return any(keyword in nome_lower for keyword in keywords)

    def handle(self, *args, **options):
        estado = options['estado']
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

        self.stdout.write(f'Buscando cidades do estado {estado}...')
        try:
            response = requests.post(url, headers=headers, data={'estado': estado})
            response.raise_for_status()
            cidades = response.json()
            self.stdout.write(f'Cidades encontradas: {len(cidades)}')
        except Exception as e:
            logger.error(f'Erro ao buscar cidades do estado {estado}: {str(e)}')
            self.stdout.write(self.style.ERROR(f'Erro ao buscar cidades do estado {estado}: {str(e)}'))
            return

        total_cartorios = 0
        cartorios_imoveis = 0
        cidades_com_erro = 0
        
        for i, cidade_dict in enumerate(cidades):
            # Tratar caso onde cidade_dict pode ser string ou dicionário
            if isinstance(cidade_dict, str):
                cidade = cidade_dict
            else:
                cidade = cidade_dict.get('value')
                
            if not cidade:
                continue
                
            self.stdout.write(f'Buscando cartórios de {cidade}... ({i+1}/{len(cidades)})')
            
            # Delay reduzido para cartórios de imóveis
            delay = 0.5 + random.uniform(0, 1)  # 0.5-1.5 segundos
            time.sleep(delay)
            
            # Retry logic para lidar com erros 403
            max_retries = 2  # Reduzido para 2 tentativas
            for retry in range(max_retries):
                try:
                    response = requests.post(url, headers=headers, data={
                        'estado': estado,
                        'cidade': cidade
                    })
                    response.raise_for_status()
                    cartorios = response.json()
                    
                    # Filtrar apenas cartórios de imóveis
                    cartorios_filtrados = []
                    for cartorio in cartorios:
                        nome = html.unescape(cartorio.get('nome_serventia', ''))
                        if self.is_cartorio_imoveis(nome):
                            cartorios_filtrados.append(cartorio)
                    
                    if cartorios_filtrados:
                        self.stdout.write(f'  Encontrados {len(cartorios_filtrados)} cartórios de imóveis (de {len(cartorios)} total).')
                        
                        for cartorio in cartorios_filtrados:
                            try:
                                cns = cartorio.get('codigo_cns', '')
                                nome = html.unescape(cartorio.get('nome_serventia', ''))
                                email = html.unescape(cartorio.get('publico_email', ''))
                                telefone = html.unescape(cartorio.get('telefone_1', ''))
                                endereco = html.unescape((
                                    (cartorio.get('descricao_tipo_logradouro', '') + ' ' if cartorio.get('descricao_tipo_logradouro') else '') +
                                    (cartorio.get('endereco_logradouro', '') + ', ' if cartorio.get('endereco_logradouro') else '') +
                                    (cartorio.get('endereco_numero', '') + ' ' if cartorio.get('endereco_numero') else '') +
                                    (cartorio.get('endereco_complemento', '') + ' ' if cartorio.get('endereco_complemento') else '') +
                                    (cartorio.get('endereco_bairro', '') + ' ' if cartorio.get('endereco_bairro') else '') +
                                    (cartorio.get('endereco_cep', '') if cartorio.get('endereco_cep') else '')
                                ).strip())

                                if not nome or not cns:
                                    self.stdout.write(f'  Cartório ignorado por falta de dados: {cartorio}')
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
                                total_cartorios += 1
                                cartorios_imoveis += 1
                                self.stdout.write(f'  ✅ Cartório de imóveis importado: {nome}')
                            except Exception as e:
                                logger.error(f'Erro ao salvar cartório: {str(e)}')
                                self.stdout.write(f'  ❌ Erro ao salvar cartório: {str(e)}')
                    else:
                        self.stdout.write(f'  ⏭️  Nenhum cartório de imóveis encontrado em {cidade}')
                    
                    # Se chegou aqui, deu certo, sai do loop de retry
                    break
                    
                except requests.exceptions.HTTPError as e:
                    if e.response.status_code == 403:
                        cidades_com_erro += 1
                        if retry < max_retries - 1:
                            wait_time = (retry + 1) * 3  # 3, 6 segundos
                            self.stdout.write(f'  ⏳ Erro 403, tentativa {retry + 1}/{max_retries}. Aguardando {wait_time}s...')
                            time.sleep(wait_time)
                            continue
                        else:
                            self.stdout.write(f'  ❌ Erro 403 após {max_retries} tentativas para {cidade}')
                            logger.error(f'Erro 403 após {max_retries} tentativas para {cidade}')
                    else:
                        self.stdout.write(f'  ❌ Erro HTTP {e.response.status_code} para {cidade}: {str(e)}')
                        logger.error(f'Erro HTTP {e.response.status_code} para {cidade}: {str(e)}')
                        break
                except Exception as e:
                    self.stdout.write(f'  ❌ Erro ao buscar cartórios de {cidade}: {str(e)}')
                    logger.error(f'Erro ao buscar cartórios de {cidade}: {str(e)}')
                    break
        
        self.stdout.write(self.style.SUCCESS(f'✅ Importação concluída!'))
        self.stdout.write(f'📊 Total de cartórios de imóveis importados: {cartorios_imoveis}')
        self.stdout.write(f'📊 Total geral de cartórios no banco: {total_cartorios}')
        if cidades_com_erro > 0:
            self.stdout.write(self.style.WARNING(f'⚠️  Cidades com erro (403): {cidades_com_erro}')) 