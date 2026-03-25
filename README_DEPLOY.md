# Corpsite Deployment Notes

This project is developed locally and deployed into a closed corporate environment.
Use one repeatable deployment flow for every update.

## Environment policy

- Local development:
  - `APP_ENV=dev`
  - `NEXT_PUBLIC_APP_ENV=dev`
  - `ENABLE_DIRECTORY_DEBUG=1`
  - `ENABLE_LEGACY_X_USER_ID=1`
- Server / production:
  - `APP_ENV=prod`
  - `NEXT_PUBLIC_APP_ENV=prod`
  - `ENABLE_DIRECTORY_DEBUG=0`
  - `ENABLE_LEGACY_X_USER_ID=0`
  - `AUTH_JWT_SECRET` must be set to a non-default value
  - `INTERNAL_API_TOKEN` must be set if the bot still calls per-user internal endpoints

`ENABLE_LEGACY_X_USER_ID=1` can be used temporarily during migration if an internal helper still sends `X-User-Id` without a service token.
Treat it as a compatibility flag, not as the target production setup.

Recommended production setup for the Telegram bot:

- bot sends `X-User-Id`
- bot also sends `X-Internal-Api-Token`
- backend validates the internal token before trusting the user id
- use `corpsite-bot/.env.example` as the starting point for bot configuration

## Before every deployment

1. Back up the database.
2. Save the current server `.env`.
3. Review what changed:
   - backend code
   - frontend code
   - database migrations
4. Confirm production env values:
   - `APP_ENV=prod`
   - `NEXT_PUBLIC_APP_ENV=prod`
   - `AUTH_JWT_SECRET` is not default
   - `INTERNAL_API_TOKEN` matches between backend and bot
   - debug/dev flags are disabled unless explicitly needed

## Deployment order

1. Stop application services if needed.
2. Copy updated project files to the server.
3. Apply DB migrations before starting the new backend version.
4. Update backend dependencies if they changed.
5. Build/update the frontend.
6. Start backend and frontend services.
7. Run the smoke check below.

## Smoke check after deployment

1. `GET /health` returns `{"status":"ok"}`.
2. Login works for a real test user.
3. The tasks page opens successfully.
4. A pilot user can see their tasks.
5. A privileged user can open the periods screen.
6. A test task can move through the expected status flow.
7. No debug UI is visible in production.

PowerShell helper:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\smoke_check.ps1 `
  -BaseUrl "http://127.0.0.1:8000" `
  -Login "test_user_login" `
  -Password "test_user_password"
```

If login/password are omitted, the script checks only `/health`.

## Pilot update checklist

For the first pilot in one department:

1. Update only what is needed for the pilot workflow.
2. Avoid schema changes unless necessary.
3. Keep one test user per role.
4. Record each release in a short log:
   - date
   - what changed
   - what to verify
   - rollback note

Operational checklist for the first live week:

- see `docs/PILOT_WEEK1_CHECKLIST.md`

## Rollback minimum

If an update fails:

1. Restore the previous backend/frontend build.
2. Restore the previous `.env` if it was changed.
3. Restore the database from backup if the issue is caused by a migration or bad data update.
