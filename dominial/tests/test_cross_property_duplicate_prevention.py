"""
Tests for cross-property chain duplicate import prevention.

These tests verify that the ImportacaoCadeiaService correctly prevents
duplicate imports of documents that appear in chains from different properties.

Bug Fix: Previously, the duplicate check only looked at documents imported from
the specific source property, allowing the same document to be imported multiple
times if reached through different property paths in the chain.
"""

import pytest
from datetime import date
from django.contrib.auth.models import User

from dominial.services.importacao_cadeia_service import ImportacaoCadeiaService
from dominial.models import DocumentoImportado
from dominial.tests.factories import (
    TIsFactory,
    ImovelFactory,
    DocumentoFactory,
    DocumentoTipoFactory,
    LancamentoFactory,
    LancamentoTipoFactory,
    PessoasFactory,
    CartoriosFactory,
)


@pytest.mark.unit
@pytest.mark.service
class TestCrossPropertyDuplicatePrevention:
    """Test duplicate prevention across different property chains."""

    @pytest.fixture
    def test_user(self, db):
        """Create a test user."""
        return User.objects.create_user(
            username='testuser',
            password='testpass123',
            email='test@test.com'
        )

    @pytest.fixture
    def complex_chain_scenario(self, db):
        """
        Create a complex chain scenario:

        Property 1 (Imovel1):
            Doc A (belongs to Imovel1)
              ↓
            Doc B (belongs to Imovel2)

        Property 2 (Imovel2):
            Doc B (belongs to Imovel2)
              ↓
            Doc C (belongs to Imovel3)

        Property 3 (Imovel3) - Destination:
            Will import documents from chains

        The critical case: Doc B appears in both Property 1 and Property 2 chains
        """
        ti = TIsFactory()

        # Create three properties
        imovel1 = ImovelFactory(terra_indigena_id=ti, matricula="PROP-001")
        imovel2 = ImovelFactory(terra_indigena_id=ti, matricula="PROP-002")
        imovel3 = ImovelFactory(terra_indigena_id=ti, matricula="PROP-003")  # Destination

        # Document A - originally in Imovel1
        doc_a = DocumentoFactory(
            imovel=imovel1,
            numero="DOC-A",
            tipo=DocumentoTipoFactory.transcricao()
        )

        # Document B - originally in Imovel2 (appears in both chains!)
        doc_b = DocumentoFactory(
            imovel=imovel2,
            numero="DOC-B",
            tipo=DocumentoTipoFactory.matricula()
        )

        # Document C - originally in Imovel3
        doc_c = DocumentoFactory(
            imovel=imovel3,
            numero="DOC-C",
            tipo=DocumentoTipoFactory.matricula()
        )

        # Create chain links
        # Chain 1: Doc A -> Doc B (Doc B originates from Doc A)
        LancamentoFactory.inicio_matricula(
            documento=doc_b,
            documento_origem=doc_a,
            origem="DOC-A"
        )

        # Chain 2: Doc B -> Doc C (Doc C originates from Doc B)
        LancamentoFactory.registro(
            documento=doc_c,
            documento_origem=doc_b,
            origem="DOC-B"
        )

        return {
            'imovel1': imovel1,
            'imovel2': imovel2,
            'imovel3': imovel3,
            'doc_a': doc_a,
            'doc_b': doc_b,
            'doc_c': doc_c,
        }

    def test_prevents_duplicate_import_from_different_property_paths(
        self, complex_chain_scenario, test_user
    ):
        """
        Test that a document reached through different property paths
        is only imported once.

        Scenario:
        1. Import Doc B from Imovel1's chain to Imovel3
        2. Try to import Doc B again from Imovel2's chain to Imovel3
        3. Should be rejected as duplicate
        """
        imovel3 = complex_chain_scenario['imovel3']
        doc_a = complex_chain_scenario['doc_a']
        doc_b = complex_chain_scenario['doc_b']
        doc_c = complex_chain_scenario['doc_c']

        # First import: Import Doc B through Imovel1's chain
        resultado1 = ImportacaoCadeiaService.importar_cadeia_dominial(
            imovel_destino_id=imovel3.id,
            documento_origem_id=doc_a.id,
            documentos_importaveis_ids=[doc_b.id],
            usuario_id=test_user.id
        )

        # Assert first import succeeded
        assert resultado1['sucesso'] is True
        assert resultado1['total_importados'] == 1
        assert resultado1['documentos_importados'][0]['numero'] == 'DOC-B'

        # Verify Doc B is marked as imported
        assert DocumentoImportado.objects.filter(documento=doc_b).exists()

        # Second import attempt: Try to import Doc B again through Imovel2's chain
        # (Doc B now appears to come from Imovel2 in this path)
        resultado2 = ImportacaoCadeiaService.importar_cadeia_dominial(
            imovel_destino_id=imovel3.id,
            documento_origem_id=doc_c.id,  # Different origin document
            documentos_importaveis_ids=[doc_b.id],
            usuario_id=test_user.id
        )

        # Assert second import was prevented
        assert resultado2['sucesso'] is True  # Still success (handled gracefully)
        assert resultado2['total_importados'] == 0  # But nothing new imported
        # Check that it was identified as duplicate (either in erros or mensagem)
        if 'erros' in resultado2:
            assert 'já foi importado' in resultado2['erros'][0]
        else:
            assert 'já foram importados anteriormente' in resultado2['mensagem']

        # Verify only one DocumentoImportado record exists for Doc B
        assert DocumentoImportado.objects.filter(documento=doc_b).count() == 1

    def test_import_different_documents_from_different_chains(
        self, complex_chain_scenario, test_user
    ):
        """
        Test that different documents can be imported from different chains.
        """
        imovel3 = complex_chain_scenario['imovel3']
        doc_a = complex_chain_scenario['doc_a']
        doc_b = complex_chain_scenario['doc_b']
        doc_c = complex_chain_scenario['doc_c']

        # Import Doc A from Imovel1's chain
        resultado1 = ImportacaoCadeiaService.importar_cadeia_dominial(
            imovel_destino_id=imovel3.id,
            documento_origem_id=doc_b.id,
            documentos_importaveis_ids=[doc_a.id],
            usuario_id=test_user.id
        )

        assert resultado1['sucesso'] is True
        assert resultado1['total_importados'] == 1

        # Import Doc B from Imovel2's chain (should succeed - different document)
        resultado2 = ImportacaoCadeiaService.importar_cadeia_dominial(
            imovel_destino_id=imovel3.id,
            documento_origem_id=doc_c.id,
            documentos_importaveis_ids=[doc_b.id],
            usuario_id=test_user.id
        )

        assert resultado2['sucesso'] is True
        assert resultado2['total_importados'] == 1

        # Verify both documents are imported
        assert DocumentoImportado.objects.filter(documento=doc_a).exists()
        assert DocumentoImportado.objects.filter(documento=doc_b).exists()
        assert DocumentoImportado.objects.count() == 2

    def test_batch_import_with_duplicate_in_different_chains(
        self, complex_chain_scenario, test_user
    ):
        """
        Test batch import where one document was already imported
        through a different chain.
        """
        imovel3 = complex_chain_scenario['imovel3']
        doc_a = complex_chain_scenario['doc_a']
        doc_b = complex_chain_scenario['doc_b']
        doc_c = complex_chain_scenario['doc_c']

        # First: Import Doc B
        resultado1 = ImportacaoCadeiaService.importar_cadeia_dominial(
            imovel_destino_id=imovel3.id,
            documento_origem_id=doc_a.id,
            documentos_importaveis_ids=[doc_b.id],
            usuario_id=test_user.id
        )

        assert resultado1['sucesso'] is True
        assert resultado1['total_importados'] == 1

        # Second: Try to import both Doc A and Doc B (Doc B already imported)
        resultado2 = ImportacaoCadeiaService.importar_cadeia_dominial(
            imovel_destino_id=imovel3.id,
            documento_origem_id=doc_c.id,
            documentos_importaveis_ids=[doc_a.id, doc_b.id],  # Batch with duplicate
            usuario_id=test_user.id
        )

        # Should succeed and import Doc A, skip Doc B
        assert resultado2['sucesso'] is True
        assert resultado2['total_importados'] == 1  # Only Doc A imported
        assert resultado2['documentos_importados'][0]['numero'] == 'DOC-A'
        assert len(resultado2['erros']) == 1
        assert 'DOC-B' in resultado2['erros'][0]
        assert 'já foi importado' in resultado2['erros'][0]

    def test_records_correct_imovel_origem_for_each_import(
        self, complex_chain_scenario, test_user
    ):
        """
        Test that imovel_origem is correctly recorded as the document's
        original property, not the source property of the import operation.
        """
        imovel1 = complex_chain_scenario['imovel1']
        imovel2 = complex_chain_scenario['imovel2']
        imovel3 = complex_chain_scenario['imovel3']
        doc_a = complex_chain_scenario['doc_a']
        doc_b = complex_chain_scenario['doc_b']

        # Import Doc A (originally from Imovel1)
        ImportacaoCadeiaService.importar_cadeia_dominial(
            imovel_destino_id=imovel3.id,
            documento_origem_id=doc_b.id,  # Source is Doc B
            documentos_importaveis_ids=[doc_a.id],
            usuario_id=test_user.id
        )

        # Import Doc B (originally from Imovel2)
        ImportacaoCadeiaService.importar_cadeia_dominial(
            imovel_destino_id=imovel3.id,
            documento_origem_id=doc_a.id,  # Source is Doc A
            documentos_importaveis_ids=[doc_b.id],
            usuario_id=test_user.id
        )

        # Verify imovel_origem is the document's original property
        doc_a_import = DocumentoImportado.objects.get(documento=doc_a)
        assert doc_a_import.imovel_origem == imovel1  # Doc A's original property

        doc_b_import = DocumentoImportado.objects.get(documento=doc_b)
        assert doc_b_import.imovel_origem == imovel2  # Doc B's original property


@pytest.mark.unit
@pytest.mark.service
class TestImportServiceDuplicateEdgeCases:
    """Test edge cases for duplicate detection."""

    @pytest.fixture
    def test_user(self, db):
        """Create a test user."""
        return User.objects.create_user(
            username='testuser',
            password='testpass123'
        )

    def test_same_document_number_different_properties_allowed(
        self, test_user, db
    ):
        """
        Test that documents with the same number but from different properties
        can both be imported (they are different documents).
        """
        ti = TIsFactory()
        imovel1 = ImovelFactory(terra_indigena_id=ti)
        imovel2 = ImovelFactory(terra_indigena_id=ti)
        imovel_dest = ImovelFactory(terra_indigena_id=ti)

        # Two different documents with same number in different properties
        doc1 = DocumentoFactory(imovel=imovel1, numero="M-100")
        doc2 = DocumentoFactory(imovel=imovel2, numero="M-100")  # Same number, different doc
        origem_doc = DocumentoFactory(imovel=imovel_dest)

        # Import both
        resultado1 = ImportacaoCadeiaService.importar_cadeia_dominial(
            imovel_destino_id=imovel_dest.id,
            documento_origem_id=origem_doc.id,
            documentos_importaveis_ids=[doc1.id],
            usuario_id=test_user.id
        )

        resultado2 = ImportacaoCadeiaService.importar_cadeia_dominial(
            imovel_destino_id=imovel_dest.id,
            documento_origem_id=origem_doc.id,
            documentos_importaveis_ids=[doc2.id],
            usuario_id=test_user.id
        )

        # Both should succeed (different documents)
        assert resultado1['sucesso'] is True
        assert resultado2['sucesso'] is True
        assert DocumentoImportado.objects.count() == 2

    def test_all_documents_already_imported_returns_success(
        self, test_user, db
    ):
        """
        Test that attempting to import all already-imported documents
        returns success with appropriate message.
        """
        ti = TIsFactory()
        imovel_origem = ImovelFactory(terra_indigena_id=ti)
        imovel_dest = ImovelFactory(terra_indigena_id=ti)

        doc1 = DocumentoFactory(imovel=imovel_origem)
        doc2 = DocumentoFactory(imovel=imovel_origem)
        origem_doc = DocumentoFactory(imovel=imovel_dest)

        # First import
        ImportacaoCadeiaService.importar_cadeia_dominial(
            imovel_destino_id=imovel_dest.id,
            documento_origem_id=origem_doc.id,
            documentos_importaveis_ids=[doc1.id, doc2.id],
            usuario_id=test_user.id
        )

        # Try to import again
        resultado = ImportacaoCadeiaService.importar_cadeia_dominial(
            imovel_destino_id=imovel_dest.id,
            documento_origem_id=origem_doc.id,
            documentos_importaveis_ids=[doc1.id, doc2.id],
            usuario_id=test_user.id
        )

        # Should return success with message
        assert resultado['sucesso'] is True
        assert resultado['total_importados'] == 0
        assert 'já foram importados anteriormente' in resultado['mensagem']
