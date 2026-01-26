#!/usr/bin/env python
import argparse
import hashlib
import sys
import sqlite3
import datetime as dt
from decimal import Decimal

from expected import EXPECTED_COUNTS

try:
    import psycopg2
except ImportError as exc:
    sys.stderr.write("psycopg2 is required. install with `pip install psycopg2-binary`.\n")
    raise


def pg_columns(conn, table):
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_schema='public' AND table_name=%s
            ORDER BY ordinal_position
            """,
            (table,),
        )
        return cur.fetchall()


def sqlite_columns(conn, table):
    cur = conn.execute(f'PRAGMA table_info("{table}")')
    return [row[1] for row in cur.fetchall()]


def normalize_value(val):
    if val is None:
        return ""
    if isinstance(val, bool):
        return "1" if val else "0"
    if isinstance(val, dt.datetime):
        return val.astimezone(dt.timezone.utc).isoformat().replace("+00:00", "Z")
    if isinstance(val, (Decimal, float, int)):
        try:
            return format(Decimal(str(val)).normalize(), 'f').rstrip('0').rstrip('.') or '0'
        except Exception:
            return str(val)
    return str(val)


def checksum_rows(rows):
    h = hashlib.md5()
    norm_rows = ["|".join(normalize_value(v) for v in row) for row in rows]
    for row_str in sorted(norm_rows):
        h.update(row_str.encode("utf-8"))
    return h.hexdigest()


def fetch_pg_rows(conn, table, cols, common_cols):
    col_names = ", ".join(f'"{c}"' for c in common_cols)
    with conn.cursor() as cur:
        cur.execute(f'SELECT {col_names} FROM "{table}" ORDER BY 1')
        return cur.fetchall()


def fetch_sqlite_rows(conn, table, common_cols):
    col_names = ", ".join(f'"{c}"' for c in common_cols)
    cur = conn.execute(f'SELECT {col_names} FROM "{table}" ORDER BY rowid')
    return cur.fetchall()


def get_count_pg(conn, table):
    with conn.cursor() as cur:
        cur.execute(f'SELECT COUNT(*) FROM "{table}"')
        return cur.fetchone()[0]


def get_count_sqlite(conn, table):
    cur = conn.execute(f'SELECT COUNT(*) FROM "{table}"')
    return cur.fetchone()[0]


def main():
    parser = argparse.ArgumentParser(description="Row count and checksum comparison")
    parser.add_argument("--pg", required=True)
    parser.add_argument("--sqlite", required=True)
    args = parser.parse_args()

    pg_conn = psycopg2.connect(args.pg)
    sqlite_conn = sqlite3.connect(args.sqlite)

    failures = []
    for table, expected in EXPECTED_COUNTS.items():
        pg_count = get_count_pg(pg_conn, table)
        sqlite_count = get_count_sqlite(sqlite_conn, table)
        if pg_count != sqlite_count:
            failures.append(f"{table}: count PG {pg_count} != SQLite {sqlite_count}")
            continue
        pg_cols = pg_columns(pg_conn, table)
        sqlite_cols = sqlite_columns(sqlite_conn, table)
        if not pg_cols or not sqlite_cols:
            failures.append(f"{table}: missing columns metadata")
            continue
        common_cols = sorted(set(c for c, _ in pg_cols) & set(sqlite_cols))
        if not common_cols:
            failures.append(f"{table}: no shared columns")
            continue
        pg_rows = fetch_pg_rows(pg_conn, table, pg_cols, common_cols)
        sqlite_rows = fetch_sqlite_rows(sqlite_conn, table, common_cols)
        if len(pg_rows) != len(sqlite_rows):
            failures.append(f"{table}: row count diverged during fetch")
            continue
        pg_hash = checksum_rows(pg_rows)
        sqlite_hash = checksum_rows(sqlite_rows)
        if pg_hash != sqlite_hash:
            failures.append(f"{table}: checksum mismatch")

    if failures:
        sys.stderr.write("Count/Checksum mismatches:\n")
        for msg in failures:
            sys.stderr.write(f"  {msg}\n")
        sys.exit(1)

    print("Counts and checksums match.")


if __name__ == "__main__":
    main()
