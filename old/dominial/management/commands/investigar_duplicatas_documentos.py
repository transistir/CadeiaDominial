from django.core.management.base import BaseCommand
from django.db.models import Count, Q
from dominial.models import Documento, Lancamento
from datetime import datetime


class Command(BaseCommand):
    help = 'Investiga duplicatas de documentos e problemas de integridade'

    def add_arguments(self, parser):
        parser.add_argument(
            '--tipo',
            type=str,
            choices=['matricula', 'transcricao'],
            help='Tipo específico de documento para investigar'
        )
        parser.add_argument(
            '--cartorio',
            type=str,
            help='Nome do cartório para filtrar'
        )
        parser.add_argument(
            '--exportar',
            action='store_true',
            help='Exportar resultados para arquivo CSV'
        )

    def handle(self, *args, **options):
        self.stdout.write("🔍 INICIANDO INVESTIGAÇÃO DE DUPLICATAS")
        self.stdout.write("=" * 60)
        
        # Filtros
        filtros = {}
        if options['tipo']:
            filtros['tipo__tipo'] = options['tipo']
        if options['cartorio']:
            filtros['cartorio__nome__icontains'] = options['cartorio']
        
        # 1. Buscar duplicatas por número e cartório
        self.stdout.write("\n📊 1. ANÁLISE DE DUPLICATAS POR NÚMERO E CARTÓRIO")
        self.stdout.write("-" * 50)
        
        duplicatas = Documento.objects.filter(**filtros).values(
            'numero', 'cartorio__nome', 'cartorio__id'
        ).annotate(
            count=Count('id')
        ).filter(count__gt=1).order_by('numero', 'cartorio__nome')
        
        if duplicatas:
            self.stdout.write(f"❌ Encontradas {len(duplicatas)} combinações duplicadas:")
            for dup in duplicatas:
                self.stdout.write(f"   - Número: {dup['numero']}")
                self.stdout.write(f"     Cartório: {dup['cartorio__nome']}")
                self.stdout.write(f"     Quantidade: {dup['count']} documentos")
                
                # Mostrar detalhes dos documentos duplicados
                docs = Documento.objects.filter(
                    numero=dup['numero'],
                    cartorio__id=dup['cartorio__id']
                ).select_related('imovel', 'tipo').prefetch_related('lancamentos')
                
                for i, doc in enumerate(docs, 1):
                    lancamentos_count = doc.lancamentos.count()
                    self.stdout.write(f"     {i}. ID: {doc.id}, Imóvel: {doc.imovel.matricula}, "
                                   f"Lançamentos: {lancamentos_count}, Data: {doc.data}")
                self.stdout.write("")
        else:
            self.stdout.write("✅ Nenhuma duplicata encontrada!")
        
        # 2. Análise de documentos sem lançamentos
        self.stdout.write("\n📋 2. ANÁLISE DE DOCUMENTOS SEM LANÇAMENTOS")
        self.stdout.write("-" * 50)
        
        docs_sem_lancamentos = Documento.objects.filter(**filtros).annotate(
            lancamentos_count=Count('lancamentos')
        ).filter(lancamentos_count=0)
        
        if docs_sem_lancamentos:
            self.stdout.write(f"⚠️ Encontrados {docs_sem_lancamentos.count()} documentos sem lançamentos:")
            for doc in docs_sem_lancamentos[:10]:  # Mostrar apenas os primeiros 10
                self.stdout.write(f"   - ID: {doc.id}, Número: {doc.numero}, "
                               f"Cartório: {doc.cartorio.nome}, Imóvel: {doc.imovel.matricula}")
            if docs_sem_lancamentos.count() > 10:
                self.stdout.write(f"   ... e mais {docs_sem_lancamentos.count() - 10} documentos")
        else:
            self.stdout.write("✅ Todos os documentos possuem lançamentos!")
        
        # 3. Análise de documentos com muitos lançamentos
        self.stdout.write("\n📈 3. ANÁLISE DE DOCUMENTOS COM MUITOS LANÇAMENTOS")
        self.stdout.write("-" * 50)
        
        docs_com_muitos_lancamentos = Documento.objects.filter(**filtros).annotate(
            lancamentos_count=Count('lancamentos')
        ).filter(lancamentos_count__gt=5).order_by('-lancamentos_count')
        
        if docs_com_muitos_lancamentos:
            self.stdout.write(f"📊 Encontrados {docs_com_muitos_lancamentos.count()} documentos com mais de 5 lançamentos:")
            for doc in docs_com_muitos_lancamentos[:10]:
                self.stdout.write(f"   - ID: {doc.id}, Número: {doc.numero}, "
                               f"Cartório: {doc.cartorio.nome}, Lançamentos: {doc.lancamentos_count}")
        else:
            self.stdout.write("✅ Nenhum documento com mais de 5 lançamentos encontrado!")
        
        # 4. Estatísticas gerais
        self.stdout.write("\n📊 4. ESTATÍSTICAS GERAIS")
        self.stdout.write("-" * 50)
        
        total_docs = Documento.objects.filter(**filtros).count()
        total_lancamentos = Lancamento.objects.filter(documento__in=Documento.objects.filter(**filtros)).count()
        
        docs_com_lancamentos = Documento.objects.filter(**filtros).annotate(
            lancamentos_count=Count('lancamentos')
        ).filter(lancamentos_count__gt=0).count()
        
        docs_sem_lancamentos_count = total_docs - docs_com_lancamentos
        
        self.stdout.write(f"   Total de documentos: {total_docs}")
        self.stdout.write(f"   Total de lançamentos: {total_lancamentos}")
        self.stdout.write(f"   Documentos com lançamentos: {docs_com_lancamentos}")
        self.stdout.write(f"   Documentos sem lançamentos: {docs_sem_lancamentos_count}")
        
        if total_docs > 0:
            media_lancamentos = total_lancamentos / total_docs
            self.stdout.write(f"   Média de lançamentos por documento: {media_lancamentos:.2f}")
        
        # 5. Exportar para CSV se solicitado
        if options['exportar']:
            self.exportar_csv(duplicatas, docs_sem_lancamentos, docs_com_muitos_lancamentos)
        
        self.stdout.write("\n✅ Investigação concluída!")
    
    def exportar_csv(self, duplicatas, docs_sem_lancamentos, docs_com_muitos_lancamentos):
        """
        Exporta os resultados para arquivo CSV
        """
        import csv
        from django.utils import timezone
        
        timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
        filename = f'investigacao_duplicatas_{timestamp}.csv'
        
        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            
            # Cabeçalho
            writer.writerow(['Tipo', 'Número', 'Cartório', 'ID', 'Imóvel', 'Lançamentos', 'Data'])
            
            # Duplicatas
            for dup in duplicatas:
                docs = Documento.objects.filter(
                    numero=dup['numero'],
                    cartorio__id=dup['cartorio__id']
                ).select_related('imovel', 'tipo').prefetch_related('lancamentos')
                
                for doc in docs:
                    writer.writerow([
                        'DUPLICATA',
                        doc.numero,
                        doc.cartorio.nome,
                        doc.id,
                        doc.imovel.matricula,
                        doc.lancamentos.count(),
                        doc.data
                    ])
            
            # Documentos sem lançamentos
            for doc in docs_sem_lancamentos:
                writer.writerow([
                    'SEM_LANCAMENTOS',
                    doc.numero,
                    doc.cartorio.nome,
                    doc.id,
                    doc.imovel.matricula,
                    0,
                    doc.data
                ])
            
            # Documentos com muitos lançamentos
            for doc in docs_com_muitos_lancamentos:
                writer.writerow([
                    'MUITOS_LANCAMENTOS',
                    doc.numero,
                    doc.cartorio.nome,
                    doc.id,
                    doc.imovel.matricula,
                    doc.lancamentos.count(),
                    doc.data
                ])
        
        self.stdout.write(f"📄 Resultados exportados para: {filename}") 