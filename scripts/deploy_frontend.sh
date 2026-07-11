#!/usr/bin/env bash
# ADR-INFRA-004/005 — build Next.js production bundle and restart corpsite-frontend.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
UI_DIR="${REPO_ROOT}/corpsite-ui"
SERVICE_NAME="${CORPSITE_FRONTEND_SERVICE:-corpsite-frontend}"
ENSURE_PORT="${REPO_ROOT}/scripts/ops/ensure_port_free.sh"
HEALTH_URL="${CORPSITE_FRONTEND_HEALTH_URL:-http://127.0.0.1:3000/}"
HEALTH_PERSONNEL_URL="${CORPSITE_FRONTEND_PERSONNEL_URL:-http://127.0.0.1:3000/directory/personnel}"
HEALTH_STAFF_URL="${CORPSITE_FRONTEND_STAFF_URL:-http://127.0.0.1:3000/directory/staff}"
PUBLIC_PERSONNEL_URL="${CORPSITE_PUBLIC_PERSONNEL_URL:-https://mmc.004.kz/directory/personnel}"
PUBLIC_STAFF_URL="${CORPSITE_PUBLIC_STAFF_URL:-https://mmc.004.kz/directory/staff}"
HEALTH_RETRIES="${CORPSITE_FRONTEND_HEALTH_RETRIES:-30}"
HEALTH_INTERVAL_SEC="${CORPSITE_FRONTEND_HEALTH_INTERVAL_SEC:-2}"

log() {
  echo "[deploy-frontend] $*"
}

fail() {
  echo "[deploy-frontend] ERROR: $*" >&2
  if command -v systemctl >/dev/null 2>&1; then
    if [[ "$(id -u)" -eq 0 ]]; then
      journalctl -u "${SERVICE_NAME}" -n 40 --no-pager >&2 || true
    else
      sudo journalctl -u "${SERVICE_NAME}" -n 40 --no-pager >&2 || true
    fi
  fi
  exit 1
}

systemctl_cmd() {
  if [[ "$(id -u)" -eq 0 ]]; then
    systemctl "$@"
  else
    sudo systemctl "$@"
  fi
}

check_http() {
  local url="$1"
  local label="$2"
  curl -sS -o /dev/null -w '%{http_code}' --max-time 15 "${url}" 2>/dev/null || echo "000"
}

smoke_url() {
  local url="$1"
  local label="$2"
  local code
  code="$(check_http "${url}" "${label}")"
  case "${code}" in
    200|301|302|303|307|308)
      log "smoke ${label}: OK (HTTP ${code}) ${url}"
      ;;
    *)
      fail "smoke ${label}: failed (HTTP ${code}) ${url}"
      ;;
  esac
}

if [[ ! -d "${UI_DIR}" ]]; then
  fail "corpsite-ui directory not found: ${UI_DIR}"
fi

if [[ ! -f "${UI_DIR}/package.json" ]]; then
  fail "package.json missing in ${UI_DIR}"
fi

CURSOR_GUARD="${REPO_ROOT}/scripts/ops/check_cursor_remote.sh"
if [[ -x "${CURSOR_GUARD}" ]]; then
  log "cursor remote guard"
  "${CURSOR_GUARD}" || fail "Refusing on-VPS build while Cursor remote is active"
fi

if command -v sar >/dev/null 2>&1; then
  log "disk snapshot (sar -d 1 3)"
  sar -d 1 3 2>/dev/null | tail -n 8 || true
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

if command -v systemctl >/dev/null 2>&1 && systemctl_cmd cat "${SERVICE_NAME}" >/dev/null 2>&1; then
  log "reset-failed ${SERVICE_NAME}"
  systemctl_cmd reset-failed "${SERVICE_NAME}" 2>/dev/null || true

  if [[ -x "${ENSURE_PORT}" ]]; then
    log "port guard :3000"
    "${ENSURE_PORT}" 3000 \
      --service "${SERVICE_NAME}" \
      --orphan-pattern 'next-server' \
      --orphan-pattern 'npm run start' \
      --orphan-pattern 'node'
  else
    fail "missing executable: ${ENSURE_PORT}"
  fi

  log "Restarting ${SERVICE_NAME}"
  systemctl_cmd restart "${SERVICE_NAME}" || fail "systemctl restart ${SERVICE_NAME} failed"
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
  last_code="$(check_http "${HEALTH_URL}" "root")"
  case "${last_code}" in
    200|301|302|303|307|308)
      log "Health check passed (HTTP ${last_code}, attempt ${attempt}/${HEALTH_RETRIES})"
      break
      ;;
    *)
      sleep "${HEALTH_INTERVAL_SEC}"
      ;;
  esac
  if [[ "${attempt}" -eq "${HEALTH_RETRIES}" ]]; then
    fail "Health check failed after ${HEALTH_RETRIES} attempts (last HTTP ${last_code})"
  fi
done

smoke_url "${HEALTH_PERSONNEL_URL}" "local personnel"
smoke_url "${HEALTH_STAFF_URL}" "local staff"
if curl -sS --max-time 15 -o /dev/null "https://mmc.004.kz/" 2>/dev/null; then
  smoke_url "${PUBLIC_PERSONNEL_URL}" "public personnel"
  smoke_url "${PUBLIC_STAFF_URL}" "public staff"
else
  log "WARN: skipping public smoke (https://mmc.004.kz unreachable from this host)"
fi

log "deploy-frontend complete"
