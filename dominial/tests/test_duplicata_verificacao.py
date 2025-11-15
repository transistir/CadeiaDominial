"""
Testes unitários para a funcionalidade de verificação de duplicatas.
"""

from django.test import TestCase
from django.contrib.auth.models import User
from django.test.utils import override_settings
from ..models import Imovel, Documento, DocumentoTipo, Cartorios, DocumentoImportado
from ..services.duplicata_verificacao_service import DuplicataVerificacaoService
from ..services.importacao_cadeia_service import ImportacaoCadeiaService


class DuplicataVerificacaoServiceTest(TestCase):
    """Testes para o service de verificação de duplicatas."""
    
    def setUp(self):
        """Configurar dados de teste."""
        # Criar usuário
        self.usuario = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        
        # Criar cartórios
        self.cartorio = Cartorios.objects.create(
            nome='Cartório Teste',
            cns='CNS001',
            cidade='Cidade Teste',
            estado='TS'
        )

        self.cartorio2 = Cartorios.objects.create(
            nome='Cartório Teste 2',
            cns='CNS002',
            cidade='Cidade Teste 2',
            estado='TS'
        )

        # Criar tipo de documento
        self.tipo_documento = DocumentoTipo.objects.create(
            tipo='matricula'
        )

        # Criar TI and Pessoa for Imovel
        from ..models import TIs, Pessoas
        self.tis = TIs.objects.create(
            nome='TI Teste',
            codigo='TEST001',
            etnia='Teste'
        )
        self.pessoa = Pessoas.objects.create(
            nome='Proprietário Teste',
            cpf='12345678901'
        )

        # Criar imóveis
        self.imovel1 = Imovel.objects.create(
            matricula='123456',
            terra_indigena_id=self.tis,
            proprietario=self.pessoa
        )

        self.imovel2 = Imovel.objects.create(
            matricula='789012',
            terra_indigena_id=self.tis,
            proprietario=self.pessoa
        )

        # Criar documentos (with different cartórios to avoid UNIQUE constraint)
        self.documento1 = Documento.objects.create(
            numero='M123456',
            tipo=self.tipo_documento,
            cartorio=self.cartorio,
            imovel=self.imovel1,
            data='2023-01-01'
        )

        self.documento2 = Documento.objects.create(
            numero='M123456',  # Mesmo número, cartório diferente
            tipo=self.tipo_documento,
            cartorio=self.cartorio2,  # Different cartório
            imovel=self.imovel2,
            data='2023-01-01'
        )
    
    def test_verificar_duplicata_origem_existente(self):
        """Testa verificação de duplicata quando existe."""
        resultado = DuplicataVerificacaoService.verificar_duplicata_origem(
            origem='M123456',
            cartorio_id=self.cartorio.id,
            imovel_atual_id=self.imovel1.id
        )
        
        self.assertTrue(resultado['existe'])
        self.assertEqual(resultado['documento']['numero'], 'M123456')
        self.assertEqual(resultado['documento']['imovel']['id'], self.imovel2.id)
    
    def test_verificar_duplicata_origem_inexistente(self):
        """Testa verificação de duplicata quando não existe."""
        resultado = DuplicataVerificacaoService.verificar_duplicata_origem(
            origem='M999999',
            cartorio_id=self.cartorio.id,
            imovel_atual_id=self.imovel1.id
        )
        
        self.assertFalse(resultado['existe'])
    
    def test_verificar_duplicata_mesmo_imovel(self):
        """Testa que não considera duplicata no mesmo imóvel."""
        resultado = DuplicataVerificacaoService.verificar_duplicata_origem(
            origem='M123456',
            cartorio_id=self.cartorio.id,
            imovel_atual_id=self.imovel2.id
        )
        
        self.assertFalse(resultado['existe'])
    
    @override_settings(DUPLICATA_VERIFICACAO_ENABLED=False)
    def test_verificacao_desabilitada(self):
        """Testa que retorna False quando a funcionalidade está desabilitada."""
        resultado = DuplicataVerificacaoService.verificar_duplicata_origem(
            origem='M123456',
            cartorio_id=self.cartorio.id,
            imovel_atual_id=self.imovel1.id
        )
        
        self.assertFalse(resultado['existe'])
    
    def test_calcular_documentos_importaveis(self):
        """Testa cálculo de documentos importáveis."""
        documentos = DuplicataVerificacaoService.calcular_documentos_importaveis(
            self.documento1
        )
        
        # Por enquanto deve retornar lista vazia (sem lançamentos)
        self.assertEqual(len(documentos), 0)
    
    def test_obter_cadeia_dominial_origem(self):
        """Testa obtenção de cadeia dominial."""
        cadeia = DuplicataVerificacaoService.obter_cadeia_dominial_origem(
            self.documento1
        )
        
        self.assertEqual(cadeia['documento_origem']['numero'], 'M123456')
        self.assertEqual(cadeia['total_documentos'], 1)  # Apenas o documento origem
    
    def test_verificar_performance_consulta(self):
        """Testa verificação de performance."""
        resultado = DuplicataVerificacaoService.verificar_performance_consulta(
            origem='M123456',
            cartorio_id=self.cartorio.id
        )
        
        self.assertIn('tempo_execucao', resultado)
        self.assertIn('tempo_aceitavel', resultado)
        self.assertIn('resultado', resultado)


class ImportacaoCadeiaServiceTest(TestCase):
    """Testes para o service de importação de cadeia."""

    def setUp(self):
        """Configurar dados de teste."""
        # Criar usuário
        self.usuario = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )

        # Criar cartório
        self.cartorio = Cartorios.objects.create(
            nome='Cartório Teste',
            cns='CNS003',
            cidade='Cidade Teste',
            estado='TS'
        )

        # Criar tipo de documento
        self.tipo_documento = DocumentoTipo.objects.create(
            tipo='matricula'
        )

        # Criar TI and Pessoa for Imovel
        from ..models import TIs, Pessoas
        self.tis = TIs.objects.create(
            nome='TI Teste',
            codigo='TEST002',
            etnia='Teste'
        )
        self.pessoa = Pessoas.objects.create(
            nome='Proprietário Teste',
            cpf='98765432109'
        )

        # Criar imóveis
        self.imovel_origem = Imovel.objects.create(
            matricula='123456',
            terra_indigena_id=self.tis,
            proprietario=self.pessoa
        )

        self.imovel_destino = Imovel.objects.create(
            matricula='789012',
            terra_indigena_id=self.tis,
            proprietario=self.pessoa
        )
        
        # Criar documentos
        self.documento_origem = Documento.objects.create(
            numero='M123456',
            tipo=self.tipo_documento,
            cartorio=self.cartorio,
            imovel=self.imovel_origem,
            data='2023-01-01'
        )
        
        self.documento_importavel = Documento.objects.create(
            numero='M789012',
            tipo=self.tipo_documento,
            cartorio=self.cartorio,
            imovel=self.imovel_origem,
            data='2023-01-01'
        )
    
    def test_marcar_documento_importado(self):
        """Testa marcação de documento como importado."""
        documento_importado = ImportacaoCadeiaService.marcar_documento_importado(
            documento=self.documento_importavel,
            imovel_origem=self.imovel_origem,
            importado_por=self.usuario
        )
        
        self.assertEqual(documento_importado.documento, self.documento_importavel)
        self.assertEqual(documento_importado.imovel_origem, self.imovel_origem)
        self.assertEqual(documento_importado.importado_por, self.usuario)
    
    def test_importar_cadeia_dominial_sucesso(self):
        """Testa importação de cadeia dominial com sucesso."""
        resultado = ImportacaoCadeiaService.importar_cadeia_dominial(
            imovel_destino_id=self.imovel_destino.id,
            documento_origem_id=self.documento_origem.id,
            documentos_importaveis_ids=[self.documento_importavel.id],
            usuario_id=self.usuario.id
        )
        
        self.assertTrue(resultado['sucesso'])
        self.assertEqual(resultado['total_importados'], 1)
        self.assertEqual(len(resultado['documentos_importados']), 1)
    
    def test_importar_cadeia_dominial_imovel_inexistente(self):
        """Testa importação com imóvel destino inexistente."""
        resultado = ImportacaoCadeiaService.importar_cadeia_dominial(
            imovel_destino_id=99999,
            documento_origem_id=self.documento_origem.id,
            documentos_importaveis_ids=[self.documento_importavel.id],
            usuario_id=self.usuario.id
        )
        
        self.assertFalse(resultado['sucesso'])
        self.assertIn('erro', resultado)
    
    def test_verificar_documentos_importados(self):
        """Testa verificação de documentos importados."""
        # Primeiro importar um documento
        ImportacaoCadeiaService.importar_cadeia_dominial(
            imovel_destino_id=self.imovel_destino.id,
            documento_origem_id=self.documento_origem.id,
            documentos_importaveis_ids=[self.documento_importavel.id],
            usuario_id=self.usuario.id
        )
        
        # Verificar documentos importados
        documentos_importados = ImportacaoCadeiaService.verificar_documentos_importados(
            self.imovel_destino.id
        )
        
        self.assertEqual(len(documentos_importados), 1)
        self.assertEqual(documentos_importados[0]['numero'], 'M789012')
    
    def test_desfazer_importacao(self):
        """Testa desfazer importação."""
        # Primeiro importar um documento
        ImportacaoCadeiaService.importar_cadeia_dominial(
            imovel_destino_id=self.imovel_destino.id,
            documento_origem_id=self.documento_origem.id,
            documentos_importaveis_ids=[self.documento_importavel.id],
            usuario_id=self.usuario.id
        )
        
        # Obter o ID do documento importado
        documento_importado = DocumentoImportado.objects.get(
            documento=self.documento_importavel
        )
        
        # Desfazer importação
        resultado = ImportacaoCadeiaService.desfazer_importacao(
            documento_importado_id=documento_importado.id,
            usuario_id=self.usuario.id
        )
        
        self.assertTrue(resultado['sucesso'])
        
        # Verificar que foi removido
        self.assertFalse(
            DocumentoImportado.objects.filter(id=documento_importado.id).exists()
        )


class DocumentoImportadoModelTest(TestCase):
    """Testes para o modelo DocumentoImportado."""

    def setUp(self):
        """Configurar dados de teste."""
        # Criar usuário
        self.usuario = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )

        # Criar cartório
        self.cartorio = Cartorios.objects.create(
            nome='Cartório Teste',
            cns='CNS004',
            cidade='Cidade Teste',
            estado='TS'
        )

        # Criar tipo de documento
        self.tipo_documento = DocumentoTipo.objects.create(
            tipo='matricula'
        )

        # Criar TI and Pessoa for Imovel
        from ..models import TIs, Pessoas
        self.tis = TIs.objects.create(
            nome='TI Teste',
            codigo='TEST003',
            etnia='Teste'
        )
        self.pessoa = Pessoas.objects.create(
            nome='Proprietário Teste',
            cpf='11122233344'
        )

        # Criar imóveis
        self.imovel_origem = Imovel.objects.create(
            matricula='123456',
            terra_indigena_id=self.tis,
            proprietario=self.pessoa
        )

        self.imovel_destino = Imovel.objects.create(
            matricula='789012',
            terra_indigena_id=self.tis,
            proprietario=self.pessoa
        )
        
        # Criar documento
        self.documento = Documento.objects.create(
            numero='M123456',
            tipo=self.tipo_documento,
            cartorio=self.cartorio,
            imovel=self.imovel_destino,
            data='2023-01-01'
        )
    
    def test_criar_documento_importado(self):
        """Testa criação de documento importado."""
        documento_importado = DocumentoImportado.objects.create(
            documento=self.documento,
            imovel_origem=self.imovel_origem,
            importado_por=self.usuario
        )
        
        self.assertEqual(documento_importado.documento, self.documento)
        self.assertEqual(documento_importado.imovel_origem, self.imovel_origem)
        self.assertEqual(documento_importado.importado_por, self.usuario)
    
    def test_str_representation(self):
        """Testa representação string do modelo."""
        documento_importado = DocumentoImportado.objects.create(
            documento=self.documento,
            imovel_origem=self.imovel_origem,
            importado_por=self.usuario
        )
        
        expected = f"Documento {self.documento.numero} importado de {self.imovel_origem.matricula}"
        self.assertEqual(str(documento_importado), expected)
    
    def test_get_origem_info(self):
        """Testa método get_origem_info."""
        documento_importado = DocumentoImportado.objects.create(
            documento=self.documento,
            imovel_origem=self.imovel_origem,
            importado_por=self.usuario
        )
        
        info = documento_importado.get_origem_info()
        self.assertIn(self.imovel_origem.matricula, info)
        self.assertIn('Importado de', info)
    
    def test_get_importador_info(self):
        """Testa método get_importador_info."""
        documento_importado = DocumentoImportado.objects.create(
            documento=self.documento,
            imovel_origem=self.imovel_origem,
            importado_por=self.usuario
        )
        
        info = documento_importado.get_importador_info()
        self.assertEqual(info, self.usuario.username)
    
    def test_is_documento_importado(self):
        """Testa método is_documento_importado."""
        documento_importado = DocumentoImportado.objects.create(
            documento=self.documento,
            imovel_origem=self.imovel_origem,
            importado_por=self.usuario
        )
        
        # Verificar se é importado
        self.assertTrue(DocumentoImportado.is_documento_importado(self.documento))
        self.assertTrue(DocumentoImportado.is_documento_importado(self.documento, self.imovel_origem))
        
        # Verificar com imóvel diferente
        self.assertFalse(DocumentoImportado.is_documento_importado(self.documento, self.imovel_destino))
    
    def test_get_documentos_importados_imovel(self):
        """Testa método get_documentos_importados_imovel."""
        documento_importado = DocumentoImportado.objects.create(
            documento=self.documento,
            imovel_origem=self.imovel_origem,
            importado_por=self.usuario
        )
        
        documentos = DocumentoImportado.get_documentos_importados_imovel(self.imovel_destino.id)
        self.assertEqual(documentos.count(), 1)
        self.assertEqual(documentos.first(), documento_importado) 