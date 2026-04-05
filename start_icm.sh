#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${ROOT_DIR}"

UV_BIN="${UV:-uv}"

usage() {
  cat <<'EOF'
Usage:
  ./start_icm.sh
  ./start_icm.sh desktop [extra desktop args...]
  ./start_icm.sh api
  ./start_icm.sh cli [contract-intelligence args...]
  ./start_icm.sh help

Default behavior:
  No arguments launches the Intelligent Contract Management desktop surface.
EOF
}

ensure_uv() {
  if ! command -v "${UV_BIN}" >/dev/null 2>&1; then
    echo "Required tool not found: ${UV_BIN}" >&2
    exit 1
  fi
}

ensure_install() {
  ensure_uv
  echo "Syncing Intelligent Contract Management with uv..."
  "${UV_BIN}" sync --locked --group dev --group desktop
}

run_desktop() {
  exec "${UV_BIN}" run ese desktop --surface icm-workbench "$@"
}

run_api() {
  exec "${UV_BIN}" run uvicorn apps.contract_intelligence.api.app:app --host 127.0.0.1 --port 8000
}

run_cli() {
  exec "${UV_BIN}" run python -m apps.contract_intelligence "$@"
}

mode="${1:-desktop}"
shift || true

case "${mode}" in
  desktop)
    ensure_install
    run_desktop "$@"
    ;;
  api)
    ensure_install
    run_api "$@"
    ;;
  cli)
    ensure_install
    run_cli "$@"
    ;;
  help|-h|--help)
    usage
    ;;
  *)
    echo "Unknown mode: ${mode}" >&2
    usage
    exit 2
    ;;
esac
