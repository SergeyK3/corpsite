# Backend pytest

Pytest **must** use a dedicated PostgreSQL database via `TEST_DATABASE_URL`. It must **not** read or fall back to `DATABASE_URL`.

## Guard behavior

Before any conftest, fixture, or schema setup, pytest loads `tests/pytest_db_guard_plugin.py` via **`pytest.ini`**:

```ini
addopts = -p tests.pytest_db_guard_plugin
```

This registers the plugin **before** `tests/conftest.py` is imported. Registering the same plugin only through `pytest_plugins` inside conftest is **not** sufficient: `pytest_load_initial_conftests` runs prior to conftest discovery.

The hook order is:

1. `pytest_load_initial_conftests` in `tests/pytest_db_guard_plugin.py`
2. validate/bind `TEST_DATABASE_URL` → `app.db.engine`
3. only then root/isolated `conftest.py` imports `app.db.engine`

Subprocess proof: `tests/test_db_guard.py::TestGuardPluginLoadOrder`.

1. Requires `TEST_DATABASE_URL` to be set.
2. Rejects database names that do not end with `_test` or `-test` (for example `corpsite_test`, `corpsite-test`).
3. Compares normalized `TEST_DATABASE_URL` with `DATABASE_URL` (host, port, database only — driver, password, and query params are ignored). If they match, pytest exits with code `1`.
4. Rebinds `app.db.engine.engine` to `TEST_DATABASE_URL` so all tests use the test database.

Normalization examples treated as the **same** target:

- `postgresql+psycopg2://…@127.0.0.1:5432/corpsite` vs `postgresql://…@localhost:5432/corpsite`
- Different passwords or `?sslmode=…` query parameters

No database connections are opened during the guard check itself.

## Local setup

### 1. Configure the local test connection

Set `TEST_DATABASE_URL` to a loopback PostgreSQL URL whose database name is
`corpsite_test`. The runner below uses its credentials to create a new,
randomly named `corpsite_test_*_test` database; it never writes to that base
database. The database user needs `CREATEDB` permission.

### 2. Configure `.env`

Copy from `.env.example` and set:

```env
DATABASE_URL=postgresql+psycopg2://postgres:postgres@127.0.0.1:5432/corpsite
TEST_DATABASE_URL=postgresql+psycopg2://postgres:postgres@127.0.0.1:5432/corpsite_test
```

### 3. Prepare a fresh database and run tests

The historical grant migrations require initial roles, an active user and a
parented `DISP` unit. A bare `alembic upgrade head` on an empty database stops
at `i6j7k8l9m0n1`. Use the disposable runner from the repository root:

```powershell
# TEST_DATABASE_URL is set in the shell to the local corpsite_test URL
python -m scripts.run_isolated_test_db -- -q tests/test_personnel_order_termination_reason.py tests/test_personnel_order_numeric_search_readonly.py
```

The runner upgrades to `h5c6d7e8f9a0`, loads the canonical role catalog from
`db/init/020_seed_roles_users_employees.sql`, the maintained pilot directory and
user seeds, and `tests/personnel_lk/adr065_test_org_bootstrap.sql`. It adds an
`ADMIN` role and unit 44 only inside the disposable database. It then
upgrades to head, runs pytest with the existing database guard, and removes only
the newly created database. The old seed's employee IDs are text, so its
employee/user statements cannot run against the current numeric ID schema.
Pass other pytest paths after `--` to use the same isolated setup.

## CI (recommended)

There is no backend pytest workflow in `.github/workflows/` yet. When added:

```yaml
services:
  postgres:
    image: postgres:16
    env:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: corpsite_test
    ports:
      - 5432:5432

env:
  DATABASE_URL: postgresql://postgres:postgres@127.0.0.1:5432/corpsite
  TEST_DATABASE_URL: postgresql://postgres:postgres@127.0.0.1:5432/corpsite_test

steps:
  - run: python -m scripts.run_isolated_test_db -- -q
```

Use distinct `DATABASE_URL` (dummy or dev name) and `TEST_DATABASE_URL` so the guard passes.

## Guard unit tests

```powershell
python -m pytest tests/test_db_guard.py -q
```

Covers: missing URL, dev DB collision, invalid DB name, valid `corpsite_test`, URL normalization.

---

# IMPORTANT (ACL contract):

Executor visibility requires:

- users.unit_id == tasks.unit_id
- assignment_scope NOT IN ('admin', 'super', 'root')
