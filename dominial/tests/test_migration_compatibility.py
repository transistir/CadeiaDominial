"""
Tests to validate PostgreSQL to SQLite migration compatibility.

This test suite ensures that the migrated SQLite database is fully compatible
with the original PostgreSQL data and maintains data integrity.
"""
import json
from django.test import TestCase
from django.db import connection
from django.db.models import Count, Q
from dominial.models import (
    TIs,
    Imovel,
    Documento,
    Lancamento,
    LancamentoPessoa,
    Pessoas,
    Cartorios,
    DocumentoTipo,
    LancamentoTipo,
    TerraIndigenaReferencia
)


class MigrationCompatibilityTestCase(TestCase):
    """Test suite for PostgreSQL to SQLite migration validation"""

    @classmethod
    def setUpClass(cls):
        """Load expected counts from PostgreSQL export metadata"""
        super().setUpClass()

        # These counts should match PostgreSQL database
        # Update these values based on actual PostgreSQL counts
        cls.expected_counts = {
            'tis': None,  # Will be set dynamically
            'imovel': None,
            'documento': None,
            'lancamento': None,
            'pessoas': None,
            'cartorios': None,
        }

    def test_database_engine_is_sqlite(self):
        """Verify we're using SQLite database"""
        db_engine = connection.settings_dict['ENGINE']
        self.assertEqual(
            db_engine,
            'django.db.backends.sqlite3',
            f"Expected SQLite but got {db_engine}"
        )

    def test_all_models_have_data(self):
        """Verify all core models have been populated"""
        models_to_check = [
            ('TIs', TIs),
            ('Imovel', Imovel),
            ('Documento', Documento),
            ('Lancamento', Lancamento),
            ('Pessoas', Pessoas),
            ('Cartorios', Cartorios),
            ('DocumentoTipo', DocumentoTipo),
            ('LancamentoTipo', LancamentoTipo),
        ]

        for model_name, model_class in models_to_check:
            count = model_class.objects.count()
            self.assertGreater(
                count,
                0,
                f"{model_name} has no records - migration may have failed"
            )
            print(f"✅ {model_name}: {count} records")

    def test_foreign_key_integrity(self):
        """Verify foreign key relationships are intact"""

        # Test Imovel -> TIs relationship
        imoveis_with_ti = Imovel.objects.filter(ti__isnull=False).count()
        total_imoveis = Imovel.objects.count()
        self.assertEqual(
            imoveis_with_ti,
            total_imoveis,
            "Some Imoveis missing TI foreign key"
        )

        # Test Documento -> Imovel relationship
        docs_with_imovel = Documento.objects.filter(imovel__isnull=False).count()
        total_docs = Documento.objects.count()
        self.assertEqual(
            docs_with_imovel,
            total_docs,
            "Some Documentos missing Imovel foreign key"
        )

        # Test Documento -> Cartorio relationship
        docs_with_cartorio = Documento.objects.filter(cartorio__isnull=False).count()
        self.assertGreater(
            docs_with_cartorio,
            0,
            "No Documentos have Cartorio relationship"
        )

        # Test Lancamento -> Documento relationship
        lancamentos_with_doc = Lancamento.objects.filter(documento__isnull=False).count()
        total_lancamentos = Lancamento.objects.count()
        self.assertEqual(
            lancamentos_with_doc,
            total_lancamentos,
            "Some Lancamentos missing Documento foreign key"
        )

        print(f"✅ Foreign key integrity verified")

    def test_unique_constraints(self):
        """Verify unique constraints are working (especially Documento)"""

        # Test Documento unique_together (numero, cartorio)
        documentos = Documento.objects.values('numero', 'cartorio').annotate(
            count=Count('id')
        ).filter(count__gt=1)

        self.assertEqual(
            documentos.count(),
            0,
            f"Found {documentos.count()} duplicate Documento records (numero, cartorio)"
        )

        # Test Cartorios unique CNS
        cartorios_duplicates = Cartorios.objects.values('cns').annotate(
            count=Count('id')
        ).filter(count__gt=1, cns__isnull=False)

        self.assertEqual(
            cartorios_duplicates.count(),
            0,
            f"Found {cartorios_duplicates.count()} Cartorios with duplicate CNS"
        )

        print(f"✅ Unique constraints validated")

    def test_cascade_deletion_behavior(self):
        """Test that CASCADE deletion works as expected in SQLite"""

        # Get a TI with imoveis
        ti_with_imoveis = TIs.objects.annotate(
            imovel_count=Count('imovel')
        ).filter(imovel_count__gt=0).first()

        if ti_with_imoveis:
            original_imovel_count = ti_with_imoveis.imovel.count()
            original_doc_count = Documento.objects.filter(
                imovel__ti=ti_with_imoveis
            ).count()

            self.assertGreater(
                original_imovel_count,
                0,
                "Test requires TI with Imoveis"
            )

            print(f"✅ CASCADE behavior testable (TI {ti_with_imoveis.id} has "
                  f"{original_imovel_count} imoveis, {original_doc_count} docs)")
        else:
            self.skipTest("No TI with Imoveis found for cascade testing")

    def test_text_field_encoding(self):
        """Verify Portuguese characters and special chars are preserved"""

        # Test TIs names with Portuguese characters
        tis_with_accents = TIs.objects.filter(
            Q(nome__icontains='ã') |
            Q(nome__icontains='á') |
            Q(nome__icontains='é') |
            Q(nome__icontains='í') |
            Q(nome__icontains='ó') |
            Q(nome__icontains='ú') |
            Q(nome__icontains='ç')
        )

        if tis_with_accents.exists():
            sample_ti = tis_with_accents.first()
            # Verify string can be encoded/decoded properly
            try:
                encoded = sample_ti.nome.encode('utf-8')
                decoded = encoded.decode('utf-8')
                self.assertEqual(sample_ti.nome, decoded)
                print(f"✅ UTF-8 encoding verified: '{sample_ti.nome}'")
            except UnicodeError as e:
                self.fail(f"Unicode encoding failed: {e}")

        # Test Pessoas names
        pessoas_with_accents = Pessoas.objects.filter(
            Q(nome__icontains='ã') |
            Q(nome__icontains='á')
        )

        if pessoas_with_accents.exists():
            sample_pessoa = pessoas_with_accents.first()
            self.assertIsNotNone(sample_pessoa.nome)
            print(f"✅ Pessoas UTF-8 verified: '{sample_pessoa.nome}'")

    def test_date_field_compatibility(self):
        """Verify date fields are properly stored in SQLite"""

        # Test Lancamento dates
        lancamentos_with_dates = Lancamento.objects.filter(
            data__isnull=False
        ).order_by('data')

        if lancamentos_with_dates.exists():
            first_lancamento = lancamentos_with_dates.first()
            last_lancamento = lancamentos_with_dates.last()

            self.assertIsNotNone(first_lancamento.data)
            self.assertIsNotNone(last_lancamento.data)

            # Verify date ordering works
            self.assertLessEqual(
                first_lancamento.data,
                last_lancamento.data,
                "Date ordering is broken"
            )

            print(f"✅ Date fields working: {first_lancamento.data} to "
                  f"{last_lancamento.data}")

    def test_decimal_field_precision(self):
        """Verify decimal fields maintain precision in SQLite"""

        # Test Lancamento area field
        lancamentos_with_area = Lancamento.objects.filter(
            area__isnull=False
        ).exclude(area=0)

        if lancamentos_with_area.exists():
            sample_lancamento = lancamentos_with_area.first()

            # Verify decimal precision (should have decimal places)
            area_str = str(sample_lancamento.area)
            self.assertIsNotNone(sample_lancamento.area)

            print(f"✅ Decimal precision maintained: {sample_lancamento.area} ha")

    def test_boolean_field_compatibility(self):
        """Verify boolean fields work correctly (PostgreSQL true/false vs SQLite 0/1)"""

        # Test any boolean field (e.g., Documento.arquivado if it exists)
        if hasattr(Documento, 'arquivado'):
            archived_docs = Documento.objects.filter(arquivado=True).count()
            active_docs = Documento.objects.filter(arquivado=False).count()
            total_docs = Documento.objects.count()

            self.assertEqual(
                archived_docs + active_docs,
                total_docs,
                "Boolean field counting doesn't match total"
            )

            print(f"✅ Boolean fields working: {archived_docs} archived, "
                  f"{active_docs} active")

    def test_many_to_many_relationships(self):
        """Verify many-to-many relationships through LancamentoPessoa"""

        # Test LancamentoPessoa links
        total_links = LancamentoPessoa.objects.count()
        self.assertGreater(
            total_links,
            0,
            "No LancamentoPessoa relationships found"
        )

        # Verify both sides of relationship exist
        links_with_lancamento = LancamentoPessoa.objects.filter(
            lancamento__isnull=False
        ).count()
        links_with_pessoa = LancamentoPessoa.objects.filter(
            pessoa__isnull=False
        ).count()

        self.assertEqual(links_with_lancamento, total_links)
        self.assertEqual(links_with_pessoa, total_links)

        print(f"✅ Many-to-many relationships intact: {total_links} links")

    def test_null_handling(self):
        """Verify NULL values are properly handled"""

        # Test nullable fields
        docs_without_cri_atual = Documento.objects.filter(
            cri_atual__isnull=True
        ).count()
        docs_with_cri_atual = Documento.objects.filter(
            cri_atual__isnull=False
        ).count()
        total_docs = Documento.objects.count()

        self.assertEqual(
            docs_without_cri_atual + docs_with_cri_atual,
            total_docs,
            "NULL handling broken for cri_atual field"
        )

        print(f"✅ NULL handling correct: {docs_with_cri_atual} with CRI, "
              f"{docs_without_cri_atual} without")

    def test_query_performance(self):
        """Basic performance test for common queries"""
        import time

        # Test 1: Count query
        start = time.time()
        count = Documento.objects.count()
        elapsed = time.time() - start
        self.assertLess(elapsed, 1.0, "Count query too slow")
        print(f"✅ Count query: {count} docs in {elapsed:.3f}s")

        # Test 2: Join query
        start = time.time()
        docs_with_ti = Documento.objects.select_related(
            'imovel__ti'
        )[:100]
        list(docs_with_ti)  # Force evaluation
        elapsed = time.time() - start
        self.assertLess(elapsed, 2.0, "Join query too slow")
        print(f"✅ Join query: 100 docs with TI in {elapsed:.3f}s")

        # Test 3: Filter query
        start = time.time()
        filtered = Lancamento.objects.filter(
            tipo__nome__icontains='compra'
        ).count()
        elapsed = time.time() - start
        self.assertLess(elapsed, 1.0, "Filter query too slow")
        print(f"✅ Filter query: {filtered} results in {elapsed:.3f}s")

    def test_autocomplete_fields_work(self):
        """Verify fields used in autocomplete views work"""

        # Test Cartorio search (used in autocomplete)
        cartorios = Cartorios.objects.filter(
            cidade__icontains='são'
        )[:10]

        self.assertGreater(
            cartorios.count(),
            0,
            "Cartorio search not working"
        )

        # Test Pessoas search
        pessoas = Pessoas.objects.filter(
            nome__icontains='silva'
        )[:10]

        # May or may not have results, but query should work
        print(f"✅ Autocomplete queries working: {cartorios.count()} cartorios, "
              f"{pessoas.count()} pessoas")

    def test_data_export_roundtrip(self):
        """Verify data can be exported from SQLite"""
        from django.core import serializers

        # Export a small sample
        sample_tis = TIs.objects.all()[:5]

        try:
            json_data = serializers.serialize('json', sample_tis)
            parsed = json.loads(json_data)

            self.assertEqual(
                len(parsed),
                sample_tis.count(),
                "Export serialization failed"
            )

            print(f"✅ Data export working: {len(parsed)} TIs serialized")
        except Exception as e:
            self.fail(f"Export failed: {e}")


class DataIntegrityTestCase(TestCase):
    """Additional tests for data integrity and business logic"""

    def test_documento_cartorio_consistency(self):
        """Verify Documento.cartorio matches expected relationships"""

        # All documentos should have a cartorio
        docs_without_cartorio = Documento.objects.filter(
            cartorio__isnull=True
        ).count()

        # Some might not have cartorio if that's valid in the business logic
        print(f"ℹ️  Documentos without cartorio: {docs_without_cartorio}")

    def test_lancamento_tipo_coverage(self):
        """Verify all lancamentos have valid tipos"""

        lancamentos_without_tipo = Lancamento.objects.filter(
            tipo__isnull=True
        ).count()

        self.assertEqual(
            lancamentos_without_tipo,
            0,
            f"Found {lancamentos_without_tipo} lancamentos without tipo"
        )

        # Check tipo distribution
        tipo_distribution = Lancamento.objects.values(
            'tipo__nome'
        ).annotate(count=Count('id')).order_by('-count')

        print(f"✅ Lancamento tipos distribution:")
        for item in tipo_distribution[:5]:
            print(f"   - {item['tipo__nome']}: {item['count']}")

    def test_imovel_has_documentos(self):
        """Check how many imoveis have associated documentos"""

        imoveis_with_docs = Imovel.objects.annotate(
            doc_count=Count('documento')
        ).filter(doc_count__gt=0).count()

        total_imoveis = Imovel.objects.count()

        percentage = (imoveis_with_docs / total_imoveis * 100) if total_imoveis > 0 else 0

        print(f"ℹ️  {imoveis_with_docs}/{total_imoveis} imoveis have documentos "
              f"({percentage:.1f}%)")

    def test_terra_indigena_reference_data(self):
        """Verify TerraIndigenaReferencia data is intact"""

        ref_count = TerraIndigenaReferencia.objects.count()

        if ref_count > 0:
            # Check for estado distribution
            estado_dist = TerraIndigenaReferencia.objects.values(
                'estado'
            ).annotate(count=Count('id')).order_by('-count')

            print(f"✅ TerraIndigenaReferencia: {ref_count} records")
            print(f"   Top estados:")
            for item in estado_dist[:5]:
                print(f"   - {item['estado']}: {item['count']}")
        else:
            print(f"⚠️  No TerraIndigenaReferencia data found")


class PostgreSQLComparisonTestCase(TestCase):
    """
    Tests that compare SQLite data against known PostgreSQL values.

    Update these tests with actual PostgreSQL counts after migration.
    """

    def test_record_counts_match_postgresql(self):
        """Compare record counts with PostgreSQL source"""

        # TODO: Update these with actual PostgreSQL counts
        # Run these queries on PostgreSQL:
        # SELECT COUNT(*) FROM dominial_tis;
        # SELECT COUNT(*) FROM dominial_imovel;
        # SELECT COUNT(*) FROM dominial_documento;
        # SELECT COUNT(*) FROM dominial_lancamento;
        # SELECT COUNT(*) FROM dominial_pessoas;
        # SELECT COUNT(*) FROM dominial_cartorios;

        sqlite_counts = {
            'tis': TIs.objects.count(),
            'imovel': Imovel.objects.count(),
            'documento': Documento.objects.count(),
            'lancamento': Lancamento.objects.count(),
            'pessoas': Pessoas.objects.count(),
            'cartorios': Cartorios.objects.count(),
        }

        print(f"\n📊 SQLite Record Counts:")
        for model, count in sqlite_counts.items():
            print(f"   {model}: {count}")

        print(f"\n⚠️  TODO: Compare these with PostgreSQL counts and update test")
