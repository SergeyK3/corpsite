#!/usr/bin/env bash
set -euo pipefail

package=${1:?package path required}
expected_sha=${2:?sha256 required}
[[ $expected_sha =~ ^[0-9a-f]{64}$ ]] || exit 2
test_root=/opt/projects/corpsite-hire-prep
prod_base=/opt/projects/corpsite/releases/7ce7f06f-access-people
test_runtime=$test_root/releases/20261125-hire-name
prefix=20261125-order67-prod-base-${expected_sha:0:12}
backend=$test_root/releases/$prefix-backend
frontend=$test_root/releases/$prefix-frontend
unpack=$test_root/releases/$prefix-source

printf '%s  %s\n' "$expected_sha" "$package" | sha256sum -c -
test -d "$prod_base/app"
test -d "$prod_base/corpsite-ui/app"
test ! -e "$backend"
test ! -e "$frontend"
test ! -e "$unpack"
mkdir -p "$backend" "$frontend" "$unpack"
tar -xzf "$package" -C "$unpack"
python3 - "$unpack" <<'PY'
import hashlib, json, pathlib, sys
root = pathlib.Path(sys.argv[1])
manifest = json.loads((root / 'release-manifest.json').read_text())
for name, expected in manifest['files'].items():
    p = root / name
    if not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest() != expected:
        raise SystemExit(f'Bad package member: {name}')
print('PACKAGE_MEMBERS', len(manifest['files']))
PY
rsync -a --exclude='.venv' --exclude='node_modules' --exclude='.next' --exclude='corpsite-ui' "$prod_base/" "$backend/"
rsync -a --exclude='node_modules' --exclude='.next' "$prod_base/corpsite-ui/" "$frontend/"
rsync -a "$unpack/backend/" "$backend/"
rsync -a "$unpack/frontend/" "$frontend/"
ln -s "$test_runtime-backend/.venv" "$backend/.venv"
cp -a "$test_runtime-frontend/node_modules" "$frontend/node_modules"
cp "$unpack/release-manifest.json" "$backend/release-manifest.json"
cp "$unpack/release-manifest.json" "$frontend/release-manifest.json"
(
  cd "$backend"
  .venv/bin/python -m compileall -q app
  .venv/bin/python -m alembic heads
)
(
  set -a
  . "$test_root/releases/20261125-card-hire-catalog/frontend-test.env"
  set +a
  export NEXT_TELEMETRY_DISABLED=1
  cd "$frontend"
  node node_modules/next/dist/bin/next build --webpack > "$frontend/order67-build.log" 2>&1
)
printf 'STAGE_BACKEND=%s\nSTAGE_FRONTEND=%s\nBUILD_ID=%s\n' "$backend" "$frontend" "$(cat "$frontend/.next/BUILD_ID")"
