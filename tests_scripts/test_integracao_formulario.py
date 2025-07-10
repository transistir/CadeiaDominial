#!/usr/bin/env python
"""
Teste de integração para verificar o formulário web de lançamentos
"""
import os
import sys
import django
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'cadeia_dominial.settings')
django.setup()

from dominial.models import TIs, Imovel, Documento, DocumentoTipo, LancamentoTipo, Cartorios, Pessoas

class TestFormularioLancamento(TestCase):
    """Teste de integração para formulário de lançamentos"""
    
    def setUp(self):
        """Configurar dados de teste"""
        # Criar usuário
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        
        # Criar TI
        self.tis = TIs.objects.create(
            nome='TI Teste',
            codigo='TI001',
            etnia='Teste',
            estado='SP'
        )
        
        # Criar cartório
        self.cartorio = Cartorios.objects.create(
            nome='Cartório Teste',
            cns='CNS001',
            cidade='São Paulo',
            estado='SP'
        )
        
        # Criar pessoa
        self.pessoa = Pessoas.objects.create(
            nome='João Teste',
            cpf='12345678901'
        )
        
        # Criar imóvel
        self.imovel = Imovel.objects.create(
            nome='Imóvel Teste',
            matricula='M001',
            sncr='SNCR001',
            sigef='SIGEF001',
            proprietario=self.pessoa,
            terra_indigena_id=self.tis,
            cartorio=self.cartorio
        )
        
        # Criar tipo de documento
        self.tipo_documento = DocumentoTipo.objects.create(tipo='matricula')
        
        # Criar documento
        self.documento = Documento.objects.create(
            imovel=self.imovel,
            tipo=self.tipo_documento,
            numero='DOC001',
            data='2024-01-01',
            cartorio=self.cartorio,
            livro='1',
            folha='1'
        )
        
        # Criar tipos de lançamento
        self.tipo_averbacao = LancamentoTipo.objects.create(
            tipo='averbacao',
            requer_forma=True,
            requer_descricao=True
        )
        
        self.tipo_registro = LancamentoTipo.objects.create(
            tipo='registro',
            requer_forma=True,
            requer_titulo=True,
            requer_cartorio_origem=True
        )
        
        self.tipo_inicio = LancamentoTipo.objects.create(
            tipo='inicio_matricula',
            requer_forma=True,
            requer_descricao=True
        )
        
        # Configurar cliente
        self.client = Client()
        self.client.login(username='testuser', password='testpass123')
    
    def test_acesso_formulario_novo_lancamento(self):
        """Testa se o formulário de novo lançamento está acessível"""
        url = reverse('novo_lancamento', kwargs={
            'tis_id': self.tis.id,
            'imovel_id': self.imovel.id
        })
        
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Novo Lançamento')
        self.assertContains(response, 'Informações Básicas da Matrícula/Transcrição')
    
    def test_campos_obrigatorios_basicos(self):
        """Testa se os campos obrigatórios básicos estão presentes"""
        url = reverse('novo_lancamento', kwargs={
            'tis_id': self.tis.id,
            'imovel_id': self.imovel.id
        })
        
        response = self.client.get(url)
        
        # Verificar campos obrigatórios
        campos_obrigatorios = [
            'tipo_lancamento',
            'numero_lancamento',
            'livro',
            'folha',
            'cartorio',
            'data'
        ]
        
        for campo in campos_obrigatorios:
            self.assertContains(response, f'name="{campo}"')
    
    def test_criar_lancamento_averbacao(self):
        """Testa criação de lançamento do tipo averbação"""
        url = reverse('novo_lancamento', kwargs={
            'tis_id': self.tis.id,
            'imovel_id': self.imovel.id
        })
        
        dados = {
            'tipo_lancamento': self.tipo_averbacao.id,
            'numero_lancamento': 'AV001',
            'livro': '1',
            'folha': '1',
            'cartorio': self.cartorio.id,
            'cartorio_nome': self.cartorio.nome,
            'data': '2024-01-01',
            'forma_averbacao': 'Compra e Venda',
            'descricao': 'Averbação de teste'
        }
        
        response = self.client.post(url, dados)
        
        # Verificar se foi redirecionado (sucesso)
        self.assertEqual(response.status_code, 302)
        
        # Verificar se o lançamento foi criado
        from dominial.models import Lancamento
        lancamento = Lancamento.objects.filter(
            numero_lancamento='AV001',
            documento=self.documento
        ).first()
        
        self.assertIsNotNone(lancamento)
        self.assertEqual(lancamento.tipo.tipo, 'averbacao')
        self.assertEqual(lancamento.forma, 'Compra e Venda')
        self.assertEqual(lancamento.descricao, 'Averbação de teste')
        self.assertEqual(lancamento.cartorio_origem, self.cartorio)
        self.assertEqual(lancamento.livro_origem, '1')
        self.assertEqual(lancamento.folha_origem, '1')
    
    def test_criar_lancamento_registro(self):
        """Testa criação de lançamento do tipo registro"""
        url = reverse('novo_lancamento', kwargs={
            'tis_id': self.tis.id,
            'imovel_id': self.imovel.id
        })
        
        dados = {
            'tipo_lancamento': self.tipo_registro.id,
            'numero_lancamento': 'REG001',
            'livro': '2',
            'folha': '2',
            'cartorio': self.cartorio.id,
            'cartorio_nome': self.cartorio.nome,
            'data': '2024-01-02',
            'forma_registro': 'Doação',
            'titulo': 'Título do Registro'
        }
        
        response = self.client.post(url, dados)
        
        # Verificar se foi redirecionado (sucesso)
        self.assertEqual(response.status_code, 302)
        
        # Verificar se o lançamento foi criado
        from dominial.models import Lancamento
        lancamento = Lancamento.objects.filter(
            numero_lancamento='REG001',
            documento=self.documento
        ).first()
        
        self.assertIsNotNone(lancamento)
        self.assertEqual(lancamento.tipo.tipo, 'registro')
        self.assertEqual(lancamento.forma, 'Doação')
        self.assertEqual(lancamento.titulo, 'Título do Registro')
        self.assertEqual(lancamento.cartorio_origem, self.cartorio)
        self.assertEqual(lancamento.livro_origem, '2')
        self.assertEqual(lancamento.folha_origem, '2')
    
    def test_criar_lancamento_inicio_matricula(self):
        """Testa criação de lançamento do tipo início de matrícula"""
        url = reverse('novo_lancamento', kwargs={
            'tis_id': self.tis.id,
            'imovel_id': self.imovel.id
        })
        
        dados = {
            'tipo_lancamento': self.tipo_inicio.id,
            'numero_lancamento': 'INI001',
            'livro': '3',
            'folha': '3',
            'cartorio': self.cartorio.id,
            'cartorio_nome': self.cartorio.nome,
            'data': '2024-01-03',
            'forma_inicio': 'Abertura',
            'descricao': 'Início de matrícula de teste'
        }
        
        response = self.client.post(url, dados)
        
        # Verificar se foi redirecionado (sucesso)
        self.assertEqual(response.status_code, 302)
        
        # Verificar se o lançamento foi criado
        from dominial.models import Lancamento
        lancamento = Lancamento.objects.filter(
            numero_lancamento='INI001',
            documento=self.documento
        ).first()
        
        self.assertIsNotNone(lancamento)
        self.assertEqual(lancamento.tipo.tipo, 'inicio_matricula')
        self.assertEqual(lancamento.forma, 'Abertura')
        self.assertEqual(lancamento.descricao, 'Início de matrícula de teste')
        self.assertEqual(lancamento.cartorio_origem, self.cartorio)
        self.assertEqual(lancamento.livro_origem, '3')
        self.assertEqual(lancamento.folha_origem, '3')
    
    def test_validacao_campos_obrigatorios(self):
        """Testa validação de campos obrigatórios"""
        url = reverse('novo_lancamento', kwargs={
            'tis_id': self.tis.id,
            'imovel_id': self.imovel.id
        })
        
        # Tentar criar sem campos obrigatórios
        dados = {
            'tipo_lancamento': self.tipo_averbacao.id,
            # Campos obrigatórios faltando
        }
        
        response = self.client.post(url, dados)
        
        # Deve retornar 200 (erro de validação)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Informações Básicas da Matrícula/Transcrição')

def run_tests():
    """Executa os testes de integração"""
    print("🧪 TESTE DE INTEGRAÇÃO - FORMULÁRIO DE LANÇAMENTOS")
    print("=" * 60)
    
    # Configurar Django para testes
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'cadeia_dominial.settings')
    django.setup()
    
    # Executar testes
    from django.test.utils import get_runner
    from django.conf import settings
    
    TestRunner = get_runner(settings)
    test_runner = TestRunner()
    
    failures = test_runner.run_tests(['test_integracao_formulario'])
    
    if failures:
        print(f"\n❌ {failures} teste(s) falharam")
        return False
    else:
        print("\n✅ TODOS OS TESTES PASSARAM!")
        return True

if __name__ == "__main__":
    try:
        success = run_tests()
        if success:
            print("\n🎯 Formulário de lançamentos está funcionando perfeitamente!")
        else:
            print("\n❌ Alguns problemas foram encontrados")
            sys.exit(1)
    except Exception as e:
        print(f"\n💥 Erro durante os testes: {e}")
        sys.exit(1) 