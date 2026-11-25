#!/usr/bin/env bash
set -euo pipefail

package=${1:?full source package required}
expected_sha=${2:?full source sha256 required}
[[ $expected_sha =~ ^[0-9a-f]{64}$ ]] || exit 2
base=/opt/projects/corpsite/releases/7ce7f06f-access-people
test_base=/opt/projects/corpsite-hire-prep/releases/20261125-hire-name
stage=/opt/projects/corpsite/releases/20261125-order67-${expected_sha:0:12}

printf '%s  %s\n' "$expected_sha" "$package" | sha256sum -c -
test "$(systemctl show corpsite-backend -p WorkingDirectory --value)" = "$base"
test "$(systemctl show corpsite-frontend -p WorkingDirectory --value)" = "$base/corpsite-ui"
test ! -e "$stage"
mkdir -p "$stage"
tar -xzf "$package" -C "$stage"
python3 - "$stage" <<'PY'
import hashlib, json, pathlib, sys
root = pathlib.Path(sys.argv[1])
manifest = json.loads((root / 'release-source-manifest.json').read_text())
if manifest['overlay_sha256'] != '0cf613ec338b674ddfd2534760432271c76759f51f7486e903245f6830d0f3cd':
    raise SystemExit('Unexpected overlay package')
for name, expected in manifest['files'].items():
    p = root / name
    if not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest() != expected:
        raise SystemExit(f'Bad source member: {name}')
print('VERIFIED_SOURCE_MEMBERS', len(manifest['files']))
PY
cp -aL "$test_base-backend/.venv" "$stage/backend/.venv"
cp -a "$test_base-frontend/node_modules" "$stage/frontend/node_modules"
install -m 0600 "$base/corpsite-ui/.env.production" "$stage/frontend/.env.production"
(
  set -a
  . /opt/projects/corpsite/app/.env
  set +a
  cd "$stage/backend"
  .venv/bin/python -m compileall -q app
  .venv/bin/python -m alembic heads
  .venv/bin/python -m alembic current
)
(
  cd "$stage/frontend"
  export NEXT_TELEMETRY_DISABLED=1
  node node_modules/next/dist/bin/next build --webpack > "$stage/frontend/order67-build.log" 2>&1
)
printf 'PROD_STAGE=%s\nBUILD_ID=%s\n' "$stage" "$(cat "$stage/frontend/.next/BUILD_ID")"
