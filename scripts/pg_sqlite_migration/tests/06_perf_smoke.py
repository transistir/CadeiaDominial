#!/usr/bin/env python
import argparse
import sys
import time
import sqlite3

try:
    import psycopg2
except ImportError as exc:
    sys.stderr.write("psycopg2 is required. install with `pip install psycopg2-binary`.\n")
    raise


def time_query(conn, sql):
    start = time.perf_counter()
    with conn.cursor() as cur:
        cur.execute(sql)
        cur.fetchone()
    return time.perf_counter() - start


def time_query_sqlite(conn, sql):
    start = time.perf_counter()
    cur = conn.execute(sql)
    cur.fetchone()
    return time.perf_counter() - start


def main():
    parser = argparse.ArgumentParser(description="Perf smoke test PG vs SQLite")
    parser.add_argument("--pg", required=True)
    parser.add_argument("--sqlite", required=True)
    parser.add_argument("--table", default="dominial_lancamento", help="table to sample for read perf")
    parser.add_argument("--max-factor", type=float, default=5.0, help="allowed slowdown factor for reads")
    args = parser.parse_args()

    pg_conn = psycopg2.connect(args.pg)
    sqlite_conn = sqlite3.connect(args.sqlite)

    read_sql = f'SELECT COUNT(*) FROM "{args.table}"'
    pg_read = time_query(pg_conn, read_sql)
    sqlite_read = time_query_sqlite(sqlite_conn, read_sql)

    # Write test: temp table to avoid mutations
    pg_write_sql = "CREATE TEMP TABLE tmp_perf(id serial); INSERT INTO tmp_perf DEFAULT VALUES;"
    sqlite_write_sql = "CREATE TEMP TABLE tmp_perf(id integer primary key autoincrement); INSERT INTO tmp_perf DEFAULT VALUES;"

    pg_write_start = time.perf_counter()
    with pg_conn:
        with pg_conn.cursor() as cur:
            cur.execute(pg_write_sql)
    pg_write = time.perf_counter() - pg_write_start

    sqlite_write_start = time.perf_counter()
    with sqlite_conn:
        sqlite_conn.executescript(sqlite_write_sql)
    sqlite_write = time.perf_counter() - sqlite_write_start

    failures = []
    if sqlite_read > args.max_factor * pg_read:
        failures.append(f"Read slowdown {sqlite_read/pg_read:.1f}x > {args.max_factor}x")
    if sqlite_write > args.max_factor * pg_write:
        failures.append(f"Write slowdown {sqlite_write/pg_write:.1f}x > {args.max_factor}x")

    if failures:
        sys.stderr.write("Performance smoke failures:\n")
        for msg in failures:
            sys.stderr.write(f"  {msg}\n")
        sys.exit(1)

    print(
        f"Perf OK: read {sqlite_read/pg_read:.1f}x, write {sqlite_write/pg_write:.1f}x slower than PG "
        f"(limit {args.max_factor}x)"
    )


if __name__ == "__main__":
    main()
