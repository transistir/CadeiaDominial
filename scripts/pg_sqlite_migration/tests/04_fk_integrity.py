#!/usr/bin/env python
import argparse
import sqlite3
import sys


def main():
    parser = argparse.ArgumentParser(description="SQLite foreign key integrity check")
    parser.add_argument("--sqlite", required=True)
    args = parser.parse_args()

    conn = sqlite3.connect(args.sqlite)
    cur = conn.execute("PRAGMA foreign_key_check;")
    rows = cur.fetchall()
    if rows:
        sys.stderr.write("Foreign key violations:\n")
        for row in rows:
            sys.stderr.write(f"  {row}\n")
        sys.exit(1)

    print("No foreign key violations detected.")


if __name__ == "__main__":
    main()
