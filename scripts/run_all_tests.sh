#!/usr/bin/env bash
# Run all automated tests (unit + E2E smoke + frontend typecheck/tests)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "=== Backend unit tests ==="
cd "$ROOT/backend" && source .venv/bin/activate
pytest tests/unit -v

echo ""
echo "=== Backend E2E smoke (all endpoints) ==="
python scripts/e2e_smoke.py

echo ""
echo "=== Frontend typecheck + tests ==="
cd "$ROOT/frontend/dashboard" && npm run typecheck && npm run test
cd "$ROOT/frontend/widget" && npm run typecheck
cd "$ROOT/frontend/admin" && npm run typecheck

echo ""
echo "All automated tests passed."
