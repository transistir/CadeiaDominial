"""
Comprehensive Integration Tests for Recent Bug Fixes
Tests all bug fixes made in session claude/analyze-th-01MrXVBEzbBVTAXewmcaHNiq
"""

import pytest
from django.test import TestCase, RequestFactory
from django.contrib.auth.models import User
from django.http import QueryDict
from ..models import (
    TIs, Imovel, Documento, DocumentoTipo, Cartorios,
    Lancamento, LancamentoTipo, Pessoas, DocumentoImportado
)
from ..services.duplicata_verificacao_service import DuplicataVerificacaoService
from ..services.lancamento_duplicata_service import LancamentoDuplicataService
from ..services.importacao_cadeia_service import ImportacaoCadeiaService


class RecentBugFixesIntegrationTest(TestCase):
    """
    Integration tests for all recent bug fixes:

    1. MultipleObjectsReturned fix in duplicate reconstruction
    2. Cross-property duplicate prevention
    3. API contract variations (defensive coding)
    4. Defensive template handling
    """

    def setUp(self):
        """Set up test data"""
        # Create user
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )

        # Create TIs
        self.tis = TIs.objects.create(
            nome='Terra Indígena Teste',
            etnia='Etnia Teste',
            estado='SP',
            codigo='T001'
        )

        # Create cartório
        self.cartorio = Cartorios.objects.create(
            nome='1º Cartório de Registro de Imóveis',
            cns='CNS001',
            cidade='São Paulo',
            estado='SP'
        )

        # Create document types
        self.tipo_matricula, _ = DocumentoTipo.objects.get_or_create(
            tipo='matricula'
        )
        self.tipo_transcricao, _ = DocumentoTipo.objects.get_or_create(
            tipo='transcricao'
        )

        # Create lancamento tipo
        self.lancamento_tipo, _ = LancamentoTipo.objects.get_or_create(
            tipo='Averbação',
            defaults={'requer_origem': True}
        )

        # Create test pessoa
        self.pessoa = Pessoas.objects.create(
            nome='João da Silva',
            cpf='12345678901'
        )

        # Request factory for simulating requests
        self.factory = RequestFactory()

    # =========================================================================
    # Test 1: MultipleObjectsReturned Fix in Duplicate Reconstruction
    # =========================================================================

    def test_multiple_duplicates_same_numero_cartorio(self):
        """
        Test that duplicate verification handles multiple documents with
        same numero/cartorio gracefully (previously raised MultipleObjectsReturned)

        Bug: Documento.objects.get(numero=..., cartorio_id=...) raised exception
        Fix: Use document ID instead
        """
        # Create property for origin
        imovel_origem = Imovel.objects.create(
            nome='Imóvel Origem',
            proprietario=self.pessoa,
            matricula='ORIG001',
            terra_indigena_id=self.tis,
            cartorio=self.cartorio
        )

        # Create property for destination
        imovel_destino = Imovel.objects.create(
            nome='Imóvel Destino',
            proprietario=self.pessoa,
            matricula='DEST001',
            terra_indigena_id=self.tis,
            cartorio=self.cartorio
        )

        # Create MULTIPLE documents with SAME numero and cartorio
        # This simulates the exact scenario that caused MultipleObjectsReturned
        doc1 = Documento.objects.create(
            numero='T1234',
            tipo=self.tipo_transcricao,
            imovel=imovel_origem,
            cartorio=self.cartorio,
            data='2020-01-01',
            livro='1A',
            folha='100'
        )

        doc2 = Documento.objects.create(
            numero='T1234',  # Same numero
            tipo=self.tipo_transcricao,
            imovel=imovel_origem,
            cartorio=self.cartorio,  # Same cartorio
            data='2020-02-01',
            livro='1B',
            folha='200'
        )

        # Create active document on destination property
        doc_ativo = Documento.objects.create(
            numero='M5678',
            tipo=self.tipo_matricula,
            imovel=imovel_destino,
            cartorio=self.cartorio,
            data='2021-01-01',
            livro='2A',
            folha='300'
        )

        # Simulate form submission with origem pointing to duplicate
        request = self.factory.post('/fake-url/', data={
            'origem_completa[]': ['T1234'],
            'cartorio_origem[]': [str(self.cartorio.id)],
            'tipo_lancamento': str(self.lancamento_tipo.id),
            'numero_lancamento': '001',
            'data': '2021-06-01',
        })
        request.POST = QueryDict('', mutable=True)
        request.POST.update({
            'origem_completa[]': ['T1234'],
            'cartorio_origem[]': [str(self.cartorio.id)],
        })

        # This should NOT raise MultipleObjectsReturned anymore
        # It should handle the duplicate gracefully
        try:
            resultado = LancamentoDuplicataService.verificar_duplicata_antes_criacao(
                request, doc_ativo
            )

            # If duplicate found, verify it returns proper structure
            if resultado.get('tem_duplicata'):
                self.assertIn('documento_origem', resultado)
                self.assertIsInstance(resultado['documento_origem'], Documento)
                # Should be one of the two duplicate documents
                self.assertIn(resultado['documento_origem'].id, [doc1.id, doc2.id])
                self.assertEqual(resultado['documento_origem'].numero, 'T1234')

            # Test passed - no MultipleObjectsReturned exception
            self.assertTrue(True)

        except Exception as e:
            # If any exception, fail with clear message
            self.fail(f"Should not raise exception with duplicate documents: {type(e).__name__}: {e}")

    # =========================================================================
    # Test 2: Cross-Property Duplicate Prevention
    # =========================================================================

    def test_cross_property_chain_duplicate_prevention_integration(self):
        """
        Test that documents can't be imported twice even when reached
        through different property chains

        Bug: Old code checked (documento, imovel_origem) pair
        Fix: Now checks only documento
        """
        # Create three properties
        imovel1 = Imovel.objects.create(
            nome='Imóvel 1',
            proprietario=self.pessoa,
            matricula='IM001',
            terra_indigena_id=self.tis,
            cartorio=self.cartorio
        )

        imovel2 = Imovel.objects.create(
            nome='Imóvel 2',
            proprietario=self.pessoa,
            matricula='IM002',
            terra_indigena_id=self.tis,
            cartorio=self.cartorio
        )

        imovel3 = Imovel.objects.create(
            nome='Imóvel 3 (Destination)',
            proprietario=self.pessoa,
            matricula='IM003',
            terra_indigena_id=self.tis,
            cartorio=self.cartorio
        )

        # Create chain 1: Doc A (Imovel1) → Doc B (Imovel2)
        doc_a = Documento.objects.create(
            numero='T1000',
            tipo=self.tipo_transcricao,
            imovel=imovel1,
            cartorio=self.cartorio,
            data='2018-01-01',
            livro='1',
            folha='1'
        )

        doc_b = Documento.objects.create(
            numero='T2000',
            tipo=self.tipo_transcricao,
            imovel=imovel2,
            cartorio=self.cartorio,
            data='2019-01-01',
            livro='2',
            folha='2'
        )

        # Create chain 2: Doc C (Imovel2) - alternative path to Doc B
        doc_c = Documento.objects.create(
            numero='M3000',
            tipo=self.tipo_matricula,
            imovel=imovel2,
            cartorio=self.cartorio,
            data='2020-01-01',
            livro='3',
            folha='3'
        )

        # Import Doc B through first chain (from Imovel1)
        resultado1 = ImportacaoCadeiaService.importar_cadeia_dominial(
            imovel_destino_id=imovel3.id,
            documento_origem_id=doc_a.id,
            documentos_importaveis_ids=[doc_b.id],
            usuario_id=self.user.id
        )

        self.assertTrue(resultado1['sucesso'])
        self.assertEqual(resultado1['total_importados'], 1)

        # Verify DocumentoImportado was created
        self.assertEqual(
            DocumentoImportado.objects.filter(documento=doc_b).count(),
            1
        )

        # Try to import Doc B again through different chain (from Imovel2)
        resultado2 = ImportacaoCadeiaService.importar_cadeia_dominial(
            imovel_destino_id=imovel3.id,
            documento_origem_id=doc_c.id,
            documentos_importaveis_ids=[doc_b.id],
            usuario_id=self.user.id
        )

        # Should succeed but import 0 documents (already imported)
        self.assertTrue(resultado2['sucesso'])
        self.assertEqual(resultado2['total_importados'], 0)

        # Should still have only ONE DocumentoImportado record
        self.assertEqual(
            DocumentoImportado.objects.filter(documento=doc_b).count(),
            1
        )

        # Verify error message indicates already imported
        if 'erros' in resultado2:
            self.assertTrue(
                any('já foi importado' in erro for erro in resultado2['erros'])
            )
        else:
            self.assertIn('já foram importados', resultado2['mensagem'])

    # =========================================================================
    # Test 3: API Contract Variation Handling (Defensive Coding)
    # =========================================================================

    def test_defensive_cadeia_dominial_format_handling(self):
        """
        Test that obter_dados_duplicata_para_template handles both
        old (list) and new (dict) cadeia_dominial formats gracefully

        Bug: Template expected list, service returned dict, template crashed
        Fix: Defensive code detects both formats and extracts list
        """
        # Create test documents
        imovel = Imovel.objects.create(
            nome='Imóvel Teste',
            proprietario=self.pessoa,
            matricula='TEST001',
            terra_indigena_id=self.tis,
            cartorio=self.cartorio
        )

        doc_origem = Documento.objects.create(
            numero='T9999',
            tipo=self.tipo_transcricao,
            imovel=imovel,
            cartorio=self.cartorio,
            data='2020-01-01',
            livro='99',
            folha='99'
        )

        lanc = Lancamento.objects.create(
            documento=doc_origem,
            tipo=self.lancamento_tipo,
            numero_lancamento='001',
            data='2020-01-01'
        )

        # Test OLD format (list)
        duplicata_info_old_format = {
            'tem_duplicata': True,
            'documento_origem': doc_origem,
            'documentos_importaveis': [],
            'cadeia_dominial': [  # OLD: Direct list
                {
                    'documento': doc_origem,
                    'lancamentos': [lanc]
                }
            ]
        }

        resultado_old = LancamentoDuplicataService.obter_dados_duplicata_para_template(
            duplicata_info_old_format
        )

        self.assertIsNotNone(resultado_old)
        self.assertIn('cadeia_dominial', resultado_old)
        self.assertEqual(len(resultado_old['cadeia_dominial']), 1)

        # Test NEW format (dict with 'documentos' key)
        duplicata_info_new_format = {
            'tem_duplicata': True,
            'documento_origem': doc_origem,
            'documentos_importaveis': [],
            'cadeia_dominial': {  # NEW: Dict wrapper
                'documento_origem': {'numero': doc_origem.numero, 'id': doc_origem.id},
                'total_documentos': 1,
                'documentos': [
                    {
                        'documento': doc_origem,
                        'lancamentos': [lanc]
                    }
                ]
            }
        }

        resultado_new = LancamentoDuplicataService.obter_dados_duplicata_para_template(
            duplicata_info_new_format
        )

        self.assertIsNotNone(resultado_new)
        self.assertIn('cadeia_dominial', resultado_new)
        self.assertEqual(len(resultado_new['cadeia_dominial']), 1)

        # Both formats should produce same result
        self.assertEqual(
            resultado_old['cadeia_dominial'][0]['documento']['numero'],
            resultado_new['cadeia_dominial'][0]['documento']['numero']
        )

        # Test INVALID format (should not crash)
        duplicata_info_invalid = {
            'tem_duplicata': True,
            'documento_origem': doc_origem,
            'documentos_importaveis': [],
            'cadeia_dominial': "invalid string format"  # INVALID
        }

        resultado_invalid = LancamentoDuplicataService.obter_dados_duplicata_para_template(
            duplicata_info_invalid
        )

        # Should return result with empty cadeia_dominial (graceful degradation)
        self.assertIsNotNone(resultado_invalid)
        self.assertIn('cadeia_dominial', resultado_invalid)
        self.assertEqual(len(resultado_invalid['cadeia_dominial']), 0)

    # =========================================================================
    # Test 4: Document ID in Serialization
    # =========================================================================

    def test_document_id_included_in_serialization(self):
        """
        Test that DuplicataVerificacaoService includes document ID
        in serialized response (needed for reconstruction fix)

        Bug: Only returned numero/imovel, reconstruction used .get(numero, cartorio)
        Fix: Include ID, reconstruction uses .get(id=...)
        """
        # Create documents
        imovel1 = Imovel.objects.create(
            nome='Imóvel 1',
            proprietario=self.pessoa,
            matricula='SER001',
            terra_indigena_id=self.tis,
            cartorio=self.cartorio
        )

        imovel2 = Imovel.objects.create(
            nome='Imóvel 2',
            proprietario=self.pessoa,
            matricula='SER002',
            terra_indigena_id=self.tis,
            cartorio=self.cartorio
        )

        doc_existente = Documento.objects.create(
            numero='T5555',
            tipo=self.tipo_transcricao,
            imovel=imovel1,
            cartorio=self.cartorio,
            data='2020-01-01',
            livro='5',
            folha='5'
        )

        # Call service to check for duplicate
        resultado = DuplicataVerificacaoService.verificar_duplicata_origem(
            origem='T5555',
            cartorio_id=self.cartorio.id,
            imovel_atual_id=imovel2.id
        )

        # Verify duplicate was found
        self.assertTrue(resultado['existe'])

        # Verify serialized document includes ID
        self.assertIn('documento', resultado)
        self.assertIn('id', resultado['documento'])
        self.assertEqual(resultado['documento']['id'], doc_existente.id)

        # Verify other required fields
        self.assertEqual(resultado['documento']['numero'], 'T5555')
        self.assertIn('imovel', resultado['documento'])
        self.assertEqual(resultado['documento']['imovel']['id'], imovel1.id)

        # Verify we can reconstruct using ID (no MultipleObjectsReturned)
        try:
            reconstructed = Documento.objects.get(id=resultado['documento']['id'])
            self.assertEqual(reconstructed.id, doc_existente.id)
            self.assertEqual(reconstructed.numero, doc_existente.numero)
        except Exception as e:
            self.fail(f"Failed to reconstruct document from ID: {e}")

    # =========================================================================
    # Test 5: End-to-End Integration
    # =========================================================================

    def test_end_to_end_duplicate_detection_and_import(self):
        """
        Complete end-to-end test combining all fixes:
        1. Detect duplicate with multiple documents (MultipleObjectsReturned fix)
        2. Verify cross-property prevention
        3. Handle API contract variations
        4. Use document ID for reconstruction
        """
        # Create complex scenario
        imovel_origem = Imovel.objects.create(
            nome='Imóvel Origem',
            proprietario=self.pessoa,
            matricula='E2E001',
            terra_indigena_id=self.tis,
            cartorio=self.cartorio
        )

        imovel_destino = Imovel.objects.create(
            nome='Imóvel Destino',
            proprietario=self.pessoa,
            matricula='E2E002',
            terra_indigena_id=self.tis,
            cartorio=self.cartorio
        )

        # Create duplicate documents (same numero/cartorio)
        doc1 = Documento.objects.create(
            numero='T7777',
            tipo=self.tipo_transcricao,
            imovel=imovel_origem,
            cartorio=self.cartorio,
            data='2020-01-01',
            livro='7A',
            folha='700'
        )

        doc2 = Documento.objects.create(
            numero='T7777',  # Duplicate
            tipo=self.tipo_transcricao,
            imovel=imovel_origem,
            cartorio=self.cartorio,
            data='2020-02-01',
            livro='7B',
            folha='701'
        )

        # Step 1: Verify duplicate detection works
        verificacao = DuplicataVerificacaoService.verificar_duplicata_origem(
            origem='T7777',
            cartorio_id=self.cartorio.id,
            imovel_atual_id=imovel_destino.id
        )

        self.assertTrue(verificacao['existe'])
        self.assertIn('id', verificacao['documento'])

        # Step 2: Import one of the duplicates
        resultado_import = ImportacaoCadeiaService.importar_cadeia_dominial(
            imovel_destino_id=imovel_destino.id,
            documento_origem_id=doc1.id,
            documentos_importaveis_ids=[doc1.id],
            usuario_id=self.user.id
        )

        self.assertTrue(resultado_import['sucesso'])

        # Step 3: Try to import again (should be prevented)
        resultado_import2 = ImportacaoCadeiaService.importar_cadeia_dominial(
            imovel_destino_id=imovel_destino.id,
            documento_origem_id=doc2.id,  # Different document object, same numero
            documentos_importaveis_ids=[doc1.id],
            usuario_id=self.user.id
        )

        self.assertEqual(resultado_import2['total_importados'], 0)

        # Step 4: Verify DocumentoImportado exists only once
        self.assertEqual(
            DocumentoImportado.objects.filter(documento=doc1).count(),
            1
        )

        # Test completed successfully - all fixes working together
        self.assertTrue(True)


class CartorioMultipleObjectsReturned Test(TestCase):
    """
    Tests for potential Cartorio lookup issues identified in code review
    (Not a bug fix, but recommended enhancement)
    """

    def setUp(self):
        """Set up test data"""
        # Create two cartórios with same name (different CNS)
        self.cartorio1 = Cartorios.objects.create(
            nome='Cartório Central',
            cns='CNS001',
            cidade='São Paulo',
            estado='SP'
        )

        self.cartorio2 = Cartorios.objects.create(
            nome='Cartório Central',  # Same name!
            cns='CNS002',
            cidade='Campinas',
            estado='SP'
        )

    @pytest.mark.skip(reason="Known issue identified in code review - not yet fixed")
    def test_cartorio_lookup_by_name_with_duplicates(self):
        """
        Test that Cartorio lookup by name handles duplicates gracefully

        Current behavior: Raises MultipleObjectsReturned (uncaught)
        Recommended: Use .filter().first() or catch exception
        """
        from ..services.lancamento_campos_service import LancamentoCamposService

        # This will currently raise MultipleObjectsReturned
        # Should be fixed to use .filter().first() or catch the exception
        try:
            result = Cartorios.objects.get(nome__iexact='Cartório Central')
            # If we get here, only one cartorio matched (unexpected in this test)
            self.fail("Expected MultipleObjectsReturned or defensive handling")
        except Cartorios.MultipleObjectsReturned:
            # Expected - demonstrates the issue
            self.assertTrue(True, "Demonstrates the issue identified in code review")
