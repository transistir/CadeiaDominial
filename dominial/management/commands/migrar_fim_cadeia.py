"""
Comando Django para migrar dados de fim de cadeia do formato antigo para o novo
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from dominial.models import Lancamento, Documento, OrigemFimCadeia
import re


class Command(BaseCommand):
    help = 'Migra dados de fim de cadeia do formato antigo para o novo formato'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Executa a migração sem fazer alterações no banco',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Força a migração mesmo se houver dados já migrados',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        force = options['force']
        
        self.stdout.write(
            self.style.SUCCESS('🔄 Iniciando migração de fim de cadeia...')
        )
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING('⚠️  MODO DRY-RUN: Nenhuma alteração será feita no banco')
            )
        
        # 1. Verificar lançamentos com FIM_CADEIA
        lancamentos_fim_cadeia = Lancamento.objects.filter(
            origem__contains='FIM_CADEIA'
        )
        
        total_lancamentos = lancamentos_fim_cadeia.count()
        self.stdout.write(f'📊 Encontrados {total_lancamentos} lançamentos com fim de cadeia')
        
        if total_lancamentos == 0:
            self.stdout.write(
                self.style.SUCCESS('✅ Nenhum lançamento com fim de cadeia encontrado')
            )
            return
        
        # 2. Verificar documentos de fim de cadeia criados incorretamente
        documentos_fim_cadeia = Documento.objects.filter(
            classificacao_fim_cadeia__isnull=False
        )
        
        total_documentos = documentos_fim_cadeia.count()
        self.stdout.write(f'📊 Encontrados {total_documentos} documentos de fim de cadeia (serão removidos)')
        
        # 3. Verificar se já existem registros OrigemFimCadeia
        origens_fim_cadeia_existentes = OrigemFimCadeia.objects.count()
        if origens_fim_cadeia_existentes > 0 and not force:
            self.stdout.write(
                self.style.ERROR(
                    f'❌ Já existem {origens_fim_cadeia_existentes} registros de OrigemFimCadeia. '
                    'Use --force para continuar.'
                )
            )
            return
        
        if not dry_run:
            with transaction.atomic():
                # 4. Migrar lançamentos
                self.migrar_lancamentos(lancamentos_fim_cadeia)
                
                # 5. Remover documentos de fim de cadeia incorretos
                self.remover_documentos_fim_cadeia(documentos_fim_cadeia)
                
                # 6. Limpar registros OrigemFimCadeia existentes se force
                if force and origens_fim_cadeia_existentes > 0:
                    OrigemFimCadeia.objects.all().delete()
                    self.stdout.write(
                        self.style.WARNING(f'🗑️  Removidos {origens_fim_cadeia_existentes} registros OrigemFimCadeia existentes')
                    )
        
        self.stdout.write(
            self.style.SUCCESS('🎉 Migração concluída com sucesso!')
        )

    def migrar_lancamentos(self, lancamentos):
        """Migra lançamentos do formato antigo para o novo"""
        self.stdout.write('🔄 Migrando lançamentos...')
        
        for lancamento in lancamentos:
            origem_antiga = lancamento.origem
            origem_nova = self.converter_origem_fim_cadeia(origem_antiga)
            
            if origem_nova != origem_antiga:
                lancamento.origem = origem_nova
                lancamento.save()
                
                self.stdout.write(
                    f'   ✅ Lançamento {lancamento.id}: {origem_antiga} → {origem_nova}'
                )
            else:
                self.stdout.write(
                    f'   ⚠️  Lançamento {lancamento.id}: Formato já correto'
                )

    def converter_origem_fim_cadeia(self, origem_antiga):
        """
        Converte origem do formato antigo para o novo
        Formato antigo: FIM_CADEIA:tipo_origem:numero:tipo_fim_cadeia:classificacao:sigla_patrimonio
        Formato novo: Destacamento Público:Sigla:Classificação
        """
        if 'FIM_CADEIA' not in origem_antiga:
            return origem_antiga
        
        # Extrair partes da origem
        partes = origem_antiga.split(':')
        
        if len(partes) < 4:
            self.stdout.write(
                self.style.WARNING(f'   ⚠️  Formato inválido: {origem_antiga}')
            )
            return origem_antiga
        
        # Determinar tipo de fim de cadeia
        if len(partes) == 4:  # Formato sem tipo de origem
            tipo_fim_cadeia = partes[2] if len(partes) > 2 else 'sem_origem'
            classificacao = partes[3] if len(partes) > 3 else 'sem_origem'
            sigla_patrimonio = ''
        elif len(partes) == 5:  # Formato sem tipo de origem (com sigla)
            tipo_fim_cadeia = partes[2] if len(partes) > 2 else 'sem_origem'
            classificacao = partes[3] if len(partes) > 3 else 'sem_origem'
            sigla_patrimonio = partes[4] if len(partes) > 4 else ''
        else:  # Formato com tipo de origem
            tipo_fim_cadeia = partes[3] if len(partes) > 3 else 'sem_origem'
            classificacao = partes[4] if len(partes) > 4 else 'sem_origem'
            sigla_patrimonio = partes[5] if len(partes) > 5 else ''
        
        # Mapear tipos para nomes legíveis
        tipo_nomes = {
            'destacamento_publico': 'Destacamento Público',
            'outra': 'Outra',
            'sem_origem': 'Sem Origem'
        }
        
        # Mapear classificações para nomes legíveis
        classificacao_nomes = {
            'origem_lidima': 'Origem Lídima',
            'sem_origem': 'Sem Origem',
            'inconclusa': 'Situação Inconclusa'
        }
        
        tipo_legivel = tipo_nomes.get(tipo_fim_cadeia, tipo_fim_cadeia)
        classificacao_legivel = classificacao_nomes.get(classificacao, classificacao)
        
        # Construir origem no novo formato
        if sigla_patrimonio and sigla_patrimonio.strip():
            origem_nova = f"{tipo_legivel}:{sigla_patrimonio.strip()}:{classificacao_legivel}"
        else:
            origem_nova = f"{tipo_legivel}::{classificacao_legivel}"
        
        return origem_nova

    def remover_documentos_fim_cadeia(self, documentos):
        """Remove documentos de fim de cadeia criados incorretamente"""
        self.stdout.write('🗑️  Removendo documentos de fim de cadeia incorretos...')
        
        for documento in documentos:
            self.stdout.write(
                f'   🗑️  Removendo documento {documento.numero} (ID: {documento.id})'
            )
            documento.delete()
        
        self.stdout.write(
            self.style.SUCCESS(f'✅ Removidos {documentos.count()} documentos de fim de cadeia')
        )
