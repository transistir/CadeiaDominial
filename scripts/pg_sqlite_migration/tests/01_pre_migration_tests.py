#!/usr/bin/env python
import argparse
import sys

from expected import EXPECTED_COUNTS, TABLES

try:
    import psycopg2
except ImportError as exc:
    sys.stderr.write("psycopg2 is required. install with `pip install psycopg2-binary`.\n")
    raise


def get_count(conn, table):
    with conn.cursor() as cur:
        cur.execute(f'SELECT COUNT(*) FROM "{table}"')
        return cur.fetchone()[0]


def main():
    parser = argparse.ArgumentParser(description="Pre-migration PG row count baseline")
    parser.add_argument("--pg", required=True, help="PostgreSQL connection string")
    args = parser.parse_args()

    conn = psycopg2.connect(args.pg)
    failures = []
    for table, expected in EXPECTED_COUNTS.items():
        count = get_count(conn, table)
        if count != expected:
            failures.append((table, expected, count))

    if failures:
        sys.stderr.write("Baseline row count mismatches:\n")
        for t, exp, got in failures:
            sys.stderr.write(f"  {t}: expected {exp}, got {got}\n")
        sys.exit(1)

    print("Pre-migration row counts match expected.")


if __name__ == "__main__":
    main()
