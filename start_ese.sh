#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${ROOT_DIR}"

UV_BIN="${UV:-uv}"
DEFAULT_ARTIFACTS_DIR="${ESE_ARTIFACTS_DIR:-${ROOT_DIR}/artifacts}"
OLLAMA_LOG_FILE="${ROOT_DIR}/.ollama.log"

usage() {
  cat <<'EOF'
Usage:
  ./start_ese.sh
  ./start_ese.sh desktop [extra ese desktop args...]
  ./start_ese.sh dashboard [extra ese dashboard args...]
  ./start_ese.sh task "Your task scope" [extra ese task args...]
  ./start_ese.sh pr [ese pr args...]
  ./start_ese.sh cli [raw ese args...]
  ./start_ese.sh test
  ./start_ese.sh help

Default behavior:
  No arguments starts the native desktop shell on macOS and the browser dashboard elsewhere.

Examples:
  ./start_ese.sh
  ./start_ese.sh desktop
  ./start_ese.sh task "Prepare a staged rollout plan for billing"
  ./start_ese.sh pr --repo-path . --base origin/main --head HEAD
  ./start_ese.sh cli report --artifacts-dir artifacts
EOF
}

ensure_uv() {
  if ! command -v "${UV_BIN}" >/dev/null 2>&1; then
    echo "Required tool not found: ${UV_BIN}" >&2
    echo "Install uv from https://docs.astral.sh/uv/ and re-run this launcher." >&2
    exit 1
  fi
}

ensure_install() {
  ensure_uv
  local mode="${1:-dashboard}"
  local groups=(--group dev)
  if [[ "${mode}" == "desktop" ]]; then
    groups+=(--group desktop)
  fi
  echo "Syncing ESE with uv for ${mode}..."
  "${UV_BIN}" sync --locked "${groups[@]}"
}

run_dashboard() {
  exec "${UV_BIN}" run ese dashboard --artifacts-dir "${DEFAULT_ARTIFACTS_DIR}" "$@"
}

run_desktop() {
  exec "${UV_BIN}" run ese desktop --artifacts-dir "${DEFAULT_ARTIFACTS_DIR}" "$@"
}

run_task() {
  if [[ $# -lt 1 ]]; then
    echo "Task mode requires a scope string." >&2
    usage
    exit 2
  fi
  exec "${UV_BIN}" run ese task "$1" --artifacts-dir "${DEFAULT_ARTIFACTS_DIR}" "${@:2}"
}

run_pr() {
  exec "${UV_BIN}" run ese pr --repo-path "${ROOT_DIR}" --artifacts-dir "${DEFAULT_ARTIFACTS_DIR}" "$@"
}

run_cli() {
  exec "${UV_BIN}" run ese "$@"
}

run_tests() {
  exec "${UV_BIN}" run pytest "$@"
}

ollama_installed() {
  command -v ollama >/dev/null 2>&1
}

ollama_running() {
  ollama list >/dev/null 2>&1
}

start_ollama() {
  if ollama_running; then
    return 0
  fi

  if ! ollama_installed; then
    return 1
  fi

  echo "Starting Ollama..."
  if command -v brew >/dev/null 2>&1 && brew list --versions ollama >/dev/null 2>&1; then
    brew services start ollama >/dev/null 2>&1 || true
  fi

  if ! ollama_running; then
    nohup ollama serve >"${OLLAMA_LOG_FILE}" 2>&1 < /dev/null &
  fi

  for _ in $(seq 1 20); do
    if ollama_running; then
      echo "Ollama is running."
      return 0
    fi
    sleep 0.5
  done

  echo "Ollama did not start successfully. Check ${OLLAMA_LOG_FILE} or run 'ollama serve' manually." >&2
  return 1
}

prompt_for_ollama_install_or_hosted_model() {
  echo
  echo "Local runtime selected, but Ollama is not installed."
  echo "Choose one:"
  echo "  1) Install Ollama now"
  echo "  2) Switch to a hosted model instead"
  echo "  3) Cancel"

  local choice
  read -r -p "Enter 1, 2, or 3: " choice
  case "${choice}" in
    1)
      if command -v brew >/dev/null 2>&1; then
        echo "Installing Ollama with Homebrew..."
        brew install ollama
        start_ollama
        return 0
      fi

      if command -v open >/dev/null 2>&1; then
        echo "Opening the official Ollama download page..."
        open "https://ollama.com/download"
      fi
      echo "Install Ollama, then re-run this launcher."
      exit 2
      ;;
    2)
      echo "Launching the advanced setup wizard so you can choose a hosted provider instead."
      exec "${UV_BIN}" run ese init --advanced
      ;;
    *)
      echo "Canceled."
      exit 2
      ;;
  esac
}

config_uses_local_runtime() {
  local config_path="$1"
  "${UV_BIN}" run python - "$config_path" <<'PY'
from __future__ import annotations
import sys
from pathlib import Path
import yaml

path = Path(sys.argv[1])
if not path.exists():
    print("false")
    raise SystemExit(0)

loaded = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
if not isinstance(loaded, dict):
    print("false")
    raise SystemExit(0)

runtime = loaded.get("runtime") or {}
provider = loaded.get("provider") or {}
adapter = str(runtime.get("adapter") or "").strip().lower()
provider_name = str(provider.get("name") or "").strip().lower()

print("true" if adapter == "local" or provider_name == "local" else "false")
PY
}

task_or_pr_uses_local_provider() {
  local default_provider="$1"
  shift || true
  local provider="${default_provider}"
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --provider)
        provider="${2:-}"
        shift 2
        ;;
      --provider=*)
        provider="${1#*=}"
        shift
        ;;
      *)
        shift
        ;;
    esac
  done

  [[ "${provider}" == "local" ]]
}

ensure_local_runtime_for_invocation() {
  local mode="${1:-dashboard}"
  shift || true

  case "${mode}" in
    task)
      if task_or_pr_uses_local_provider "openai" "$@"; then
        if ! ollama_installed; then
          prompt_for_ollama_install_or_hosted_model
        else
          start_ollama
        fi
      fi
      ;;
    pr)
      if task_or_pr_uses_local_provider "openai" "$@"; then
        if ! ollama_installed; then
          prompt_for_ollama_install_or_hosted_model
        else
          start_ollama
        fi
      fi
      ;;
    cli)
      local subcommand="${1:-}"
      shift || true
      case "${subcommand}" in
        run|start)
          local config_path="ese.config.yaml"
          while [[ $# -gt 0 ]]; do
            case "$1" in
              --config)
                config_path="${2:-ese.config.yaml}"
                shift 2
                ;;
              --config=*)
                config_path="${1#*=}"
                shift
                ;;
              *)
                shift
                ;;
            esac
          done
          if [[ "$(config_uses_local_runtime "${config_path}")" == "true" ]]; then
            if ! ollama_installed; then
              prompt_for_ollama_install_or_hosted_model
            else
              start_ollama
            fi
          fi
          ;;
        task)
          if task_or_pr_uses_local_provider "openai" "$@"; then
            if ! ollama_installed; then
              prompt_for_ollama_install_or_hosted_model
            else
              start_ollama
            fi
          fi
          ;;
        pr)
          if task_or_pr_uses_local_provider "openai" "$@"; then
            if ! ollama_installed; then
              prompt_for_ollama_install_or_hosted_model
            else
              start_ollama
            fi
          fi
          ;;
      esac
      ;;
  esac
}

main() {
  local mode="${1:-}"
  if [[ -z "${mode}" ]]; then
    if [[ "$(uname -s)" == "Darwin" ]]; then
      mode="desktop"
    else
      mode="dashboard"
    fi
  fi

  ensure_install "${mode}"
  case "${mode}" in
    desktop|dashboard|task|pr|cli)
      ensure_local_runtime_for_invocation "${mode}" "${@:2}"
      ;;
    *)
      ensure_local_runtime_for_invocation cli "$@"
      ;;
  esac
  case "${mode}" in
    desktop)
      shift || true
      run_desktop "$@"
      ;;
    dashboard)
      shift || true
      run_dashboard "$@"
      ;;
    task)
      shift || true
      run_task "$@"
      ;;
    pr)
      shift || true
      run_pr "$@"
      ;;
    cli)
      shift || true
      run_cli "$@"
      ;;
    test)
      shift || true
      run_tests "$@"
      ;;
    help|-h|--help)
      usage
      ;;
    *)
      run_cli "$@"
      ;;
  esac
}

main "$@"
