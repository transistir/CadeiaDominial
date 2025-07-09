#!/usr/bin/env python3
"""
Script para analisar a estrutura atual dos cartórios
e identificar possíveis problemas antes da implementação
"""

import os
import sys
import django

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'cadeia_dominial.settings_dev')
django.setup()

from dominial.models import Cartorios, Imovel, Documento, Lancamento, Alteracoes

def analisar_estrutura_atual():
    """Analisa a estrutura atual dos cartórios no sistema"""
    
    print("🔍 ANÁLISE DA ESTRUTURA ATUAL DOS CARTÓRIOS")
    print("=" * 60)
    
    # 1. Análise geral dos cartórios
    total_cartorios = Cartorios.objects.count()
    print(f"\n📊 ESTATÍSTICAS GERAIS:")
    print(f"   - Total de cartórios: {total_cartorios}")
    
    # 2. Análise de uso dos cartórios
    print(f"\n🔗 USO DOS CARTÓRIOS:")
    
    # Imóveis
    imoveis_com_cartorio = Imovel.objects.filter(cartorio__isnull=False).count()
    imoveis_sem_cartorio = Imovel.objects.filter(cartorio__isnull=True).count()
    print(f"   - Imóveis com cartório: {imoveis_com_cartorio}")
    print(f"   - Imóveis sem cartório: {imoveis_sem_cartorio}")
    
    # Documentos
    documentos_com_cartorio = Documento.objects.filter(cartorio__isnull=False).count()
    documentos_sem_cartorio = Documento.objects.filter(cartorio__isnull=True).count()
    print(f"   - Documentos com cartório: {documentos_com_cartorio}")
    print(f"   - Documentos sem cartório: {documentos_sem_cartorio}")
    
    # Lançamentos
    lancamentos_origem = Lancamento.objects.filter(cartorio_origem__isnull=False).count()
    lancamentos_transacao = Lancamento.objects.filter(cartorio_transacao__isnull=False).count()
    print(f"   - Lançamentos com cartório_origem: {lancamentos_origem}")
    print(f"   - Lançamentos com cartorio_transacao: {lancamentos_transacao}")
    
    # Alterações
    alteracoes_com_cartorio = Alteracoes.objects.filter(cartorio__isnull=False).count()
    alteracoes_com_cartorio_origem = Alteracoes.objects.filter(cartorio_origem__isnull=False).count()
    print(f"   - Alterações com cartório: {alteracoes_com_cartorio}")
    print(f"   - Alterações com cartorio_origem: {alteracoes_com_cartorio_origem}")
    
    # 3. Análise de cartórios mais usados
    print(f"\n🏆 CARTÓRIOS MAIS UTILIZADOS:")
    
    # Por imóveis
    cartorios_imoveis = Cartorios.objects.annotate(
        total_imoveis=models.Count('imovel')
    ).filter(total_imoveis__gt=0).order_by('-total_imoveis')[:5]
    
    print(f"   - Top 5 cartórios por imóveis:")
    for cartorio in cartorios_imoveis:
        print(f"     • {cartorio.nome}: {cartorio.total_imoveis} imóveis")
    
    # Por documentos
    cartorios_documentos = Cartorios.objects.annotate(
        total_documentos=models.Count('documento')
    ).filter(total_documentos__gt=0).order_by('-total_documentos')[:5]
    
    print(f"   - Top 5 cartórios por documentos:")
    for cartorio in cartorios_documentos:
        print(f"     • {cartorio.nome}: {cartorio.total_documentos} documentos")
    
    # 4. Análise de problemas potenciais
    print(f"\n⚠️  PROBLEMAS POTENCIAIS:")
    
    # Cartórios sem uso
    cartorios_sem_uso = Cartorios.objects.annotate(
        total_imoveis=models.Count('imovel'),
        total_documentos=models.Count('documento'),
        total_lancamentos_origem=models.Count('cartorio_origem_lancamento'),
        total_lancamentos_transacao=models.Count('cartorio_transacao_lancamento'),
        total_alteracoes=models.Count('alteracoes'),
        total_alteracoes_origem=models.Count('cartorio_responsavel')
    ).filter(
        total_imoveis=0,
        total_documentos=0,
        total_lancamentos_origem=0,
        total_lancamentos_transacao=0,
        total_alteracoes=0,
        total_alteracoes_origem=0
    ).count()
    
    print(f"   - Cartórios sem uso: {cartorios_sem_uso}")
    
    # Cartórios com dados inconsistentes
    cartorios_inconsistentes = Cartorios.objects.filter(
        models.Q(estado__isnull=True) |
        models.Q(cidade__isnull=True) |
        models.Q(cns='0') |
        models.Q(cns='')
    ).count()
    
    print(f"   - Cartórios com dados inconsistentes: {cartorios_inconsistentes}")
    
    # 5. Análise de estrutura de dados
    print(f"\n📋 ESTRUTURA DE DADOS:")
    
    # Campos obrigatórios vs opcionais
    cartorios_com_estado = Cartorios.objects.filter(estado__isnull=False).count()
    cartorios_com_cidade = Cartorios.objects.filter(cidade__isnull=False).count()
    cartorios_com_endereco = Cartorios.objects.filter(endereco__isnull=False).count()
    cartorios_com_telefone = Cartorios.objects.filter(telefone__isnull=False).count()
    cartorios_com_email = Cartorios.objects.filter(email__isnull=False).count()
    
    print(f"   - Cartórios com estado: {cartorios_com_estado}/{total_cartorios}")
    print(f"   - Cartórios com cidade: {cartorios_com_cidade}/{total_cartorios}")
    print(f"   - Cartórios com endereço: {cartorios_com_endereco}/{total_cartorios}")
    print(f"   - Cartórios com telefone: {cartorios_com_telefone}/{total_cartorios}")
    print(f"   - Cartórios com email: {cartorios_com_email}/{total_cartorios}")
    
    # 6. Recomendações
    print(f"\n💡 RECOMENDAÇÕES PARA IMPLEMENTAÇÃO:")
    
    print(f"   1. Migração segura:")
    print(f"      - Preservar todos os dados existentes")
    print(f"      - Manter compatibilidade com dados antigos")
    print(f"      - Implementar novos campos gradualmente")
    
    print(f"   2. Validações necessárias:")
    print(f"      - Cartórios de registro devem ter dados completos")
    print(f"      - Cartórios de transmissão podem ser livres")
    print(f"      - Validar integridade dos dados existentes")
    
    print(f"   3. Estrutura proposta:")
    print(f"      - Campo 'tipo' no modelo Cartorios")
    print(f"      - Novos campos no modelo Lancamento")
    print(f"      - Migração gradual dos dados")
    
    print(f"   4. Testes necessários:")
    print(f"      - Testes de migração de dados")
    print(f"      - Testes de formulários atualizados")
    print(f"      - Testes de compatibilidade")
    print(f"      - Testes de performance")

def analisar_impacto_mudancas():
    """Analisa o impacto das mudanças propostas"""
    
    print(f"\n🎯 ANÁLISE DE IMPACTO DAS MUDANÇAS")
    print("=" * 60)
    
    # 1. Impacto nos formulários
    print(f"\n📝 IMPACTO NOS FORMULÁRIOS:")
    
    formularios_afetados = [
        "dominial/forms/imovel_forms.py",
        "templates/dominial/imovel_form.html",
        "templates/dominial/documento_form.html",
        "templates/dominial/lancamento_form.html",
        "templates/dominial/components/_lancamento_basico_form.html"
    ]
    
    for formulario in formularios_afetados:
        print(f"   - {formulario}")
    
    # 2. Impacto nas views
    print(f"\n👁️  IMPACTO NAS VIEWS:")
    
    views_afetadas = [
        "dominial/views/imovel_views.py",
        "dominial/views/documento_views.py",
        "dominial/views/lancamento_views.py",
        "dominial/views/api_views.py",
        "dominial/views/cadeia_dominial_views.py"
    ]
    
    for view in views_afetadas:
        print(f"   - {view}")
    
    # 3. Impacto nos templates
    print(f"\n🎨 IMPACTO NOS TEMPLATES:")
    
    templates_afetados = [
        "templates/dominial/cadeia_dominial.html",
        "templates/dominial/cadeia_dominial_tabela.html",
        "templates/dominial/lancamento_detail.html",
        "templates/dominial/lancamento_confirm_delete.html"
    ]
    
    for template in templates_afetados:
        print(f"   - {template}")
    
    # 4. Impacto nos serviços
    print(f"\n⚙️  IMPACTO NOS SERVIÇOS:")
    
    servicos_afetados = [
        "dominial/services/lancamento_campos_service.py",
        "dominial/services/lancamento_form_service.py",
        "dominial/services/cartorio_verificacao_service.py"
    ]
    
    for servico in servicos_afetados:
        print(f"   - {servico}")
    
    # 5. Estimativa de esforço
    print(f"\n⏱️  ESTIMATIVA DE ESFORÇO:")
    
    print(f"   - Modelos: 2-3 horas")
    print(f"   - Formulários: 4-6 horas")
    print(f"   - Templates: 3-4 horas")
    print(f"   - Views: 2-3 horas")
    print(f"   - Serviços: 2-3 horas")
    print(f"   - Testes: 4-6 horas")
    print(f"   - Total estimado: 17-25 horas")

def verificar_estrutura_projeto():
    """Verifica se a estrutura do projeto faz sentido"""
    
    print(f"\n🏗️  VERIFICAÇÃO DA ESTRUTURA DO PROJETO")
    print("=" * 60)
    
    # 1. Verificar organização dos modelos
    print(f"\n📦 ORGANIZAÇÃO DOS MODELOS:")
    
    modelos_por_arquivo = {
        "dominial/models/imovel_models.py": ["Imovel", "Cartorios", "ImportacaoCartorios"],
        "dominial/models/documento_models.py": ["Documento", "DocumentoTipo"],
        "dominial/models/lancamento_models.py": ["Lancamento", "LancamentoTipo", "LancamentoPessoa"],
        "dominial/models/alteracao_models.py": ["Alteracoes", "AlteracoesTipo", "RegistroTipo", "AverbacoesTipo"],
        "dominial/models/pessoa_models.py": ["Pessoas"],
        "dominial/models/tis_models.py": ["TIs", "TerraIndigenaReferencia"]
    }
    
    for arquivo, modelos in modelos_por_arquivo.items():
        print(f"   - {arquivo}: {', '.join(modelos)}")
    
    # 2. Verificar organização dos formulários
    print(f"\n📝 ORGANIZAÇÃO DOS FORMULÁRIOS:")
    
    formularios_por_arquivo = {
        "dominial/forms/imovel_forms.py": ["ImovelForm"],
        "dominial/forms/tis_forms.py": ["TIsForm"]
    }
    
    for arquivo, formularios in formularios_por_arquivo.items():
        print(f"   - {arquivo}: {', '.join(formularios)}")
    
    # 3. Verificar organização das views
    print(f"\n👁️  ORGANIZAÇÃO DAS VIEWS:")
    
    views_por_arquivo = {
        "dominial/views/imovel_views.py": ["Imóveis"],
        "dominial/views/documento_views.py": ["Documentos"],
        "dominial/views/lancamento_views.py": ["Lançamentos"],
        "dominial/views/tis_views.py": ["TIs"],
        "dominial/views/api_views.py": ["APIs"],
        "dominial/views/autocomplete_views.py": ["Autocomplete"],
        "dominial/views/cadeia_dominial_views.py": ["Cadeia Dominial"]
    }
    
    for arquivo, views in views_por_arquivo.items():
        print(f"   - {arquivo}: {', '.join(views)}")
    
    # 4. Verificar organização dos serviços
    print(f"\n⚙️  ORGANIZAÇÃO DOS SERVIÇOS:")
    
    servicos_por_arquivo = {
        "dominial/services/lancamento_service.py": ["LancamentoService"],
        "dominial/services/lancamento_campos_service.py": ["LancamentoCamposService"],
        "dominial/services/lancamento_form_service.py": ["LancamentoFormService"],
        "dominial/services/cartorio_verificacao_service.py": ["CartorioVerificacaoService"]
    }
    
    for arquivo, servicos in servicos_por_arquivo.items():
        print(f"   - {arquivo}: {', '.join(servicos)}")
    
    # 5. Avaliação da estrutura
    print(f"\n✅ AVALIAÇÃO DA ESTRUTURA:")
    
    pontos_positivos = [
        "Modelos bem organizados por domínio",
        "Views separadas por funcionalidade",
        "Serviços para lógica de negócio",
        "Formulários organizados",
        "Templates bem estruturados"
    ]
    
    pontos_melhorias = [
        "Alguns serviços poderiam ser mais específicos",
        "Algumas views poderiam ser mais modulares",
        "Alguns formulários poderiam ser mais reutilizáveis"
    ]
    
    print(f"   Pontos positivos:")
    for ponto in pontos_positivos:
        print(f"     ✅ {ponto}")
    
    print(f"   Pontos de melhoria:")
    for ponto in pontos_melhorias:
        print(f"     🔄 {ponto}")

if __name__ == "__main__":
    print("🚀 INICIANDO ANÁLISE DA ESTRUTURA DOS CARTÓRIOS")
    print("=" * 80)
    
    try:
        # Importar models para análise
        from django.db import models
        
        # Executar análises
        analisar_estrutura_atual()
        analisar_impacto_mudancas()
        verificar_estrutura_projeto()
        
        print(f"\n✅ ANÁLISE CONCLUÍDA COM SUCESSO!")
        print(f"📋 Verifique o arquivo PLANEJAMENTO_REFORMULACAO_CARTORIOS.md para o plano detalhado")
        
    except Exception as e:
        print(f"❌ ERRO durante a análise: {e}")
        sys.exit(1) 