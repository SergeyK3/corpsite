#!/usr/bin/env bash
# ADR-INFRA-005 — restart corpsite-backend with port guard, health smoke, scheduler smoke.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SERVICE_NAME="${CORPSITE_BACKEND_SERVICE:-corpsite-backend}"
HEALTH_URL="${CORPSITE_BACKEND_HEALTH_URL:-http://127.0.0.1:8000/health}"
ENSURE_PORT="${REPO_ROOT}/scripts/ops/ensure_port_free.sh"
SCHEDULER_SMOKE="${REPO_ROOT}/scripts/ops/scheduler_post_deploy_smoke.sh"

log() {
  echo "[deploy-backend] $*"
}

fail() {
  echo "[deploy-backend] ERROR: $*" >&2
  if command -v systemctl >/dev/null 2>&1; then
    if [[ "$(id -u)" -eq 0 ]]; then
      journalctl -u "${SERVICE_NAME}" -n 30 --no-pager >&2 || true
    else
      sudo journalctl -u "${SERVICE_NAME}" -n 30 --no-pager >&2 || true
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

run_scheduler_smoke() {
  if [[ "${CORPSITE_SKIP_SCHEDULER_SMOKE:-}" == "1" ]]; then
    log "WARN: CORPSITE_SKIP_SCHEDULER_SMOKE=1 — skipping scheduler smoke"
    return 0
  fi
  if [[ ! -f "${SCHEDULER_SMOKE}" ]]; then
    fail "missing scheduler smoke script: ${SCHEDULER_SMOKE}"
  fi
  if [[ ! -x "${SCHEDULER_SMOKE}" ]]; then
    chmod +x "${SCHEDULER_SMOKE}" 2>/dev/null || true
  fi
  log "scheduler post-deploy smoke"
  "${SCHEDULER_SMOKE}" || fail "scheduler post-deploy smoke failed"
}

if ! command -v systemctl >/dev/null 2>&1 || ! systemctl_cmd cat "${SERVICE_NAME}" >/dev/null 2>&1; then
  fail "systemd unit ${SERVICE_NAME} not found"
fi

log "reset-failed ${SERVICE_NAME}"
systemctl_cmd reset-failed "${SERVICE_NAME}" 2>/dev/null || true

if [[ -x "${ENSURE_PORT}" ]]; then
  log "port guard :8000"
  "${ENSURE_PORT}" 8000 \
    --service "${SERVICE_NAME}" \
    --orphan-pattern 'uvicorn' \
    --orphan-pattern 'app.main:app'
else
  fail "missing executable: ${ENSURE_PORT}"
fi

log "restart ${SERVICE_NAME}"
systemctl_cmd restart "${SERVICE_NAME}" || fail "systemctl restart ${SERVICE_NAME} failed"

if command -v curl >/dev/null 2>&1; then
  log "health check ${HEALTH_URL}"
  code="000"
  for attempt in $(seq 1 15); do
    code="$(curl -sS -o /dev/null -w '%{http_code}' "${HEALTH_URL}" 2>/dev/null || echo '000')"
    if [[ "${code}" == "200" ]]; then
      log "health OK (HTTP ${code}, attempt ${attempt}/15)"
      run_scheduler_smoke
      log "deploy backend OK"
      exit 0
    fi
    sleep 2
  done
  fail "health check failed (last HTTP ${code})"
else
  log "WARN: curl not found — skipping health check"
  run_scheduler_smoke
  log "deploy backend OK (health check skipped)"
  exit 0
fi
