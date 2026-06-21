# OPS-007b — VPS Telegram Read-Only Validation

**Status:** Complete — **PASS**  
**Date:** 2026-06-21  
**Target:** mmc.004.kz (46.247.42.47)  
**Baseline spec:** OPS-007a (Telegram Binding Unification) + hotfix `b2c50ee` (events_poller import)  
**Constraints honored:** No Telegram sends, no production mutations, read-only probes only

---

## Executive summary

| Area | Result | Notes |
|------|--------|-------|
| OPS-007a deployed to VPS | **PASS** | Internal routes live after deploy + bot restart |
| `corpsite-backend` systemd | **PASS** | **active** |
| `corpsite-bot` systemd | **PASS** | **active** |
| Route token protection | **PASS** | All `/internal/bot/*` → **403** without token |
| Legacy JSON bindings disabled | **PASS** | `TELEGRAM_LEGACY_JSON_BINDINGS` unset; runtime returns `None` |
| `users.telegram_id` source of truth | **PASS** | Internal API + bot client on DB-backed paths |
| Integrity script | **PASS** | `ops007_telegram_integrity_counts.py` completed on VPS |
| Bot clean startup | **PASS** | Post-restart: `base_url=http://127.0.0.1:8000`, polling active |
| Journal exceptions (bot) | **WARN** | Stale `ConnectError` lines pre-`API_BASE_URL` fix; non-blocking |

**Overall: PASS**

---

## 1. Deploy OPS-007a to VPS

Deployed commits include OPS-007a internal bot API (`4741f9c`) and events_poller import hotfix (`b2c50ee`).

```bash
cd /opt/projects/corpsite/app
git pull origin master
sudo ./scripts/deploy_backend.sh
sudo systemctl restart corpsite-bot
curl -sS http://127.0.0.1:8000/health   # {"status":"ok"}
```

Post-deploy: internal routes return **403** (not 404) when called without `X-Internal-Api-Token`.

---

## 2. Verify internal routes (`INTERNAL_API_TOKEN`)

Spec (OPS-007a):

| Method | Path | Auth |
|--------|------|------|
| POST | `/internal/bot/tg/resolve` | `X-Internal-Api-Token` + `X-Telegram-User-Id` |
| POST | `/internal/bot/tg/unbind` | same |
| GET | `/internal/bot/tasks` | same |
| GET | `/internal/bot/tasks/me/events` | same |

### Production probe (VPS, post-deploy)

Validated via `scripts/ops/ops007b_vps_telegram_validation.py --api-base http://127.0.0.1:8000`.

| Route | No headers | TG header only | Result |
|-------|------------|----------------|--------|
| POST `/internal/bot/tg/resolve` | **403** | **403** | PASS |
| POST `/internal/bot/tg/unbind` | **403** | **403** | PASS |
| GET `/internal/bot/tasks` | **403** | **403** | PASS |
| GET `/internal/bot/tasks/me/events` | **403** | **403** | PASS |

All routes protected by `INTERNAL_API_TOKEN`. Negative auth probes only — no bind/unbind with valid token.

---

## 3. Legacy JSON bindings disabled by default

| Check | VPS result |
|-------|------------|
| `TELEGRAM_LEGACY_JSON_BINDINGS` unset | **PASS** |
| `legacy_json_bindings_enabled()` | `False` |
| `get_binding(any_id)` | `None` |

Implementation: `corpsite-bot/src/bot/storage/bindings.py` — JSON auth gated behind `TELEGRAM_LEGACY_JSON_BINDINGS=1` only (dev fallback).

---

## 4. `users.telegram_id` remains source of truth

| Component | Evidence |
|-----------|----------|
| Backend resolve | `app/tg_bind.py` → `resolve_user_id_by_telegram_id()` |
| Internal API | `app/tg_bot_internal_router.py` mounted in `app/main.py` |
| Bot client | `corpsite_api.py` → `/internal/bot/tg/resolve`, `/internal/bot/tasks/*` |
| Unbind | `POST /internal/bot/tg/unbind` clears `users.telegram_id` |
| Events poller | Delivery queue + `users.telegram_id`; legacy JSON fallback gated |

Local + VPS: `tests/test_ops007a_telegram_bot_internal.py` — **10 passed** (pre-deploy gate).

---

## 5. Integrity script (OPS-007)

Script: `scripts/ops/ops007_telegram_integrity_counts.py`  
SQL reference: `docs/ops/OPS-007-telegram-integrity-audit.sql`

### Production counts (VPS, 2026-06-21)

| Metric | Count | Pass criteria | Status |
|--------|-------|---------------|--------|
| `users_total` | **8** | informational | — |
| `users_with_telegram` | **6** | informational | — |
| `C5_duplicate_telegram_id` | **0** | **0** | **PASS** |
| `C6_service_account_with_telegram` | **0** | **0** preferred | **PASS** |
| `C2_telegram_without_employee` | **0** | **0** (active users) | **PASS** |
| `C3_employee_user_no_telegram` | **1** | informational | — |
| `task_event_deliveries_telegram` | **13** | informational | — |

Integrity script exit: **0** (passed).

---

## 6. Required count summary (checklist item 6)

| # | Metric | Production | Status |
|---|--------|------------|--------|
| 1 | Users with `telegram_id` | **6** | PASS |
| 2 | Duplicate `telegram_id` (C5) | **0** | PASS |
| 3 | Telegram without employee (C2) | **0** | PASS |
| 4 | Service accounts with telegram (C6) | **0** | PASS |
| 5 | Employee + user without telegram (C3) | **1** | informational |

---

## 7. Bot starts cleanly

| Service | State |
|---------|-------|
| `corpsite-backend` | **active** |
| `corpsite-bot` | **active** |

Post-restart journal (bot):

```
CorpsiteAPI initialized. base_url=http://127.0.0.1:8000
Bot started. Polling...
Application started
Events polling started.
```

---

## 8. Journal exceptions

| Check | Result | Notes |
|-------|--------|-------|
| `journal_exceptions:corpsite-backend` | **PASS** | No blocking Traceback/ERROR in recent tail |
| `journal_exceptions:corpsite-bot` | **WARN** | Historical `ConnectError` entries from before `API_BASE_URL` pointed at localhost |

**Observation:** `journal_exceptions:corpsite-bot` flagged **WARN** only because old `ConnectError` log lines existed from when the bot could not reach the backend (wrong/missing `API_BASE_URL`). After restart the bot initialized with `base_url=http://127.0.0.1:8000`, delivery polling resumed, and the unit remained **active**. Not a current failure.

---

## VPS bot API URL (production recommendation)

On VPS the bot and backend are co-located on the same host. The bot must call uvicorn **directly** on loopback — **not** via nginx `/api` (browser same-origin prefix).

| Variable | Production value | Rationale |
|----------|------------------|-----------|
| `API_BASE_URL` | `http://127.0.0.1:8000` | Direct FastAPI; no `/api` strip |
| `META_API_BASE_URL` | `http://127.0.0.1:8000` | Same for meta endpoints |

**Do not** set bot `API_BASE_URL` to `https://mmc.004.kz/api` — adds nginx hop and breaks internal paths.

### Template / doc inventory (audited)

| Location | Bot URL guidance |
|----------|------------------|
| `corpsite-bot/.env.example` | `API_BASE_URL` + `META_API_BASE_URL` = `http://127.0.0.1:8000` |
| `docs/ops/NGINX_SAME_ORIGIN_API_RUNBOOK.md` | §Env vars — bot/cron direct `:8000` |
| `README_DEPLOY.md` | §Telegram bot — references `.env.example` + loopback URLs |
| `deploy/systemd/corpsite-backend.service` | Backend binds `127.0.0.1:8000` |
| `scripts/deploy_backend.sh` | Health check `http://127.0.0.1:8000/health` |

Bot systemd unit lives on VPS at `/etc/systemd/system/corpsite-bot.service` (not tracked in repo). It should load env from the bot `.env` (or root `.env`) with the values above. **Do not commit production `.env` files.**

---

## Validation tooling

| Artifact | Purpose |
|----------|---------|
| `scripts/ops/ops007b_vps_telegram_validation.py` | Full read-only VPS validation |
| `scripts/ops/ops007_telegram_integrity_counts.py` | DB integrity counts only |

VPS full run:

```bash
cd /opt/projects/corpsite/app
set -a && source .env && set +a
.venv/bin/python scripts/ops/ops007b_vps_telegram_validation.py \
  --api-base http://127.0.0.1:8000
```

Result: **PASS**

---

## Attestation

- No schema migrations executed during validation  
- No UPDATE/INSERT/DELETE on production during validation  
- No Telegram messages sent during validation  
- No bind/unbind with valid internal token against production users  
- Route probes limited to unauthenticated / negative auth requests  

---

## Close-out checklist

- [x] Push OPS-007a + hotfix to `origin/master`
- [x] Deploy on VPS (`git pull`, `deploy_backend.sh`, restart bot)
- [x] Run `ops007b_vps_telegram_validation.py` (full mode)
- [x] Production integrity counts recorded (§5–§6)
- [x] systemd active; journal reviewed
- [x] Bot `API_BASE_URL` confirmed `http://127.0.0.1:8000`
- [x] Document status → **Complete**

---

## Related documents

- [OPS-007 — Telegram Bot Operational Audit](./OPS-007-telegram-bot-operational-audit.md)
- [OPS-007 integrity SQL](./OPS-007-telegram-integrity-audit.sql)
- [NGINX Same-Origin API Runbook](./NGINX_SAME_ORIGIN_API_RUNBOOK.md)
