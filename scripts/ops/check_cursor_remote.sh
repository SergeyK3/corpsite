#!/usr/bin/env bash
# WP-INFRA-IO-002 — refuse on-VPS npm build while Cursor remote is active.
set -euo pipefail

log() {
  echo "[cursor-guard] $*" >&2
}

cursor_remote_active() {
  if pgrep -f '[c]ursor-server' >/dev/null 2>&1; then
    return 0
  fi
  if pgrep -f '[f]ileWatcher.*cursor' >/dev/null 2>&1; then
    return 0
  fi
  if [[ -d "${HOME}/.cursor-server" ]] && pgrep -f '[n]ode.*\.cursor-server' >/dev/null 2>&1; then
    return 0
  fi
  return 1
}

if [[ "${CORPSITE_ALLOW_CURSOR_BUILD:-}" == "1" ]]; then
  log "WARN: CORPSITE_ALLOW_CURSOR_BUILD=1 — guard skipped"
  exit 0
fi

if cursor_remote_active; then
  log "ERROR: Cursor remote session detected on this host."
  log "Disconnect Cursor (close remote window) before npm run build on the VPS."
  log "See docs/ops/WP-INFRA-IO-002-VPS-IO-Guardrails.md"
  log "Emergency override: CORPSITE_ALLOW_CURSOR_BUILD=1"
  exit 1
fi

exit 0
