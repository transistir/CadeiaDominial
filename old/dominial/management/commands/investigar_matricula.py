from django.core.management.base import BaseCommand
from dominial.models import Documento, Lancamento
from django.db.models import Count


class Command(BaseCommand):
    help = 'Investiga uma matrícula específica em detalhes para escolha manual'

    def add_arguments(self, parser):
        parser.add_argument('numero', type=str, help='Número da matrícula/transcrição para investigar')
        parser.add_argument(
            '--cartorio',
            type=str,
            help='Nome do cartório (opcional)'
        )
        parser.add_argument(
            '--detalhes',
            action='store_true',
            help='Mostrar detalhes completos dos lançamentos'
        )
        parser.add_argument(
            '--comparar',
            action='store_true',
            help='Mostrar comparação detalhada entre documentos duplicados'
        )

    def handle(self, *args, **options):
        numero = options['numero']
        cartorio_nome = options['cartorio']
        mostrar_detalhes = options['detalhes']
        comparar = options['comparar']
        
        self.stdout.write(f"🔍 INVESTIGANDO MATRÍCULA: {numero}")
        self.stdout.write("=" * 60)
        
        # Construir filtros
        filtros = {'numero': numero}
        if cartorio_nome:
            filtros['cartorio__nome__icontains'] = cartorio_nome
        
        # Buscar documentos
        documentos = Documento.objects.filter(**filtros).select_related(
            'cartorio', 'imovel', 'imovel__terra_indigena_id', 'tipo'
        ).prefetch_related(
            'lancamentos', 
            'lancamentos__tipo',
            'lancamentos__transmitente',
            'lancamentos__adquirente',
            'lancamentos__pessoas'
        )
        
        if not documentos.exists():
            self.stdout.write(f"❌ Nenhum documento encontrado com número: {numero}")
            if cartorio_nome:
                self.stdout.write(f"   Filtro de cartório: {cartorio_nome}")
            return
        
        # Mostrar resumo
        self.stdout.write(f"\n📊 RESUMO ENCONTRADO:")
        self.stdout.write(f"   Total de documentos: {documentos.count()}")
        
        # Agrupar por cartório
        por_cartorio = {}
        for doc in documentos:
            cartorio_nome = doc.cartorio.nome
            if cartorio_nome not in por_cartorio:
                por_cartorio[cartorio_nome] = []
            por_cartorio[cartorio_nome].append(doc)
        
        # Mostrar detalhes por cartório
        for cartorio_nome, docs in por_cartorio.items():
            self.stdout.write(f"\n🏛️ CARTÓRIO: {cartorio_nome}")
            self.stdout.write("-" * 40)
            
            if len(docs) > 1:
                self.stdout.write(f"⚠️ ATENÇÃO: {len(docs)} documentos encontrados neste cartório!")
            
            for i, doc in enumerate(docs, 1):
                self.stdout.write(f"\n   📄 Documento {i}:")
                self.stdout.write(f"      ID: {doc.id}")
                self.stdout.write(f"      Tipo: {doc.tipo.get_tipo_display()}")
                self.stdout.write(f"      Data: {doc.data}")
                self.stdout.write(f"      Livro: {doc.livro}")
                self.stdout.write(f"      Folha: {doc.folha}")
                self.stdout.write(f"      Imóvel: {doc.imovel.matricula}")
                self.stdout.write(f"      TIs: {doc.imovel.terra_indigena_id.nome}")
                
                # Contar lançamentos
                lancamentos = doc.lancamentos.all()
                self.stdout.write(f"      Lançamentos: {lancamentos.count()}")
                
                if mostrar_detalhes and lancamentos.exists():
                    self.stdout.write(f"      Detalhes dos lançamentos:")
                    for j, lanc in enumerate(lancamentos, 1):
                        self.stdout.write(f"        {j}. ID: {lanc.id}")
                        self.stdout.write(f"           Tipo: {lanc.tipo.get_tipo_display()}")
                        self.stdout.write(f"           Número: {lanc.numero_lancamento}")
                        self.stdout.write(f"           Data: {lanc.data}")
                        if lanc.transmitente:
                            self.stdout.write(f"           Transmitente: {lanc.transmitente.nome}")
                        if lanc.adquirente:
                            self.stdout.write(f"           Adquirente: {lanc.adquirente.nome}")
                        if lanc.area:
                            self.stdout.write(f"           Área: {lanc.area}")
                        if lanc.valor_transacao:
                            self.stdout.write(f"           Valor: R$ {lanc.valor_transacao}")
                        if lanc.observacoes:
                            self.stdout.write(f"           Observações: {lanc.observacoes}")
                        
                        # Mostrar pessoas do lançamento
                        pessoas = lanc.pessoas.all()
                        if pessoas.exists():
                            self.stdout.write(f"           Pessoas:")
                            for pessoa in pessoas:
                                self.stdout.write(f"             - {pessoa.pessoa.nome} ({pessoa.get_tipo_display()})")
                        
                        self.stdout.write("")
        
        # Se há duplicatas e foi solicitada comparação
        if documentos.count() > 1 and comparar:
            self.stdout.write(f"\n📋 COMPARAÇÃO DETALHADA DOS DOCUMENTOS:")
            self.stdout.write("=" * 60)
            
            docs_list = list(documentos)
            for i, doc1 in enumerate(docs_list):
                for j, doc2 in enumerate(docs_list[i+1:], i+1):
                    self.stdout.write(f"\n🔍 Comparando Documento {i+1} vs Documento {j+1}:")
                    self.stdout.write(f"   Documento {i+1} (ID: {doc1.id}):")
                    self.stdout.write(f"      Lançamentos: {doc1.lancamentos.count()}")
                    self.stdout.write(f"      Data: {doc1.data}")
                    self.stdout.write(f"      Livro/Folha: {doc1.livro}/{doc1.folha}")
                    
                    self.stdout.write(f"   Documento {j+1} (ID: {doc2.id}):")
                    self.stdout.write(f"      Lançamentos: {doc2.lancamentos.count()}")
                    self.stdout.write(f"      Data: {doc2.data}")
                    self.stdout.write(f"      Livro/Folha: {doc2.livro}/{doc2.folha}")
                    
                    # Comparar lançamentos
                    lanc1_ids = set(doc1.lancamentos.values_list('id', flat=True))
                    lanc2_ids = set(doc2.lancamentos.values_list('id', flat=True))
                    
                    lanc_iguais = lanc1_ids.intersection(lanc2_ids)
                    lanc_apenas_1 = lanc1_ids - lanc2_ids
                    lanc_apenas_2 = lanc2_ids - lanc1_ids
                    
                    self.stdout.write(f"   📊 Análise dos lançamentos:")
                    self.stdout.write(f"      Lançamentos iguais: {len(lanc_iguais)}")
                    self.stdout.write(f"      Apenas no Doc {i+1}: {len(lanc_apenas_1)}")
                    self.stdout.write(f"      Apenas no Doc {j+1}: {len(lanc_apenas_2)}")
                    
                    if len(lanc_iguais) > 0:
                        self.stdout.write(f"      ⚠️ ATENÇÃO: Há {len(lanc_iguais)} lançamentos duplicados!")
        
        # Verificar se há duplicatas
        if documentos.count() > 1:
            self.stdout.write(f"\n🚨 PROBLEMA IDENTIFICADO:")
            self.stdout.write(f"   Existem {documentos.count()} documentos com o mesmo número!")
            self.stdout.write(f"   Isso pode indicar uma duplicata no sistema.")
            
            # Mostrar diferenças entre os documentos
            self.stdout.write(f"\n📋 RESUMO DOS DOCUMENTOS:")
            for i, doc in enumerate(documentos, 1):
                self.stdout.write(f"   Documento {i}:")
                self.stdout.write(f"      ID: {doc.id}")
                self.stdout.write(f"      Cartório: {doc.cartorio.nome}")
                self.stdout.write(f"      Imóvel: {doc.imovel.matricula}")
                self.stdout.write(f"      Lançamentos: {doc.lancamentos.count()}")
                self.stdout.write(f"      Data: {doc.data}")
                self.stdout.write(f"      Livro/Folha: {doc.livro}/{doc.folha}")
                self.stdout.write("")
        
        # Estatísticas
        total_lancamentos = sum(doc.lancamentos.count() for doc in documentos)
        self.stdout.write(f"\n📊 ESTATÍSTICAS:")
        self.stdout.write(f"   Total de documentos: {documentos.count()}")
        self.stdout.write(f"   Total de lançamentos: {total_lancamentos}")
        self.stdout.write(f"   Média de lançamentos por documento: {total_lancamentos / documentos.count():.2f}")
        
        # Recomendações para escolha manual
        self.stdout.write(f"\n💡 RECOMENDAÇÕES PARA ESCOLHA MANUAL:")
        if documentos.count() > 1:
            self.stdout.write(f"   ❌ DUPLICATA DETECTADA: Existem {documentos.count()} documentos com o mesmo número")
            self.stdout.write(f"   🔍 CRITÉRIOS PARA ESCOLHA:")
            self.stdout.write(f"      1. Documento com mais lançamentos")
            self.stdout.write(f"      2. Documento com data mais recente")
            self.stdout.write(f"      3. Documento com livro/folha preenchidos")
            self.stdout.write(f"      4. Documento com lançamentos mais completos")
            self.stdout.write(f"   🛠️ AÇÕES SUGERIDAS:")
            self.stdout.write(f"      1. Analisar cada documento em detalhes")
            self.stdout.write(f"      2. Verificar se há lançamentos duplicados")
            self.stdout.write(f"      3. Escolher qual documento manter")
            self.stdout.write(f"      4. Mover lançamentos importantes para o documento escolhido")
            self.stdout.write(f"      5. Remover documento(s) incorreto(s) manualmente")
        else:
            self.stdout.write(f"   ✅ Nenhuma duplicata encontrada")
        
        if any(doc.lancamentos.count() == 0 for doc in documentos):
            self.stdout.write(f"   ⚠️ Documentos sem lançamentos encontrados")
        
        self.stdout.write(f"\n✅ Investigação concluída!")
        self.stdout.write(f"\n💡 PRÓXIMOS PASSOS:")
        self.stdout.write(f"   1. Use '--detalhes' para ver todos os lançamentos")
        self.stdout.write(f"   2. Use '--comparar' para análise detalhada de duplicatas")
        self.stdout.write(f"   3. Acesse o admin para fazer as correções manualmente") 