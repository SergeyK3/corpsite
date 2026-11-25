#!/usr/bin/env bash
set -euo pipefail
umask 077

source_sha=fbe378d5c3e21d3f6bc8babc3e6d3cdfd9c939124a1cc8e5347b90c6c2a4a8e7
stage=/opt/projects/corpsite/releases/20261125-order67-${source_sha:0:12}
old=/opt/projects/corpsite/releases/7ce7f06f-access-people
package=/tmp/order67-full-source-0cf613ec338b.tar.gz
backend_conf=/etc/systemd/system/corpsite-backend.service.d/zzzzzzzzzzzzzzzzzzzzzzzz-order67.conf
frontend_conf=/etc/systemd/system/corpsite-frontend.service.d/zzzzzzzzzzzzzzzzzzzzzzzz-order67.conf

printf '%s  %s\n' "$source_sha" "$package" | sha256sum -c -
test "$(systemctl show corpsite-backend -p WorkingDirectory --value)" = "$old"
test "$(systemctl show corpsite-frontend -p WorkingDirectory --value)" = "$old/corpsite-ui"
test ! -e "$backend_conf"
test ! -e "$frontend_conf"
test -s "$stage/backend/release-source-manifest.json" || test -s "$stage/release-source-manifest.json"
test -s "$stage/frontend/.next/BUILD_ID"
python3 - "$stage" <<'PY'
import hashlib, json, pathlib, sys
root = pathlib.Path(sys.argv[1])
manifest = json.loads((root / 'release-source-manifest.json').read_text())
for name, expected in manifest['files'].items():
    p = root / name
    if not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest() != expected:
        raise SystemExit(f'Source mismatch: {name}')
print('SOURCE_MEMBERS', len(manifest['files']))
PY

set -a
. /opt/projects/corpsite/app/.env
set +a
before=$(cd "$stage/backend" && .venv/bin/python -m alembic current)
[[ $before == ehpt20261123* ]] || { echo "Unexpected migration: $before" >&2; exit 1; }
backup=/opt/projects/corpsite/backups/order67-$(date -u +%Y%m%dT%H%M%SZ)-before.dump
pg_dump "$DATABASE_URL" --format=custom --file="$backup"
pg_restore --list "$backup" >/dev/null
echo "BACKUP=$backup"

(
  cd "$stage/backend"
  .venv/bin/python -m alembic upgrade head
  after=$(.venv/bin/python -m alembic current)
  [[ $after == eha005* ]] || { echo "Unexpected migrated revision: $after" >&2; exit 1; }
)

rollback_services() {
  sudo rm -f -- "$backend_conf" "$frontend_conf"
  sudo systemctl daemon-reload
  sudo systemctl restart corpsite-backend corpsite-frontend
}
trap rollback_services ERR

cat > /tmp/order67-prod-backend.conf <<EOF
[Service]
WorkingDirectory=$stage/backend
Environment=PYTHONDONTWRITEBYTECODE=1
ExecStartPre=
ExecStart=
ExecStart=$stage/backend/.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
EOF
cat > /tmp/order67-prod-frontend.conf <<EOF
[Service]
WorkingDirectory=$stage/frontend
Environment=CORPSITE_UI_DIR=$stage/frontend
Environment=NEXT_DEPLOYMENT_ID=order67-${source_sha:0:12}
ExecStartPre=
ExecStartPre=/usr/bin/test -s $stage/frontend/.next/BUILD_ID
ExecStart=
ExecStart=/usr/bin/node $stage/frontend/node_modules/next/dist/bin/next start --hostname 127.0.0.1 --port 3000
EOF
sudo install -m 0644 /tmp/order67-prod-backend.conf "$backend_conf"
sudo install -m 0644 /tmp/order67-prod-frontend.conf "$frontend_conf"
sudo systemctl daemon-reload
sudo systemctl restart corpsite-backend corpsite-frontend

for attempt in $(seq 1 40); do
  if curl -fsS http://127.0.0.1:8000/health >/dev/null 2>&1 &&
     curl -fsS http://127.0.0.1:3000/ >/dev/null 2>&1; then break; fi
  sleep 1
done
test "$(systemctl show corpsite-backend -p WorkingDirectory --value)" = "$stage/backend"
test "$(systemctl show corpsite-frontend -p WorkingDirectory --value)" = "$stage/frontend"
systemctl is-active --quiet corpsite-backend
systemctl is-active --quiet corpsite-frontend
curl -fsS http://127.0.0.1:8000/health >/dev/null
curl -fsS http://127.0.0.1:3000/ >/dev/null
trap - ERR
printf 'ACTIVE_SOURCE_SHA256=%s\nBUILD_ID=%s\nBACKUP=%s\n' "$source_sha" "$(cat "$stage/frontend/.next/BUILD_ID")" "$backup"
