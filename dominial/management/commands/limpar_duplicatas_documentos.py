"""
Comando para limpar documentos duplicados criados incorretamente pelo sistema
Remove apenas duplicatas vazios (sem lançamentos), preservando documentos com dados
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from dominial.models import Documento
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Remove documentos duplicados vazios (sem lançamentos)'

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
        
        self.stdout.write('🧹 Iniciando limpeza de documentos duplicados...')
        
        # 1. Identificar duplicatas
        duplicatas = self._identificar_duplicatas()
        
        if not duplicatas:
            self.stdout.write(
                self.style.SUCCESS('✅ Nenhum documento duplicado encontrado!')
            )
            return
        
        self.stdout.write(f'📊 Encontrados {len(duplicatas)} documentos com duplicatas')
        
        # 2. Separar vazios dos com lançamentos
        vazios_para_remover = []
        documentos_preservados = []
        
        for numero, docs in duplicatas.items():
            docs_vazios = [d for d in docs if d.lancamentos.count() == 0]
            docs_com_lancamentos = [d for d in docs if d.lancamentos.count() > 0]
            
            if docs_vazios:
                vazios_para_remover.extend(docs_vazios)
                documentos_preservados.extend(docs_com_lancamentos)
                
                if verbose:
                    self.stdout.write(f'\n📄 {numero}:')
                    self.stdout.write(f'  🗑️  Vazios (remover): {len(docs_vazios)}')
                    for doc in docs_vazios:
                        self.stdout.write(f'    - ID: {doc.id}, Cartório: {doc.cartorio.nome}')
                    self.stdout.write(f'  ✅ Com lançamentos (preservar): {len(docs_com_lancamentos)}')
                    for doc in docs_com_lancamentos:
                        self.stdout.write(f'    - ID: {doc.id}, Cartório: {doc.cartorio.nome}, Lançamentos: {doc.lancamentos.count()}')
        
        # 3. Mostrar resumo
        self.stdout.write(f'\n📋 RESUMO:')
        self.stdout.write(f'  🗑️  Documentos vazios para remover: {len(vazios_para_remover)}')
        self.stdout.write(f'  ✅ Documentos com lançamentos preservados: {len(documentos_preservados)}')
        
        if not vazios_para_remover:
            self.stdout.write(
                self.style.SUCCESS('✅ Nenhum documento vazio para remover!')
            )
            return
        
        # 4. Confirmar operação
        if not dry_run:
            confirm = input(f'\n⚠️  Confirma remoção de {len(vazios_para_remover)} documentos vazios? (s/N): ')
            if confirm.lower() != 's':
                self.stdout.write('❌ Operação cancelada pelo usuário')
                return
        
        # 5. Executar remoção
        if dry_run:
            self.stdout.write('\n🔍 SIMULAÇÃO - Documentos que seriam removidos:')
            for doc in vazios_para_remover:
                self.stdout.write(f'  - {doc.numero} (ID: {doc.id}) - {doc.cartorio.nome}')
        else:
            self._remover_documentos_vazios(vazios_para_remover)
        
        self.stdout.write(
            self.style.SUCCESS(f'\n✅ Limpeza concluída!')
        )

    def _identificar_duplicatas(self):
        """Identifica documentos duplicados por número"""
        docs_por_numero = defaultdict(list)
        
        for doc in Documento.objects.all():
            docs_por_numero[doc.numero].append(doc)
        
        # Retorna apenas os que têm duplicatas
        return {numero: docs for numero, docs in docs_por_numero.items() if len(docs) > 1}

    def _remover_documentos_vazios(self, documentos):
        """Remove documentos vazios em transação"""
        with transaction.atomic():
            removidos = 0
            
            for doc in documentos:
                try:
                    # Verificar se realmente está vazio
                    if doc.lancamentos.count() == 0:
                        numero = doc.numero
                        cartorio = doc.cartorio.nome
                        doc_id = doc.id
                        
                        doc.delete()
                        removidos += 1
                        
                        self.stdout.write(
                            f'  🗑️  Removido: {numero} (ID: {doc_id}) - {cartorio}'
                        )
                    else:
                        self.stdout.write(
                            self.style.WARNING(
                                f'  ⚠️  Pulado: {doc.numero} (ID: {doc.id}) - tem {doc.lancamentos.count()} lançamentos'
                            )
                        )
                        
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(
                            f'  ❌ Erro ao remover {doc.numero} (ID: {doc.id}): {e}'
                        )
                    )
            
            self.stdout.write(f'\n📊 Total removido: {removidos} documentos')
