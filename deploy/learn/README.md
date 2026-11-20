# Isolated learning instance: learn.mmc.004.kz

Application source SHA (`APP_SOURCE_SHA`):
`3f545d63f01b001640447d6088603aad12a41f36`.
Published procedure baseline SHA:
`528ed8e2485ce95bc52d4cfee9b9e6d3fc65060b`.
Deployment procedure SHA (`DEPLOY_FILES_SHA`): the current published commit
on `origin/feature/learning-site`; record its full SHA when packaging. It may
be newer than the procedure baseline after corrections. These are separate
identifiers. The frontend artifact must be built
from `APP_SOURCE_SHA`; the deployment files are overlaid from
`DEPLOY_FILES_SHA`. Do not label the resulting mixed release as a single Git
checkout.
Use a separate VPS. This is a future deployment procedure, not an instruction to
modify production or the certificate test stand. All accounts and certificates
created by the bootstrap are fictional.

## Files and isolation

- `corpsite-learn-backend.service`: FastAPI on `127.0.0.1:8003`.
- `corpsite-learn-frontend.service`: Next.js on `127.0.0.1:3003`.
- `learn.mmc.004.kz.nginx.conf`: TLS reverse proxy, with no static alias for files.
- `backend.env.example` and `frontend.env.example`: examples only; secrets
  belong in private `/etc/corpsite-learn/*.env`, never in Git.
- `scripts/learn/prepare.py`: guarded preflight, migration and repeatable data
  preparation. It refuses any server DB name except `corpsite_learn`, any
  non-loopback DB host, other storage roots, wrong Alembic head or unexpected
  existing revision. `check` is read-only. `apply` only proceeds after it.
- `scripts/learn/rehearse_local.py`: on Windows, creates its own temporary local PostgreSQL
  role and `corpsite_learn_*_test` DB, runs preparation twice, tests the workflow,
  then drops that DB and role. Only this mode simulates the absent local scanner.
  The server `corpsite_learn` database cannot use this mode.

Do not install or enable `corpsite-bot`, `corpsite-regular-tasks.timer`, or
production integration timers for learn. The backend and frontend units permit
network access only to localhost. FreshClam updates run independently. All
fictional users have no Telegram ID, phone or email. A blank
`TELEGRAM_DELIVERY_ALLOW_USER_IDS` is not an external-notification switch.
The application's required `BOT_BIND_TOKEN` and `INTERNAL_API_TOKEN` still
need **new, independent** values, but no learn bot or delivery worker is started.

## New VPS order

1. Provision Linux with PostgreSQL 16, Python, Node.js compatible with the
   lockfile, Nginx, `clamav` and `clamav-freshclam`. Confirm the scanner
   signatures are current. Create the Unix user `corpsite-learn` and own
   `/opt/projects/corpsite-learn/app`, `/var/lib/corpsite-learn`,
   `/var/lib/corpsite-learn/photos`, `/var/lib/corpsite-learn/files` with it.
   Set all three storage directories to mode `0700`; `photos` and `files`
   must be those exact children of `/var/lib/corpsite-learn`. Keep files outside Nginx
   roots; back up DB and files together.

   ```sh
   sudo useradd --system --user-group --home-dir /var/lib/corpsite-learn \
     --shell /usr/sbin/nologin corpsite-learn
   sudo install -d -o corpsite-learn -g corpsite-learn -m 0700 \
     /var/lib/corpsite-learn /var/lib/corpsite-learn/photos \
     /var/lib/corpsite-learn/files
   ```

2. As PostgreSQL administrator, create login role `corpsite_learn_app` with
   its own password and create DB `corpsite_learn` owned by that role. Revoke
   PUBLIC access to this DB. Bind PostgreSQL to loopback or a private socket.
   The role may create objects in its own empty DB for Alembic. The URL must
   resolve to `127.0.0.1` or `localhost`; query parameters are rejected.

   ```sh
   sudo -u postgres createuser --login --pwprompt corpsite_learn_app
   sudo -u postgres createdb --owner=corpsite_learn_app corpsite_learn
   sudo -u postgres psql -d postgres -c \
     'REVOKE ALL ON DATABASE corpsite_learn FROM PUBLIC'
   ```

3. From a Git clone **outside** the VPS, package the application from
   `APP_SOURCE_SHA` and the two procedure directories from
   `DEPLOY_FILES_SHA` separately. Extract the application into
   `/opt/projects/corpsite-learn/app`, then overlay only those two directories.
   Record both full Git SHAs and the two archive checksums before transfer. Install Python
   requirements in the release's private venv. Build the UI from
   `APP_SOURCE_SHA` **outside** the VPS using `npm ci`,
   `NEXT_PUBLIC_APP_ENV=production`,
   `NEXT_PUBLIC_API_BASE_URL=/api`, then `npm run build`. Transfer the
   `.next` artifact and verify its manifest `git_rev` is the short prefix of
   `APP_SOURCE_SHA`, its `package_lock_sha256` matches that app archive, and
   its `BUILD_ID` matches the extracted build. Install runtime
   Node dependencies with `npm ci --omit=dev` on the VPS; do not run
   `npm run build` there. Keep the learn release path distinct from production.
   Build the frontend in a detached checkout at `APP_SOURCE_SHA` so the artifact
   manifest's `git_rev` records the application source, not the procedure commit.
   Set `NEXT_DEPLOYMENT_ID` to the same full SHA. `next.config.ts` otherwise
   calls Git at runtime, which fails in a release without `.git`.

   ```sh
   APP_SOURCE_SHA=3f545d63f01b001640447d6088603aad12a41f36
   PROCEDURE_BASE_SHA=528ed8e2485ce95bc52d4cfee9b9e6d3fc65060b
   DEPLOY_FILES_SHA=$(git rev-parse origin/feature/learning-site)
   test "$(git rev-parse "$APP_SOURCE_SHA^{commit}")" = "$APP_SOURCE_SHA"
   git merge-base --is-ancestor "$PROCEDURE_BASE_SHA" "$DEPLOY_FILES_SHA"
   git worktree add --detach ./learn-app-build "$APP_SOURCE_SHA"
   cd ./learn-app-build
   export NEXT_PUBLIC_APP_ENV=production NEXT_PUBLIC_API_BASE_URL=/api
   export NEXT_DEPLOYMENT_ID="$APP_SOURCE_SHA"
   ./scripts/build_frontend_artifact.sh
   ```

   Build the artifact on Linux with the release's Node major version. A
   Windows build of this SHA contains an absolute Playwright junction and
   cannot be extracted or run reliably on Linux. The Linux build has a
   relative `.next/node_modules/playwright-*` link; install Linux runtime
   dependencies at the matching release path before starting Next.js.
4. Put independent secrets and the learn DB URL in
   `/etc/corpsite-learn/backend.env` (copy the example, owner
   `corpsite-learn`, mode `0600`). The two DB URL variables must be identical.
   Put frontend variables in its own private env file, including the same
   `NEXT_DEPLOYMENT_ID=APP_SOURCE_SHA`. Replace every
   `REPLACE_*` value; the preflight rejects placeholders and reused application
   secrets. Check both release SHAs, free
   ports 8003/3003, storage ownership/modes, DB identity, scanner, and the
   single Alembic head **before migration**:

   ```sh
   sudo -u corpsite-learn /opt/projects/corpsite-learn/app/.venv/bin/python \
     /opt/projects/corpsite-learn/app/scripts/learn/prepare.py check \
     --env-file /etc/corpsite-learn/backend.env
   ```

5. Make a private one-time `/etc/corpsite-learn/bootstrap.env` (owner
   `corpsite-learn`, mode `0600`) with three unique fictional login passwords:
   `LEARN_WORKER_PASSWORD`, `LEARN_HR_PASSWORD`, and
   `LEARN_OUTSIDER_PASSWORD`. Run `prepare.py apply` with both `--env-file`
   and `--password-file` using the same executable as in step 4; remove the one-time password file after the initial
   run. Repeating `apply` does not duplicate accounts or initial documents and
   does not rotate their passwords. The command migrates through the historical
   HR prerequisites to `pfiles002`, then creates fictional people, scoped
   reviewer grant, classifier editions and mapping, and two approved PDF files
   scanned by **real** ClamAV. A failed scan rejects the file. The old A and B
   certificates both start `ACTIVE/VERIFIED`.
6. Verify unit files with `systemd-analyze verify` before installation. Install
   and start only the two learn units; check `127.0.0.1:8003/health` and the
   frontend on `127.0.0.1:3003`.
   Do not use the production deploy scripts: their port guards target 8000/3000.
   Once DNS and TLS are ready, install the learn Nginx site, run `nginx -t`,
   and enable the vhost.

   ```sh
   sudo install -m 0644 deploy/learn/corpsite-learn-backend.service \
     /etc/systemd/system/corpsite-learn-backend.service
   sudo install -m 0644 deploy/learn/corpsite-learn-frontend.service \
     /etc/systemd/system/corpsite-learn-frontend.service
   sudo systemd-analyze verify /etc/systemd/system/corpsite-learn-{backend,frontend}.service
   sudo systemctl daemon-reload
   sudo systemctl enable --now corpsite-learn-backend corpsite-learn-frontend
   curl --fail http://127.0.0.1:8003/health
   curl --fail --head http://127.0.0.1:3003/
   # After TLS files exist: install the Nginx site, nginx -t, then reload Nginx.
   ```
7. In a browser, sign in as `learn.worker` and `learn.hr`; check that
   `learn.outsider` cannot see the worker's files. Replace A with a NEW-A
   certificate, return it with a reason, resubmit, then approve using the
   confirmed OLD-A → NEW-A mapping. After return, old A and B must remain
   `ACTIVE/VERIFIED`; after approval, old A must be `SUPERSEDED/VERIFIED`,
   new A `ACTIVE/VERIFIED`, and B `ACTIVE/VERIFIED`.
8. To stop the instance, take only the learn Nginx route out of service, stop
   `corpsite-learn-frontend` and `corpsite-learn-backend`, and retain a paired
   DB/files backup. These file migrations do not support a simple downgrade.

The local rehearsal does not measure real antivirus cost. On the new VPS, before
browser acceptance, scan a valid fictional PDF once and with 2–3 simultaneous
requests; capture elapsed time and maximum RSS for each `clamscan` process,
backend RSS, CPU, disk latency and free RAM. The application scanner timeout is
45 seconds. Keep the pilot serial or increase capacity if the measured peak
approaches available memory or the timeout.
