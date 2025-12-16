"""
Comando para verificar se a migração de constraint de matrícula é segura.
Verifica se há dados que podem ser afetados pela mudança.
"""

from django.core.management.base import BaseCommand
from django.db.models import Count
from dominial.models import Imovel


class Command(BaseCommand):
    help = 'Verifica se a migração de constraint de matrícula é segura para produção'

    def handle(self, *args, **options):
        self.stdout.write("🔍 VERIFICAÇÃO DE SEGURANÇA DA MIGRAÇÃO DE MATRÍCULA")
        self.stdout.write("=" * 70)
        
        # 1. Verificar se há matrículas duplicadas (isso seria um problema)
        self.stdout.write("\n1️⃣ VERIFICANDO MATRÍCULAS DUPLICADAS (mesmo cartório)")
        self.stdout.write("-" * 70)
        
        # Agrupar por matrícula e cartório para encontrar duplicatas
        duplicatas = Imovel.objects.values('matricula', 'cartorio').annotate(
            count=Count('id')
        ).filter(count__gt=1)
        
        if duplicatas.exists():
            self.stdout.write("❌ PROBLEMA ENCONTRADO: Existem matrículas duplicadas no mesmo cartório!")
            for dup in duplicatas:
                matricula = dup['matricula']
                cartorio_id = dup['cartorio']
                count = dup['count']
                cartorio_nome = "Sem cartório" if not cartorio_id else \
                    Imovel.objects.filter(cartorio_id=cartorio_id).first().cartorio.nome if cartorio_id else "Sem cartório"
                self.stdout.write(f"   Matrícula: {matricula}, Cartório: {cartorio_nome} ({cartorio_id}), Ocorrências: {count}")
            self.stdout.write("\n⚠️  A migração pode falhar se houver duplicatas no mesmo cartório!")
            self.stdout.write("   Execute uma limpeza antes de aplicar a migração.")
        else:
            self.stdout.write("✅ Nenhuma duplicata encontrada no mesmo cartório. Migração segura!")
        
        # 2. Verificar matrículas que existem em múltiplos cartórios (isso é OK agora)
        self.stdout.write("\n2️⃣ VERIFICANDO MATRÍCULAS EM MÚLTIPLOS CARTÓRIOS (esperado)")
        self.stdout.write("-" * 70)
        
        matriculas_multi_cartorio = Imovel.objects.values('matricula').annotate(
            cartorios_count=Count('cartorio', distinct=True)
        ).filter(cartorios_count__gt=1)
        
        if matriculas_multi_cartorio.exists():
            self.stdout.write(f"ℹ️  Encontradas {matriculas_multi_cartorio.count()} matrículas em múltiplos cartórios:")
            for item in matriculas_multi_cartorio[:10]:  # Mostrar apenas as 10 primeiras
                matricula = item['matricula']
                count = item['cartorios_count']
                imoveis = Imovel.objects.filter(matricula=matricula).select_related('cartorio')
                self.stdout.write(f"   Matrícula: {matricula} ({count} cartórios diferentes)")
                for imovel in imoveis:
                    cartorio_nome = imovel.cartorio.nome if imovel.cartorio else "Sem cartório"
                    self.stdout.write(f"      - Cartório: {cartorio_nome} (ID: {imovel.id})")
            if matriculas_multi_cartorio.count() > 10:
                self.stdout.write(f"   ... e mais {matriculas_multi_cartorio.count() - 10} matrículas")
            self.stdout.write("\n✅ Isso é esperado e será permitido após a migração!")
        else:
            self.stdout.write("ℹ️  Nenhuma matrícula encontrada em múltiplos cartórios.")
        
        # 3. Verificar imóveis sem cartório
        self.stdout.write("\n3️⃣ VERIFICANDO IMÓVEIS SEM CARTÓRIO")
        self.stdout.write("-" * 70)
        
        imoveis_sem_cartorio = Imovel.objects.filter(cartorio__isnull=True)
        count_sem_cartorio = imoveis_sem_cartorio.count()
        
        if count_sem_cartorio > 0:
            self.stdout.write(f"⚠️  Encontrados {count_sem_cartorio} imóveis sem cartório:")
            # Verificar se há matrículas duplicadas entre imóveis sem cartório
            matriculas_sem_cartorio = imoveis_sem_cartorio.values('matricula').annotate(
                count=Count('id')
            ).filter(count__gt=1)
            
            if matriculas_sem_cartorio.exists():
                self.stdout.write("   ❌ PROBLEMA: Existem matrículas duplicadas entre imóveis sem cartório!")
                for item in matriculas_sem_cartorio:
                    matricula = item['matricula']
                    count = item['count']
                    self.stdout.write(f"      Matrícula: {matricula}, Ocorrências: {count}")
                self.stdout.write("\n   ⚠️  A constraint permitirá múltiplos registros com cartorio=NULL")
                self.stdout.write("   ⚠️  Considere atribuir cartórios a esses imóveis antes da migração.")
            else:
                self.stdout.write("   ✅ Nenhuma duplicata entre imóveis sem cartório.")
        else:
            self.stdout.write("✅ Todos os imóveis têm cartório definido!")
        
        # 4. Estatísticas gerais
        self.stdout.write("\n4️⃣ ESTATÍSTICAS GERAIS")
        self.stdout.write("-" * 70)
        
        total_imoveis = Imovel.objects.count()
        total_matriculas = Imovel.objects.values('matricula').distinct().count()
        total_cartorios = Imovel.objects.values('cartorio').distinct().count()
        
        self.stdout.write(f"   Total de imóveis: {total_imoveis}")
        self.stdout.write(f"   Total de matrículas únicas: {total_matriculas}")
        self.stdout.write(f"   Total de cartórios diferentes: {total_cartorios}")
        
        if total_imoveis > total_matriculas:
            self.stdout.write(f"\n   ℹ️  {total_imoveis - total_matriculas} imóveis compartilham matrículas")
            self.stdout.write("   ✅ Isso será permitido após a migração (desde que em cartórios diferentes)")
        
        # 5. Resumo final
        self.stdout.write("\n" + "=" * 70)
        self.stdout.write("📋 RESUMO DA VERIFICAÇÃO")
        self.stdout.write("=" * 70)
        
        problemas = []
        if duplicatas.exists():
            problemas.append("❌ Matrículas duplicadas no mesmo cartório")
        if imoveis_sem_cartorio.filter(
            matricula__in=Imovel.objects.values('matricula').annotate(
                count=Count('id')
            ).filter(count__gt=1).values_list('matricula', flat=True)
        ).exists():
            problemas.append("⚠️  Matrículas duplicadas entre imóveis sem cartório")
        
        if problemas:
            self.stdout.write("\n⚠️  PROBLEMAS ENCONTRADOS:")
            for problema in problemas:
                self.stdout.write(f"   {problema}")
            self.stdout.write("\n❌ NÃO APLIQUE A MIGRAÇÃO até resolver esses problemas!")
        else:
            self.stdout.write("\n✅ NENHUM PROBLEMA ENCONTRADO!")
            self.stdout.write("✅ A migração pode ser aplicada com segurança!")
            self.stdout.write("\n📝 PRÓXIMOS PASSOS:")
            self.stdout.write("   1. Fazer backup do banco de dados")
            self.stdout.write("   2. Aplicar a migração: python manage.py migrate")
            self.stdout.write("   3. Testar o cadastro de novos imóveis")
            self.stdout.write("   4. Verificar se comandos de management ainda funcionam")

