"""
Comando para corrigir cartórios de origem dos lançamentos
Identifica lançamentos com cartórios de origem incorretos e permite correção manual
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from dominial.models import Documento, Lancamento, Cartorios
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Corrigir cartórios de origem dos lançamentos para documentos corretos'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Simula a operação sem fazer alterações reais',
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Mostra informações detalhadas',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        verbose = options['verbose']
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING('🔍 MODO SIMULAÇÃO - Nenhuma alteração será feita')
            )
        
        self.stdout.write('🔧 Iniciando correção de cartórios de origem...')
        
        # 1. Identificar lançamentos com múltiplas origens
        lancamentos_problematicos = self._identificar_lancamentos_problematicos()
        
        if not lancamentos_problematicos:
            self.stdout.write(
                self.style.SUCCESS('✅ Nenhum lançamento problemático encontrado!')
            )
            return
        
        self.stdout.write(f'📊 Encontrados {len(lancamentos_problematicos)} lançamentos problemáticos')
        
        # 2. Analisar cada lançamento
        correcoes_sugeridas = []
        
        for lancamento in lancamentos_problematicos:
            if verbose:
                self.stdout.write(f'\n📄 Analisando lançamento: {lancamento.numero_lancamento}')
            
            correcoes = self._analisar_lancamento(lancamento, verbose)
            if correcoes:
                correcoes_sugeridas.extend(correcoes)
        
        if not correcoes_sugeridas:
            self.stdout.write(
                self.style.SUCCESS('✅ Nenhuma correção necessária!')
            )
            return
        
        # 3. Mostrar correções sugeridas
        self._mostrar_correcoes_sugeridas(correcoes_sugeridas)
        
        # 4. Aplicar correções
        if not dry_run:
            self._aplicar_correcoes(correcoes_sugeridas)
        
        self.stdout.write(
            self.style.SUCCESS(f'\n✅ Análise concluída! {len(correcoes_sugeridas)} correções identificadas.')
        )

    def _identificar_lancamentos_problematicos(self):
        """Identifica lançamentos que podem ter cartórios de origem incorretos"""
        # Buscar lançamentos com múltiplas origens (separadas por ;)
        lancamentos = Lancamento.objects.filter(
            origem__contains=';'
        ).select_related('cartorio_origem', 'documento')
        
        return lancamentos

    def _analisar_lancamento(self, lancamento, verbose=False):
        """Analisa um lançamento e sugere correções"""
        correcoes = []
        
        if not lancamento.origem:
            return correcoes
        
        # Extrair origens
        origens = [origem.strip() for origem in lancamento.origem.split(';') if origem.strip()]
        
        if verbose:
            self.stdout.write(f'  Origem: {lancamento.origem}')
            self.stdout.write(f'  Cartório Origem: {lancamento.cartorio_origem.nome if lancamento.cartorio_origem else "None"}')
        
        # Analisar cada origem
        for origem in origens:
            if not origem:
                continue
            
            # Buscar documentos com este número
            documentos = Documento.objects.filter(numero=origem)
            
            if documentos.count() > 1:
                # Há múltiplos documentos com mesmo número
                docs_com_lancamentos = [doc for doc in documentos if doc.lancamentos.count() > 0]
                docs_vazios = [doc for doc in documentos if doc.lancamentos.count() == 0]
                
                if docs_com_lancamentos and docs_vazios:
                    # Há documentos com lançamentos e documentos vazios
                    doc_correto = docs_com_lancamentos[0]  # Primeiro com lançamentos
                    
                    if verbose:
                        self.stdout.write(f'  🔍 {origem}:')
                        self.stdout.write(f'    Documento correto: ID {doc_correto.id}, Cartório: {doc_correto.cartorio.nome}, Lançamentos: {doc_correto.lancamentos.count()}')
                        for doc in docs_vazios:
                            self.stdout.write(f'    Documento vazio: ID {doc.id}, Cartório: {doc.cartorio.nome}')
                    
                    # Verificar se o cartório de origem está correto
                    if lancamento.cartorio_origem != doc_correto.cartorio:
                        correcoes.append({
                            'lancamento': lancamento,
                            'origem': origem,
                            'cartorio_atual': lancamento.cartorio_origem,
                            'cartorio_correto': doc_correto.cartorio,
                            'documento_correto': doc_correto
                        })
        
        return correcoes

    def _mostrar_correcoes_sugeridas(self, correcoes):
        """Mostra as correções sugeridas"""
        self.stdout.write(f'\n📋 CORREÇÕES SUGERIDAS:')
        
        for i, correcao in enumerate(correcoes, 1):
            self.stdout.write(f'\n{i}. Lançamento: {correcao["lancamento"].numero_lancamento}')
            self.stdout.write(f'   Origem: {correcao["origem"]}')
            self.stdout.write(f'   Cartório atual: {correcao["cartorio_atual"].nome}')
            self.stdout.write(f'   Cartório correto: {correcao["cartorio_correto"].nome}')
            self.stdout.write(f'   Documento correto: ID {correcao["documento_correto"].id}, Lançamentos: {correcao["documento_correto"].lancamentos.count()}')

    def _aplicar_correcoes(self, correcoes):
        """Aplica as correções sugeridas"""
        if not correcoes:
            return
        
        # Agrupar por lançamento
        lancamentos_para_corrigir = defaultdict(list)
        for correcao in correcoes:
            lancamentos_para_corrigir[correcao['lancamento']].append(correcao)
        
        with transaction.atomic():
            for lancamento, correcoes_lanc in lancamentos_para_corrigir.items():
                # Para cada lançamento, usar o cartório do documento com mais lançamentos
                cartorio_mais_lancamentos = None
                max_lancamentos = 0
                
                for correcao in correcoes_lanc:
                    lanc_count = correcao['documento_correto'].lancamentos.count()
                    if lanc_count > max_lancamentos:
                        max_lancamentos = lanc_count
                        cartorio_mais_lancamentos = correcao['cartorio_correto']
                
                if cartorio_mais_lancamentos:
                    lancamento.cartorio_origem = cartorio_mais_lancamentos
                    lancamento.save()
                    
                    self.stdout.write(
                        f'✅ Corrigido: {lancamento.numero_lancamento} -> Cartório: {cartorio_mais_lancamentos.nome}'
                    )