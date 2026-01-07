from django.core.management.base import BaseCommand
from django.db import transaction
from dominial.models import Documento, Lancamento
from collections import defaultdict


class Command(BaseCommand):
    help = 'Identifica e corrige documentos duplicados com cartórios diferentes'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Apenas mostra os documentos que seriam afetados, sem fazer alterações',
        )
        parser.add_argument(
            '--imovel-id',
            type=int,
            help='Processar apenas um imóvel específico',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        imovel_id = options['imovel_id']
        
        self.stdout.write(
            self.style.SUCCESS('🔍 Iniciando análise de documentos duplicados...')
        )
        
        # Buscar documentos duplicados
        documentos_duplicados = self._encontrar_documentos_duplicados(imovel_id)
        
        if not documentos_duplicados:
            self.stdout.write(
                self.style.SUCCESS('✅ Nenhum documento duplicado encontrado!')
            )
            return
        
        self.stdout.write(
            self.style.WARNING(f'⚠️  Encontrados {len(documentos_duplicados)} grupos de documentos duplicados:')
        )
        
        for numero, documentos in documentos_duplicados.items():
            self.stdout.write(f'\n📋 Documento {numero}:')
            for doc in documentos:
                lancamentos_count = doc.lancamentos.count()
                self.stdout.write(
                    f'  - ID: {doc.id}, Cartório: {doc.cartorio.nome}, '
                    f'Lançamentos: {lancamentos_count}'
                )
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING('\n🔍 Modo dry-run: nenhuma alteração será feita.')
            )
            return
        
        # Processar correções
        self._processar_correcoes(documentos_duplicados)
    
    def _encontrar_documentos_duplicados(self, imovel_id=None):
        """
        Encontra documentos duplicados (mesmo número, cartórios diferentes)
        """
        # Buscar todos os documentos
        queryset = Documento.objects.select_related('cartorio', 'imovel')
        if imovel_id:
            queryset = queryset.filter(imovel_id=imovel_id)
        
        # Agrupar por número
        documentos_por_numero = defaultdict(list)
        for doc in queryset:
            documentos_por_numero[doc.numero].append(doc)
        
        # Filtrar apenas grupos com mais de um documento
        duplicados = {}
        for numero, documentos in documentos_por_numero.items():
            if len(documentos) > 1:
                # Verificar se há cartórios diferentes
                cartorios = {doc.cartorio for doc in documentos}
                if len(cartorios) > 1:
                    duplicados[numero] = documentos
        
        return duplicados
    
    def _processar_correcoes(self, documentos_duplicados):
        """
        Processa as correções dos documentos duplicados
        """
        self.stdout.write('\n🔧 Iniciando correções...')
        
        for numero, documentos in documentos_duplicados.items():
            self.stdout.write(f'\n📋 Processando documento {numero}:')
            
            # Ordenar por número de lançamentos (menos primeiro)
            documentos_ordenados = sorted(
                documentos, 
                key=lambda doc: doc.lancamentos.count()
            )
            
            # Encontrar o documento principal (com mais lançamentos)
            documento_principal = documentos_ordenados[-1]
            documentos_secundarios = documentos_ordenados[:-1]
            
            self.stdout.write(f'  ✅ Documento principal: ID {documento_principal.id} ({documento_principal.cartorio.nome})')
            
            for doc_secundario in documentos_secundarios:
                lancamentos_count = doc_secundario.lancamentos.count()
                
                if lancamentos_count == 0:
                    # Documento sem lançamentos - pode ser removido
                    self.stdout.write(
                        f'  🗑️  Removendo documento {doc_secundario.id} '
                        f'({doc_secundario.cartorio.nome}) - sem lançamentos'
                    )
                    if not self._remover_documento_vazio(doc_secundario):
                        self.stdout.write(
                            self.style.ERROR(f'    ❌ Erro ao remover documento {doc_secundario.id}')
                        )
                else:
                    # Documento com lançamentos - precisa de intervenção manual
                    self.stdout.write(
                        self.style.WARNING(
                            f'  ⚠️  Documento {doc_secundario.id} '
                            f'({doc_secundario.cartorio.nome}) tem {lancamentos_count} lançamentos - '
                            f'intervenção manual necessária'
                        )
                    )
    
    def _remover_documento_vazio(self, documento):
        """
        Remove um documento que não tem lançamentos
        """
        try:
            with transaction.atomic():
                documento.delete()
                return True
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'    Erro ao remover documento {documento.id}: {e}')
            )
            return False 