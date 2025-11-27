"""
Integration tests for ImportacaoCadeiaService.

Tests the import/undo cycle to ensure:
- New imports keep documents in their original imóvel
- Old imports (with moved documents) can be undone correctly
- Backward compatibility is maintained
"""
import pytest
from django.test import TestCase
from django.contrib.auth.models import User
from ..models import DocumentoImportado, Documento
from ..services.importacao_cadeia_service import ImportacaoCadeiaService
from .factories import ImovelFactory, DocumentoFactory


class ImportacaoCadeiaServiceTest(TestCase):
    """
    Integration tests for ImportacaoCadeiaService
    """

    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )

        # Create source and destination imóveis
        self.imovel_origem = ImovelFactory(matricula='ORIGEM-001', nome='Imóvel Origem')
        self.imovel_destino = ImovelFactory(matricula='DESTINO-001', nome='Imóvel Destino')

        # Create a document in the source imóvel
        self.documento = DocumentoFactory(
            imovel=self.imovel_origem,
            numero='DOC-TEST-001'
        )

    def test_import_keeps_document_in_original_imovel(self):
        """
        Test that importing a document keeps it in its original imóvel.

        The new import behavior should only create a DocumentoImportado
        record without moving the document.
        """
        result = ImportacaoCadeiaService.importar_cadeia_dominial(
            imovel_destino_id=self.imovel_destino.id,
            documento_origem_id=self.documento.id,
            documentos_importaveis_ids=[self.documento.id],
            usuario_id=self.user.id
        )

        self.assertTrue(result['sucesso'])
        self.assertEqual(result['total_importados'], 1)

        # Refresh document from database
        self.documento.refresh_from_db()

        # Document should still be in the original imóvel
        self.assertEqual(
            self.documento.imovel_id,
            self.imovel_origem.id,
            "Document should remain in original imóvel after import"
        )

        # DocumentoImportado should have correct imovel_destino
        doc_importado = DocumentoImportado.objects.get(documento=self.documento)
        self.assertEqual(doc_importado.imovel_origem_id, self.imovel_origem.id)
        self.assertEqual(doc_importado.imovel_destino_id, self.imovel_destino.id)

    def test_undo_import_for_new_style_import(self):
        """
        Test that undoing a new-style import (document stayed in place)
        correctly removes the DocumentoImportado record.
        """
        # First, import the document
        ImportacaoCadeiaService.importar_cadeia_dominial(
            imovel_destino_id=self.imovel_destino.id,
            documento_origem_id=self.documento.id,
            documentos_importaveis_ids=[self.documento.id],
            usuario_id=self.user.id
        )

        doc_importado = DocumentoImportado.objects.get(documento=self.documento)

        # Undo the import
        result = ImportacaoCadeiaService.desfazer_importacao(
            documento_importado_id=doc_importado.id,
            usuario_id=self.user.id
        )

        self.assertTrue(result['sucesso'])

        # Document should still be in original imóvel
        self.documento.refresh_from_db()
        self.assertEqual(self.documento.imovel_id, self.imovel_origem.id)

        # DocumentoImportado record should be deleted
        self.assertFalse(
            DocumentoImportado.objects.filter(documento=self.documento).exists()
        )

    def test_undo_import_for_old_style_import_restores_document(self):
        """
        Test backward compatibility: undoing an old-style import
        (where document was moved) restores the document to its origin.

        This simulates imports made before the fix that kept documents in place.
        """
        # Simulate old-style import by manually moving the document
        self.documento.imovel = self.imovel_destino
        self.documento.save()

        # Create DocumentoImportado record (like old code did)
        doc_importado = DocumentoImportado.objects.create(
            documento=self.documento,
            imovel_origem=self.imovel_origem,
            imovel_destino=self.imovel_destino,
            importado_por=self.user
        )

        # Verify document is in destination
        self.assertEqual(self.documento.imovel_id, self.imovel_destino.id)

        # Undo the import
        result = ImportacaoCadeiaService.desfazer_importacao(
            documento_importado_id=doc_importado.id,
            usuario_id=self.user.id
        )

        self.assertTrue(result['sucesso'])

        # Document should be restored to original imóvel
        self.documento.refresh_from_db()
        self.assertEqual(
            self.documento.imovel_id,
            self.imovel_origem.id,
            "Document should be restored to original imóvel after undo"
        )

        # DocumentoImportado record should be deleted
        self.assertFalse(
            DocumentoImportado.objects.filter(documento=self.documento).exists()
        )

    def test_cannot_import_same_document_twice(self):
        """
        Test that the same document cannot be imported twice.

        The duplicate check should prevent re-importing regardless of destination.
        """
        # First import
        result1 = ImportacaoCadeiaService.importar_cadeia_dominial(
            imovel_destino_id=self.imovel_destino.id,
            documento_origem_id=self.documento.id,
            documentos_importaveis_ids=[self.documento.id],
            usuario_id=self.user.id
        )

        self.assertTrue(result1['sucesso'])
        self.assertEqual(result1['total_importados'], 1)

        # Create another destination
        imovel_destino2 = ImovelFactory(matricula='DESTINO-002', nome='Imóvel Destino 2')

        # Try to import to different destination
        result2 = ImportacaoCadeiaService.importar_cadeia_dominial(
            imovel_destino_id=imovel_destino2.id,
            documento_origem_id=self.documento.id,
            documentos_importaveis_ids=[self.documento.id],
            usuario_id=self.user.id
        )

        # Should report already imported
        self.assertEqual(result2['total_importados'], 0)
        self.assertTrue(any('já foi importado' in erro for erro in result2.get('erros', [])))

    def test_verificar_documentos_importados_by_destination(self):
        """
        Test that verificar_documentos_importados correctly queries by destination.
        """
        # Import document
        ImportacaoCadeiaService.importar_cadeia_dominial(
            imovel_destino_id=self.imovel_destino.id,
            documento_origem_id=self.documento.id,
            documentos_importaveis_ids=[self.documento.id],
            usuario_id=self.user.id
        )

        # Query by destination should find it
        result = ImportacaoCadeiaService.verificar_documentos_importados(
            self.imovel_destino.id
        )
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['numero'], 'DOC-TEST-001')

        # Query by origin should NOT find it (document wasn't imported TO origin)
        result_origem = ImportacaoCadeiaService.verificar_documentos_importados(
            self.imovel_origem.id
        )
        self.assertEqual(len(result_origem), 0)

    def test_permission_check_in_undo(self):
        """
        Test that only the user who imported can undo the import.
        """
        # Import as user1
        ImportacaoCadeiaService.importar_cadeia_dominial(
            imovel_destino_id=self.imovel_destino.id,
            documento_origem_id=self.documento.id,
            documentos_importaveis_ids=[self.documento.id],
            usuario_id=self.user.id
        )

        doc_importado = DocumentoImportado.objects.get(documento=self.documento)

        # Create another user
        user2 = User.objects.create_user(
            username='testuser2',
            password='testpass123'
        )

        # Try to undo as user2
        result = ImportacaoCadeiaService.desfazer_importacao(
            documento_importado_id=doc_importado.id,
            usuario_id=user2.id
        )

        self.assertFalse(result['sucesso'])
        self.assertIn('permissão', result['erro'])

        # Record should still exist
        self.assertTrue(
            DocumentoImportado.objects.filter(documento=self.documento).exists()
        )
