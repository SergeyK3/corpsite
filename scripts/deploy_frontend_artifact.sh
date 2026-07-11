#!/usr/bin/env bash
# WP-INFRA-IO-002 — install pre-built .next artifact and restart corpsite-frontend.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
UI_DIR="${REPO_ROOT}/corpsite-ui"
SERVICE_NAME="${CORPSITE_FRONTEND_SERVICE:-corpsite-frontend}"
ENSURE_PORT="${REPO_ROOT}/scripts/ops/ensure_port_free.sh"
HEALTH_URL="${CORPSITE_FRONTEND_HEALTH_URL:-http://127.0.0.1:3000/}"
HEALTH_RETRIES="${CORPSITE_FRONTEND_HEALTH_RETRIES:-30}"
HEALTH_INTERVAL_SEC="${CORPSITE_FRONTEND_HEALTH_INTERVAL_SEC:-2}"

log() {
  echo "[deploy-frontend-artifact] $*"
}

fail() {
  echo "[deploy-frontend-artifact] ERROR: $*" >&2
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
  curl -sS -o /dev/null -w '%{http_code}' --max-time 15 "${url}" 2>/dev/null || echo "000"
}

usage() {
  cat <<EOF
Usage: sudo ./scripts/deploy_frontend_artifact.sh <path-to-artifact.tar.gz>

Installs a .next tarball produced by scripts/build_frontend_artifact.sh.
Does not run npm run build on the VPS.

See docs/ops/WP-INFRA-IO-002-VPS-IO-Guardrails.md
EOF
}

ARTIFACT="${1:-}"
if [[ -z "${ARTIFACT}" || "${ARTIFACT}" == "-h" || "${ARTIFACT}" == "--help" ]]; then
  usage
  exit 0
fi

if [[ ! -f "${ARTIFACT}" ]]; then
  fail "Artifact not found: ${ARTIFACT}"
fi

if [[ ! -d "${UI_DIR}" ]]; then
  fail "corpsite-ui directory not found: ${UI_DIR}"
fi

cd "${UI_DIR}"

WORK_DIR="${UI_DIR}/.deploy-work.$$"
PREVIOUS="${UI_DIR}/.next.prev.$$"

cleanup() {
  rm -rf "${WORK_DIR}" 2>/dev/null || true
}
trap cleanup EXIT

log "Extracting artifact"
rm -rf "${WORK_DIR}"
mkdir -p "${WORK_DIR}"
tar -xzf "${ARTIFACT}" -C "${WORK_DIR}"

if [[ ! -f "${WORK_DIR}/.next/BUILD_ID" ]]; then
  fail "Artifact invalid: .next/BUILD_ID missing"
fi

BUILD_ID="$(tr -d '\n' < "${WORK_DIR}/.next/BUILD_ID")"
log "Artifact BUILD_ID=${BUILD_ID}"

if [[ -d .next ]]; then
  log "Backing up current .next to ${PREVIOUS}"
  rm -rf "${PREVIOUS}"
  mv .next "${PREVIOUS}"
fi

if ! mv "${WORK_DIR}/.next" .next; then
  if [[ -d "${PREVIOUS}" ]]; then
    log "WARN: restore previous .next after failed switch"
    rm -rf .next 2>/dev/null || true
    mv "${PREVIOUS}" .next || true
  fi
  fail "Failed to activate new .next"
fi

rm -rf "${PREVIOUS}" 2>/dev/null || true
cleanup
trap - EXIT

if command -v systemctl >/dev/null 2>&1 && systemctl_cmd cat "${SERVICE_NAME}" >/dev/null 2>&1; then
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

if command -v curl >/dev/null 2>&1; then
  log "Health check ${HEALTH_URL}"
  last_code="000"
  for ((attempt = 1; attempt <= HEALTH_RETRIES; attempt++)); do
    last_code="$(check_http "${HEALTH_URL}")"
    case "${last_code}" in
      200|301|302|303|307|308)
        log "Health check passed (HTTP ${last_code})"
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
fi

log "deploy-frontend-artifact complete (BUILD_ID=${BUILD_ID})"
