#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

find "$ROOT_DIR" -type d -name "node_modules" -prune -exec rm -rf {} +

pnpm install --frozen-lockfile
pnpm build

echo "✅ Clean install and build successful"
