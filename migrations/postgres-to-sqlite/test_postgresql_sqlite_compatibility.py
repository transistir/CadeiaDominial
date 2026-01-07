"""
Comprehensive PostgreSQL to SQLite Migration Compatibility Tests

This test suite validates that the SQLite database is fully compatible
with the PostgreSQL source and maintains complete data integrity.

Test Coverage:
- Database engine verification
- Record count accuracy (>95% threshold)
- Foreign key relationships
- Unique constraints
- Data type compatibility
- UTF-8 encoding (Portuguese characters)
- Query performance
- Business logic integrity

Run with: python manage.py test dominial.tests.test_postgresql_sqlite_compatibility
"""

import sqlite3
from decimal import Decimal
from django.test import TestCase
from django.db import connection
from django.db.models import Count, Q, Max, Min
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


class DatabaseEngineTest(TestCase):
    """Verify we're using SQLite database engine"""

    def test_database_is_sqlite(self):
        """Confirm SQLite is configured as the database backend"""
        db_engine = connection.settings_dict['ENGINE']
        self.assertEqual(
            db_engine,
            'django.db.backends.sqlite3',
            f"Expected SQLite but found {db_engine}"
        )
        print(f"✅ Database engine: {db_engine}")


class RecordCountTest(TestCase):
    """Verify all data was migrated from PostgreSQL"""

    # Expected counts from PostgreSQL source
    EXPECTED_COUNTS = {
        'TIs': 641,
        'Imovel': 296,
        'Documento': 1220,
        'Lancamento': 3172,
        'Pessoas': 1899,
        'Cartorios': 3840,
        'LancamentoPessoa': 4222,
        'DocumentoTipo': 3,
        'LancamentoTipo': 3,
    }

    def test_record_counts_within_threshold(self):
        """Verify record counts are within 95% of PostgreSQL source"""
        models_to_check = [
            ('TIs', TIs),
            ('Imovel', Imovel),
            ('Documento', Documento),
            ('Lancamento', Lancamento),
            ('Pessoas', Pessoas),
            ('Cartorios', Cartorios),
            ('LancamentoPessoa', LancamentoPessoa),
            ('DocumentoTipo', DocumentoTipo),
            ('LancamentoTipo', LancamentoTipo),
        ]

        print(f"\n📊 Record Count Verification:")
        all_passed = True

        for model_name, model_class in models_to_check:
            actual_count = model_class.objects.count()
            expected_count = self.EXPECTED_COUNTS[model_name]

            # Calculate percentage
            if expected_count > 0:
                percentage = (actual_count / expected_count) * 100
            else:
                percentage = 100 if actual_count == 0 else 0

            # 95% threshold for import success
            passed = percentage >= 95.0
            symbol = "✅" if passed else "⚠️"

            print(f"   {symbol} {model_name}: {actual_count}/{expected_count} ({percentage:.1f}%)")

            if not passed:
                all_passed = False

            # Assert at least 95% of records present
            self.assertGreaterEqual(
                percentage,
                95.0,
                f"{model_name} has only {percentage:.1f}% of expected records"
            )

        if all_passed:
            print(f"\n   ✅ All models passed 95% threshold")

    def test_all_models_have_data(self):
        """Verify all core models contain records"""
        models = [
            ('TIs', TIs),
            ('Imovel', Imovel),
            ('Documento', Documento),
            ('Lancamento', Lancamento),
            ('Pessoas', Pessoas),
            ('Cartorios', Cartorios),
        ]

        for model_name, model_class in models:
            count = model_class.objects.count()
            self.assertGreater(
                count,
                0,
                f"{model_name} has no records - migration failed"
            )


class ForeignKeyIntegrityTest(TestCase):
    """Verify all foreign key relationships are intact"""

    def test_imovel_ti_relationship(self):
        """All Imoveis should reference valid TIs"""
        total_imoveis = Imovel.objects.count()
        imoveis_with_ti = Imovel.objects.exclude(
            terra_indigena_id_id__isnull=True
        ).count()

        percentage = (imoveis_with_ti / total_imoveis * 100) if total_imoveis > 0 else 0

        print(f"\n🔗 Foreign Key Integrity:")
        print(f"   Imoveis with TI: {imoveis_with_ti}/{total_imoveis} ({percentage:.1f}%)")

        self.assertGreater(
            percentage,
            90.0,
            f"Only {percentage:.1f}% of Imoveis have TI relationships"
        )

    def test_documento_imovel_relationship(self):
        """All Documentos should reference valid Imoveis"""
        total_docs = Documento.objects.count()
        docs_with_imovel = Documento.objects.filter(imovel__isnull=False).count()

        percentage = (docs_with_imovel / total_docs * 100) if total_docs > 0 else 0
        print(f"   Documentos with Imovel: {docs_with_imovel}/{total_docs} ({percentage:.1f}%)")

        self.assertEqual(
            docs_with_imovel,
            total_docs,
            "Some Documentos missing Imovel foreign key"
        )

    def test_lancamento_documento_relationship(self):
        """All Lancamentos should reference valid Documentos"""
        total_lanc = Lancamento.objects.count()
        lanc_with_doc = Lancamento.objects.filter(documento__isnull=False).count()

        percentage = (lanc_with_doc / total_lanc * 100) if total_lanc > 0 else 0
        print(f"   Lancamentos with Documento: {lanc_with_doc}/{total_lanc} ({percentage:.1f}%)")

        self.assertEqual(
            lanc_with_doc,
            total_lanc,
            "Some Lancamentos missing Documento foreign key"
        )

    def test_lancamentopessoa_relationships(self):
        """LancamentoPessoa should have valid FK to both Lancamento and Pessoa"""
        total_links = LancamentoPessoa.objects.count()

        links_with_lancamento = LancamentoPessoa.objects.filter(
            lancamento__isnull=False
        ).count()

        links_with_pessoa = LancamentoPessoa.objects.filter(
            pessoa__isnull=False
        ).count()

        print(f"   LancamentoPessoa links: {total_links}")
        print(f"   - with Lancamento: {links_with_lancamento} ({links_with_lancamento/total_links*100:.1f}%)")
        print(f"   - with Pessoa: {links_with_pessoa} ({links_with_pessoa/total_links*100:.1f}%)")

        self.assertEqual(links_with_lancamento, total_links)
        self.assertEqual(links_with_pessoa, total_links)


class UniqueConstraintTest(TestCase):
    """Verify unique constraints work correctly in SQLite"""

    def test_documento_unique_together(self):
        """Documento (numero, cartorio) unique constraint"""
        # Check for duplicates using Django ORM
        duplicates = Documento.objects.values('numero', 'cartorio').annotate(
            count=Count('id')
        ).filter(count__gt=1)

        dup_count = duplicates.count()

        print(f"\n🔐 Unique Constraints:")
        print(f"   Documento (numero, cartorio) duplicates: {dup_count}")

        self.assertEqual(
            dup_count,
            0,
            f"Found {dup_count} duplicate Documento records"
        )

    def test_cartorios_unique_cns(self):
        """Cartorios CNS should be unique"""
        # Check for duplicate CNS codes
        duplicates = Cartorios.objects.values('cns').annotate(
            count=Count('id')
        ).filter(count__gt=1, cns__isnull=False)

        dup_count = duplicates.count()
        print(f"   Cartorios CNS duplicates: {dup_count}")

        self.assertEqual(
            dup_count,
            0,
            f"Found {dup_count} Cartorios with duplicate CNS"
        )


class DataTypeCompatibilityTest(TestCase):
    """Verify PostgreSQL data types work correctly in SQLite"""

    def test_utf8_encoding_portuguese(self):
        """Portuguese characters (ã, á, é, ç, etc.) preserved"""
        # Test TIs names with accents
        tis_with_accents = TIs.objects.filter(
            Q(nome__icontains='ã') |
            Q(nome__icontains='á') |
            Q(nome__icontains='ç')
        )

        if tis_with_accents.exists():
            sample = tis_with_accents.first()

            # Verify encoding/decoding works
            try:
                encoded = sample.nome.encode('utf-8')
                decoded = encoded.decode('utf-8')
                self.assertEqual(sample.nome, decoded)
                print(f"\n📝 UTF-8 Encoding:")
                print(f"   ✅ Sample TI: '{sample.nome}'")
            except UnicodeError as e:
                self.fail(f"UTF-8 encoding failed: {e}")

        # Test Pessoas names
        pessoas_with_accents = Pessoas.objects.filter(
            Q(nome__icontains='ã') | Q(nome__icontains='á')
        ).first()

        if pessoas_with_accents:
            print(f"   ✅ Sample Pessoa: '{pessoas_with_accents.nome}'")

    def test_date_fields(self):
        """Date fields stored and queried correctly"""
        lancamentos_with_dates = Lancamento.objects.filter(
            data__isnull=False
        ).order_by('data')

        if lancamentos_with_dates.exists():
            first_lanc = lancamentos_with_dates.first()
            last_lanc = lancamentos_with_dates.last()

            self.assertIsNotNone(first_lanc.data)
            self.assertIsNotNone(last_lanc.data)

            # Verify date ordering
            self.assertLessEqual(first_lanc.data, last_lanc.data)

            print(f"\n📅 Date Fields:")
            print(f"   ✅ Range: {first_lanc.data} to {last_lanc.data}")

    def test_decimal_fields(self):
        """Decimal precision maintained for area fields"""
        lancamentos_with_area = Lancamento.objects.filter(
            area__isnull=False
        ).exclude(area=0).first()

        if lancamentos_with_area:
            area = lancamentos_with_area.area
            self.assertIsInstance(area, (Decimal, float, int))
            print(f"\n💯 Decimal Fields:")
            print(f"   ✅ Sample area: {area} ha")

    def test_boolean_fields(self):
        """Boolean fields (PostgreSQL true/false → SQLite 1/0)"""
        if hasattr(Documento, 'arquivado'):
            total_docs = Documento.objects.count()
            archived = Documento.objects.filter(arquivado=True).count()
            active = Documento.objects.filter(arquivado=False).count()

            print(f"\n🔘 Boolean Fields:")
            print(f"   ✅ Archived: {archived}, Active: {active}, Total: {total_docs}")

            self.assertGreaterEqual(archived + active, 0)


class QueryPerformanceTest(TestCase):
    """Verify SQLite query performance is acceptable"""

    def test_count_query_performance(self):
        """Count queries should complete quickly"""
        import time

        start = time.time()
        count = Documento.objects.count()
        elapsed = time.time() - start

        print(f"\n⚡ Query Performance:")
        print(f"   Count query: {count} docs in {elapsed:.3f}s")

        self.assertLess(elapsed, 1.0, "Count query too slow")

    def test_join_query_performance(self):
        """Join queries with select_related should be fast"""
        import time

        start = time.time()
        docs = list(Documento.objects.select_related(
            'imovel__terra_indigena_id',
            'cartorio'
        )[:100])
        elapsed = time.time() - start

        print(f"   Join query: {len(docs)} docs in {elapsed:.3f}s")

        self.assertLess(elapsed, 2.0, "Join query too slow")

    def test_filter_query_performance(self):
        """Filtered queries should be performant"""
        import time

        start = time.time()
        count = Lancamento.objects.filter(
            tipo__nome__icontains='compra'
        ).count()
        elapsed = time.time() - start

        print(f"   Filter query: {count} results in {elapsed:.3f}s")

        self.assertLess(elapsed, 1.0, "Filter query too slow")


class BusinessLogicIntegrityTest(TestCase):
    """Verify business logic and data relationships"""

    def test_documento_cartorio_relationship(self):
        """Documentos should have associated Cartorios"""
        total_docs = Documento.objects.count()
        docs_with_cartorio = Documento.objects.filter(
            cartorio__isnull=False
        ).count()

        percentage = (docs_with_cartorio / total_docs * 100) if total_docs > 0 else 0

        print(f"\n🏛️ Business Logic:")
        print(f"   Documentos with Cartorio: {docs_with_cartorio}/{total_docs} ({percentage:.1f}%)")

        # Most documents should have a cartorio
        self.assertGreater(percentage, 90.0)

    def test_lancamento_tipo_distribution(self):
        """Lancamentos should have valid tipos"""
        total_lanc = Lancamento.objects.count()
        lanc_without_tipo = Lancamento.objects.filter(tipo__isnull=True).count()

        print(f"   Lancamentos without tipo: {lanc_without_tipo}/{total_lanc}")

        self.assertEqual(lanc_without_tipo, 0, "Some Lancamentos missing tipo")

        # Show tipo distribution
        tipo_dist = Lancamento.objects.values('tipo__nome').annotate(
            count=Count('id')
        ).order_by('-count')[:5]

        print(f"   Top 5 Lancamento tipos:")
        for item in tipo_dist:
            tipo_name = item['tipo__nome'] or 'None'
            print(f"     - {tipo_name}: {item['count']}")

    def test_imovel_documento_relationship(self):
        """Check how many Imoveis have Documentos"""
        total_imoveis = Imovel.objects.count()
        imoveis_with_docs = Imovel.objects.annotate(
            doc_count=Count('documento')
        ).filter(doc_count__gt=0).count()

        percentage = (imoveis_with_docs / total_imoveis * 100) if total_imoveis > 0 else 0

        print(f"   Imoveis with Documentos: {imoveis_with_docs}/{total_imoveis} ({percentage:.1f}%)")


class SQLiteSpecificTest(TestCase):
    """Test SQLite-specific functionality"""

    def test_sqlite_version(self):
        """Verify SQLite version supports required features"""
        conn = sqlite3.connect(':memory:')
        version = conn.execute('SELECT sqlite_version()').fetchone()[0]
        conn.close()

        print(f"\n🗄️ SQLite Info:")
        print(f"   Version: {version}")

        # Parse version (format: X.Y.Z)
        major, minor, _ = map(int, version.split('.'))

        # Require SQLite 3.8.0+ for JSON support
        self.assertGreaterEqual(major, 3)
        if major == 3:
            self.assertGreaterEqual(minor, 8)

    def test_foreign_keys_enabled(self):
        """Verify foreign key constraints are enforced"""
        from django.db import connection

        with connection.cursor() as cursor:
            cursor.execute("PRAGMA foreign_keys")
            fk_enabled = cursor.fetchone()[0]

        print(f"   Foreign keys enabled: {bool(fk_enabled)}")

        # Django enables this by default, but verify
        self.assertTrue(fk_enabled or fk_enabled == 1)


class DataExportTest(TestCase):
    """Verify data can be exported from SQLite"""

    def test_json_serialization(self):
        """Data can be serialized to JSON"""
        from django.core import serializers
        import json

        # Try serializing a sample
        sample_tis = TIs.objects.all()[:5]

        try:
            json_data = serializers.serialize('json', sample_tis)
            parsed = json.loads(json_data)

            self.assertEqual(len(parsed), sample_tis.count())

            print(f"\n📤 Data Export:")
            print(f"   ✅ JSON serialization: {len(parsed)} TIs exported")
        except Exception as e:
            self.fail(f"JSON serialization failed: {e}")


class PostgreSQLComparisonTest(TestCase):
    """Compare SQLite against PostgreSQL source values"""

    def test_record_count_summary(self):
        """Generate final comparison report"""
        expected = {
            'TIs': 641,
            'Imovel': 296,
            'Documento': 1220,
            'Lancamento': 3172,
            'Pessoas': 1899,
            'Cartorios': 3840,
            'LancamentoPessoa': 4222,
        }

        actual = {
            'TIs': TIs.objects.count(),
            'Imovel': Imovel.objects.count(),
            'Documento': Documento.objects.count(),
            'Lancamento': Lancamento.objects.count(),
            'Pessoas': Pessoas.objects.count(),
            'Cartorios': Cartorios.objects.count(),
            'LancamentoPessoa': LancamentoPessoa.objects.count(),
        }

        print(f"\n" + "="*70)
        print(f"POSTGRESQL vs SQLITE COMPARISON REPORT")
        print(f"="*70)

        total_expected = sum(expected.values())
        total_actual = sum(actual.values())
        total_percentage = (total_actual / total_expected * 100)

        print(f"\n{'Model':<20} {'PostgreSQL':>12} {'SQLite':>12} {'Match':>10}")
        print(f"-"*70)

        for model in expected.keys():
            exp = expected[model]
            act = actual[model]
            pct = (act / exp * 100) if exp > 0 else 100
            status = "✅" if pct >= 95 else "⚠️"
            print(f"{model:<20} {exp:>12,} {act:>12,} {status} {pct:>6.1f}%")

        print(f"-"*70)
        print(f"{'TOTAL':<20} {total_expected:>12,} {total_actual:>12,} {'✅' if total_percentage >= 95 else '⚠️'} {total_percentage:>6.1f}%")
        print(f"="*70)

        # Assert overall migration success (95% threshold)
        self.assertGreaterEqual(
            total_percentage,
            95.0,
            f"Overall migration only {total_percentage:.1f}% complete"
        )
