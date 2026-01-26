#!/usr/bin/env python
import argparse
import sys
import sqlite3

from expected import TABLES

try:
    import psycopg2
except ImportError:
    psycopg2 = None


def pg_tables(pg_url):
    conn = psycopg2.connect(pg_url)
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT table_name FROM information_schema.tables
            WHERE table_schema = 'public' AND table_type='BASE TABLE'
            """
        )
        return {row[0] for row in cur.fetchall()}


def sqlite_tables(sqlite_path):
    conn = sqlite3.connect(sqlite_path)
    cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    return {row[0] for row in cur.fetchall()}


def main():
    parser = argparse.ArgumentParser(description="Schema presence check")
    parser.add_argument("--pg", help="PostgreSQL connection string")
    parser.add_argument("--sqlite", required=True, help="SQLite file path")
    parser.add_argument("--skip-pg", action="store_true", help="Skip PostgreSQL checks")
    args = parser.parse_args()

    missing = []

    sqlite_set = sqlite_tables(args.sqlite)
    for t in TABLES:
        if t not in sqlite_set:
            missing.append(f"SQLite missing table {t}")

    if not args.skip_pg:
        if psycopg2 is None:
            sys.stderr.write("psycopg2 required for PostgreSQL schema check\n")
            sys.exit(1)
        if not args.pg:
            sys.stderr.write("--pg is required unless --skip-pg is set\n")
            sys.exit(1)
        pg_set = pg_tables(args.pg)
        for t in TABLES:
            if t not in pg_set:
                missing.append(f"PostgreSQL missing table {t}")

    if missing:
        sys.stderr.write("Schema presence issues:\n")
        for msg in missing:
            sys.stderr.write(f"  {msg}\n")
        sys.exit(1)

    print("Schema presence check passed.")


if __name__ == "__main__":
    main()
