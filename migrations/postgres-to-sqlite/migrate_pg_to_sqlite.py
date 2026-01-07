#!/usr/bin/env python3
"""
PostgreSQL to SQLite data migration script
Transforms PostgreSQL INSERT statements to SQLite-compatible format

Usage:
    python migrate_pg_to_sqlite.py <postgres_dump.sql> <output.db>

Example:
    python migrate_pg_to_sqlite.py postgres_data_dump.sql db.sqlite3
"""
import sqlite3
import re
import sys
import os

def transform_postgres_to_sqlite(input_file, output_db):
    """
    Read PostgreSQL dump and import into SQLite database

    Args:
        input_file: Path to PostgreSQL dump file
        output_db: Path to SQLite database file
    """
    if not os.path.exists(input_file):
        print(f"❌ Error: Input file not found: {input_file}")
        sys.exit(1)

    if not os.path.exists(output_db):
        print(f"❌ Error: SQLite database not found: {output_db}")
        print("   Please run 'python manage.py migrate' first to create the database schema")
        sys.exit(1)

    print(f"📖 Reading PostgreSQL dump: {input_file}")

    with open(input_file, 'r', encoding='utf-8') as f:
        content = f.read()

    # Remove schema prefix (public.)
    content = content.replace('public.', '')

    # Remove comments
    content = re.sub(r'--.*?\n', '', content)

    # Extract INSERT statements
    statements = [line.strip() for line in content.split('\n')
                  if line.strip().startswith('INSERT INTO')]

    print(f"📊 Found {len(statements)} INSERT statements")

    if len(statements) == 0:
        print("❌ Error: No INSERT statements found in input file")
        print("   Make sure the PostgreSQL dump was created with --data-only flag")
        sys.exit(1)

    # Connect to SQLite
    print(f"🔗 Connecting to SQLite: {output_db}")
    conn = sqlite3.connect(output_db)
    cursor = conn.cursor()

    # Disable foreign keys temporarily for performance
    cursor.execute("PRAGMA foreign_keys = OFF;")

    success_count = 0
    error_count = 0
    error_details = []

    print("⚙️  Importing data...")

    for i, statement in enumerate(statements, 1):
        try:
            cursor.execute(statement)
            success_count += 1

            # Progress reporting
            if i % 500 == 0:
                print(f"   Processed {i}/{len(statements)} statements ({success_count} successful, {error_count} errors)")
                conn.commit()

        except sqlite3.IntegrityError as e:
            # Duplicate keys or constraint violations (expected for some records)
            error_count += 1
            error_msg = str(e)

            # Only log non-duplicate errors
            if 'UNIQUE constraint' not in error_msg and len(error_details) < 10:
                error_details.append(f"Statement {i}: {error_msg}")

        except sqlite3.Error as e:
            error_count += 1
            error_msg = str(e)

            # Log first 10 errors for debugging
            if len(error_details) < 10:
                error_details.append(f"Statement {i}: {error_msg}")

    # Final commit
    conn.commit()

    # Re-enable foreign keys
    cursor.execute("PRAGMA foreign_keys = ON;")

    # Verify foreign key integrity
    print("\n🔍 Verifying foreign key integrity...")
    cursor.execute("PRAGMA foreign_key_check;")
    fk_violations = cursor.fetchall()

    if fk_violations:
        print(f"⚠️  Found {len(fk_violations)} foreign key violations:")
        for violation in fk_violations[:10]:  # Show first 10
            print(f"   {violation}")
    else:
        print("✅ No foreign key violations detected")

    # Get record counts
    print("\n📊 Record counts after migration:")
    tables = [
        'dominial_tis',
        'dominial_imovel',
        'dominial_documento',
        'dominial_lancamento',
        'dominial_pessoas',
        'dominial_cartorios',
        'dominial_lancamentopessoa'
    ]

    for table in tables:
        try:
            cursor.execute(f"SELECT COUNT(*) FROM {table};")
            count = cursor.fetchone()[0]
            print(f"   {table}: {count}")
        except sqlite3.Error:
            pass

    conn.close()

    # Summary
    print(f"\n{'='*60}")
    print(f"📈 Migration Summary:")
    print(f"{'='*60}")
    print(f"Total statements: {len(statements)}")
    print(f"Successful imports: {success_count} ({success_count/len(statements)*100:.1f}%)")
    print(f"Errors/Duplicates: {error_count} ({error_count/len(statements)*100:.1f}%)")

    if error_details:
        print(f"\n⚠️  Sample errors (first 10):")
        for error in error_details:
            print(f"   {error}")

    print(f"{'='*60}")

    # Success criteria
    success_rate = success_count / len(statements) * 100
    if success_rate >= 95:
        print(f"\n✅ Migration successful! ({success_rate:.1f}% success rate)")
        return 0
    else:
        print(f"\n⚠️  Migration completed with warnings ({success_rate:.1f}% success rate)")
        print("   Review errors above and verify data integrity")
        return 1

if __name__ == '__main__':
    if len(sys.argv) != 3:
        print("Usage: python migrate_pg_to_sqlite.py <postgres_dump.sql> <output.db>")
        print()
        print("Example:")
        print("  python migrate_pg_to_sqlite.py postgres_data_dump.sql db.sqlite3")
        print()
        print("Note: The SQLite database must already exist with schema created.")
        print("      Run 'python manage.py migrate' first.")
        sys.exit(1)

    input_file = sys.argv[1]
    output_db = sys.argv[2]

    sys.exit(transform_postgres_to_sqlite(input_file, output_db))
