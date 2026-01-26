#!/usr/bin/env python
import argparse
import datetime as dt
import sqlite3
import sys
from pathlib import Path

try:
    import psycopg2
except ImportError:
    sys.stderr.write("psycopg2 is required; install with pip.\n")
    sys.exit(1)


TABLE_ORDER = [
    "django_content_type",
    "auth_permission",
    "auth_user",
    "django_admin_log",
    "django_migrations",
    "django_session",
    "dominial_cartorios",
    "dominial_documento",
    "dominial_documentotipo",
    "dominial_fimcadeia",
    "dominial_imovel",
    "dominial_lancamentotipo",
    "dominial_lancamento",
    "dominial_lancamentopessoa",
    "dominial_origemfimcadeia",
    "dominial_pessoas",
    "dominial_documentoimportado",
    "dominial_tis",
    "dominial_terraindigenareferencia",
    "dominial_alteracoes",
    "dominial_importacaocartorios",
]

TS_TYPES = {"timestamp with time zone", "timestamp without time zone"}
NUM_TYPES = {"numeric", "double precision"}


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


def fetch_rows(conn, table, cols):
    col_list = ", ".join(f'"{c}"' for c, _ in cols)
    with conn.cursor() as cur:
        cur.execute(f'SELECT {col_list} FROM "{table}"')
        for row in cur.fetchall():
            yield row


def transform_row(row, cols):
    out = []
    for (col, dtype), val in zip(cols, row):
        if val is None:
            out.append(None)
            continue
        if dtype in TS_TYPES and isinstance(val, dt.datetime):
            out.append(val.astimezone(dt.timezone.utc).isoformat().replace("+00:00", "Z"))
        elif dtype in NUM_TYPES:
            out.append(str(val))
        else:
            out.append(val)
    return out


def copy_table(pg_conn, sqlite_conn, table):
    cols = pg_columns(pg_conn, table)
    if not cols:
        print(f"Skipping {table}, no columns")
        return

    placeholders = ", ".join("?" for _ in cols)
    col_names = ", ".join(f'"{c}"' for c, _ in cols)
    insert_sql = f'INSERT INTO "{table}" ({col_names}) VALUES ({placeholders})'

    rows = [transform_row(r, cols) for r in fetch_rows(pg_conn, table, cols)]
    if rows:
        sqlite_conn.executemany(insert_sql, rows)
    print(f"Copied {len(rows)} rows into {table}")


def main():
    parser = argparse.ArgumentParser(description="Copy PostgreSQL → SQLite without db-to-sqlite")
    parser.add_argument("--pg", required=True, help="PostgreSQL connection string")
    parser.add_argument("--sqlite", required=True, help="SQLite file path")
    args = parser.parse_args()

    pg_conn = psycopg2.connect(args.pg)
    sqlite_conn = sqlite3.connect(args.sqlite)
    sqlite_conn.execute("PRAGMA foreign_keys=OFF;")

    try:
        for table in TABLE_ORDER:
            copy_table(pg_conn, sqlite_conn, table)
        sqlite_conn.execute("PRAGMA foreign_keys=ON;")
        sqlite_conn.commit()
    finally:
        pg_conn.close()
        sqlite_conn.close()


if __name__ == "__main__":
    main()
