#!/usr/bin/env bash
set -euo pipefail

ICM_REFERENCE_ROOT="${ICM_REFERENCE_ROOT:-/var/data/icm/reference}"
ICM_REFERENCE_SITE_DIR="${ICM_REFERENCE_SITE_DIR:-$ICM_REFERENCE_ROOT/site}"
ICM_BOOTSTRAP_REFERENCE="${ICM_BOOTSTRAP_REFERENCE:-1}"

export CONTRACT_INTELLIGENCE_REFERENCE_ROOT="$ICM_REFERENCE_ROOT"
export CONTRACT_INTELLIGENCE_REFERENCE_SITE_DIR="$ICM_REFERENCE_SITE_DIR"

if [[ "$ICM_BOOTSTRAP_REFERENCE" == "1" ]]; then
  if [[ ! -f "$ICM_REFERENCE_SITE_DIR/manifest.json" ]]; then
    mkdir -p "$ICM_REFERENCE_ROOT" "$ICM_REFERENCE_SITE_DIR"
    uv run python -m apps.contract_intelligence build-demo \
      --reference-root "$ICM_REFERENCE_ROOT" \
      --site-dir "$ICM_REFERENCE_SITE_DIR"
  fi
fi

exec uv run uvicorn apps.contract_intelligence.api.app:app --host 0.0.0.0 --port "${PORT:-8000}"
