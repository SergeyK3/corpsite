#!/usr/bin/env bash
set -euo pipefail

sha=${1:?source package sha256 required}
[[ $sha =~ ^[0-9a-f]{64}$ ]] || { echo 'Invalid package sha256' >&2; exit 2; }
variant=${2:-test-base}
[[ $variant == test-base || $variant == prod-base ]] || exit 2
root=/opt/projects/corpsite-hire-prep
if [[ $variant == prod-base ]]; then
  prefix=20261125-order67-prod-base-${sha:0:12}
  previous=20261125-order67-${sha:0:12}
else
  prefix=20261125-order67-${sha:0:12}
  previous=20261125-hire-name
fi
backend=$root/releases/$prefix-backend
frontend=$root/releases/$prefix-frontend
dropins=/etc/systemd/system
backend_conf=$dropins/corpsite-hire-prep-backend.service.d/zzzzzzzzzzzzzzzzzzzzzzzzzzzzzz-order67.conf
frontend_conf=$dropins/corpsite-hire-prep-frontend.service.d/zzzzzzzzzzzzzzzzzzzzzzzzzzzzzz-order67.conf

test -s "$backend/release-manifest.json"
test -s "$frontend/release-manifest.json"
test -s "$frontend/.next/BUILD_ID"
test "$(systemctl show corpsite-hire-prep-backend -p WorkingDirectory --value)" = "$root/releases/$previous-backend"
test "$(systemctl show corpsite-hire-prep-frontend -p WorkingDirectory --value)" = "$root/releases/$previous-frontend"
if [[ $variant == test-base ]]; then
  test ! -e "$backend_conf"
  test ! -e "$frontend_conf"
fi

rollback() {
  if [[ $variant == prod-base ]]; then
    sudo install -m 0644 /tmp/order67-test-backend.previous.conf "$backend_conf"
    sudo install -m 0644 /tmp/order67-test-frontend.previous.conf "$frontend_conf"
  else
    sudo rm -f -- "$backend_conf" "$frontend_conf"
  fi
  sudo systemctl daemon-reload
  sudo systemctl restart corpsite-hire-prep-backend corpsite-hire-prep-frontend
}
trap rollback ERR

if [[ $variant == prod-base ]]; then
  cp "$backend_conf" /tmp/order67-test-backend.previous.conf
  cp "$frontend_conf" /tmp/order67-test-frontend.previous.conf
fi

cat > /tmp/order67-test-backend.conf <<EOF
[Service]
WorkingDirectory=$backend
Environment=PYTHONDONTWRITEBYTECODE=1
ExecStart=
ExecStart=$backend/.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8003
EOF
cat > /tmp/order67-test-frontend.conf <<EOF
[Service]
WorkingDirectory=$frontend
EnvironmentFile=
EnvironmentFile=$root/releases/20261125-card-hire-catalog/frontend-test.env
Environment=CORPSITE_UI_DIR=$frontend
Environment=NEXT_DEPLOYMENT_ID=order67-${sha:0:12}
ExecStartPre=
ExecStartPre=/usr/bin/test -s $frontend/.next/BUILD_ID
ExecStart=
ExecStart=/usr/bin/node $frontend/node_modules/next/dist/bin/next start --hostname 127.0.0.1 --port 3003
EOF
sudo install -m 0644 /tmp/order67-test-backend.conf "$backend_conf"
sudo install -m 0644 /tmp/order67-test-frontend.conf "$frontend_conf"
sudo systemctl daemon-reload
sudo systemctl restart corpsite-hire-prep-backend corpsite-hire-prep-frontend
test "$(systemctl show corpsite-hire-prep-backend -p WorkingDirectory --value)" = "$backend"
test "$(systemctl show corpsite-hire-prep-frontend -p WorkingDirectory --value)" = "$frontend"
systemctl is-active --quiet corpsite-hire-prep-backend
systemctl is-active --quiet corpsite-hire-prep-frontend
for attempt in $(seq 1 30); do
  if curl -fsS http://127.0.0.1:8003/health >/dev/null 2>&1 &&
     curl -fsS http://127.0.0.1:3003/ >/dev/null 2>&1; then
    break
  fi
  sleep 1
done
curl -fsS http://127.0.0.1:8003/health >/dev/null
curl -fsS http://127.0.0.1:3003/ >/dev/null
trap - ERR
printf 'ACTIVE_BACKEND=%s\nACTIVE_FRONTEND=%s\nBUILD_ID=%s\n' "$backend" "$frontend" "$(cat "$frontend/.next/BUILD_ID")"
