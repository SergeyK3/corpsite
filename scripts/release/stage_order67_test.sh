#!/usr/bin/env bash
set -euo pipefail

package=${1:?package path required}
expected_sha=${2:?expected sha256 required}
root=/opt/projects/corpsite-hire-prep
base_backend=$root/releases/20261125-hire-name-backend
base_frontend=$root/releases/20261125-hire-name-frontend
prefix=20261125-order67-${expected_sha:0:12}
stage_backend=$root/releases/$prefix-backend
stage_frontend=$root/releases/$prefix-frontend
unpack=$root/releases/$prefix-source

printf '%s  %s\n' "$expected_sha" "$package" | sha256sum -c -
test "$(systemctl show corpsite-hire-prep-backend -p WorkingDirectory --value)" = "$base_backend"
test "$(systemctl show corpsite-hire-prep-frontend -p WorkingDirectory --value)" = "$base_frontend"
test ! -e "$stage_backend"
test ! -e "$stage_frontend"
test ! -e "$unpack"

mkdir -p "$unpack" "$stage_backend" "$stage_frontend"
tar -xzf "$package" -C "$unpack"
python3 - "$unpack" <<'PY'
import hashlib, json, pathlib, sys
root = pathlib.Path(sys.argv[1])
manifest = json.loads((root / 'release-manifest.json').read_text())
for name, expected in manifest['files'].items():
    path = root / name
    if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
        raise SystemExit(f'Package member failed: {name}')
print('PACKAGE_MEMBERS', len(manifest['files']))
PY

rsync -a --exclude='.venv' --exclude='node_modules' --exclude='.next' "$base_backend/" "$stage_backend/"
rsync -a --exclude='node_modules' --exclude='.next' "$base_frontend/" "$stage_frontend/"
rsync -a "$unpack/backend/" "$stage_backend/"
rsync -a "$unpack/frontend/" "$stage_frontend/"
ln -s "$base_backend/.venv" "$stage_backend/.venv"
cp -a "$base_frontend/node_modules" "$stage_frontend/node_modules"
cp "$unpack/release-manifest.json" "$stage_backend/release-manifest.json"
cp "$unpack/release-manifest.json" "$stage_frontend/release-manifest.json"

(
  cd "$stage_backend"
  .venv/bin/python -m compileall -q app
  .venv/bin/python -m alembic heads
)
(
  set -a
  . "$root/releases/20261125-card-hire-catalog/frontend-test.env"
  set +a
  export NEXT_TELEMETRY_DISABLED=1
  cd "$stage_frontend"
  node node_modules/next/dist/bin/next build --webpack > "$stage_frontend/order67-build.log" 2>&1
)
printf 'STAGE_BACKEND=%s\nSTAGE_FRONTEND=%s\nBUILD_ID=%s\n' \
  "$stage_backend" "$stage_frontend" "$(cat "$stage_frontend/.next/BUILD_ID")"
