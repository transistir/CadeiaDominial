from django.core.management.base import BaseCommand
from dominial.models import Pessoas
from django.db.models import Count
from django.db import transaction


class Command(BaseCommand):
    help = 'Investiga e corrige pessoas duplicadas que causam erro MultipleObjectsReturned'

    def add_arguments(self, parser):
        parser.add_argument(
            '--corrigir',
            action='store_true',
            help='Executar correção automática das duplicatas'
        )
        parser.add_argument(
            '--nome',
            type=str,
            help='Nome específico para investigar'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Mostrar o que seria feito sem executar as correções'
        )

    def handle(self, *args, **options):
        self.stdout.write("🔍 INVESTIGANDO PESSOAS DUPLICADAS")
        self.stdout.write("=" * 60)
        
        # Buscar pessoas com nomes duplicados
        pessoas_duplicadas = Pessoas.objects.values('nome').annotate(
            count=Count('id')
        ).filter(count__gt=1).order_by('nome')
        
        if not pessoas_duplicadas.exists():
            self.stdout.write("✅ Nenhuma pessoa duplicada encontrada!")
            return
        
        self.stdout.write(f"📊 Encontradas {len(pessoas_duplicadas)} pessoas com nomes duplicados")
        self.stdout.write("")
        
        total_corrigidas = 0
        
        for dup in pessoas_duplicadas:
            nome = dup['nome']
            
            # Filtrar por nome específico se fornecido
            if options['nome'] and options['nome'].lower() not in nome.lower():
                continue
            
            self.stdout.write(f"🔍 PESSOA DUPLICADA: '{nome}'")
            self.stdout.write("-" * 50)
            
            # Buscar todas as pessoas com este nome
            pessoas = Pessoas.objects.filter(nome=nome).order_by('id')
            
            self.stdout.write(f"   Encontradas {pessoas.count()} pessoas com este nome:")
            self.stdout.write("")
            
            for i, pessoa in enumerate(pessoas, 1):
                self.stdout.write(f"   👤 Pessoa {i} (ID: {pessoa.id}):")
                self.stdout.write(f"      Nome: {pessoa.nome}")
                self.stdout.write(f"      CPF: {pessoa.cpf or 'Não informado'}")
                self.stdout.write(f"      RG: {pessoa.rg or 'Não informado'}")
                self.stdout.write(f"      Email: {pessoa.email or 'Não informado'}")
                self.stdout.write(f"      Telefone: {pessoa.telefone or 'Não informado'}")
                self.stdout.write(f"      Data Nascimento: {pessoa.data_nascimento or 'Não informada'}")
                
                # Verificar relacionamentos
                imoveis_proprietario = pessoa.imovel_set.count()
                lancamentos_transmitente = pessoa.lancamento_set.filter(tipo__tipo='transmissao').count()
                lancamentos_adquirente = pessoa.lancamento_set.filter(tipo__tipo='aquisicao').count()
                
                self.stdout.write(f"      Relacionamentos:")
                self.stdout.write(f"        - Imóveis como proprietário: {imoveis_proprietario}")
                self.stdout.write(f"        - Lançamentos como transmitente: {lancamentos_transmitente}")
                self.stdout.write(f"        - Lançamentos como adquirente: {lancamentos_adquirente}")
                self.stdout.write("")
            
            # Sugestões para correção
            self.stdout.write(f"   💡 SUGESTÕES PARA CORREÇÃO:")
            
            # Ordenar por quantidade de relacionamentos
            pessoas_com_relacionamentos = []
            for pessoa in pessoas:
                total_relacionamentos = (
                    pessoa.imovel_set.count() +
                    pessoa.lancamento_set.count()
                )
                pessoas_com_relacionamentos.append((pessoa, total_relacionamentos))
            
            pessoas_com_relacionamentos.sort(key=lambda x: x[1], reverse=True)
            
            self.stdout.write(f"      📊 Por número de relacionamentos:")
            for k, (pessoa, count) in enumerate(pessoas_com_relacionamentos, 1):
                self.stdout.write(f"         {k}. Pessoa ID {pessoa.id}: {count} relacionamentos")
            
            # Verificar qual tem mais dados preenchidos
            pessoas_com_dados = []
            for pessoa in pessoas:
                dados_preenchidos = sum([
                    1 if pessoa.cpf else 0,
                    1 if pessoa.rg else 0,
                    1 if pessoa.email else 0,
                    1 if pessoa.telefone else 0,
                    1 if pessoa.data_nascimento else 0
                ])
                pessoas_com_dados.append((pessoa, dados_preenchidos))
            
            pessoas_com_dados.sort(key=lambda x: x[1], reverse=True)
            
            self.stdout.write(f"      📝 Por dados preenchidos:")
            for k, (pessoa, count) in enumerate(pessoas_com_dados, 1):
                self.stdout.write(f"         {k}. Pessoa ID {pessoa.id}: {count} campos preenchidos")
            
            # Executar correção se solicitado
            if options['corrigir'] and not options['dry_run']:
                self.stdout.write(f"   🛠️ EXECUTANDO CORREÇÃO...")
                
                try:
                    with transaction.atomic():
                        # Manter a pessoa com mais relacionamentos
                        pessoa_principal = pessoas_com_relacionamentos[0][0]
                        pessoas_para_remover = [p for p, _ in pessoas_com_relacionamentos[1:]]
                        
                        # Mover relacionamentos para a pessoa principal
                        for pessoa_remover in pessoas_para_remover:
                            # Mover imóveis
                            for imovel in pessoa_remover.imovel_set.all():
                                imovel.proprietario = pessoa_principal
                                imovel.save()
                            
                            # Mover lançamentos como transmitente
                            for lancamento in pessoa_remover.lancamento_set.filter(tipo__tipo='transmissao'):
                                lancamento.transmitente = pessoa_principal
                                lancamento.save()
                            
                            # Mover lançamentos como adquirente
                            for lancamento in pessoa_remover.lancamento_set.filter(tipo__tipo='aquisicao'):
                                lancamento.adquirente = pessoa_principal
                                lancamento.save()
                            
                            # Remover pessoa duplicada
                            pessoa_remover.delete()
                        
                        self.stdout.write(f"      ✅ Correção executada! Mantida pessoa ID {pessoa_principal.id}")
                        total_corrigidas += len(pessoas_para_remover)
                        
                except Exception as e:
                    self.stdout.write(f"      ❌ Erro na correção: {str(e)}")
            
            elif options['dry_run']:
                self.stdout.write(f"   🔍 DRY RUN - O que seria feito:")
                pessoa_principal = pessoas_com_relacionamentos[0][0]
                pessoas_para_remover = [p for p, _ in pessoas_com_relacionamentos[1:]]
                
                self.stdout.write(f"      - Manteria pessoa ID {pessoa_principal.id}")
                self.stdout.write(f"      - Removeria {len(pessoas_para_remover)} pessoas duplicadas")
                for p in pessoas_para_remover:
                    self.stdout.write(f"        * Pessoa ID {p.id}")
            
            self.stdout.write("")
            self.stdout.write("=" * 60)
            self.stdout.write("")
        
        if options['corrigir'] and not options['dry_run']:
            self.stdout.write(f"✅ Correção concluída! {total_corrigidas} pessoas duplicadas removidas.")
        elif options['dry_run']:
            self.stdout.write(f"🔍 Dry run concluído!")
        
        self.stdout.write(f"\n💡 PRÓXIMOS PASSOS:")
        self.stdout.write(f"   1. Use '--corrigir' para executar as correções")
        self.stdout.write(f"   2. Use '--dry-run' para ver o que seria feito")
        self.stdout.write(f"   3. Use '--nome \"Nome Específico\"' para focar em uma pessoa") 