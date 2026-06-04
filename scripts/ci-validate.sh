#!/usr/bin/env bash
# CI-only script. Mimics a clean GitHub Actions install by removing the root
# and direct workspace package `node_modules` directories before reinstalling
# from the lockfile. Local use is guarded below because this intentionally
# deletes dependency directories.
set -euo pipefail

if [ "${CI:-}" != "true" ] && [ -z "${HERMES_CI_VALIDATE_FORCE:-}" ]; then
  echo "ERROR: ci-validate.sh is intended for CI runners only." >&2
  echo "       Set CI=true to run locally (e.g. CI=true ./scripts/ci-validate.sh)." >&2
  echo "       Or set HERMES_CI_VALIDATE_FORCE=1 to skip this guard." >&2
  exit 2
fi

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

# Scope to the packages dir + root, not a recursive `find` over the whole
# workspace — that would also nuke `node_modules` of sibling repos checked
# out alongside this one.
rm -rf node_modules packages/*/node_modules

pnpm install --frozen-lockfile
pnpm build

echo "✅ Clean install and build successful"
