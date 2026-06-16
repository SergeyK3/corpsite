#!/usr/bin/env bash
# Verify production frontend bundle contains Phase 2F.3 training UI (not old candidates screen).
set -euo pipefail

UI_DIR="${1:-/opt/projects/corpsite/app/corpsite-ui}"
cd "$UI_DIR"

echo "== corpsite-ui path =="
pwd

echo "== git HEAD =="
git rev-parse --short HEAD

echo "== training page import =="
grep -n "PersonnelImportTrainingPageClient" app/directory/personnel/import/\[batchId\]/training/page.tsx

echo "== source must NOT contain old candidates title =="
if grep -R "Кандидаты документов" app/directory/personnel/_components/PersonnelImportTrainingPageClient.tsx; then
  echo "FAIL: old title still in training client"
  exit 1
fi
echo "OK: old title absent from training client source"

echo "== production build markers in .next =="
if [ ! -d .next ]; then
  echo "FAIL: .next missing — run npm run build"
  exit 1
fi

if grep -R "2f3-education-profiles" .next 2>/dev/null | head -n 3; then
  echo "OK: found data-ui-phase marker in build"
else
  echo "WARN: data-ui-phase marker not found (may be minified away)"
fi

if grep -R "Образовательные профили сотрудников из импорта" .next 2>/dev/null | head -n 3; then
  echo "OK: new training title present in build"
else
  echo "FAIL: new training title missing from .next — stale build?"
  exit 1
fi

if grep -R "Кандидаты документов" .next 2>/dev/null | head -n 3; then
  echo "FAIL: old candidates title still in .next bundle"
  exit 1
fi
echo "OK: old candidates title absent from .next"

echo "== systemd frontend working directory (if available) =="
if command -v systemctl >/dev/null 2>&1; then
  systemctl cat corpsite-frontend 2>/dev/null | grep -E 'WorkingDirectory|ExecStart' || true
fi

echo "ALL CHECKS PASSED"
