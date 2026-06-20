# ADR-042 Phase C1 — Sysadmin Cabinet UI

## Статус

**Implemented** (2026-06-20)

## Связанные документы

- [ADR-042 Phase C1.1 — UI Polish + Reference Endpoints](./ADR-042-phase-c1-1-polish.md)
- [ADR-042 Phase B4 — Admin API](./ADR-042-phase-b4-admin-api.md)
- [ADR-042 Phase B5 — Auth Policy](./ADR-042-phase-b5-auth-policy.md)

---

## Scope Phase C1

React UI кабинета системного администратора поверх B4 REST API.

| In scope | Out of scope |
|----------|--------------|
| `/admin/system` + 5 вкладок | Backend enforcement changes |
| Typed API client | `access_grants_enforced` rollout |
| Admin-only nav (role_id=2) | Password reset UI |
| Manual smoke checklist | Task/sidebar RBAC changes |

---

## UI routes

| Route | Title |
|-------|-------|
| `/admin/system` | Кабинет системного администратора |

**Navigation:** `components/AppShell.tsx` → `PRIMARY_ADMIN_NAV` (visible when `role_id === 2`).

Non-admin users are redirected from `/admin/*` to `/tasks` by existing `AppShell` logic.

---

## Tabs

| Tab | Component | Backend endpoints |
|-----|-----------|-------------------|
| Пользователи | `UsersTab.tsx` | `GET/POST /admin/users/*` |
| Доступы | `AccessTab.tsx` | `/admin/access/*` |
| Enrollment | `EnrollmentTab.tsx` | `/admin/enrollment/*` |
| Назначения | `AssignmentsTab.tsx` | `/admin/assignments/*` |
| Аудит безопасности | `AuditTab.tsx` | `GET /admin/security-audit` |

### Users

- Table with search/filter
- Status: active / locked / must_change_password
- Actions: lock, unlock, force-password-change
- Password never displayed; reset not implemented (501 → “будет реализовано позже”)

### Access

- Grants list (active; optional revoked in gray)
- Grant create form with role dropdown from `GET /admin/access/roles` (C1.1), target search, scope, reason
- Effective access per user with expandable explanation
- Notice: enforcement disabled by default

### Enrollment

- Queue with status filter
- Detect candidates (dry_run toggle)
- Approve / reject / apply (apply only for APPROVED)
- Warning: employee created only on apply

### Assignments

- Drift table with diff preview
- Reconcile dry_run by default; apply with confirm dialog
- Drift count displayed

### Security audit

- Filtered table, newest first
- Expandable metadata
- Highlight key event types
- Warning if sensitive keys detected in metadata

---

## Frontend files

```
corpsite-ui/app/admin/system/
  page.tsx
  _lib/
    adminSystemApi.client.ts
    adminSystemLabels.ts
    adminSystemLabels.test.ts
  _components/
    SystemAdminClient.tsx
    shared/ErrorBanner.tsx, ConfirmDialog.tsx
    tabs/UsersTab.tsx, AccessTab.tsx, ...
```

**API client:** uses `apiFetchJson` from `lib/api.ts` + `resolveApiUrl` (no localhost hardcode).

---

## Known limitations

1. **Role picker** uses `GET /admin/access/roles` (implemented in [C1.1](./ADR-042-phase-c1-1-polish.md)).
2. **Privileged check** — sysadmin nav uses `is_privileged` from `/auth/me` (C1.1); full admin sidebar remains `role_id=2` only.
3. **Password change** endpoint returns 501 — UI shows future message.
4. **Enrollment explanation** — full `explain_candidate` not exposed via B4 API; card shows queue fields only.
5. **Enforcement** — UI disclaimer only; no sidebar/task gating.

---

## Frontend tests

```bash
cd corpsite-ui
npm test -- app/admin/system/_lib/adminSystemLabels.test.ts
```

---

## Manual smoke checklist

Prerequisites: backend running, B2 migrations applied, admin user (`role_id=2`) logged in.

1. [ ] Open `/admin/system` as admin — page loads with 5 tabs
2. [ ] Non-admin — no sidebar link; direct URL redirects to `/tasks`
3. [ ] **Users** — table loads; search works
4. [ ] Lock / unlock user — status updates; audit event created
5. [ ] **Access** — create grant; revoke grant; effective access explanation shows
6. [ ] **Enrollment** — detect (dry_run) does not create employees; approve/reject/apply flow
7. [ ] **Assignments** — drift list shows rows (~70 on dev DB); dry_run reconcile; apply requires confirm
8. [ ] **Audit** — events listed newest first; filters work; metadata expands
9. [ ] Existing pages (`/tasks`, `/directory`, `/admin/sync`) still work

---

## Deferred to C2+

- Admin password reset UI
- Self-service password change form
- Shadow/enforced guard mode indicators in UI
- Full enrollment candidate explanation panel
