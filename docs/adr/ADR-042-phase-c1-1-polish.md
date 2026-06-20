# ADR-042 Phase C1.1 — Sysadmin UI Polish + Reference Endpoints

## Статус

**Implemented** (2026-06-20)

## Связанные документы

- [ADR-042 Phase C1 — Sysadmin UI](./ADR-042-phase-c1-sysadmin-ui.md)
- [ADR-042 Phase B4 — Admin API](./ADR-042-phase-b4-admin-api.md)
- [ADR-042 Phase B5 — Auth Policy](./ADR-042-phase-b5-auth-policy.md)

---

## Backend — new read-only endpoints

All protected by `require_sysadmin_api` (no audit on search).

| Method | Path | Description |
|--------|------|-------------|
| GET | `/admin/access/roles` | List `access_roles` (id, code, label, level_rank, …) |
| GET | `/admin/access/targets/search` | Unified target picker search |
| GET | `/admin/access/guard-mode` | Current `ADR042_ADMIN_GUARD_MODE` + UX message |

### GET `/admin/access/targets/search`

Query: `target_type`, `q`, `limit`

Returns items: `{ target_type, target_id, label, subtitle, metadata }`

Supported types: `USER`, `EMPLOYEE`, `PERSON`, `ASSIGNMENT`, `POSITION`, `ORG_UNIT`

### GET `/auth/me` extension

Added read-only flags (no enforcement):

- `is_privileged` — backend `is_privileged()` (role_id=2 or env allowlist)
- `is_system_admin` — role_id === 2

---

## Frontend UX changes

### Access tab (Доступы)

- Role **dropdown** from `/admin/access/roles` (labels: ADMIN, MANAGER, OBSERVER, SYSADMIN_CABINET, …)
- Target **search/select** via `/admin/access/targets/search`
- Scope org unit search when `scope_type=ORG_UNIT`
- Warnings:
  - ACCESS_NONE: does not block when enforcement off
  - Shadow / enforced guard mode banners from `/admin/access/guard-mode`

### Sidebar visibility

| User | `/admin/system` nav | Full admin sidebar (directory, sync, …) |
|------|---------------------|----------------------------------------|
| role_id=2 | Yes | Yes |
| env privileged (`is_privileged`) | Yes | No |
| SYSADMIN_CABINET grant only | **No until C2** | No |
| Regular user | No | No |

Helpers: `corpsite-ui/lib/adminNav.ts`

**Limitation:** env allowlist is evaluated on server; frontend uses `/auth/me.is_privileged`.

---

## Files

| Area | Path |
|------|------|
| Service | `app/services/admin_reference_service.py` |
| Router | `app/api/admin_router.py` |
| Auth | `app/auth.py` (`is_privileged` on `/auth/me`) |
| API client | `corpsite-ui/app/admin/system/_lib/adminSystemApi.client.ts` |
| Target search UI | `corpsite-ui/app/admin/system/_components/shared/TargetSearchField.tsx` |
| Nav helpers | `corpsite-ui/lib/adminNav.ts` |

---

## Tests

Backend:

```bash
pytest tests/test_adr042_phase_c1_1_admin_reference.py -v
```

Frontend:

```bash
cd corpsite-ui
npm test -- app/admin/system/_lib/adminSystemApi.client.test.ts lib/adminNav.test.ts
```

---

## Known limitations

1. SYSADMIN_CABINET grant does not show sidebar until C2.
2. Target search returns first N matches; no pagination UI yet.
3. `access_role_id` still sent to API internally — user never types it.
4. Enforcement remains off by default.

---

## VPS smoke checklist

### Backend deploy

```bash
cd /path/to/09-Corpsite
git pull
alembic current
alembic heads
alembic upgrade head
# restart API (systemd/docker — per your setup)
sudo systemctl restart corpsite-api   # example
curl -s -H "Authorization: Bearer $TOKEN" https://your-host/admin/access/roles | head
curl -s -H "Authorization: Bearer $TOKEN" "https://your-host/admin/access/guard-mode"
curl -s -H "Authorization: Bearer $TOKEN" "https://your-host/admin/access/targets/search?target_type=USER&q=&limit=5"
```

### Frontend deploy

```bash
cd corpsite-ui
npm install    # if package.json changed
npm run build  # or: npx tsc --noEmit
# restart Next (pm2/systemd — per your setup)
pm2 restart corpsite-ui   # example
```

### UI verification

1. [ ] Login as admin (role_id=2) → sidebar shows «Кабинет системного администратора»
2. [ ] `/admin/system` → Access tab → roles dropdown populated
3. [ ] Search USER/PERSON target → select → create grant
4. [ ] Effective access explanation updates for user
5. [ ] Security audit shows `ACCESS_GRANTED`
6. [ ] Users / Enrollment / Assignments / Audit tabs still work
7. [ ] Non-admin cannot open `/admin/system` (403 or redirect)
8. [ ] Reconcile dry_run still read-only by default

---

## Deferred to C2

- Sidebar visibility via SYSADMIN_CABINET grant
- Password reset UI
- Full access enforcement in UI
