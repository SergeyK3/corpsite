#!/usr/bin/env bash
# Exit 203 = missing production build (systemd RestartPreventExitStatus — no restart loop).
set -euo pipefail

UI_DIR="${CORPSITE_UI_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../corpsite-ui" && pwd)}"
BUILD_ID_FILE="${UI_DIR}/.next/BUILD_ID"

if [[ ! -f "${BUILD_ID_FILE}" ]]; then
  echo "corpsite-frontend: production build missing (${BUILD_ID_FILE})" >&2
  echo "Run: sudo ./scripts/deploy_frontend.sh" >&2
  exit 203
fi

echo "corpsite-frontend: build OK (BUILD_ID=$(tr -d '\n' < "${BUILD_ID_FILE}"))"
exit 0
