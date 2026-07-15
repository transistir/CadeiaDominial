from django.core.management.base import BaseCommand
from dominial.models import Documento, Lancamento
from django.db.models import Count


class Command(BaseCommand):
    help = 'Lista duplicatas de documentos para escolha manual'

    def add_arguments(self, parser):
        parser.add_argument(
            '--tipo',
            type=str,
            choices=['matricula', 'transcricao'],
            help='Tipo específico de documento para listar'
        )
        parser.add_argument(
            '--cartorio',
            type=str,
            help='Nome do cartório para filtrar'
        )
        parser.add_argument(
            '--detalhes',
            action='store_true',
            help='Mostrar detalhes dos lançamentos'
        )

    def handle(self, *args, **options):
        self.stdout.write("📋 LISTANDO DUPLICATAS PARA ESCOLHA MANUAL")
        self.stdout.write("=" * 60)
        
        # Filtros
        filtros = {}
        if options['tipo']:
            filtros['tipo__tipo'] = options['tipo']
        if options['cartorio']:
            filtros['cartorio__nome__icontains'] = options['cartorio']
        
        # Buscar duplicatas
        duplicatas = Documento.objects.filter(**filtros).values(
            'numero', 'cartorio__nome', 'cartorio__id'
        ).annotate(
            count=Count('id')
        ).filter(count__gt=1).order_by('numero', 'cartorio__nome')
        
        if not duplicatas.exists():
            self.stdout.write("✅ Nenhuma duplicata encontrada!")
            return
        
        self.stdout.write(f"📊 Encontradas {len(duplicatas)} combinações duplicadas")
        self.stdout.write("")
        
        for i, dup in enumerate(duplicatas, 1):
            self.stdout.write(f"🔍 DUPLICATA {i}: {dup['numero']} - {dup['cartorio__nome']}")
            self.stdout.write("-" * 50)
            
            # Buscar documentos duplicados
            docs = Documento.objects.filter(
                numero=dup['numero'],
                cartorio__id=dup['cartorio__id']
            ).select_related('imovel', 'tipo').prefetch_related('lancamentos').order_by('id')
            
            self.stdout.write(f"   Encontrados {docs.count()} documentos:")
            self.stdout.write("")
            
            for j, doc in enumerate(docs, 1):
                lancamentos = doc.lancamentos.all()
                self.stdout.write(f"   📄 Documento {j} (ID: {doc.id}):")
                self.stdout.write(f"      Tipo: {doc.tipo.get_tipo_display()}")
                self.stdout.write(f"      Data: {doc.data}")
                self.stdout.write(f"      Livro/Folha: {doc.livro}/{doc.folha}")
                self.stdout.write(f"      Imóvel: {doc.imovel.matricula}")
                self.stdout.write(f"      TIs: {doc.imovel.terra_indigena_id.nome}")
                self.stdout.write(f"      Lançamentos: {lancamentos.count()}")
                
                if options['detalhes'] and lancamentos.exists():
                    self.stdout.write(f"      Detalhes dos lançamentos:")
                    for k, lanc in enumerate(lancamentos, 1):
                        self.stdout.write(f"        {k}. ID: {lanc.id} - {lanc.tipo.get_tipo_display()}")
                        self.stdout.write(f"           Número: {lanc.numero_lancamento}")
                        self.stdout.write(f"           Data: {lanc.data}")
                        if lanc.transmitente:
                            self.stdout.write(f"           Transmitente: {lanc.transmitente.nome}")
                        if lanc.adquirente:
                            self.stdout.write(f"           Adquirente: {lanc.adquirente.nome}")
                        if lanc.area:
                            self.stdout.write(f"           Área: {lanc.area}")
                        self.stdout.write("")
                
                self.stdout.write("")
            
            # Sugestões para esta duplicata
            self.stdout.write(f"   💡 SUGESTÕES PARA ESCOLHA:")
            
            # Ordenar por número de lançamentos
            docs_com_lancamentos = [(doc, doc.lancamentos.count()) for doc in docs]
            docs_com_lancamentos.sort(key=lambda x: x[1], reverse=True)
            
            self.stdout.write(f"      📊 Por número de lançamentos:")
            for k, (doc, count) in enumerate(docs_com_lancamentos, 1):
                self.stdout.write(f"         {k}. Documento ID {doc.id}: {count} lançamentos")
            
            # Ordenar por data
            docs_por_data = sorted(docs, key=lambda x: x.data, reverse=True)
            self.stdout.write(f"      📅 Por data (mais recente primeiro):")
            for k, doc in enumerate(docs_por_data, 1):
                self.stdout.write(f"         {k}. Documento ID {doc.id}: {doc.data}")
            
            # Verificar se há livro/folha preenchidos
            docs_com_livro_folha = [doc for doc in docs if doc.livro and doc.livro != '0' and doc.folha and doc.folha != '0']
            if docs_com_livro_folha:
                self.stdout.write(f"      📚 Com livro/folha preenchidos:")
                for k, doc in enumerate(docs_com_livro_folha, 1):
                    self.stdout.write(f"         {k}. Documento ID {doc.id}: Livro {doc.livro}, Folha {doc.folha}")
            else:
                self.stdout.write(f"      ⚠️ Nenhum documento com livro/folha preenchidos")
            
            self.stdout.write("")
            self.stdout.write(f"   🛠️ AÇÕES SUGERIDAS:")
            self.stdout.write(f"      1. Analisar cada documento em detalhes")
            self.stdout.write(f"      2. Escolher qual documento manter")
            self.stdout.write(f"      3. Mover lançamentos importantes se necessário")
            self.stdout.write(f"      4. Remover documento(s) incorreto(s) manualmente")
            self.stdout.write("")
            self.stdout.write("=" * 60)
            self.stdout.write("")
        
        self.stdout.write(f"✅ Listagem concluída!")
        self.stdout.write(f"\n💡 PRÓXIMOS PASSOS:")
        self.stdout.write(f"   1. Use '--detalhes' para ver todos os lançamentos")
        self.stdout.write(f"   2. Use 'investigar_matricula <numero>' para análise específica")
        self.stdout.write(f"   3. Acesse o admin para fazer as correções manualmente") 