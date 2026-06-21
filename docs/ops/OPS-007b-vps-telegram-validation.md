# OPS-007b — VPS Telegram Read-Only Validation

**Status:** Partial — deploy blocked; post-deploy checks pending  
**Date:** 2026-06-21  
**Target:** mmc.004.kz (46.247.42.47)  
**Baseline spec:** OPS-007a (Telegram Binding Unification)  
**Constraints honored:** No Telegram sends, no production mutations, read-only probes only

---

## Executive summary

| Area | Result | Notes |
|------|--------|-------|
| OPS-007a deployed to VPS | **BLOCKED** | Production returns **404** on all `/internal/bot/*` routes; code not yet on VPS |
| SSH access to VPS | **BLOCKED** | `Permission denied (publickey)` from audit environment |
| Route token protection | **NOT VERIFIED (prod)** | Routes absent until deploy |
| Legacy JSON bindings disabled | **PASS (code)** | Verified on local checkout |
| `users.telegram_id` source of truth | **PASS (code)** | Bot client + internal router present locally |
| Integrity counts (production DB) | **PENDING** | Requires VPS DB session |
| Bot clean startup | **PENDING** | Requires SSH + `journalctl` |
| Local OPS-007a tests | **PASS** | 10/10 pytest |

**Overall:** OPS-007b cannot be closed until OPS-007a is deployed on VPS and full validation script is run on-server.

---

## 1. Deploy OPS-007a to VPS

### Attempted

- Remote API probe: `GET https://mmc.004.kz/api/internal/bot/tasks` → **404 Not Found**
- Same for `/internal/bot/tg/resolve`, `/internal/bot/tg/unbind`, `/internal/bot/tasks/me/events`
- Confirms **OPS-007a backend router is not live** on production (VPS git HEAD expected: `7413d49` or earlier — no `tg_bot_internal_router.py`)

### SSH deploy (blocked)

```
ssh corpsite   # Host 46.247.42.47, User ubuntu, IdentityFile ~/.ssh/id_ed25519
→ Permission denied (publickey,password)
```

### Required operator steps (when SSH restored)

```bash
cd /opt/projects/corpsite/app
git pull origin master   # must include OPS-007a commit
sudo ./scripts/deploy_backend.sh
sudo systemctl restart corpsite-bot

# Verify backend health
curl -sS http://127.0.0.1:8000/health
```

**Expected after deploy:** internal routes return **403** (not 404) when called without `X-Internal-Api-Token`.

---

## 2. Verify internal routes (`INTERNAL_API_TOKEN`)

Spec (OPS-007a):

| Method | Path | Auth |
|--------|------|------|
| POST | `/internal/bot/tg/resolve` | `X-Internal-Api-Token` + `X-Telegram-User-Id` |
| POST | `/internal/bot/tg/unbind` | same |
| GET | `/internal/bot/tasks` | same |
| GET | `/internal/bot/tasks/me/events` | same |

### Production probe (pre-deploy, 2026-06-21)

| Route | No headers | TG header only |
|-------|------------|----------------|
| POST `/api/internal/bot/tg/resolve` | **404** | **404** |
| POST `/api/internal/bot/tg/unbind` | **404** | **404** |
| GET `/api/internal/bot/tasks` | **404** | **404** |
| GET `/api/internal/bot/tasks/me/events` | **404** | **404** |

Reference endpoints (already deployed, pre-007a):

| Route | No headers | Notes |
|-------|------------|-------|
| POST `/api/auth/self-bind` | **400** | Requires `X-Telegram-User-Id` |
| GET `/api/health` | **200** | `{"status":"ok"}` |

### Post-deploy acceptance (run on VPS)

```bash
set -a && source /opt/projects/corpsite/app/.env && set +a
cd /opt/projects/corpsite/app
.venv/bin/python scripts/ops/ops007b_vps_telegram_validation.py \
  --api-base http://127.0.0.1:8000
```

Expected: all `route_token_guard:*` checks **pass** with HTTP **403** (invalid/missing token).  
Do **not** call resolve/unbind with a valid token against real bound users unless intentional — use negative tests only for read-only validation.

---

## 3. Legacy JSON bindings disabled by default

Verified on **local OPS-007a checkout** (matches intended VPS behavior after deploy):

| Check | Result |
|-------|--------|
| `TELEGRAM_LEGACY_JSON_BINDINGS` unset | PASS |
| `legacy_json_bindings_enabled()` | `False` |
| `get_binding(any_id)` | `None` |

Implementation: `corpsite-bot/src/bot/storage/bindings.py` — JSON auth gated behind `TELEGRAM_LEGACY_JSON_BINDINGS=1` only.

**VPS env check (pending SSH):**

```bash
grep TELEGRAM_LEGACY_JSON_BINDINGS /opt/projects/corpsite/app/.env /opt/projects/corpsite/app/corpsite-bot/.env 2>/dev/null || true
# Expected: unset or empty
```

---

## 4. `users.telegram_id` remains source of truth

Verified on **local checkout**:

| Component | Evidence |
|-----------|----------|
| Backend resolve | `app/tg_bind.py` → `resolve_user_id_by_telegram_id()` |
| Internal API | `app/tg_bot_internal_router.py` mounted in `app/main.py` |
| Bot client | `corpsite_api.py` calls `/internal/bot/tg/resolve`, `/internal/bot/tasks/*` |
| Unbind | `POST /internal/bot/tg/unbind` clears `users.telegram_id` (not local JSON) |
| Events poller | Uses delivery queue + `users.telegram_id` (legacy JSON fallback gated) |

Local tests confirming DB-backed resolve/unbind: `tests/test_ops007a_telegram_bot_internal.py` — **10 passed**.

---

## 5. Integrity script (OPS-007)

Script: `scripts/ops/ops007_telegram_integrity_counts.py`  
SQL reference: `docs/ops/OPS-007-telegram-integrity-audit.sql`

### Production counts

**Not executed** — requires VPS shell with `.env` / DB connectivity.

Operator command:

```bash
cd /opt/projects/corpsite/app
set -a && source .env && set +a
.venv/bin/python scripts/ops/ops007_telegram_integrity_counts.py
```

Paste output into the table below to close OPS-007b:

| Metric | Production count | Pass criteria |
|--------|------------------|---------------|
| `users_with_telegram` | _pending_ | informational |
| `C5_duplicate_telegram_id` | _pending_ | **0** |
| `C2_telegram_without_employee` | _pending_ | **0** (active users) |
| `C6_service_account_with_telegram` | _pending_ | **0** preferred |
| `users_total` | _pending_ | informational |
| `tg_bindings_legacy_rows` | _pending_ | informational |
| `C8_tg_bindings_drift` | _pending_ | **0** |

---

## 6. Required count summary (checklist item 6)

| # | Metric | Production | Status |
|---|--------|------------|--------|
| 1 | Users with `telegram_id` | _pending_ | PENDING |
| 2 | Duplicate `telegram_id` (C5) | _pending_ | PENDING |
| 3 | Telegram without employee (C2) | _pending_ | PENDING |
| 4 | Service accounts with telegram (C6) | _pending_ | PENDING |

---

## 7. Bot starts cleanly

**Not verified** — SSH required.

```bash
systemctl status corpsite-bot --no-pager -l
systemctl is-active corpsite-backend corpsite-bot
```

Expected: both **active**.

---

## 8. No startup exceptions

**Not verified** — SSH required.

```bash
journalctl -u corpsite-bot -n 80 --no-pager -o cat
journalctl -u corpsite-backend -n 80 --no-pager -o cat | grep -iE 'traceback|error|exception' || true
```

The automated script flags recent Traceback/ERROR lines in journal tail.

---

## Validation tooling

| Artifact | Purpose |
|----------|---------|
| `scripts/ops/ops007b_vps_telegram_validation.py` | Full read-only VPS validation (routes, legacy JSON, integrity, systemd) |
| `scripts/ops/ops007_telegram_integrity_counts.py` | DB integrity counts only |

Remote-only probe (no SSH, no DB — used for this report):

```bash
python scripts/ops/ops007b_vps_telegram_validation.py \
  --api-base https://mmc.004.kz/api --skip-db --skip-systemd
```

Result: **FAIL** — all internal routes **404** (pre-deploy).

---

## Local pre-flight (audit environment)

| Check | Result |
|-------|--------|
| `pytest tests/test_ops007a_telegram_bot_internal.py` | **10 passed** |
| Legacy JSON disabled | **PASS** |
| Internal router + bot client paths | **PASS** |
| Production `/api/health` | **200** |
| Production internal routes | **404** (not deployed) |

---

## Attestation

- No schema migrations executed on production  
- No UPDATE/INSERT/DELETE on production  
- No Telegram messages sent  
- No bind/unbind with valid internal token against production  
- Remote probes limited to unauthenticated / negative auth requests  

---

## Close-out checklist

- [ ] Push OPS-007a to `origin/master`
- [ ] Restore SSH (`ubuntu@46.247.42.47` / `ssh corpsite`)
- [ ] `git pull` + `deploy_backend.sh` + restart `corpsite-bot`
- [ ] Run `ops007b_vps_telegram_validation.py` on VPS (full mode)
- [ ] Paste production integrity counts into §5–§6
- [ ] Confirm systemd active + clean journal
- [ ] Update this document status to **Complete**

---

## Related documents

- [OPS-007 — Telegram Bot Operational Audit](./OPS-007-telegram-bot-operational-audit.md)
- [OPS-007 integrity SQL](./OPS-007-telegram-integrity-audit.sql)
