"""
Comando para testar otimizações de performance
"""
from django.core.management.base import BaseCommand
from django.db import connection
from django.test.utils import override_settings
from dominial.models import TIs, Imovel, Documento, Lancamento
from dominial.services.cache_service import CacheService
import time
import statistics


class Command(BaseCommand):
    help = 'Testa otimizações de performance implementadas'

    def add_arguments(self, parser):
        parser.add_argument(
            '--tis-id',
            type=int,
            help='ID da TI para testar (opcional)',
        )
        parser.add_argument(
            '--iterations',
            type=int,
            default=5,
            help='Número de iterações para teste (padrão: 5)',
        )

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS('🚀 Iniciando testes de performance...')
        )
        
        tis_id = options['tis_id']
        iterations = options['iterations']
        
        # Obter TI para teste
        if tis_id:
            try:
                tis = TIs.objects.get(id=tis_id)
            except TIs.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(f'❌ TI com ID {tis_id} não encontrada')
                )
                return
        else:
            # Usar primeira TI disponível
            tis = TIs.objects.first()
            if not tis:
                self.stdout.write(
                    self.style.ERROR('❌ Nenhuma TI encontrada no sistema')
                )
                return
        
        self.stdout.write(f'📋 Testando com TI: {tis.nome} (ID: {tis.id})')
        
        # Teste 1: Performance de queries de documentos
        self._test_documentos_performance(tis, iterations)
        
        # Teste 2: Performance de queries de lançamentos
        self._test_lancamentos_performance(tis, iterations)
        
        # Teste 3: Performance de cache
        self._test_cache_performance(tis, iterations)
        
        # Teste 4: Performance de hierarquia
        self._test_hierarquia_performance(tis, iterations)
        
        self.stdout.write(
            self.style.SUCCESS('✅ Testes de performance concluídos!')
        )

    def _test_documentos_performance(self, tis, iterations):
        """Testa performance de queries de documentos"""
        self.stdout.write('\n📄 Testando performance de documentos...')
        
        # Obter imóveis da TI
        imoveis = Imovel.objects.filter(terra_indigena_id=tis)[:3]
        
        if not imoveis:
            self.stdout.write('⚠️  Nenhum imóvel encontrado para teste')
            return
        
        times = []
        
        for i in range(iterations):
            start_time = time.time()
            
            for imovel in imoveis:
                # Query otimizada com select_related e prefetch_related
                documentos = Documento.objects.filter(imovel=imovel)\
                    .select_related('cartorio', 'tipo')\
                    .prefetch_related('lancamentos', 'lancamentos__tipo')\
                    .order_by('data')
                
                # Forçar execução da query
                list(documentos)
            
            end_time = time.time()
            times.append(end_time - start_time)
        
        avg_time = statistics.mean(times)
        min_time = min(times)
        max_time = max(times)
        
        self.stdout.write(f'   ⏱️  Tempo médio: {avg_time:.4f}s')
        self.stdout.write(f'   🏃 Tempo mínimo: {min_time:.4f}s')
        self.stdout.write(f'   🐌 Tempo máximo: {max_time:.4f}s')
        self.stdout.write(f'   📊 Queries executadas: {len(connection.queries)}')

    def _test_lancamentos_performance(self, tis, iterations):
        """Testa performance de queries de lançamentos"""
        self.stdout.write('\n📋 Testando performance de lançamentos...')
        
        # Obter documentos da TI
        documentos = Documento.objects.filter(imovel__terra_indigena_id=tis)[:5]
        
        if not documentos:
            self.stdout.write('⚠️  Nenhum documento encontrado para teste')
            return
        
        times = []
        
        for i in range(iterations):
            start_time = time.time()
            
            for documento in documentos:
                # Query otimizada com select_related e prefetch_related
                lancamentos = documento.lancamentos.all()\
                    .select_related('tipo', 'transmitente', 'adquirente')\
                    .prefetch_related('pessoas')\
                    .order_by('id')
                
                # Forçar execução da query
                list(lancamentos)
            
            end_time = time.time()
            times.append(end_time - start_time)
        
        avg_time = statistics.mean(times)
        min_time = min(times)
        max_time = max(times)
        
        self.stdout.write(f'   ⏱️  Tempo médio: {avg_time:.4f}s')
        self.stdout.write(f'   🏃 Tempo mínimo: {min_time:.4f}s')
        self.stdout.write(f'   🐌 Tempo máximo: {max_time:.4f}s')

    def _test_cache_performance(self, tis, iterations):
        """Testa performance do sistema de cache"""
        self.stdout.write('\n💾 Testando performance do cache...')
        
        # Obter um imóvel para teste
        imovel = Imovel.objects.filter(terra_indigena_id=tis).first()
        
        if not imovel:
            self.stdout.write('⚠️  Nenhum imóvel encontrado para teste de cache')
            return
        
        # Limpar cache antes do teste
        CacheService.clear_all_caches()
        
        times_without_cache = []
        times_with_cache = []
        
        for i in range(iterations):
            # Teste sem cache
            start_time = time.time()
            documentos = Documento.objects.filter(imovel=imovel)\
                .select_related('cartorio', 'tipo')\
                .prefetch_related('lancamentos')\
                .order_by('data')
            list(documentos)
            end_time = time.time()
            times_without_cache.append(end_time - start_time)
            
            # Armazenar no cache
            CacheService.set_cached_documentos_imovel(imovel.id, list(documentos))
            
            # Teste com cache
            start_time = time.time()
            cached_docs = CacheService.get_cached_documentos_imovel(imovel.id)
            end_time = time.time()
            times_with_cache.append(end_time - start_time)
        
        avg_without_cache = statistics.mean(times_without_cache)
        avg_with_cache = statistics.mean(times_with_cache)
        
        self.stdout.write(f'   ⏱️  Sem cache (médio): {avg_without_cache:.4f}s')
        self.stdout.write(f'   ⏱️  Com cache (médio): {avg_with_cache:.4f}s')
        
        if avg_without_cache > 0:
            improvement = ((avg_without_cache - avg_with_cache) / avg_without_cache) * 100
            self.stdout.write(f'   📈 Melhoria: {improvement:.1f}%')

    def _test_hierarquia_performance(self, tis, iterations):
        """Testa performance da hierarquia"""
        self.stdout.write('\n🌳 Testando performance da hierarquia...')
        
        # Obter um imóvel para teste
        imovel = Imovel.objects.filter(terra_indigena_id=tis).first()
        
        if not imovel:
            self.stdout.write('⚠️  Nenhum imóvel encontrado para teste de hierarquia')
            return
        
        from dominial.services.hierarquia_service import HierarquiaService
        
        times = []
        
        for i in range(iterations):
            start_time = time.time()
            
            # Testar construção da árvore
            arvore = HierarquiaService.construir_arvore_cadeia_dominial(imovel)
            
            end_time = time.time()
            times.append(end_time - start_time)
        
        avg_time = statistics.mean(times)
        min_time = min(times)
        max_time = max(times)
        
        self.stdout.write(f'   ⏱️  Tempo médio: {avg_time:.4f}s')
        self.stdout.write(f'   🏃 Tempo mínimo: {min_time:.4f}s')
        self.stdout.write(f'   🐌 Tempo máximo: {max_time:.4f}s')
        
        # Mostrar estatísticas da árvore
        if 'documentos' in arvore:
            self.stdout.write(f'   📄 Documentos na árvore: {len(arvore["documentos"])}')
        if 'origens_identificadas' in arvore:
            self.stdout.write(f'   🔗 Origens identificadas: {len(arvore["origens_identificadas"])}') 