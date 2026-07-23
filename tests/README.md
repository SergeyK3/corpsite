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

### 1. Create the test database (once)

```powershell
# PowerShell — adjust user/host if needed
psql "postgresql://postgres:postgres@127.0.0.1:5432/postgres" -c "CREATE DATABASE corpsite_test;"
```

```bash
# bash
psql "postgresql://postgres:postgres@127.0.0.1:5432/postgres" -c "CREATE DATABASE corpsite_test;"
```

### 2. Configure `.env`

Copy from `.env.example` and set:

```env
DATABASE_URL=postgresql+psycopg2://postgres:postgres@127.0.0.1:5432/corpsite
TEST_DATABASE_URL=postgresql+psycopg2://postgres:postgres@127.0.0.1:5432/corpsite_test
```

### 3. Apply migrations to the test database

Alembic reads `DATABASE_URL` from `.env`. Point it at the test DB for migrations:

```powershell
$env:DATABASE_URL = $env:TEST_DATABASE_URL
alembic upgrade head
```

```bash
export DATABASE_URL="$TEST_DATABASE_URL"
alembic upgrade head
```

Or in one line without changing `.env`:

```bash
DATABASE_URL=postgresql+psycopg2://postgres:postgres@127.0.0.1:5432/corpsite_test alembic upgrade head
```

### 4. Run tests

```powershell
# from repo root, with TEST_DATABASE_URL in .env or shell
python -m pytest tests/test_db_guard.py -q
python -m pytest tests/test_admin_org_units_crud.py -q
python -m pytest -q
```

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
  - run: alembic upgrade head
    env:
      DATABASE_URL: ${{ env.TEST_DATABASE_URL }}
  - run: python -m pytest -q
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
