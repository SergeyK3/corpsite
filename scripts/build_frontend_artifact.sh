#!/usr/bin/env bash
# WP-INFRA-IO-002 — build Next.js off-box and pack .next for VPS deploy.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
UI_DIR="${REPO_ROOT}/corpsite-ui"
OUT_DIR="${CORPSITE_ARTIFACT_DIR:-${REPO_ROOT}/tmp/frontend-artifacts}"

log() {
  echo "[build-frontend-artifact] $*"
}

fail() {
  echo "[build-frontend-artifact] ERROR: $*" >&2
  exit 1
}

if [[ ! -d "${UI_DIR}" ]]; then
  fail "corpsite-ui directory not found: ${UI_DIR}"
fi

mkdir -p "${OUT_DIR}"

cd "${UI_DIR}"
log "Working directory: $(pwd)"

log "npm ci"
npm ci

log "npm run build"
npm run build

if [[ ! -f .next/BUILD_ID ]]; then
  fail "Build failed: .next/BUILD_ID not found"
fi

BUILD_ID="$(tr -d '\n' < .next/BUILD_ID)"
GIT_REV="$(git -C "${REPO_ROOT}" rev-parse --short HEAD 2>/dev/null || echo unknown)"
LOCK_HASH="$(sha256sum package-lock.json | awk '{print $1}')"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
ARTIFACT_NAME="corpsite-ui-next-${STAMP}-${GIT_REV}.tar.gz"
ARTIFACT_PATH="${OUT_DIR}/${ARTIFACT_NAME}"
MANIFEST_PATH="${OUT_DIR}/${ARTIFACT_NAME%.tar.gz}.manifest.json"

log "Packing .next (BUILD_ID=${BUILD_ID})"
tar -C "${UI_DIR}" -czf "${ARTIFACT_PATH}" .next

cat > "${MANIFEST_PATH}" <<EOF
{
  "artifact": "$(basename "${ARTIFACT_PATH}")",
  "build_id": "${BUILD_ID}",
  "git_rev": "${GIT_REV}",
  "package_lock_sha256": "${LOCK_HASH}",
  "created_at_utc": "${STAMP}",
  "ui_dir": "corpsite-ui"
}
EOF

log "Artifact: ${ARTIFACT_PATH}"
log "Manifest: ${MANIFEST_PATH}"
log "Deploy on VPS: sudo ./scripts/deploy_frontend_artifact.sh ${ARTIFACT_PATH}"
