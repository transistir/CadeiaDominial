#!/usr/bin/env python3
"""
Script para importar cartórios de todos os estados do Brasil
Executa a importação de forma organizada com logs detalhados
"""

import os
import sys
import django
import logging
from datetime import datetime
import time
import subprocess
import html

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'cadeia_dominial.settings_prod')
django.setup()

from dominial.models import Cartorios

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('importacao_cartorios.log'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

# Lista de todos os estados do Brasil
ESTADOS = [
    'AC', 'AL', 'AP', 'AM', 'BA', 'CE', 'DF', 'ES', 'GO', 'MA', 
    'MT', 'MS', 'MG', 'PA', 'PB', 'PR', 'PE', 'PI', 'RJ', 'RN', 
    'RS', 'RO', 'RR', 'SC', 'SP', 'SE', 'TO'
]

def limpar_nome_cidade(cidade):
    """Limpa caracteres HTML entities do nome da cidade"""
    if not cidade:
        return cidade
    return html.unescape(cidade).strip()

def executar_importacao_estado(estado):
    """Executa a importação de cartórios para um estado específico"""
    try:
        logger.info(f"🚀 Iniciando importação do estado {estado}")
        
        # Comando para executar a importação
        comando = f"python manage.py importar_cartorios_estado {estado}"
        
        # Executar o comando
        resultado = subprocess.run(
            comando, 
            shell=True, 
            capture_output=True, 
            text=True,
            cwd='/app'  # Diretório do projeto Django
        )
        
        if resultado.returncode == 0:
            logger.info(f"✅ Importação do estado {estado} concluída com sucesso")
            # Log apenas as últimas linhas para não poluir o output
            linhas_output = resultado.stdout.strip().split('\n')
            if len(linhas_output) > 5:
                logger.info("📝 Últimas linhas do output:")
                for linha in linhas_output[-5:]:
                    if linha.strip():
                        logger.info(f"   {linha.strip()}")
            else:
                logger.info(f"📝 Output: {resultado.stdout.strip()}")
        else:
            logger.error(f"❌ Erro na importação do estado {estado}")
            logger.error(f"📝 Erro: {resultado.stderr}")
            return False
            
        return True
        
    except Exception as e:
        logger.error(f"❌ Exceção na importação do estado {estado}: {str(e)}")
        return False

def verificar_cartorios_estado(estado):
    """Verifica quantos cartórios existem para um estado"""
    try:
        count = Cartorios.objects.filter(estado=estado).count()
        logger.info(f"📊 Estado {estado}: {count} cartórios")
        return count
    except Exception as e:
        logger.error(f"❌ Erro ao verificar cartórios do estado {estado}: {str(e)}")
        return 0

def verificar_estado_ja_importado(estado):
    """Verifica se um estado já foi importado recentemente"""
    try:
        # Verificar se há cartórios para este estado
        count = Cartorios.objects.filter(estado=estado).count()
        if count > 0:
            logger.info(f"📋 Estado {estado} já possui {count} cartórios")
            return True
        return False
    except Exception as e:
        logger.error(f"❌ Erro ao verificar estado {estado}: {str(e)}")
        return False

def main():
    """Função principal do script"""
    logger.info("=" * 60)
    logger.info("🏛️  INICIANDO IMPORTAÇÃO DE TODOS OS CARTÓRIOS DO BRASIL")
    logger.info("=" * 60)
    
    # Verificar cartórios existentes antes da importação
    total_inicial = Cartorios.objects.count()
    logger.info(f"📊 Total de cartórios no banco antes da importação: {total_inicial}")
    
    # Estatísticas
    estados_sucesso = []
    estados_erro = []
    estados_pulados = []
    total_cartorios_antes = {}
    
    # Verificar cartórios existentes por estado
    logger.info("📋 Verificando cartórios existentes por estado:")
    for estado in ESTADOS:
        count = verificar_cartorios_estado(estado)
        total_cartorios_antes[estado] = count
    
    logger.info("=" * 60)
    logger.info("🚀 Iniciando importações...")
    logger.info("=" * 60)
    
    # Executar importação para cada estado
    for i, estado in enumerate(ESTADOS, 1):
        logger.info(f"🔄 [{i}/{len(ESTADOS)}] Processando estado: {estado}")
        
        # Verificar se já foi importado
        if verificar_estado_ja_importado(estado):
            logger.info(f"⏭️  Estado {estado} já possui cartórios. Pulando...")
            estados_pulados.append(estado)
            continue
        
        # Aguardar um pouco entre as importações para evitar sobrecarga
        if i > 1:
            logger.info("⏳ Aguardando 10 segundos antes da próxima importação...")
            time.sleep(10)
        
        # Executar importação
        sucesso = executar_importacao_estado(estado)
        
        if sucesso:
            estados_sucesso.append(estado)
            logger.info(f"✅ Estado {estado} processado com sucesso")
        else:
            estados_erro.append(estado)
            logger.error(f"❌ Estado {estado} falhou na importação")
        
        # Verificar resultado da importação
        count_depois = verificar_cartorios_estado(estado)
        count_antes = total_cartorios_antes[estado]
        novos_cartorios = count_depois - count_antes
        
        if novos_cartorios > 0:
            logger.info(f"📈 Estado {estado}: +{novos_cartorios} novos cartórios")
        elif novos_cartorios == 0:
            logger.info(f"📊 Estado {estado}: Nenhum novo cartório")
        else:
            logger.warning(f"⚠️  Estado {estado}: {novos_cartorios} cartórios (possível limpeza)")
        
        logger.info("-" * 40)
    
    # Relatório final
    logger.info("=" * 60)
    logger.info("📊 RELATÓRIO FINAL DA IMPORTAÇÃO")
    logger.info("=" * 60)
    
    total_final = Cartorios.objects.count()
    total_importados = total_final - total_inicial
    
    logger.info(f"📈 Total de cartórios importados: {total_importados}")
    logger.info(f"📊 Total final no banco: {total_final}")
    logger.info(f"✅ Estados com sucesso: {len(estados_sucesso)}")
    logger.info(f"❌ Estados com erro: {len(estados_erro)}")
    logger.info(f"⏭️  Estados pulados: {len(estados_pulados)}")
    
    if estados_sucesso:
        logger.info(f"✅ Estados processados com sucesso: {', '.join(estados_sucesso)}")
    
    if estados_erro:
        logger.error(f"❌ Estados com erro: {', '.join(estados_erro)}")
    
    if estados_pulados:
        logger.info(f"⏭️  Estados pulados: {', '.join(estados_pulados)}")
    
    # Estatísticas por estado
    logger.info("📋 Estatísticas finais por estado:")
    for estado in ESTADOS:
        count = Cartorios.objects.filter(estado=estado).count()
        logger.info(f"  {estado}: {count} cartórios")
    
    logger.info("=" * 60)
    logger.info("🏁 IMPORTAÇÃO CONCLUÍDA!")
    logger.info("=" * 60)

if __name__ == "__main__":
    main() 