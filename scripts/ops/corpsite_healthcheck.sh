#!/usr/bin/env bash
# ADR-INFRA-005 — periodic health check + controlled recovery for Corpsite VPS services.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
LOG_FILE="${CORPSITE_HEALTHCHECK_LOG:-/var/log/corpsite-healthcheck.log}"
FRONTEND_SERVICE="${CORPSITE_FRONTEND_SERVICE:-corpsite-frontend}"
BACKEND_SERVICE="${CORPSITE_BACKEND_SERVICE:-corpsite-backend}"
FRONTEND_URL="${CORPSITE_FRONTEND_HEALTH_URL:-http://127.0.0.1:3000/}"
BACKEND_HEALTH_URL="${CORPSITE_BACKEND_HEALTH_URL:-http://127.0.0.1:8000/health}"
PUBLIC_PERSONNEL_URL="${CORPSITE_PUBLIC_PERSONNEL_URL:-https://mmc.004.kz/directory/personnel}"
ENSURE_PORT="${REPO_ROOT}/scripts/ops/ensure_port_free.sh"
ATTEMPT_RECOVERY="${CORPSITE_HEALTHCHECK_RECOVER:-1}"

timestamp() {
  date -u '+%Y-%m-%dT%H:%M:%SZ'
}

log() {
  local line="[$(timestamp)] $*"
  echo "${line}"
  if [[ -w "${LOG_FILE}" ]] || [[ "${EUID}" -eq 0 ]]; then
    echo "${line}" >> "${LOG_FILE}" 2>/dev/null || true
  fi
}

http_code() {
  curl -sS -o /dev/null -w '%{http_code}' --max-time 10 "$1" 2>/dev/null || echo '000'
}

systemctl_cmd() {
  if [[ "${EUID}" -eq 0 ]]; then
    systemctl "$@"
  else
    sudo systemctl "$@"
  fi
}

service_active() {
  systemctl_cmd is-active --quiet "$1"
}

service_failed() {
  systemctl_cmd is-failed --quiet "$1" 2>/dev/null
}

recover_frontend() {
  log "RECOVER frontend: reset-failed + port guard + start"
  systemctl_cmd reset-failed "${FRONTEND_SERVICE}" 2>/dev/null || true
  if [[ -x "${ENSURE_PORT}" ]]; then
    "${ENSURE_PORT}" 3000 \
      --service "${FRONTEND_SERVICE}" \
      --orphan-pattern 'next-server' \
      --orphan-pattern 'npm run start' \
      --orphan-pattern 'node' || {
      log "RECOVER frontend: port guard failed"
      return 1
    }
  fi
  systemctl_cmd start "${FRONTEND_SERVICE}" || {
    log "RECOVER frontend: systemctl start failed"
    return 1
  }
  sleep 3
  local code
  code="$(http_code "${FRONTEND_URL}")"
  if [[ "${code}" =~ ^(200|301|302|303|307|308)$ ]]; then
    log "RECOVER frontend: OK (HTTP ${code})"
    return 0
  fi
  log "RECOVER frontend: still unhealthy (HTTP ${code})"
  return 1
}

recover_backend() {
  log "RECOVER backend: reset-failed + port guard + start"
  systemctl_cmd reset-failed "${BACKEND_SERVICE}" 2>/dev/null || true
  if [[ -x "${ENSURE_PORT}" ]]; then
    "${ENSURE_PORT}" 8000 \
      --service "${BACKEND_SERVICE}" \
      --orphan-pattern 'uvicorn' \
      --orphan-pattern 'app.main:app' || {
      log "RECOVER backend: port guard failed"
      return 1
    }
  fi
  systemctl_cmd start "${BACKEND_SERVICE}" || {
    log "RECOVER backend: systemctl start failed"
    return 1
  }
  sleep 2
  local code
  code="$(http_code "${BACKEND_HEALTH_URL}")"
  if [[ "${code}" == "200" ]]; then
    log "RECOVER backend: OK (HTTP ${code})"
    return 0
  fi
  log "RECOVER backend: still unhealthy (HTTP ${code})"
  return 1
}

main() {
  log "healthcheck start"

  local backend_code frontend_code public_code
  backend_code="$(http_code "${BACKEND_HEALTH_URL}")"
  frontend_code="$(http_code "${FRONTEND_URL}")"
  public_code="$(http_code "${PUBLIC_PERSONNEL_URL}")"

  log "backend ${BACKEND_HEALTH_URL} -> HTTP ${backend_code} (active=$(service_active "${BACKEND_SERVICE}" && echo yes || echo no))"
  log "frontend ${FRONTEND_URL} -> HTTP ${frontend_code} (active=$(service_active "${FRONTEND_SERVICE}" && echo yes || echo no))"
  log "public ${PUBLIC_PERSONNEL_URL} -> HTTP ${public_code}"

  local ok=0

  if [[ "${backend_code}" != "200" ]] || ! service_active "${BACKEND_SERVICE}"; then
    ok=1
    if [[ "${ATTEMPT_RECOVERY}" == "1" ]]; then
      recover_backend || true
    else
      log "backend unhealthy; recovery disabled"
    fi
  fi

  if [[ ! "${frontend_code}" =~ ^(200|301|302|303|307|308)$ ]] || ! service_active "${FRONTEND_SERVICE}" || service_failed "${FRONTEND_SERVICE}"; then
    ok=1
    if [[ "${ATTEMPT_RECOVERY}" == "1" ]]; then
      recover_frontend || true
    else
      log "frontend unhealthy; recovery disabled"
    fi
  fi

  if [[ "${ok}" -eq 0 ]]; then
    log "healthcheck OK"
    exit 0
  fi

  log "healthcheck DEGRADED (see journalctl -u ${FRONTEND_SERVICE} -u ${BACKEND_SERVICE})"
  exit 1
}

main "$@"
