#!/usr/bin/env bash
# ADR-INFRA-005 — restart corpsite-backend with port guard, health smoke, scheduler smoke.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SERVICE_NAME="${CORPSITE_BACKEND_SERVICE:-corpsite-backend}"
HEALTH_URL="${CORPSITE_BACKEND_HEALTH_URL:-http://127.0.0.1:8000/health}"
ENSURE_PORT="${REPO_ROOT}/scripts/ops/ensure_port_free.sh"
SCHEDULER_SMOKE="${REPO_ROOT}/scripts/ops/scheduler_post_deploy_smoke.sh"
ALEMBIC="${REPO_ROOT}/.venv/bin/alembic"

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

run_migrations() {
  if [[ ! -x "${ALEMBIC}" ]]; then
    fail "missing executable: ${ALEMBIC}"
  fi

  log "database migration upgrade to head"
  (cd "${REPO_ROOT}" && "${ALEMBIC}" upgrade head) \
    || fail "alembic upgrade head failed"

  local heads_output
  local current_output
  local expected_head
  local current_revision
  local head_count
  local current_count

  heads_output="$(cd "${REPO_ROOT}" && "${ALEMBIC}" heads)" \
    || fail "alembic heads failed"
  head_count="$(printf '%s\n' "${heads_output}" | awk 'NF { count += 1 } END { print count + 0 }')"
  if [[ "${head_count}" != "1" ]]; then
    fail "expected exactly one Alembic head, found ${head_count}"
  fi
  expected_head="$(printf '%s\n' "${heads_output}" | awk 'NF { print $1; exit }')"

  current_output="$(cd "${REPO_ROOT}" && "${ALEMBIC}" current)" \
    || fail "alembic current failed"
  current_count="$(printf '%s\n' "${current_output}" | awk 'NF { count += 1 } END { print count + 0 }')"
  if [[ "${current_count}" != "1" ]]; then
    fail "expected exactly one current Alembic revision, found ${current_count}"
  fi
  current_revision="$(printf '%s\n' "${current_output}" | awk 'NF { print $1; exit }')"
  if [[ -z "${current_revision}" || "${current_revision}" != "${expected_head}" ]]; then
    fail "database revision does not match the single Alembic head"
  fi
  log "database migration OK (revision ${current_revision})"
}

if ! command -v systemctl >/dev/null 2>&1 || ! systemctl_cmd cat "${SERVICE_NAME}" >/dev/null 2>&1; then
  fail "systemd unit ${SERVICE_NAME} not found"
fi

run_migrations

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
