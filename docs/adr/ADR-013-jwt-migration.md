# ADR-013: Migration from X-User-Id to JWT Authentication

## Status
In Progress

## Date
2026-02-14

## Context

Currently the system supports two authentication mechanisms:

1. Legacy header-based authentication via `X-User-Id`
2. JWT-based authentication via `Authorization: Bearer <token>`

The project has already partially migrated:

- UI uses JWT (login + sessionStorage access_token).
- Backend still supports `X-User-Id` in directory and other modules.
- Telegram bot currently works via header-based or implicit user binding.
- RBAC logic depends on user_id and role_id loaded from DB.

This dual model increases:

- Cognitive complexity
- Risk of inconsistent authorization
- Risk of security regression
- Maintenance overhead

Primary architectural principle: **long-term stability, clarity, and maintainability.**

Therefore, the system must move to a single authentication model: **JWT-only.**

---

## Decision

We will:

1. Make JWT the single source of authentication.
2. Remove `X-User-Id` usage from:
   - UI
   - Backend routers
   - Bot integration
3. Introduce service JWT login for the Telegram bot.
4. Keep a short dual-stack transition window.
5. Fully remove legacy header logic after verification.

Final state:

- Every request is authenticated via JWT.
- Backend extracts user from JWT dependency (`get_current_user`).
- No endpoint reads `X-User-Id`.
- No frontend passes devUserId.
- Bot authenticates via service account login.

---

## Migration Plan (Step-by-Step, No-Break Strategy)

### Phase 1 — Backend Adapter Layer

Goal: introduce unified user extraction without breaking current endpoints.

1. Create unified request user dependency:
   - Prefer JWT (`get_current_user`)
   - Temporarily fallback to `X-User-Id` (for transition only)

2. Replace direct calls to:
   - `require_user_id`
   - manual header extraction

   with unified adapter.

3. Ensure all endpoints function in dual mode.

Acceptance:
- All existing flows still work.
- JWT requests function identically to header requests.

---

### Phase 2 — UI JWT Hardening

Goal: remove any legacy dev mode behavior.

1. Remove all devUserId usage.
2. Remove any `X-User-Id` header logic.
3. Ensure:
   - Login works
   - /auth/me works
   - All task endpoints function via JWT only.

Acceptance:
- UI works with JWT.
- Removing header fallback does not break UI.

---

### Phase 3 — Telegram Bot JWT Service Login

Goal: move bot to service authentication model.

Design:

- Create dedicated service user in DB (e.g., role: SYSTEM_BOT).
- Bot performs `/auth/login` at startup.
- Bot stores JWT in memory.
- Bot refreshes token on 401.

Complexity level: Low to Moderate.

Operational impact:
- Slight increase in initialization logic.
- No runtime complexity increase.

Benefits:
- Unified security model.
- No privileged header bypass.
- Clear audit trail.

Acceptance:
- Bot successfully polls events using JWT.
- Bot handles 401 by re-login.

---

### Phase 4 — Remove X-User-Id Fallback

After:

- UI fully JWT
- Bot fully JWT
- All endpoints validated

We:

1. Remove:
   - `require_user_id`
   - `X-User-Id` headers
   - Fallback code
2. Simplify RBAC entrypoints.
3. Clean environment variables related to legacy auth.

Acceptance:
- No code references `X-User-Id`.
- All tests pass.
- All flows verified.

---

## Risks

1. RBAC regression (directory scope).
2. Incorrect user context resolution.
3. Bot delivery interruption.
4. Forgotten fallback usage in edge endpoint.

Mitigation:

- Use `_debug/rbac` endpoint before removal.
- Perform end-to-end test: report → approve → reject → archive.
- Test bot event delivery before header removal.

---

## Acceptance Criteria (Final State)

- UI uses JWT only.
- Bot uses JWT service login.
- Backend does not read `X-User-Id`.
- No dual authentication paths.
- RBAC operates solely from JWT-derived user context.
- Codebase simplified.

---

## Consequences

### Positive

- Single authentication model.
- Cleaner security boundary.
- Lower maintenance cost.
- Production-grade architecture.
- Reduced cognitive load.

### Negative

- Slightly more complex bot startup.
- Requires careful phased migration.

---

## Long-Term Principle

Security model must be:

- Explicit
- Single-source
- Stateless
- JWT-based
- RBAC-driven

No hidden header-based overrides.

---

## Next Action

Begin Phase 1 (Backend adapter layer).
