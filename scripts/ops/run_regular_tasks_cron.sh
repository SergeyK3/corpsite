#!/usr/bin/env bash
# Invoke automatic regular-tasks generation (same contract as production cron).
# Run on VPS from repo root, or via corpsite-regular-tasks.service.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ENV_FILE="${ROOT}/.env"
LOG_TAG="corpsite-regular-tasks-cron"

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "${LOG_TAG}: missing ${ENV_FILE}" >&2
  exit 1
fi

# shellcheck disable=SC1090
set -a
source "${ENV_FILE}"
set +a

: "${INTERNAL_API_TOKEN:?INTERNAL_API_TOKEN is not set in .env}"
: "${REGULAR_TASKS_CRON_USER_ID:?REGULAR_TASKS_CRON_USER_ID is not set in .env}"

BACKEND_URL="${BACKEND_URL:-http://127.0.0.1:8000}"
BACKEND_URL="${BACKEND_URL%/}"

payload='{"dry_run": false}'
if [[ "${1:-}" == "--dry-run" ]]; then
  payload='{"dry_run": true}'
fi

http_code="$(
  curl -sS -o /tmp/corpsite_regular_tasks_cron_last.json -w "%{http_code}" \
    -X POST "${BACKEND_URL}/internal/regular-tasks/run" \
    -H "Content-Type: application/json" \
    -H "X-Internal-Api-Token: ${INTERNAL_API_TOKEN}" \
    -H "X-User-Id: ${REGULAR_TASKS_CRON_USER_ID}" \
    -d "${payload}"
)"

if [[ "${http_code}" != "200" ]]; then
  echo "${LOG_TAG}: HTTP ${http_code}" >&2
  head -c 500 /tmp/corpsite_regular_tasks_cron_last.json >&2 || true
  echo >&2
  exit 1
fi

cat /tmp/corpsite_regular_tasks_cron_last.json
echo
