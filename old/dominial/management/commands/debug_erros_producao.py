from django.core.management.base import BaseCommand
from dominial.models import Documento, Lancamento, DocumentoImportado
from django.db.models import Count
import re


class Command(BaseCommand):
    help = 'Debuga erros específicos de produção'

    def add_arguments(self, parser):
        parser.add_argument(
            '--problema',
            type=str,
            choices=['conversao_string', 'documentos_duplicados', 'todos'],
            default='todos',
            help='Tipo de problema para investigar'
        )
        parser.add_argument(
            '--corrigir',
            action='store_true',
            help='Corrigir automaticamente os problemas encontrados'
        )

    def handle(self, *args, **options):
        problema = options.get('problema', 'todos')
        corrigir = options.get('corrigir', False)
        
        self.stdout.write("🔍 DEBUGANDO ERROS DE PRODUÇÃO")
        self.stdout.write("=" * 60)
        
        if problema in ['conversao_string', 'todos']:
            self.investigar_erro_conversao_string(corrigir)
        
        if problema in ['documentos_duplicados', 'todos']:
            self.investigar_documentos_importados_duplicados(corrigir)

    def investigar_erro_conversao_string(self, corrigir=False):
        """Investiga erro de conversão de string para int"""
        self.stdout.write(f"\n🔍 INVESTIGANDO ERRO DE CONVERSÃO DE STRING")
        self.stdout.write("-" * 50)
        
        # Buscar lançamentos com origens que podem causar problemas
        lancamentos_problematicos = []
        
        lancamentos = Lancamento.objects.filter(
            origem__isnull=False
        ).exclude(origem='')
        
        for lancamento in lancamentos:
            if lancamento.origem:
                # Verificar se há strings que não são números
                origens = [o.strip() for o in lancamento.origem.split(';') if o.strip()]
                
                for origem in origens:
                    # Verificar se é um padrão M/T seguido de números
                    if origem.startswith(('M', 'T')):
                        numero_part = origem[1:]  # Remove M ou T
                        try:
                            int(numero_part)
                        except ValueError:
                            lancamentos_problematicos.append({
                                'lancamento': lancamento,
                                'origem_problematica': origem,
                                'numero_part': numero_part
                            })
        
        self.stdout.write(f"Lançamentos com origens problemáticas: {len(lancamentos_problematicos)}")
        
        for item in lancamentos_problematicos:
            lanc = item['lancamento']
            origem_problematica = item['origem_problematica']
            numero_part = item['numero_part']
            
            self.stdout.write(f"   Lançamento ID: {lanc.id}")
            self.stdout.write(f"   Documento: {lanc.documento.numero}")
            self.stdout.write(f"   Origem completa: '{lanc.origem}'")
            self.stdout.write(f"   Origem problemática: '{origem_problematica}'")
            self.stdout.write(f"   Parte numérica: '{numero_part}'")
            self.stdout.write()
            
            if corrigir:
                self.corrigir_origem_lancamento(lanc, origem_problematica)

    def corrigir_origem_lancamento(self, lancamento, origem_problematica):
        """Corrige origem problemática de um lançamento"""
        self.stdout.write(f"   🔧 Corrigindo lançamento {lancamento.id}...")
        
        if lancamento.origem:
            # Remover a origem problemática
            origens = [o.strip() for o in lancamento.origem.split(';') if o.strip()]
            origens_corrigidas = [o for o in origens if o != origem_problematica]
            
            if len(origens_corrigidas) != len(origens):
                nova_origem = '; '.join(origens_corrigidas) if origens_corrigidas else ''
                lancamento.origem = nova_origem
                lancamento.save()
                self.stdout.write(f"   ✅ Origem corrigida: '{nova_origem}'")
            else:
                self.stdout.write(f"   ⚠️ Não foi necessário corrigir")

    def investigar_documentos_importados_duplicados(self, corrigir=False):
        """Investiga documentos importados duplicados"""
        self.stdout.write(f"\n🔍 INVESTIGANDO DOCUMENTOS IMPORTADOS DUPLICADOS")
        self.stdout.write("-" * 50)
        
        # Buscar documentos que têm múltiplos registros de importação
        documentos_duplicados = DocumentoImportado.objects.values('documento').annotate(
            count=Count('documento')
        ).filter(count__gt=1)
        
        self.stdout.write(f"Documentos com múltiplos registros de importação: {documentos_duplicados.count()}")
        
        for item in documentos_duplicados:
            documento_id = item['documento']
            count = item['count']
            
            documento = Documento.objects.get(id=documento_id)
            importacoes = DocumentoImportado.objects.filter(documento=documento).order_by('id')
            
            self.stdout.write(f"\n   Documento: {documento.numero} (ID: {documento.id})")
            self.stdout.write(f"   Total de importações: {count}")
            
            for i, importacao in enumerate(importacoes, 1):
                self.stdout.write(f"     Importação {i}:")
                self.stdout.write(f"       ID: {importacao.id}")
                self.stdout.write(f"       Imóvel origem: {importacao.imovel_origem.matricula}")
                self.stdout.write(f"       Data: {importacao.data_importacao}")
                self.stdout.write(f"       Importado por: {importacao.importado_por.username if importacao.importado_por else 'Sistema'}")
            
            if corrigir:
                self.corrigir_documento_importado_duplicado(documento, importacoes)

    def corrigir_documento_importado_duplicado(self, documento, importacoes):
        """Corrige documento com múltiplos registros de importação"""
        self.stdout.write(f"   🔧 Corrigindo documento {documento.numero}...")
        
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

    def testar_funcao_ordenacao(self):
        """Testa a função de ordenação que estava causando erro"""
        self.stdout.write(f"\n🧪 TESTANDO FUNÇÃO DE ORDENAÇÃO")
        self.stdout.write("-" * 50)
        
        def origem_sort_key(origem):
            if origem.startswith('M'):
                return (0, -int(origem.replace('M', '')))
            if origem.startswith('T'):
                return (1, -int(origem.replace('T', '')))
            return (2, origem)
        
        # Testar com origens válidas
        origens_validas = ['M123', 'M456', 'T789', 'T123', 'M999']
        self.stdout.write(f"Origens válidas: {origens_validas}")
        
        try:
            origens_validas.sort(key=origem_sort_key)
            self.stdout.write(f"✅ Ordenação válida: {origens_validas}")
        except Exception as e:
            self.stdout.write(f"❌ Erro na ordenação válida: {str(e)}")
        
        # Testar com origem problemática
        origem_problematica = 'Município de Guaíra'
        self.stdout.write(f"\nOrigem problemática: '{origem_problematica}'")
        
        try:
            resultado = origem_sort_key(origem_problematica)
            self.stdout.write(f"✅ Resultado: {resultado}")
        except Exception as e:
            self.stdout.write(f"❌ Erro: {str(e)}")
            
            # Mostrar como corrigir
            self.stdout.write(f"💡 Correção: A origem '{origem_problematica}' não é um padrão válido (M/T + números)")
            self.stdout.write(f"   Deve ser removida ou corrigida para um formato válido")
