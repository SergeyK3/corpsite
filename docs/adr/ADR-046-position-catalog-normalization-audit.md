# ADR-046 Follow-up — Position Catalog Normalization Audit

**Status:** Investigation / Proposed  
**Date:** 2026-06-22  
**Related:** [ADR-046 — Org-unit allowed positions (Future)](ADR-046-org-unit-allowed-positions.md), ADR-031, ADR-038 Phase 2A (`position_aliases`), Phase 3I hotfix `103be25`  
**Scope:** Audit and solution design only — **no migrations, no data changes, no production writes**

---

## Executive summary

Production содержит как минимум одну пару семантических дубликатов:

| position_id | name | category |
|-------------|------|----------|
| 77 | Зам по адм вопросам | leaders |
| 99 | Заместитель по адм. вопросам | admin |

Обе описывают одну роль. Корневая причина — **глобальный справочник без канонизации имён**: `POST /directory/positions` проверяет только `lower(name)` exact match; сокращения и пунктуация создают новые `position_id`.

Phase 3I Enrollment Wizard (`103be25`) решает **доступность** списка через fallback на global catalog, но **не** решает дубли и не реализует ADR-046 `org_unit_allowed_positions`.

---

## 1. Поиск похожих дубликатов

### 1.1. Текущая защита от дублей (code)

```29:30:app/directory/positions_routes.py
def _normalize_name(value: str) -> str:
    return " ".join((value or "").replace(" -", "-").replace("- ", "-").split()).strip()
```

При create/update: `WHERE lower(name) = lower(:name)` — **только exact match** после whitespace collapse.  
«Зам по адм вопросам» ≠ «Заместитель по адм. вопросам» → два `position_id`.

Import-side `_get_or_create_position_id` использует `lower(trim(name))` — та же слабость:

```144:156:app/services/hr_import_roster_promotion_service.py
def _get_or_create_position_id(conn: Connection, position_name: str) -> int:
    ...
    WHERE lower(trim(name)) = lower(trim(:name))
```

### 1.2. Предлагаемая функция нормализации (audit SQL)

Для отчёта на production — **read-only**. Рекомендуется создать **IMMUTABLE** helper function в отдельной миграции (future); ниже — inline expression для одноразового audit.

```sql
-- Read-only audit helper (run as SELECT, do not persist yet)
CREATE OR REPLACE FUNCTION audit_position_norm(input TEXT)
RETURNS TEXT
LANGUAGE sql
IMMUTABLE
AS $$
  SELECT trim(both ' ' FROM regexp_replace(
    regexp_replace(
      regexp_replace(
        lower(coalesce(input, '')),
        '\m(зам|замест)\M', 'заместитель ', 'g'
      ),
      '\m(адм|администр)\M', 'административ ', 'g'
    ),
    '[^a-zа-яё0-9]+', ' ', 'gi'
  ));
$$;

-- Optional: drop after audit session
-- DROP FUNCTION IF EXISTS audit_position_norm(TEXT);
```

### 1.3. Report A — exact duplicates (разный регистр / пробелы)

```sql
SELECT
    lower(trim(name)) AS norm_exact,
    count(*) AS cnt,
    array_agg(position_id ORDER BY position_id) AS position_ids,
    array_agg(name ORDER BY position_id) AS names,
    array_agg(category ORDER BY position_id) AS categories
FROM public.positions
GROUP BY lower(trim(name))
HAVING count(*) > 1
ORDER BY cnt DESC, norm_exact;
```

### 1.4. Report B — same normalized token, different category

```sql
WITH normed AS (
    SELECT
        position_id,
        name,
        category,
        audit_position_norm(name) AS norm_name
    FROM public.positions
)
SELECT
    n.norm_name,
    count(DISTINCT n.category) AS category_variants,
    array_agg(DISTINCT n.category ORDER BY n.category) AS categories,
    count(*) AS position_cnt,
    array_agg(n.position_id ORDER BY n.position_id) AS position_ids,
    array_agg(n.name ORDER BY n.position_id) AS names
FROM normed n
WHERE n.norm_name <> ''
GROUP BY n.norm_name
HAVING count(*) > 1
ORDER BY category_variants DESC, position_cnt DESC, n.norm_name;
```

**Ожидание для пары 77/99:** одна строка в Report B с `category_variants = 2`.

### 1.5. Report C — abbreviation / substring clusters (heuristic)

```sql
WITH normed AS (
    SELECT
        position_id,
        name,
        category,
        audit_position_norm(name) AS norm_name
    FROM public.positions
),
pairs AS (
    SELECT
        a.position_id AS id_a,
        b.position_id AS id_b,
        a.name AS name_a,
        b.name AS name_b,
        a.category AS cat_a,
        b.category AS cat_b,
        a.norm_name AS norm_a,
        b.norm_name AS norm_b
    FROM normed a
    JOIN normed b ON a.position_id < b.position_id
    WHERE a.norm_name <> ''
      AND (
          a.norm_name = b.norm_name
          OR (length(a.norm_name) >= 12 AND a.norm_name LIKE '%' || b.norm_name || '%')
          OR (length(b.norm_name) >= 12 AND b.norm_name LIKE '%' || a.norm_name || '%')
      )
)
SELECT * FROM pairs
ORDER BY id_a, id_b;
```

### 1.6. Report D — focus pair 77 / 99

```sql
SELECT position_id, name, category
FROM public.positions
WHERE position_id IN (77, 99)
   OR audit_position_norm(name) = audit_position_norm(
        (SELECT name FROM public.positions WHERE position_id = 77 LIMIT 1)
      )
ORDER BY position_id;
```

### 1.7. Как запускать на production

1. Read-only session (`psql` / reporting role).
2. Сохранить CSV результатов Reports A–D в `docs/ops/` или ticket attachment.
3. **Не** создавать persistent functions без change window, если политика запрещает DDL на prod — тогда inline `regexp_replace` chain в CTE вместо `audit_position_norm`.

---

## 2. Проверка использования (id=77, id=99)

Фактические counts **не снимались с production** в рамках этого audit (нет live DB access). Ниже — полный checklist FK/ссылок по schema + SQL для ops.

### 2.1. Таблицы с FK на `positions.position_id`

| Table | Column(s) | ON DELETE | Notes |
|-------|-----------|-----------|-------|
| `employees` | `position_id` | (baseline FK) | Operational staff |
| `employee_events` | `from_position_id`, `to_position_id` | FK → positions | Transfer / position change history |
| `person_assignments` | `position_id` | RESTRICT | ADR-042 lifecycle |
| `personnel_visibility_assignments` | `target_position_id` | CASCADE | ADR-042 E1 visibility |
| `position_aliases` | `position_id` | CASCADE | ADR-038 import matching |

### 2.2. Polymorphic / logical references

| Table | Match condition | Notes |
|-------|-----------------|-------|
| `access_grants` | `target_type = 'POSITION' AND target_id IN (77,99)` | ADR-042 access resolver |
| `hr_import_alias_resolutions` | `alias_type = 'position' AND canonical_id IN (77,99)` | Per-batch import cache |
| HR JSON payloads | `position_raw` text (no FK) | Canonical snapshot, change events — string match only |

**Not found:** FK from `regular_tasks` / task templates to `positions`.

### 2.3. Usage SQL — run per id (template)

```sql
-- Replace :pid for 77 and 99
\set pid 77

SELECT 'employees' AS src, count(*) AS cnt
FROM public.employees WHERE position_id = :pid;

SELECT employee_id, full_name, org_unit_id, position_id, is_active
FROM public.employees WHERE position_id = :pid
ORDER BY employee_id;

SELECT 'employee_events_from' AS src, count(*) AS cnt
FROM public.employee_events WHERE from_position_id = :pid;

SELECT 'employee_events_to' AS src, count(*) AS cnt
FROM public.employee_events WHERE to_position_id = :pid;

SELECT assignment_id, person_id, org_unit_id, position_id, active_flag
FROM public.person_assignments WHERE position_id = :pid;

SELECT assignment_id, target_type, target_position_id, is_active
FROM public.personnel_visibility_assignments
WHERE target_position_id = :pid;

SELECT grant_id, access_role_id, target_type, target_id, active_flag
FROM public.access_grants
WHERE target_type = 'POSITION' AND target_id = :pid;

SELECT alias_id, alias_text, normalized_alias
FROM public.position_aliases WHERE position_id = :pid;

SELECT resolution_id, batch_id, raw_value, canonical_id, resolved_by
FROM public.hr_import_alias_resolutions
WHERE alias_type = 'position' AND canonical_id = :pid
ORDER BY batch_id DESC
LIMIT 50;
```

### 2.4. Combined summary query

```sql
WITH targets AS (SELECT unnest(ARRAY[77, 99]) AS position_id)
SELECT
    t.position_id,
    p.name,
    p.category,
    (SELECT count(*) FROM public.employees e WHERE e.position_id = t.position_id) AS employees,
    (SELECT count(*) FROM public.employee_events ev
     WHERE ev.from_position_id = t.position_id OR ev.to_position_id = t.position_id) AS employee_events,
    (SELECT count(*) FROM public.person_assignments pa WHERE pa.position_id = t.position_id) AS person_assignments,
    (SELECT count(*) FROM public.personnel_visibility_assignments pva
     WHERE pva.target_position_id = t.position_id) AS visibility_assignments,
    (SELECT count(*) FROM public.access_grants ag
     WHERE ag.target_type = 'POSITION' AND ag.target_id = t.position_id AND ag.active_flag) AS access_grants,
    (SELECT count(*) FROM public.position_aliases pa WHERE pa.position_id = t.position_id) AS aliases,
    (SELECT count(*) FROM public.hr_import_alias_resolutions r
     WHERE r.alias_type = 'position' AND r.canonical_id = t.position_id) AS import_resolutions
FROM targets t
JOIN public.positions p ON p.position_id = t.position_id
ORDER BY t.position_id;
```

### 2.5. Merge impact rule (for §3)

| If usage shows… | Implication |
|-----------------|-------------|
| Only one id has rows | **Rename** or merge into survivor with minimal FK updates |
| Both have employees | **Merge (B)** required — rewrite FKs, then delete duplicate row |
| Visibility/access on both | Merge must include grant deduplication |
| Aliases on duplicate only | Repoint aliases to canonical `position_id` before delete |

---

## 3. Канонизация пары 77 / 99

### Proposed canonical record

| Field | Value |
|-------|--------|
| **Canonical name** | Заместитель директора по административным вопросам |
| **Recommended category** | `leaders` *(или `admin` — решение HR/policy; сейчас split `leaders` vs `admin` — defect)* |
| **Survivor `position_id`** | TBD after §2.3 — prefer id with **more FK references**; tie-break: lower id |

### Variant A — Rename only

**Action:** Update `positions.name` (and `category`) on survivor id; delete or manual retire duplicate if unused.

| Pros | Cons |
|------|------|
| Минимальный риск, один SQL UPDATE | Не снимает второй `position_id`, если оба используются |
| Не трогает FK | Два id остаются в истории `employee_events` |
| Быстро для orphan duplicate | Не решает системную проблему новых сокращений |

**When:** duplicate id has **zero** references.

### Variant B — Merge into single position

**Action:**

1. Choose survivor `position_id` (canonical name on survivor).
2. `UPDATE` all FK columns: `employees`, `employee_events`, `person_assignments`, `personnel_visibility_assignments`, `access_grants`, `position_aliases`, `hr_import_alias_resolutions`.
3. `DELETE` duplicate row (or soft-archive if delete blocked).
4. Audit log + comms.

| Pros | Cons |
|------|------|
| Single source of truth | Требует transaction + verification script |
| Корректная аналитика и фильтры | Ошибка FK update — high impact |
| Подходит при обоих id in use | Needs maintenance window |

**When:** both ids referenced — **likely for 77/99** if обе использовались в разных потоках (UI create vs import).

### Variant C — Aliases / synonym search layer

**Action:** Keep both ids (or one canonical + one deprecated); populate `position_aliases`; search/enrollment resolves via aliases.

Existing schema:

```29:36:app/db/models/aliases.py
class PositionAlias(Base):
    __tablename__ = "position_aliases"
    ...
    position_id: Mapped[int] = mapped_column(..., ForeignKey("positions.position_id", ...))
    alias_text: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_alias: Mapped[str] = mapped_column(Text, nullable=False)
```

| Pros | Cons |
|------|------|
| Без немедленного FK rewrite | Два id остаются в `employees` — отчёты дублируют роль |
| Улучшает import matching и search | Требует UI/admin для alias CRUD (partially missing) |
| Мягкий rollout | Не fixes category inconsistency without merge |

**When:** transitional phase before merge; import-heavy orgs.

### Recommendation (proposed, pending §2.3 results)

1. **Target end state:** Variant **B** → one `position_id`, canonical name above, unified category.
2. **Transitional:** seed `position_aliases` (Variant C) **before** merge so Enrollment/import hints resolve during change window.
3. **Do not** rename-only (A) if both ids have `employees` rows.

---

## 4. UX audit — `/directory/positions`

Source: `corpsite-ui/app/directory/positions/_components/PositionsPageClient.tsx`

### 4.1. OrgScopeFilter behaviour

| Question | Finding |
|----------|---------|
| Активен ли OrgScopeFilter по умолчанию? | Комponent **rendered always**; default value **«Все»** (`org_group_id` empty) → **full global catalog** |
| Фильтрует ли он `org_unit_id`? | **No** — `OrgScopeFilter` only sets `org_group_id` (department group) |
| Откуда `org_unit_id`? | Separate URL params (`org_unit_id`, `unit_id`, …) via `readSelectedOrgUnitId` — **not** exposed in Positions UI control |
| Что делает `org_group_id`? | Backend `EXISTS employees in org scope` — **not full catalog** |

```135:161:app/directory/positions_routes.py
    if org_group_id is not None or org_unit_id is not None:
        ...
        EXISTS (SELECT 1 FROM employees e WHERE e.position_id = p.position_id AND ...)
```

### 4.2. User understanding gap

| Issue | Severity |
|-------|----------|
| Selecting **Группа отделений** silently restricts list to **used** positions in scope | **High** — looks like full справочник |
| No banner «Показаны должности, используемые в выбранной группе» | High |
| Title `Должности (unit #N)` only when API returns `filter_org_unit_name` / URL org unit | Medium |
| «Всего: N» reflects filtered total, not global count | Medium |
| User creates position while group filter active → new row may **disappear** from list until an employee uses it | **High** — reported symptom for 77/99 scenario |
| Search `q` is substring on `lower(name)` only — abbreviations miss | Medium |

### 4.3. Where filter is shown today

- Page title suffix: `Должности (${filterCaption})` when org unit name/id known.
- **No** chip/badge for org **group** filter.
- OrgScopeFilter label: «Группа отделений» — does not explain side effect on result set.

### 4.4. UX improvements (proposal — no implementation)

1. **Scope banner** when `org_group_id` or `org_unit_id` active:
   - «Показаны должности, уже используемые сотрудниками в выбранном scope. [Показать весь справочник]»
2. **Toggle** «Весь справочник / Только используемые в scope» — mirror Enrollment Wizard fallback pattern (`103be25`).
3. **Post-create toast** if filtered view: «Должность создана. Она появится в списке после назначения сотруднику или в полном справочнике.»
4. **Separate org unit picker** (optional) or link from org structure — today org unit filter is URL-only.
5. **Duplicate hint on create** — soft warning if normalized name near existing (future API).

---

## 5. Search normalization — proposal (no implementation)

### 5.1. Current search paths

| Surface | Mechanism | Limitation |
|---------|-----------|------------|
| Positions page `q` | `LOWER(name) LIKE %q%` | No abbreviations, no alias table |
| Enrollment wizard | Client sort only; no typeahead search | Long lists |
| HR import | `_normalize_position` strips dates/whitespace | Not shared with directory API |
| `position_aliases` | DB exists | **Not wired** to `GET /positions?q=` |

### 5.2. Target behaviour

Queries **`административ`**, **`адм`**, **`заместитель`**, **`зам`** should resolve to canonical position (including pair 77/99 survivor).

### 5.3. Proposed architecture (phased)

**Phase S1 — Shared normalizer (library)**

Python: `app/services/position_name_normalizer.py`

- lowercase, strip dates (`04.05.2010г.`)
- punctuation → space
- abbreviation map: `зам→заместитель`, `адм→административ`, `директ→директор`, …
- optional: remove stop words (`по`, `и`) for fuzzy key only

TypeScript mirror for client typeahead (or API-only).

**Phase S2 — Alias-aware search API**

Extend `GET /directory/positions?q=`:

```sql
-- Conceptual (future)
WHERE lower(p.name) LIKE :q
   OR EXISTS (
        SELECT 1 FROM position_aliases a
        WHERE a.position_id = p.position_id
          AND a.normalized_alias LIKE :q_norm
   )
   OR audit_position_norm(p.name) LIKE :q_norm
```

Return `matched_via: 'name' | 'alias' | 'normalized'`.

**Phase S3 — Admin alias management**

- UI on position drawer: synonyms list
- Bulk import from duplicate audit (Report B)
- Unique constraint on `normalized_alias` globally — repoint on merge

**Phase S4 — Create-time dedup guard**

Before `INSERT INTO positions`:

- compute `norm_key`
- if match existing → `409` with `{ existing_position_id, suggestion: 'use existing' }`

**Phase S5 — Enrollment / Employee forms**

- typeahead calling alias-aware search
- show canonical name + «also known as …»

### 5.4. Relation to ADR-046 allowed positions

Search normalization **orthogonal** to `org_unit_allowed_positions`:

- Normalization → **which** position row
- Allowed positions → **which rows offered** per org unit

Both needed for clean HR UX long-term.

---

## 6. Safe cleanup plan (outline — no execution)

| Step | Action | Owner |
|------|--------|-------|
| 1 | Run Reports A–D + §2.4 on production (read-only) | Ops/DBA |
| 2 | HR sign-off canonical name + category for 77/99 | HR |
| 3 | Choose survivor id; draft merge script (FK updates) in staging | Eng |
| 4 | Rehearse merge on staging snapshot | Eng |
| 5 | Seed `position_aliases` for legacy strings | Eng |
| 6 | Maintenance window: merge + verify §2.4 zeros on deleted id | Ops |
| 7 | Deploy S2 search + S4 create guard | Eng |
| 8 | Positions UX banner (§4.4) | Eng |

**Rollback:** restore `positions` row from backup + reverse FK updates (script required before merge).

---

## 7. Non-goals (this document)

- No Alembic migration in this audit
- No production UPDATE/DELETE
- No change to `GET /positions?org_unit_id=` semantics (see ADR-046 main doc)
- No commit required for this investigation artifact

---

## 8. References

- `app/directory/positions_routes.py` — list/create/update/delete
- `app/db/models/aliases.py` — `position_aliases`
- `corpsite-ui/app/directory/positions/_components/PositionsPageClient.tsx`
- `docs/ops/POSITIONS_SYNC_RUNBOOK.md`
- `103be25` — Enrollment Wizard catalog fallback (interim, not catalog cleanup)

---

## Tracking

| Event | Date |
|-------|------|
| Investigation document created | 2026-06-22 |
| Production duplicate reports A–D | _Pending ops run_ |
| Usage summary §2.4 for ids 77, 99 | _Pending ops run_ |
