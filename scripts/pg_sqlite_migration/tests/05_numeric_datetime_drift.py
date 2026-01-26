#!/usr/bin/env python
import argparse
import sys
import sqlite3
import datetime as dt
from decimal import Decimal

try:
    import psycopg2
except ImportError as exc:
    sys.stderr.write("psycopg2 is required. install with `pip install psycopg2-binary`.\n")
    raise


NUMERIC_TYPES = {"numeric", "double precision", "integer", "bigint", "real", "smallint"}
TIMESTAMP_TYPES = {"timestamp with time zone", "timestamp without time zone"}


def pg_columns(conn):
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT table_name, column_name, data_type
            FROM information_schema.columns
            WHERE table_schema='public'
            """
        )
        rows = cur.fetchall()
    cols = {}
    for table, col, dtype in rows:
        cols.setdefault(table, {})[col] = dtype
    return cols


def min_max_pg(conn, table, column):
    with conn.cursor() as cur:
        cur.execute(f'SELECT MIN("{column}"), MAX("{column}") FROM "{table}"')
        return cur.fetchone()


def min_max_sqlite(conn, table, column):
    cur = conn.execute(f'SELECT MIN("{column}"), MAX("{column}") FROM "{table}"')
    return cur.fetchone()


def to_utc_iso(val):
    if val is None:
        return None
    if isinstance(val, dt.datetime):
        return val.astimezone(dt.timezone.utc).isoformat().replace("+00:00", "Z")
    return str(val)


def main():
    parser = argparse.ArgumentParser(description="Numeric and timestamp drift check")
    parser.add_argument("--pg", required=True)
    parser.add_argument("--sqlite", required=True)
    parser.add_argument("--numeric-tolerance", type=float, default=0.01)
    args = parser.parse_args()

    pg_conn = psycopg2.connect(args.pg)
    sqlite_conn = sqlite3.connect(args.sqlite)

    pg_meta = pg_columns(pg_conn)
    failures = []

    sqlite_tables = {r[0] for r in sqlite_conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}

    for table, cols in pg_meta.items():
        if table not in sqlite_tables:
            continue
        for col, dtype in cols.items():
            if dtype in NUMERIC_TYPES:
                pg_min, pg_max = min_max_pg(pg_conn, table, col)
                sql_min, sql_max = min_max_sqlite(sqlite_conn, table, col)
                if pg_min is None and pg_max is None:
                    continue
                try:
                    pg_min_f, pg_max_f = float(pg_min), float(pg_max)
                    sql_min_f, sql_max_f = float(sql_min), float(sql_max)
                except (TypeError, ValueError):
                    failures.append(f"{table}.{col}: numeric conversion failed")
                    continue
                if abs(pg_min_f - sql_min_f) > args.numeric_tolerance or abs(pg_max_f - sql_max_f) > args.numeric_tolerance:
                    failures.append(f"{table}.{col}: numeric drift PG[{pg_min},{pg_max}] SQLite[{sql_min},{sql_max}]")
            elif dtype in TIMESTAMP_TYPES:
                pg_min, pg_max = min_max_pg(pg_conn, table, col)
                sql_min, sql_max = min_max_sqlite(sqlite_conn, table, col)
                pg_min_iso, pg_max_iso = to_utc_iso(pg_min), to_utc_iso(pg_max)
                if sql_min and isinstance(sql_min, str):
                    sql_min_iso = sql_min
                else:
                    sql_min_iso = to_utc_iso(sql_min)
                if sql_max and isinstance(sql_max, str):
                    sql_max_iso = sql_max
                else:
                    sql_max_iso = to_utc_iso(sql_max)
                if pg_min_iso and sql_min_iso and pg_min_iso != sql_min_iso:
                    failures.append(f"{table}.{col}: min timestamp differs PG[{pg_min_iso}] SQLite[{sql_min_iso}]")
                if pg_max_iso and sql_max_iso and pg_max_iso != sql_max_iso:
                    failures.append(f"{table}.{col}: max timestamp differs PG[{pg_max_iso}] SQLite[{sql_max_iso}]")

    if failures:
        sys.stderr.write("Numeric/Timestamp drift detected:\n")
        for msg in failures:
            sys.stderr.write(f"  {msg}\n")
        sys.exit(1)

    print("Numeric and timestamp ranges match within tolerance.")


if __name__ == "__main__":
    main()
