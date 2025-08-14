from django.core.management.base import BaseCommand
from dominial.models import Documento, Lancamento, DocumentoImportado
from django.db.models import Count
from django.db import transaction
import re
import os
from datetime import datetime


class Command(BaseCommand):
    help = 'Corrige erros de produção de forma segura com backup automático'

    def add_arguments(self, parser):
        parser.add_argument(
            '--problema',
            type=str,
            choices=['conversao_string', 'documentos_duplicados', 'todos'],
            default='todos',
            help='Tipo de problema para corrigir'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Executar em modo de teste (não faz alterações)'
        )

    def handle(self, *args, **options):
        problema = options.get('problema', 'todos')
        dry_run = options.get('dry_run', False)
        
        self.stdout.write("🔒 CORREÇÃO SEGURA DE ERROS DE PRODUÇÃO")
        self.stdout.write("=" * 60)
        
        if dry_run:
            self.stdout.write("🧪 MODO DE TESTE - Nenhuma alteração será feita")
        
        # Fazer backup das tabelas afetadas
        self.fazer_backup_tabelas()
        
        if problema in ['conversao_string', 'todos']:
            self.corrigir_erro_conversao_string(dry_run)
        
        if problema in ['documentos_duplicados', 'todos']:
            self.corrigir_documentos_importados_duplicados(dry_run)

    def fazer_backup_tabelas(self):
        """Faz backup das tabelas que serão modificadas"""
        self.stdout.write(f"\n💾 FAZENDO BACKUP DAS TABELAS")
        self.stdout.write("-" * 50)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Criar diretório de backup se não existir
        backup_dir = '/tmp/backup_cadeia_dominial'
        try:
            os.makedirs(backup_dir, exist_ok=True)
        except Exception as e:
            self.stdout.write(f"⚠️ Não foi possível criar diretório de backup: {str(e)}")
            self.stdout.write(f"   Continuando sem backup de tabelas...")
            return
        
        # Backup da tabela Lancamento
        lancamentos_backup = list(Lancamento.objects.all().values())
        backup_file_lancamentos = os.path.join(backup_dir, f'lancamentos_backup_{timestamp}.json')
        try:
            with open(backup_file_lancamentos, 'w') as f:
                import json
                json.dump(lancamentos_backup, f, default=str, indent=2)
            self.stdout.write(f"✅ Backup de lançamentos criado: {backup_file_lancamentos}")
        except Exception as e:
            self.stdout.write(f"⚠️ Erro ao criar backup de lançamentos: {str(e)}")
        
        # Backup da tabela DocumentoImportado
        documentos_importados_backup = list(DocumentoImportado.objects.all().values())
        backup_file_importados = os.path.join(backup_dir, f'documentos_importados_backup_{timestamp}.json')
        try:
            with open(backup_file_importados, 'w') as f:
                import json
                json.dump(documentos_importados_backup, f, default=str, indent=2)
            self.stdout.write(f"✅ Backup de documentos importados criado: {backup_file_importados}")
        except Exception as e:
            self.stdout.write(f"⚠️ Erro ao criar backup de documentos importados: {str(e)}")

    def corrigir_erro_conversao_string(self, dry_run=False):
        """Corrige erro de conversão de string para int"""
        self.stdout.write(f"\n🔧 CORRIGINDO ERRO DE CONVERSÃO DE STRING")
        self.stdout.write("-" * 50)
        
        # Buscar lançamentos com origens problemáticas
        lancamentos_problematicos = []
        
        lancamentos = Lancamento.objects.filter(
            origem__isnull=False
        ).exclude(origem='')
        
        for lancamento in lancamentos:
            if lancamento.origem:
                origens = [o.strip() for o in lancamento.origem.split(';') if o.strip()]
                
                for origem in origens:
                    if origem.startswith(('M', 'T')):
                        numero_part = origem[1:]
                        try:
                            int(numero_part)
                        except ValueError:
                            lancamentos_problematicos.append({
                                'lancamento': lancamento,
                                'origem_problematica': origem,
                                'numero_part': numero_part
                            })
        
        self.stdout.write(f"Lançamentos com origens problemáticas: {len(lancamentos_problematicos)}")
        
        if dry_run:
            for item in lancamentos_problematicos:
                lanc = item['lancamento']
                origem_problematica = item['origem_problematica']
                
                self.stdout.write(f"   [DRY-RUN] Lançamento ID: {lanc.id}")
                self.stdout.write(f"   [DRY-RUN] Origem atual: '{lanc.origem}'")
                self.stdout.write(f"   [DRY-RUN] Origem problemática: '{origem_problematica}'")
                self.stdout.write()
        else:
            with transaction.atomic():
                for item in lancamentos_problematicos:
                    lanc = item['lancamento']
                    origem_problematica = item['origem_problematica']
                    
                    self.stdout.write(f"   🔧 Corrigindo lançamento {lanc.id}...")
                    
                    if lanc.origem:
                        origens = [o.strip() for o in lanc.origem.split(';') if o.strip()]
                        origens_corrigidas = [o for o in origens if o != origem_problematica]
                        
                        if len(origens_corrigidas) != len(origens):
                            nova_origem = '; '.join(origens_corrigidas) if origens_corrigidas else ''
                            lanc.origem = nova_origem
                            lanc.save()
                            self.stdout.write(f"   ✅ Origem corrigida: '{nova_origem}'")
                        else:
                            self.stdout.write(f"   ⚠️ Não foi necessário corrigir")

    def corrigir_documentos_importados_duplicados(self, dry_run=False):
        """Corrige documentos importados duplicados"""
        self.stdout.write(f"\n🔧 CORRIGINDO DOCUMENTOS IMPORTADOS DUPLICADOS")
        self.stdout.write("-" * 50)
        
        # Buscar documentos que têm múltiplos registros de importação
        documentos_duplicados = DocumentoImportado.objects.values('documento').annotate(
            count=Count('documento')
        ).filter(count__gt=1)
        
        self.stdout.write(f"Documentos com múltiplos registros de importação: {documentos_duplicados.count()}")
        
        if dry_run:
            for item in documentos_duplicados:
                documento_id = item['documento']
                count = item['count']
                
                documento = Documento.objects.get(id=documento_id)
                importacoes = DocumentoImportado.objects.filter(documento=documento).order_by('id')
                
                self.stdout.write(f"\n   [DRY-RUN] Documento: {documento.numero} (ID: {documento.id})")
                self.stdout.write(f"   [DRY-RUN] Total de importações: {count}")
                
                for i, importacao in enumerate(importacoes, 1):
                    self.stdout.write(f"     [DRY-RUN] Importação {i}: ID {importacao.id} - {importacao.imovel_origem.matricula}")
        else:
            with transaction.atomic():
                for item in documentos_duplicados:
                    documento_id = item['documento']
                    count = item['count']
                    
                    documento = Documento.objects.get(id=documento_id)
                    importacoes = DocumentoImportado.objects.filter(documento=documento).order_by('id')
                    
                    self.stdout.write(f"\n   🔧 Corrigindo documento {documento.numero}...")
                    
                    if len(importacoes) > 1:
                        # Manter apenas o registro mais recente
                        importacao_mais_recente = max(importacoes, key=lambda x: x.data_importacao)
                        
                        # Remover os registros mais antigos
                        importacoes_para_remover = [imp for imp in importacoes if imp.id != importacao_mais_recente.id]
                        
                        for importacao in importacoes_para_remover:
                            self.stdout.write(f"     Removendo importação ID: {importacao.id}")
                            importacao.delete()
                        
                        self.stdout.write(f"   ✅ Mantido apenas o registro mais recente (ID: {importacao_mais_recente.id})")
                    else:
                        self.stdout.write(f"   ⚠️ Não foi necessário corrigir")

    def verificar_correcoes(self):
        """Verifica se as correções foram aplicadas corretamente"""
        self.stdout.write(f"\n✅ VERIFICANDO CORREÇÕES")
        self.stdout.write("-" * 50)
        
        # Verificar se ainda há origens problemáticas
        lancamentos_problematicos = []
        lancamentos = Lancamento.objects.filter(origem__isnull=False).exclude(origem='')
        
        for lancamento in lancamentos:
            if lancamento.origem:
                origens = [o.strip() for o in lancamento.origem.split(';') if o.strip()]
                for origem in origens:
                    if origem.startswith(('M', 'T')):
                        numero_part = origem[1:]
                        try:
                            int(numero_part)
                        except ValueError:
                            lancamentos_problematicos.append(lancamento)
        
        if lancamentos_problematicos:
            self.stdout.write(f"❌ Ainda há {len(lancamentos_problematicos)} lançamentos com origens problemáticas")
        else:
            self.stdout.write(f"✅ Nenhum lançamento com origem problemática encontrado")
        
        # Verificar se ainda há documentos importados duplicados
        documentos_duplicados = DocumentoImportado.objects.values('documento').annotate(
            count=Count('documento')
        ).filter(count__gt=1)
        
        if documentos_duplicados:
            self.stdout.write(f"❌ Ainda há {documentos_duplicados.count()} documentos com múltiplos registros de importação")
        else:
            self.stdout.write(f"✅ Nenhum documento com múltiplos registros de importação encontrado")
