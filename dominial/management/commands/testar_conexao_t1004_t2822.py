"""
Comando para testar a conexão T1004 -> T2822
"""

from django.core.management.base import BaseCommand
from dominial.models import Documento, Lancamento, Imovel
from dominial.services.hierarquia_arvore_service import HierarquiaArvoreService
from dominial.services.lancamento_origem_service import LancamentoOrigemService
import logging
import re

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Testa a conexão T1004 -> T2822'

    def add_arguments(self, parser):
        parser.add_argument(
            '--imovel',
            type=str,
            help='Matrícula do imóvel para testar (opcional)'
        )
        parser.add_argument(
            '--criar-automatico',
            action='store_true',
            help='Criar documentos automaticamente se não existirem'
        )

    @staticmethod
    def extrair_origens_simples(texto):
        """Extrai números de origens de um texto (versão simplificada)"""
        if not texto:
            return []

        origens = []

        # Padrão 1: Letra explícita seguida de número (T2822, M9712)
        pattern_explicito = r'([TMtm])[\s\-\.]*(\d+)'
        for match in re.finditer(pattern_explicito, texto):
            letra = match.group(1).upper()
            numero = match.group(2)
            origens.append(f'{letra}{numero}')

        # Padrão 2: Só número com contexto
        if not origens:
            pattern_numero = r'\b(\d+)\b'
            for match in re.finditer(pattern_numero, texto):
                numero = match.group(1)
                # Determinar tipo baseado no contexto
                if 'transcrição' in texto.lower():
                    origens.append(f'T{numero}')
                elif 'matrícula' in texto.lower():
                    origens.append(f'M{numero}')
                else:
                    # Padrão: tentar T primeiro
                    origens.append(f'T{numero}')

        return list(set(origens))  # Remove duplicatas

    def handle(self, *args, **options):
        imovel_matricula = options.get('imovel')
        criar_automatico = options.get('criar_automatico', False)
        
        self.stdout.write("🔍 TESTANDO CONEXÃO T1004 -> T2822")
        self.stdout.write("=" * 50)
        
        # Testar extração de origens
        self.stdout.write("\n📋 TESTANDO EXTRAÇÃO DE ORIGENS")
        self.stdout.write("-" * 30)
        
        textos_teste = [
            "T2822",
            "T 2822",
            "T-2822",
            "T.2822",
            "transcrição 2822",
            "matrícula 2822",
            "2822",
            "M9712; T2822",
            "T2822; M9716"
        ]
        
        for texto in textos_teste:
            origens = self.extrair_origens_simples(texto)
            self.stdout.write(f"   '{texto}' -> {origens}")
        
        # Buscar documento T1004
        self.stdout.write("\n🔍 BUSCANDO DOCUMENTO T1004")
        self.stdout.write("-" * 30)
        
        doc_t1004 = Documento.objects.filter(numero='T1004').first()
        if doc_t1004:
            self.stdout.write(f"✅ Documento T1004 encontrado:")
            self.stdout.write(f"   ID: {doc_t1004.id}")
            self.stdout.write(f"   Imóvel: {doc_t1004.imovel.matricula}")
            self.stdout.write(f"   Cartório: {doc_t1004.cartorio.nome}")
            
            # Buscar lançamentos
            lancamentos = doc_t1004.lancamentos.all()
            self.stdout.write(f"   Lançamentos ({lancamentos.count()}):")
            for lanc in lancamentos:
                self.stdout.write(f"     - {lanc.tipo.tipo}: {lanc.numero_lancamento}")
                self.stdout.write(f"       Origem: {lanc.origem}")
                self.stdout.write(f"       Cartório Origem: {lanc.cartorio_origem.nome if lanc.cartorio_origem else 'None'}")
                
                # Testar extração de origens
                origens = self.extrair_origens_simples(lanc.origem)
                self.stdout.write(f"       Origens extraídas: {origens}")

                # Testar busca de documentos
                for origem in origens:
                    # Buscar documento com o número de origem
                    doc_encontrado = Documento.objects.filter(
                        numero=origem
                    ).first()

                    if doc_encontrado:
                        self.stdout.write(f"       ✅ {origem} encontrado: {doc_encontrado.numero} (ID: {doc_encontrado.id}) no cartório {doc_encontrado.cartorio.nome}")
                    else:
                        self.stdout.write(f"       ❌ {origem} não encontrado")
                self.stdout.write()
        else:
            self.stdout.write("❌ Documento T1004 não encontrado")
        
        # Buscar documento T2822
        self.stdout.write("\n🔍 BUSCANDO DOCUMENTO T2822")
        self.stdout.write("-" * 30)
        
        doc_t2822 = Documento.objects.filter(numero='T2822').first()
        if doc_t2822:
            self.stdout.write(f"✅ Documento T2822 encontrado:")
            self.stdout.write(f"   ID: {doc_t2822.id}")
            self.stdout.write(f"   Imóvel: {doc_t2822.imovel.matricula}")
            self.stdout.write(f"   Cartório: {doc_t2822.cartorio.nome}")
        else:
            self.stdout.write("❌ Documento T2822 não encontrado")
        
        # Testar construção da árvore se T1004 existe
        if doc_t1004:
            self.stdout.write("\n🌳 TESTANDO CONSTRUÇÃO DA ÁRVORE")
            self.stdout.write("-" * 30)
            
            try:
                arvore = HierarquiaArvoreService.construir_arvore_cadeia_dominial(
                    doc_t1004.imovel, criar_documentos_automaticos=criar_automatico
                )

                self.stdout.write(f"✅ Árvore construída com sucesso!")
                self.stdout.write(f"   Documentos: {len(arvore['documentos'])}")
                self.stdout.write(f"   Conexões: {len(arvore['conexoes'])}")
                
                # Verificar se T1004 e T2822 estão conectados
                conexao_encontrada = False
                for conexao in arvore['conexoes']:
                    if (conexao['from'] == 'T1004' and conexao['to'] == 'T2822') or \
                       (conexao['from'] == 'T2822' and conexao['to'] == 'T1004'):
                        conexao_encontrada = True
                        self.stdout.write(f"✅ CONEXÃO ENCONTRADA: {conexao['from']} -> {conexao['to']}")
                        break
                
                if not conexao_encontrada:
                    self.stdout.write("❌ CONEXÃO T1004 <-> T2822 NÃO ENCONTRADA")
                
                # Mostrar todas as conexões
                self.stdout.write("\n📊 TODAS AS CONEXÕES:")
                for conexao in arvore['conexoes']:
                    self.stdout.write(f"   {conexao['from']} -> {conexao['to']} ({conexao['tipo']})")
                
            except Exception as e:
                self.stdout.write(f"❌ Erro ao construir árvore: {e}")
                import traceback
                traceback.print_exc()
        
        # Buscar todos os lançamentos que citam T2822
        self.stdout.write("\n🔍 LANÇAMENTOS QUE CITAM T2822")
        self.stdout.write("-" * 30)
        
        lancamentos_citando_t2822 = Lancamento.objects.filter(origem__icontains='T2822')
        self.stdout.write(f"Encontrados {lancamentos_citando_t2822.count()} lançamentos que citam T2822:")
        
        for lanc in lancamentos_citando_t2822:
            self.stdout.write(f"   - Documento: {lanc.documento.numero} (ID: {lanc.documento.id})")
            self.stdout.write(f"     Lançamento: {lanc.tipo.tipo} - {lanc.numero_lancamento}")
            self.stdout.write(f"     Origem: {lanc.origem}")
            self.stdout.write(f"     Cartório Origem: {lanc.cartorio_origem.nome if lanc.cartorio_origem else 'None'}")
            
            # Testar extração
            origens = self.extrair_origens_simples(lanc.origem)
            self.stdout.write(f"     Origens extraídas: {origens}")
            self.stdout.write()
        
        self.stdout.write("✅ Teste concluído!")
