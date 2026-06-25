# OPS-026 — Contacts source cleanup + Telegram ID audit

## Scope

1. **Contacts page** (`/directory/contacts`) — operational/task contour only in main API list.
2. **QM_AMB Telegram ID** — audit before replace; target `7685102887`.

## Problem 1 — Contacts API / UI

| Layer | Path |
|-------|------|
| Backend | `GET /directory/contacts` → `app/directory/contacts_routes.py` |
| Frontend | `corpsite-ui/app/directory/contacts/page.tsx` |
| Expert slots | `GET /directory/working-contacts` (unchanged; merged in UI) |
| Positions / empty slots | `GET /directory/positions` (unchanged) |

### Tables involved (before fix)

| Source | Table / view | Role on Contacts page |
|--------|----------------|------------------------|
| Main list | `public.contacts` | All non-deleted rows (included personnel/canonical duplicates) |
| Org filter bridge | `public.contacts_working`, `public.key_contacts`, `public.v_key_contacts_auto` | Scope filter only when org_group_id / org_unit_id set |
| Expert rows (UI) | `public.users` + `roles` + `employees` via working-contacts | Merged client-side |
| Personnel import | `persons`, `hr_import_*`, enrollment | Could populate `contacts.person_id` without operational link |

### Fix

`list_contacts` adds predicate `_build_task_contour_predicate_sql()`:

- **Include:** `person_id IS NULL` (manual task contact), `contacts_working`, `key_contacts`, active `users`/`employees` link.
- **Exclude:** contacts with `person_id` only from HR/canonical contour (no operational bridge).

Search (`q`) unchanged: ID, person_id, FIO, phone, Telegram ID.

### Nurбекov

- Seed operational user: `DEP_ADMIN` / `dep_admin@corp.local` — `Нурбеков Бахдат Байтлевич` (`db/init/020_seed_roles_users_employees.sql`).
- `key_contacts.csv`: `DEP_ADMIN`, person_id `695`, FIO variant «Нурбеков Багдат…».
- **Search «Нурбеков»:** finds row if contact is in task contour (key_contacts / users / contacts_working) or manual contact without personnel-only isolation.
- **Personnel-only:** not listed; enrollment path — `/directory/personnel/import/normalized-records` → «Добавить в персонал» (`ImportEnrollEmployeeWizard`) or `/admin/system` → «Зачисление».

## Problem 2 — Telegram ID audit

Run **before** any UPDATE:

```bash
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f docs/ops/OPS-026-telegram-id-audit.sql
python scripts/ops/ops026_amb_expert_telegram_audit.py
```

### Known static references (repo, not DB)

| Location | ID | Binding |
|----------|-----|---------|
| `key_contacts.csv` DIRECTOR row | `885342581` | Director contact (dev placeholder) |
| `corpsite-ui/.../contacts/page.tsx` placeholder | was `885342581` → `7685102887` | UI hint only |
| `.env` `ADMIN_TG_IDS` | `300398364` | Admin alerts, not QM_AMB |

QM_AMB row in `key_contacts.csv` has **no** telegram_numeric_id in repo snapshot.

### Replace (after SELECT confirmation)

Use commented block in `docs/ops/OPS-026-telegram-id-audit.sql` section 6.

### Guard tests

- `tests/test_ops026_telegram_expert_slot_guard.py` — forbidden dev IDs not on QM_AMB seed lines.
- `tests/test_ops026_contacts_task_contour.py` — API contour filter.

## Verification

```bash
pytest tests/test_ops026_contacts_task_contour.py tests/test_ops026_telegram_expert_slot_guard.py -q
pytest tests/test_contacts_org_scope.py -q
```
