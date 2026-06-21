#!/usr/bin/env bash
# ADR-INFRA-005 — ensure a TCP port is free or only held by expected orphans we can kill.
#
# Usage:
#   ensure_port_free.sh PORT [--service UNIT] [--orphan-pattern REGEX]...
#
# Examples:
#   ensure_port_free.sh 3000 --service corpsite-frontend \
#     --orphan-pattern 'next-server' --orphan-pattern 'npm run start'
#   ensure_port_free.sh 8000 --service corpsite-backend \
#     --orphan-pattern 'uvicorn' --orphan-pattern 'app.main:app'
#
# Exit codes:
#   0 — port free or successfully cleared
#   1 — unknown process holds port / could not free
#   2 — usage error
set -euo pipefail

PORT=""
SERVICE=""
ORPHAN_PATTERNS=()
KILL_SIGNAL="${KILL_SIGNAL:-TERM}"
WAIT_SEC="${WAIT_SEC:-3}"

usage() {
  sed -n '2,12p' "$0" | tail -n +2
  exit 2
}

log() {
  echo "[ensure-port-free] $*" >&2
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --service)
      SERVICE="${2:-}"
      shift 2
      ;;
    --orphan-pattern)
      ORPHAN_PATTERNS+=("${2:-}")
      shift 2
      ;;
    --wait-sec)
      WAIT_SEC="${2:-3}"
      shift 2
      ;;
    -h|--help)
      usage
      ;;
    *)
      if [[ -z "${PORT}" ]]; then
        PORT="$1"
        shift
      else
        log "unexpected argument: $1"
        usage
      fi
      ;;
  esac
done

[[ -n "${PORT}" ]] || usage

if ! [[ "${PORT}" =~ ^[0-9]+$ ]]; then
  log "invalid port: ${PORT}"
  exit 2
fi

cmdline_for_pid() {
  local pid="$1"
  tr '\0' ' ' < "/proc/${pid}/cmdline" 2>/dev/null || true
}

pid_in_service_cgroup() {
  local pid="$1" unit="$2"
  [[ -f "/proc/${pid}/cgroup" ]] || return 1
  grep -q "${unit}" "/proc/${pid}/cgroup" 2>/dev/null
}

matches_orphan_pattern() {
  local cmd="$1"
  local pattern
  for pattern in "${ORPHAN_PATTERNS[@]}"; do
    if [[ "${cmd}" == *"${pattern}"* ]]; then
      return 0
    fi
  done
  return 1
}

listener_pids() {
  ss -lptn "sport = :${PORT}" 2>/dev/null \
    | grep -oE 'pid=[0-9]+' \
    | cut -d= -f2 \
    | sort -u
}

kill_pid() {
  local pid="$1" reason="$2"
  log "sending SIG${KILL_SIGNAL} to pid=${pid} (${reason})"
  kill "-${KILL_SIGNAL}" "${pid}" 2>/dev/null || true
}

describe_pid() {
  local pid="$1"
  printf 'pid=%s cmd=%q' "${pid}" "$(cmdline_for_pid "${pid}")"
}

pids="$(listener_pids || true)"
if [[ -z "${pids}" ]]; then
  log "port ${PORT}: free"
  exit 0
fi

to_kill=()
blocked=()

while read -r pid; do
  [[ -n "${pid}" ]] || continue
  if ! kill -0 "${pid}" 2>/dev/null; then
    continue
  fi

  cmd="$(cmdline_for_pid "${pid}")"

  if [[ -n "${SERVICE}" ]] && pid_in_service_cgroup "${pid}" "${SERVICE}"; then
    log "port ${PORT}: listener in ${SERVICE} cgroup — will stop: $(describe_pid "${pid}")"
    to_kill+=("${pid}")
    continue
  fi

  if [[ ${#ORPHAN_PATTERNS[@]} -gt 0 ]] && matches_orphan_pattern "${cmd}"; then
    log "port ${PORT}: orphan listener — will kill: $(describe_pid "${pid}")"
    to_kill+=("${pid}")
    continue
  fi

  blocked+=("${pid}")
done <<< "${pids}"

if [[ ${#blocked[@]} -gt 0 ]]; then
  for pid in "${blocked[@]}"; do
    log "port ${PORT}: BLOCKED by unknown process: $(describe_pid "${pid}")"
  done
  log "refusing to kill unknown process(es); free the port manually or extend --orphan-pattern"
  exit 1
fi

if [[ ${#to_kill[@]} -eq 0 ]]; then
  log "port ${PORT}: listeners present but nothing to kill"
  exit 0
fi

for pid in "${to_kill[@]}"; do
  kill_pid "${pid}" "clear port ${PORT}"
done

sleep "${WAIT_SEC}"

remaining="$(listener_pids || true)"
if [[ -n "${remaining}" ]]; then
  for pid in ${remaining}; do
    log "port ${PORT}: still held after SIG${KILL_SIGNAL}: $(describe_pid "${pid}")"
  done
  log "trying SIGKILL"
  for pid in ${remaining}; do
    kill -KILL "${pid}" 2>/dev/null || true
  done
  sleep 1
  remaining="$(listener_pids || true)"
fi

if [[ -n "${remaining}" ]]; then
  log "port ${PORT}: still not free"
  exit 1
fi

log "port ${PORT}: free after cleanup"
exit 0
