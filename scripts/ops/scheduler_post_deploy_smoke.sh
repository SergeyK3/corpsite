#!/usr/bin/env bash
# Post-deploy smoke: regular-tasks scheduler infrastructure (read-only, no task creation).
# See docs/ops/REGULAR_TASK_SCHEDULER_RUNBOOK.md and docs/deploy/VPS_STABILITY.md
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TIMER_UNIT="${CORPSITE_REGULAR_TASKS_TIMER:-corpsite-regular-tasks.timer}"
SERVICE_UNIT="${CORPSITE_REGULAR_TASKS_SERVICE:-corpsite-regular-tasks.service}"
ENV_FILE="${REPO_ROOT}/.env"
PYTHON="${CORPSITE_PYTHON:-${REPO_ROOT}/.venv/bin/python}"
AUDIT_SCRIPT="${REPO_ROOT}/scripts/ops/ops_regular_tasks_scheduler_audit.py"

log() {
  echo "[scheduler-smoke] $*"
}

fail() {
  echo "[scheduler-smoke] ERROR: $*" >&2
  exit 1
}

systemctl_cmd() {
  if [[ "$(id -u)" -eq 0 ]]; then
    systemctl "$@"
  else
    sudo systemctl "$@"
  fi
}

if ! command -v systemctl >/dev/null 2>&1; then
  fail "systemctl not available — scheduler smoke requires Linux VPS with systemd"
fi

log "checking unit ${TIMER_UNIT}"
systemctl_cmd cat "${TIMER_UNIT}" >/dev/null 2>&1 || fail "systemd unit ${TIMER_UNIT} not found"

enabled="$(systemctl_cmd is-enabled "${TIMER_UNIT}" 2>/dev/null || true)"
[[ "${enabled}" == "enabled" ]] || fail "${TIMER_UNIT} is not enabled (got: ${enabled:-unknown})"

active="$(systemctl_cmd is-active "${TIMER_UNIT}" 2>/dev/null || true)"
[[ "${active}" == "active" ]] || fail "${TIMER_UNIT} is not active (expected active/waiting, got: ${active:-unknown})"
log "${TIMER_UNIT}: enabled, active (waiting)"

log "checking next trigger for ${TIMER_UNIT}"
timer_lines="$(systemctl_cmd list-timers "${TIMER_UNIT}" --no-pager 2>/dev/null || true)"
if ! grep -q "${TIMER_UNIT}" <<< "${timer_lines}"; then
  fail "no scheduled trigger found in: systemctl list-timers ${TIMER_UNIT}"
fi
next_line="$(grep "${TIMER_UNIT}" <<< "${timer_lines}" | head -n 1)"
log "next trigger: ${next_line}"

log "checking unit ${SERVICE_UNIT}"
systemctl_cmd cat "${SERVICE_UNIT}" >/dev/null 2>&1 || fail "systemd unit ${SERVICE_UNIT} not found"

if [[ ! -f "${ENV_FILE}" ]]; then
  fail "missing ${ENV_FILE}"
fi

if [[ ! -x "${PYTHON}" ]]; then
  if command -v python3 >/dev/null 2>&1; then
    PYTHON="$(command -v python3)"
  else
    fail "python not found (expected ${REPO_ROOT}/.venv/bin/python)"
  fi
fi

if [[ ! -f "${AUDIT_SCRIPT}" ]]; then
  fail "missing audit script: ${AUDIT_SCRIPT}"
fi

log "loading env from ${ENV_FILE}"
set -a
# shellcheck disable=SC1090
source "${ENV_FILE}"
set +a

log "running scheduler audit (post-deploy smoke, dry_run probe only)"
"${PYTHON}" "${AUDIT_SCRIPT}" --post-deploy-smoke

log "scheduler post-deploy smoke OK"
