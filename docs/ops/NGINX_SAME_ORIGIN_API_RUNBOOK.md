# Same-Origin API Routing — `/api` Prefix

**Problem:** Frontend UI and FastAPI both use `/directory/*`. Nginx cannot split path prefixes reliably when both live under the same host path.

**Solution (Option A):** Browser calls same-origin `/api/...`; nginx strips `/api` and proxies to FastAPI. Backend routes stay unchanged.

| Request (browser) | Nginx → FastAPI |
|-------------------|-----------------|
| `GET /directory/personnel` | Next.js (UI page) |
| `GET /api/directory/employees` | `GET /directory/employees` |
| `POST /api/auth/login` | `POST /auth/login` |

---

## Architecture

```
Browser
  ├─ /directory/*           → Next.js :3000
  └─ /api/*                 → nginx strip → FastAPI :8000/*
```

**Dev (split ports):** no nginx; `NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000` (direct to backend).

**Prod (mmc.004.kz):** `NEXT_PUBLIC_API_BASE_URL=/api` (relative same-origin).

**SSR (Next server on VPS):** `BACKEND_URL=http://127.0.0.1:8000` (direct internal; bypass nginx `/api`).

Bot / cron keep `API_BASE_URL=http://127.0.0.1:8000` (internal, no `/api` prefix).

---

## Nginx configuration

Add **before** the catch-all frontend `location /`:

```nginx
# FastAPI — strip /api prefix
location /api/ {
    proxy_pass http://127.0.0.1:8000/;   # trailing slash strips /api/
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_read_timeout 120s;
}

# Next.js frontend (pages, static, _next)
location / {
    proxy_pass http://127.0.0.1:3000;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
}
```

**Why trailing slash on `proxy_pass`:**  
`/api/directory/employees` → upstream `/directory/employees`.

**Do not** proxy blanket `/directory/*` to FastAPI — that breaks UI pages like `/directory/personnel`.

---

## Environment variables

### Production (`corpsite-ui/.env.production` + root `.env`)

```bash
# Browser fetch (same-origin)
NEXT_PUBLIC_API_BASE_URL=/api

# Next.js server-side fetch (direct to uvicorn)
BACKEND_URL=http://127.0.0.1:8000

# Root backend
APP_ENV=prod
CORS_ALLOWED_ORIGINS=https://mmc.004.kz

# Bot / internal (unchanged — direct port 8000)
API_BASE_URL=http://127.0.0.1:8000
META_API_BASE_URL=http://127.0.0.1:8000
```

Absolute URL also works: `NEXT_PUBLIC_API_BASE_URL=https://mmc.004.kz/api`

### Development (unchanged)

```bash
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000
BACKEND_URL=http://127.0.0.1:8000
```

---

## Verification (after deploy)

```bash
# API via nginx prefix
curl -sS -o /dev/null -w "%{http_code}\n" https://mmc.004.kz/api/health
# Expect: 200

curl -sS https://mmc.004.kz/api/health
# Expect: {"status":"ok"}

# UI page (must NOT hit FastAPI)
curl -sS -o /dev/null -w "%{http_code}\n" https://mmc.004.kz/directory/personnel
# Expect: 200 with text/html (Next.js), NOT {"detail":"Not Found"}

# API path must return JSON, not HTML
curl -sS -o /dev/null -w "%{http_code}\n" https://mmc.004.kz/api/directory/employees
# Expect: 401 or 403 without auth (JSON), NOT 404 HTML
```

Local URL resolver check:

```powershell
node scripts/verify_api_base_urls.mjs
```

Frontend build:

```powershell
cd corpsite-ui
npm run build
```

---

## VPS deploy steps

1. **Backup** nginx site config and `.env` files.

2. **Pull code** on VPS:
   ```bash
   cd /opt/projects/corpsite/app
   git pull origin master
   ```

3. **Update nginx** — add `location /api/` block (see above); test and reload:
   ```bash
   sudo nginx -t
   sudo systemctl reload nginx
   ```

4. **Update env** (do not commit secrets):
   ```bash
   # corpsite-ui/.env.production
   NEXT_PUBLIC_API_BASE_URL=/api
   NEXT_PUBLIC_APP_ENV=prod

   # root .env (backend + SSR)
   BACKEND_URL=http://127.0.0.1:8000
   CORS_ALLOWED_ORIGINS=https://mmc.004.kz
   ```

5. **Rebuild frontend** (env is baked at build time for `NEXT_PUBLIC_*`):
   ```bash
   cd /opt/projects/corpsite/app
   sudo ./scripts/deploy_frontend.sh
   ```
   See `docs/deploy/frontend.md` — do **not** restart frontend without running this script.

6. **Restart backend** (if needed):
   ```bash
   sudo systemctl restart corpsite-backend
   ```

7. **Smoke checks** — run curl commands above; log in via UI; open `/directory/personnel` and `/directory/employees`; confirm network tab shows `/api/directory/...` returning JSON.

8. **Rollback** — restore previous nginx config + `NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000` (or prior value), run `sudo ./scripts/deploy_frontend.sh`, reload nginx, restart services.

---

## Why not Option B (backend `/api` mount)?

Option B requires changing every FastAPI router prefix, all pytest paths, bot integrations, and smoke scripts. Option A changes only frontend URL resolution + nginx — backend stays at `/directory/*`, `/auth/*`, etc.

---

## Related

- `corpsite-ui/lib/apiBase.ts` — `resolveApiUrl()` / `buildUrl()`
- `.env.example` — dev defaults
- `README_DEPLOY.md` — general deploy checklist
