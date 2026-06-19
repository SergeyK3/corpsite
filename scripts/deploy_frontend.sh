#!/usr/bin/env bash
# ADR-INFRA-004 — build Next.js production bundle and restart corpsite-frontend.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
UI_DIR="${REPO_ROOT}/corpsite-ui"
SERVICE_NAME="${CORPSITE_FRONTEND_SERVICE:-corpsite-frontend}"
HEALTH_URL="${CORPSITE_FRONTEND_HEALTH_URL:-http://127.0.0.1:3000/}"
HEALTH_RETRIES="${CORPSITE_FRONTEND_HEALTH_RETRIES:-30}"
HEALTH_INTERVAL_SEC="${CORPSITE_FRONTEND_HEALTH_INTERVAL_SEC:-2}"

log() {
  echo "[deploy-frontend] $*"
}

fail() {
  echo "[deploy-frontend] ERROR: $*" >&2
  exit 1
}

if [[ ! -d "${UI_DIR}" ]]; then
  fail "corpsite-ui directory not found: ${UI_DIR}"
fi

if [[ ! -f "${UI_DIR}/package.json" ]]; then
  fail "package.json missing in ${UI_DIR}"
fi

cd "${UI_DIR}"
log "Working directory: $(pwd)"

log "npm ci"
npm ci

log "npm run build"
npm run build

if [[ ! -f .next/BUILD_ID ]]; then
  fail "Build failed: .next/BUILD_ID not found after npm run build"
fi

log "Build OK: BUILD_ID=$(tr -d '\n' < .next/BUILD_ID)"

if command -v systemctl >/dev/null 2>&1 && systemctl cat "${SERVICE_NAME}" >/dev/null 2>&1; then
  log "Restarting ${SERVICE_NAME}"
  if [[ "$(id -u)" -eq 0 ]]; then
    systemctl restart "${SERVICE_NAME}" || fail "systemctl restart ${SERVICE_NAME} failed"
  else
    sudo systemctl restart "${SERVICE_NAME}" || fail "systemctl restart ${SERVICE_NAME} failed"
  fi
else
  log "WARN: systemd unit ${SERVICE_NAME} not installed — skipping restart"
fi

if ! command -v curl >/dev/null 2>&1; then
  log "WARN: curl not found — skipping health check"
  exit 0
fi

log "Health check ${HEALTH_URL} (up to ${HEALTH_RETRIES} attempts)"
last_code="000"
for ((attempt = 1; attempt <= HEALTH_RETRIES; attempt++)); do
  last_code="$(curl -sS -o /dev/null -w "%{http_code}" "${HEALTH_URL}" 2>/dev/null || echo "000")"
  case "${last_code}" in
    200|301|302|303|307|308)
      log "Health check passed (HTTP ${last_code}, attempt ${attempt}/${HEALTH_RETRIES})"
      exit 0
      ;;
    *)
      sleep "${HEALTH_INTERVAL_SEC}"
      ;;
  esac
done

fail "Health check failed after ${HEALTH_RETRIES} attempts (last HTTP ${last_code})"
