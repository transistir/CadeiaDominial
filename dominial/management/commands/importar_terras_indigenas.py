import requests
from django.core.management.base import BaseCommand
from dominial.models import TerraIndigenaReferencia, TIs
import json
from datetime import datetime

class Command(BaseCommand):
    help = 'Importa as terras indígenas do WFS da FUNAI e cria TIs automaticamente'

    def add_arguments(self, parser):
        parser.add_argument(
            '--apenas-referencia',
            action='store_true',
            help='Importar apenas para TerraIndigenaReferencia, sem criar TIs',
        )

    def limpar_data(self, data_str):
        """Limpa o formato da data removendo o Z e convertendo para o formato YYYY-MM-DD"""
        if not data_str:
            return None
        try:
            # Remove o Z do final se existir
            data_str = data_str.rstrip('Z')
            # Tenta converter para datetime e depois para string no formato correto
            data = datetime.strptime(data_str, '%Y-%m-%d')
            return data.strftime('%Y-%m-%d')
        except (ValueError, TypeError):
            return None

    def handle(self, *args, **options):
        apenas_referencia = options['apenas_referencia']
        
        if apenas_referencia:
            self.stdout.write('Iniciando importação das terras indígenas (apenas referência)...')
        else:
            self.stdout.write('Iniciando importação das terras indígenas e criação de TIs...')
        
        # URL do WFS da FUNAI
        url = 'https://geoserver.funai.gov.br/geoserver/wfs'
        
        # Parâmetros da requisição
        params = {
            'service': 'WFS',
            'version': '1.1.0',
            'request': 'GetFeature',
            'typeName': 'Funai:tis_poligonais_portarias',
            'outputFormat': 'application/json',
            'srsName': 'EPSG:4674'
        }
        
        try:
            # Fazendo a requisição
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            response = requests.get(url, params=params, headers=headers)
            response.raise_for_status()
            
            # Parseando o JSON
            data = response.json()
            
            contador_referencia = 0
            contador_tis = 0
            
            for feature in data['features']:
                try:
                    properties = feature['properties']
                    
                    # Extraindo os dados usando os nomes corretos dos campos
                    nome = properties.get('terrai_nome', '')
                    codigo = str(properties.get('terrai_codigo', ''))
                    etnia = properties.get('etnia_nome', '')
                    estado = properties.get('uf_sigla', '')
                    area = properties.get('superficie_perimetro_ha', None)
                    
                    # Informações adicionais
                    fase = properties.get('fase_ti', '')
                    modalidade = properties.get('modalidade_ti', '')
                    municipio = properties.get('municipio_nome', '')
                    cr = properties.get('cr', '')
                    
                    # Datas importantes - usando a função limpar_data
                    data_regularizada = self.limpar_data(properties.get('data_regularizada'))
                    data_homologada = self.limpar_data(properties.get('data_homologada'))
                    data_declarada = self.limpar_data(properties.get('data_declarada'))
                    data_delimitada = self.limpar_data(properties.get('data_delimitada'))
                    data_em_estudo = self.limpar_data(properties.get('data_em_estudo'))
                    
                    if nome and codigo:
                        # Criando ou atualizando o registro de referência
                        terra_referencia, created = TerraIndigenaReferencia.objects.update_or_create(
                            codigo=codigo,
                            defaults={
                                'nome': nome,
                                'etnia': etnia,
                                'estado': estado,
                                'area_ha': area,
                                'municipio': municipio,
                                'fase': fase,
                                'modalidade': modalidade,
                                'coordenacao_regional': cr,
                                'data_regularizada': data_regularizada,
                                'data_homologada': data_homologada,
                                'data_declarada': data_declarada,
                                'data_delimitada': data_delimitada,
                                'data_em_estudo': data_em_estudo
                            }
                        )
                        contador_referencia += 1
                        
                        # Criar TI automaticamente se não for apenas referência
                        if not apenas_referencia:
                            # Verificar se já existe uma TI com esse código
                            if not TIs.objects.filter(codigo=codigo).exists():
                                # Criar nova TI
                                tis = TIs.objects.create(
                                    terra_referencia=terra_referencia,
                                    nome=nome,
                                    codigo=codigo,
                                    etnia=etnia or 'Não informada'
                                )
                                contador_tis += 1
                                self.stdout.write(f'TI criada: {nome} ({codigo})')
                            else:
                                self.stdout.write(f'TI já existe: {nome} ({codigo})')
                        
                        self.stdout.write(f'Importada: {nome} ({etnia}) - {fase}')
                    
                except Exception as e:
                    self.stdout.write(self.style.WARNING(f'Erro ao processar terra indígena {nome if "nome" in locals() else "desconhecida"}: {str(e)}'))
                    continue
            
            # Resumo final
            self.stdout.write(self.style.SUCCESS(f'Importação concluída!'))
            self.stdout.write(f'Referências: {contador_referencia}')
            if not apenas_referencia:
                self.stdout.write(f'TIs criadas: {contador_tis}')
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Erro ao importar terras indígenas: {str(e)}')) 