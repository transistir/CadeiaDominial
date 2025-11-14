"""
Unit tests for HierarquiaArvoreService.

Tests the construction of property ownership chain hierarchies (cadeia dominial).
"""

import pytest
from datetime import date
from dominial.services.hierarquia_arvore_service import HierarquiaArvoreService
from dominial.models import Documento, Lancamento
from .factories import (
    ImovelFactory,
    DocumentoFactory,
    LancamentoFactory,
    LancamentoTipoFactory,
    create_simple_chain,
)


@pytest.mark.unit
@pytest.mark.service
class TestHierarquiaArvoreService:
    """Test suite for HierarquiaArvoreService."""

    def test_identificar_documento_principal_exact_match(self, db):
        """Test identifying principal document with exact matricula match."""
        # Arrange
        imovel = ImovelFactory(matricula="12345")
        doc_other = DocumentoFactory(imovel=imovel, numero="99999")
        doc_principal = DocumentoFactory(imovel=imovel, numero="12345")

        # Act
        result = HierarquiaArvoreService._identificar_documento_principal(imovel)

        # Assert
        assert result.id == doc_principal.id
        assert result.numero == imovel.matricula

    def test_identificar_documento_principal_partial_match(self, db):
        """Test identifying principal document with partial matricula match."""
        # Arrange
        imovel = ImovelFactory(matricula="6700")
        doc_principal = DocumentoFactory(imovel=imovel, numero="M-6700")
        doc_other = DocumentoFactory(imovel=imovel, numero="M-1234")

        # Act
        result = HierarquiaArvoreService._identificar_documento_principal(imovel)

        # Assert
        assert result.id == doc_principal.id
        assert imovel.matricula in result.numero

    def test_identificar_documento_principal_fallback_to_first(self, db):
        """Test fallback to first document when no match found."""
        # Arrange
        imovel = ImovelFactory(matricula="99999")
        doc_first = DocumentoFactory(imovel=imovel, numero="M-0001")
        doc_second = DocumentoFactory(imovel=imovel, numero="M-0002")

        # Act
        result = HierarquiaArvoreService._identificar_documento_principal(imovel)

        # Assert
        assert result.id == doc_first.id

    def test_identificar_documento_principal_none_when_no_documents(self, db):
        """Test returns None when imovel has no documents."""
        # Arrange
        imovel = ImovelFactory()

        # Act
        result = HierarquiaArvoreService._identificar_documento_principal(imovel)

        # Assert
        assert result is None

    def test_construir_arvore_simple_chain(self, db):
        """Test building tree for simple 2-document chain."""
        # Arrange: doc1 <- doc2 (doc2 originates from doc1)
        imovel = ImovelFactory(matricula="M-002")
        doc1 = DocumentoFactory.transcricao(imovel=imovel, numero="T-001")
        doc2 = DocumentoFactory.matricula(imovel=imovel, numero="M-002")

        # Create lancamento linking doc2 to doc1
        tipo_inicio = LancamentoTipoFactory.inicio_matricula()
        lanc = LancamentoFactory(
            documento=doc2,
            tipo=tipo_inicio,
            documento_origem=doc1,
            origem="T-001",  # Text reference to origin
            eh_inicio_matricula=True
        )

        # Act
        arvore = HierarquiaArvoreService.construir_arvore_cadeia_dominial(imovel)

        # Assert
        assert arvore is not None
        assert len(arvore['documentos']) == 2
        assert any(d['numero'] == 'M-002' for d in arvore['documentos'])
        assert any(d['numero'] == 'T-001' for d in arvore['documentos'])

        # Verify connection exists
        assert len(arvore['conexoes']) >= 1
        # Connection should be from child to parent (M-002 -> T-001)
        conexao_encontrada = any(
            c['from'] == 'M-002' and c['to'] == 'T-001'
            for c in arvore['conexoes']
        )
        assert conexao_encontrada, "Connection from M-002 to T-001 should exist"

    def test_construir_arvore_three_document_chain(self, db):
        """Test building tree for 3-document chain."""
        # Arrange: doc1 <- doc2 <- doc3
        docs = create_simple_chain(length=3)
        imovel = docs[0].imovel

        # Make the last document match the imovel matricula
        docs[2].numero = imovel.matricula
        docs[2].save()

        # Act
        arvore = HierarquiaArvoreService.construir_arvore_cadeia_dominial(imovel)

        # Assert
        assert arvore is not None
        assert len(arvore['documentos']) == 3

        # Verify all documents are in the tree
        doc_numbers = [d['numero'] for d in arvore['documentos']]
        for doc in docs:
            assert doc.numero in doc_numbers

        # Should have at least 2 connections (3 docs = 2 links minimum)
        assert len(arvore['conexoes']) >= 2

    def test_construir_arvore_no_principal_documento(self, db):
        """Test building tree when no principal document exists."""
        # Arrange
        imovel = ImovelFactory()
        # No documents created

        # Act
        arvore = HierarquiaArvoreService.construir_arvore_cadeia_dominial(imovel)

        # Assert
        assert 'erro' in arvore
        assert arvore['erro'] == 'Nenhum documento principal encontrado para este imóvel'
        assert len(arvore['documentos']) == 0

    def test_construir_arvore_circular_reference_handling(self, db):
        """Test that circular references don't cause infinite loops."""
        # Arrange: doc1 <- doc2, doc2 <- doc1 (circular)
        imovel = ImovelFactory(matricula="M-001")
        doc1 = DocumentoFactory(imovel=imovel, numero="M-001")
        doc2 = DocumentoFactory(imovel=imovel, numero="M-002")

        # Create circular reference
        LancamentoFactory(
            documento=doc1,
            documento_origem=doc2,
            origem="M-002"
        )
        LancamentoFactory(
            documento=doc2,
            documento_origem=doc1,
            origem="M-001"
        )

        # Act (should not hang)
        arvore = HierarquiaArvoreService.construir_arvore_cadeia_dominial(imovel)

        # Assert - should complete without infinite loop
        assert arvore is not None
        assert len(arvore['documentos']) <= 2  # Should not duplicate documents

    def test_construir_arvore_multiple_origins(self, db):
        """Test building tree with document having multiple origins."""
        # Arrange: doc1 <- doc3, doc2 <- doc3 (doc3 has two origins)
        imovel = ImovelFactory(matricula="M-003")
        doc1 = DocumentoFactory(imovel=imovel, numero="T-001")
        doc2 = DocumentoFactory(imovel=imovel, numero="T-002")
        doc3 = DocumentoFactory(imovel=imovel, numero="M-003")

        # Create lancamento with multiple origins
        LancamentoFactory(
            documento=doc3,
            origem="T-001 e T-002",  # Multiple origins in text
            eh_inicio_matricula=True
        )

        # Act
        arvore = HierarquiaArvoreService.construir_arvore_cadeia_dominial(imovel)

        # Assert
        assert arvore is not None
        assert len(arvore['documentos']) >= 2  # At least doc3 and one origin

    def test_criar_no_documento_structure(self, db):
        """Test document node creation has correct structure."""
        # Arrange
        imovel = ImovelFactory(matricula="M-123")
        documento = DocumentoFactory(
            imovel=imovel,
            numero="M-123",
            data=date(2024, 1, 15),
            livro="L01",
            folha="100"
        )

        # Create some lancamentos to test count
        LancamentoFactory(documento=documento)
        LancamentoFactory(documento=documento)

        # Act
        node = HierarquiaArvoreService._criar_no_documento(documento, imovel, nivel=0)

        # Assert
        assert node['id'] == documento.id
        assert node['numero'] == 'M-123'
        assert node['tipo'] == documento.tipo.tipo
        assert node['data'] == '15/01/2024'
        assert node['cartorio'] == documento.cartorio.nome
        assert node['livro'] == 'L01'
        assert node['folha'] == '100'
        assert node['total_lancamentos'] == 2
        assert node['nivel'] == 0
        assert node['is_documento_atual'] is True  # Matches matricula

    def test_criar_no_documento_shared_document(self, db):
        """Test creating node for document from different imovel (shared)."""
        # Arrange
        imovel1 = ImovelFactory(matricula="M-001")
        imovel2 = ImovelFactory(matricula="M-002")
        documento = DocumentoFactory(imovel=imovel1, numero="T-999")

        # Act - creating node for doc from imovel1 while working on imovel2
        node = HierarquiaArvoreService._criar_no_documento(
            documento, imovel2, nivel=1
        )

        # Assert
        assert node['is_compartilhado'] is True  # From different imovel
        assert node['is_documento_atual'] is False

    def test_buscar_documentos_pais_with_origem_text(self, db):
        """Test finding parent documents from origem text field."""
        # Arrange
        imovel = ImovelFactory()
        doc_pai = DocumentoFactory(imovel=imovel, numero="T-100")
        doc_filho = DocumentoFactory(imovel=imovel, numero="M-200")

        # Create lancamento with origem text
        LancamentoFactory(
            documento=doc_filho,
            origem="T-100",  # Reference to parent
            documento_origem=doc_pai
        )

        # Act
        pais = HierarquiaArvoreService._buscar_documentos_pais(
            doc_filho, imovel, criar_documentos_automaticos=False
        )

        # Assert
        assert len(pais) >= 1
        assert doc_pai in pais

    def test_buscar_documentos_pais_no_origem(self, db):
        """Test finding parent documents when no origem exists."""
        # Arrange
        imovel = ImovelFactory()
        doc = DocumentoFactory(imovel=imovel, numero="M-100")
        # No lancamentos with origem

        # Act
        pais = HierarquiaArvoreService._buscar_documentos_pais(
            doc, imovel, criar_documentos_automaticos=False
        )

        # Assert
        assert len(pais) == 0

    def test_buscar_documentos_pais_create_automatic(self, db):
        """Test automatic document creation for missing origins."""
        # Arrange
        imovel = ImovelFactory()
        doc = DocumentoFactory(imovel=imovel, numero="M-100")

        # Create lancamento referencing non-existent document
        LancamentoFactory(
            documento=doc,
            origem="T-999",  # This document doesn't exist
        )

        # Act
        pais = HierarquiaArvoreService._buscar_documentos_pais(
            doc, imovel, criar_documentos_automaticos=True
        )

        # Assert
        assert len(pais) >= 1
        # Verify the document was created
        created_doc = Documento.objects.filter(numero="T-999").first()
        assert created_doc is not None
        assert created_doc in pais

    def test_arvore_imovel_data_structure(self, db):
        """Test that arvore contains correct imovel data."""
        # Arrange
        imovel = ImovelFactory(
            matricula="12345",
            nome="Test Imovel"
        )
        DocumentoFactory(imovel=imovel, numero="12345")

        # Act
        arvore = HierarquiaArvoreService.construir_arvore_cadeia_dominial(imovel)

        # Assert
        assert 'imovel' in arvore
        assert arvore['imovel']['id'] == imovel.id
        assert arvore['imovel']['matricula'] == "12345"
        assert arvore['imovel']['nome'] == "Test Imovel"
        assert arvore['imovel']['proprietario'] == imovel.proprietario.nome

    def test_arvore_conexoes_structure(self, db):
        """Test that conexoes have correct structure."""
        # Arrange
        docs = create_simple_chain(length=2)
        imovel = docs[0].imovel
        docs[1].numero = imovel.matricula
        docs[1].save()

        # Act
        arvore = HierarquiaArvoreService.construir_arvore_cadeia_dominial(imovel)

        # Assert
        assert 'conexoes' in arvore
        if len(arvore['conexoes']) > 0:
            conexao = arvore['conexoes'][0]
            assert 'from' in conexao
            assert 'to' in conexao
            assert 'tipo' in conexao

    def test_multiple_lancamentos_same_origem(self, db):
        """Test handling multiple lancamentos referencing the same origem."""
        # Arrange
        imovel = ImovelFactory()
        doc_pai = DocumentoFactory(imovel=imovel, numero="T-100")
        doc_filho = DocumentoFactory(imovel=imovel, numero="M-200")

        # Create multiple lancamentos with same origem
        LancamentoFactory(documento=doc_filho, origem="T-100")
        LancamentoFactory(documento=doc_filho, origem="T-100")

        # Act
        pais = HierarquiaArvoreService._buscar_documentos_pais(
            doc_filho, imovel, criar_documentos_automaticos=False
        )

        # Assert - should not duplicate the parent document
        pai_ids = [p.id for p in pais]
        assert len(pai_ids) == len(set(pai_ids)), "Should not have duplicate parents"

    @pytest.mark.slow
    def test_large_chain_performance(self, db):
        """Test performance with a large chain (10 documents)."""
        # Arrange
        docs = create_simple_chain(length=10)
        imovel = docs[0].imovel
        docs[-1].numero = imovel.matricula
        docs[-1].save()

        # Act
        arvore = HierarquiaArvoreService.construir_arvore_cadeia_dominial(imovel)

        # Assert
        assert len(arvore['documentos']) == 10
        # Should have connections between all documents
        assert len(arvore['conexoes']) >= 9  # 10 docs = at least 9 connections


@pytest.mark.unit
@pytest.mark.service
class TestHierarquiaArvoreServiceEdgeCases:
    """Test edge cases and error handling."""

    def test_documento_with_empty_origem_field(self, db):
        """Test handling document with empty string origem."""
        # Arrange
        imovel = ImovelFactory()
        doc = DocumentoFactory(imovel=imovel)
        LancamentoFactory(documento=doc, origem="")  # Empty string

        # Act
        pais = HierarquiaArvoreService._buscar_documentos_pais(
            doc, imovel, criar_documentos_automaticos=False
        )

        # Assert
        assert len(pais) == 0  # Should handle empty string gracefully

    def test_documento_with_null_origem_field(self, db):
        """Test handling document with null origem."""
        # Arrange
        imovel = ImovelFactory()
        doc = DocumentoFactory(imovel=imovel)
        LancamentoFactory(documento=doc, origem=None)

        # Act
        pais = HierarquiaArvoreService._buscar_documentos_pais(
            doc, imovel, criar_documentos_automaticos=False
        )

        # Assert
        assert len(pais) == 0  # Should handle None gracefully

    def test_documento_with_malformed_origem_text(self, db):
        """Test handling document with malformed origem text."""
        # Arrange
        imovel = ImovelFactory()
        doc = DocumentoFactory(imovel=imovel)
        LancamentoFactory(
            documento=doc,
            origem="Some random text without proper doc references"
        )

        # Act
        pais = HierarquiaArvoreService._buscar_documentos_pais(
            doc, imovel, criar_documentos_automaticos=False
        )

        # Assert
        # Should not crash, might return 0 or handle gracefully
        assert isinstance(pais, list)

    def test_criar_documento_automatico_matricula(self, db):
        """Test automatic creation of matrícula document."""
        # Arrange
        imovel = ImovelFactory()

        # Act
        doc = HierarquiaArvoreService._criar_documento_automatico("M-999", imovel)

        # Assert
        assert doc is not None
        assert doc.numero == "M-999"
        assert doc.tipo.tipo == 'matricula'
        assert doc.imovel == imovel
        assert "automaticamente" in doc.observacoes.lower()

    def test_criar_documento_automatico_transcricao(self, db):
        """Test automatic creation of transcrição document."""
        # Arrange
        imovel = ImovelFactory()

        # Act
        doc = HierarquiaArvoreService._criar_documento_automatico("T-888", imovel)

        # Assert
        assert doc is not None
        assert doc.numero == "T-888"
        assert doc.tipo.tipo == 'transcricao'

    def test_criar_documento_automatico_invalid_format(self, db):
        """Test automatic creation fails for invalid document format."""
        # Arrange
        imovel = ImovelFactory()

        # Act
        doc = HierarquiaArvoreService._criar_documento_automatico("INVALID", imovel)

        # Assert
        assert doc is None  # Should return None for invalid format
