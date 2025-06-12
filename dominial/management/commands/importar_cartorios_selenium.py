from django.core.management.base import BaseCommand
from dominial.models import Cartorios
import time
import json
import logging
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.firefox.options import Options

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Importa cartórios de uma cidade específica usando Selenium para simular o navegador'

    def add_arguments(self, parser):
        parser.add_argument('estado', type=str, help='Sigla do estado (ex: AC)')
        parser.add_argument('cidade', type=str, help='Nome da cidade (ex: CRUZEIRO DO SUL)')

    def handle(self, *args, **options):
        estado = options['estado']
        cidade = options['cidade']
        self.stdout.write(f'Iniciando importação de cartórios de {cidade} ({estado})...')

        # Configurar o Firefox em modo headless
        options = Options()
        options.add_argument('-headless')
        driver = webdriver.Firefox(options=options)

        try:
            # Acessar a página de cartórios
            driver.get('https://www.registrodeimoveis.org.br/cartorios')
            self.stdout.write('Página carregada. Aguardando carregamento dos elementos...')

            # Aguardar o select de estado estar presente e selecionar o estado
            select_estado = WebDriverWait(driver, 20).until(
                EC.presence_of_element_located((By.ID, 'estado'))
            )
            select_estado.click()
            option_estado = driver.find_element(By.XPATH, f"//option[contains(text(), '{estado}')]")
            option_estado.click()
            self.stdout.write(f'Estado {estado} selecionado.')

            # Aguardar o select de cidade estar presente e selecionar a cidade
            select_cidade = WebDriverWait(driver, 20).until(
                EC.presence_of_element_located((By.ID, 'cidade'))
            )
            select_cidade.click()
            option_cidade = driver.find_element(By.XPATH, f"//option[contains(text(), '{cidade}')]")
            option_cidade.click()
            self.stdout.write(f'Cidade {cidade} selecionada.')

            # Aguardar o botão de busca estar presente e clicar nele
            botao_busca = WebDriverWait(driver, 20).until(
                EC.element_to_be_clickable((By.ID, 'buscar'))
            )
            botao_busca.click()
            self.stdout.write('Botão de busca clicado. Aguardando resposta...')

            # Aguardar a resposta da requisição AJAX (exemplo: aguardar um elemento que só aparece após a resposta)
            # Aqui, você pode ajustar o seletor conforme a resposta da página
            WebDriverWait(driver, 20).until(
                EC.presence_of_element_located((By.CLASS_NAME, 'cartorio-item'))
            )

            # Capturar o JSON da resposta (exemplo: extrair dados da tabela ou lista de cartórios)
            cartorios = []
            elementos_cartorios = driver.find_elements(By.CLASS_NAME, 'cartorio-item')
            for elemento in elementos_cartorios:
                cartorio = {
                    'nome': elemento.find_element(By.CLASS_NAME, 'nome').text,
                    'cns': elemento.find_element(By.CLASS_NAME, 'cns').text,
                    'endereco': elemento.find_element(By.CLASS_NAME, 'endereco').text,
                    'telefone': elemento.find_element(By.CLASS_NAME, 'telefone').text,
                    'email': elemento.find_element(By.CLASS_NAME, 'email').text
                }
                cartorios.append(cartorio)

            # Salvar os cartórios no banco de dados
            total = 0
            for cartorio in cartorios:
                try:
                    Cartorios.objects.update_or_create(
                        cns=cartorio['cns'],
                        defaults={
                            'nome': cartorio['nome'],
                            'endereco': cartorio['endereco'],
                            'telefone': cartorio['telefone'],
                            'email': cartorio['email'],
                            'estado': estado,
                            'cidade': cidade
                        }
                    )
                    total += 1
                except Exception as e:
                    logger.error(f'Erro ao salvar cartório: {str(e)}')

            self.stdout.write(self.style.SUCCESS(f'Importação concluída! Total de cartórios: {total}'))

        except Exception as e:
            logger.error(f'Erro durante a execução do Selenium: {str(e)}')
            self.stdout.write(self.style.ERROR(f'Erro: {str(e)}'))
        finally:
            driver.quit() 