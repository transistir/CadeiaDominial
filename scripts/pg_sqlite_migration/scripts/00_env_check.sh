#!/usr/bin/env bash
set -euo pipefail

missing=()
for bin in python python3 pip pg_dump psql sqlite3; do
  if ! command -v "$bin" >/dev/null 2>&1; then
    missing+=("$bin")
  fi
done

if [ "${#missing[@]}" -gt 0 ]; then
  echo "Missing required tools: ${missing[*]}" >&2
  exit 1
fi

echo "Environment OK."
