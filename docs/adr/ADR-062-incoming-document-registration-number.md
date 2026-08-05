# ADR-062 — Incoming Document Registration Number Generation

## Status

**Accepted**

| Field | Value |
|-------|-------|
| Work Package | WP-II-001 |
| Parent | [incoming-information-register](../implementation/incoming-information-register.md) |
| Date | 2026-08-04 |

---

## Context

The Incoming Information module requires a human-readable registration number in format `ВХ-{YYYY}-{NNNN}` (example: `ВХ-2026-0042`). Numbers must be unique, assigned at registration time on the server, and safe under concurrent registrations.

Operational Orders (`operational_order_documents`) use **manual** registration numbers at the register command (OO-IMP-005). Personnel Applications do not use a journal number. There is no existing reusable auto-sequence for this pattern.

Anti-patterns rejected:

- `SELECT MAX(registration_seq) + 1` — race under concurrency;
- pre-allocated client-side numbers;
- PostgreSQL `SERIAL` alone without year scope — does not encode annual reset.

---

## Decision

### D1 — Format

| Component | Rule |
|-----------|------|
| Prefix | Literal `ВХ-` |
| Year | Calendar year of `registered_at` (UTC date part) |
| Sequence | 4-digit zero-padded decimal, resets each calendar year |
| Example | `ВХ-2026-0042` |

Store denormalized fields on `incoming_documents`:

- `registration_number` TEXT UNIQUE NOT NULL
- `registration_year` INTEGER NOT NULL
- `registration_seq` INTEGER NOT NULL
- UNIQUE (`registration_year`, `registration_seq`)

### D2 — Counter table with row lock

Table `incoming_document_registration_counters`:

| Column | Type | Notes |
|--------|------|-------|
| `registration_year` | INTEGER PK | Calendar year |
| `last_seq` | INTEGER NOT NULL DEFAULT 0 | Last issued sequence |
| `updated_at` | TIMESTAMPTZ | Maintenance |

Allocation algorithm (inside the same DB transaction as INSERT of the document):

1. `INSERT … ON CONFLICT DO NOTHING` to ensure counter row exists for the year.
2. `SELECT last_seq FROM … WHERE registration_year = :year FOR UPDATE`.
3. `new_seq = last_seq + 1`; `UPDATE … SET last_seq = new_seq`.
4. Build `registration_number = f"ВХ-{year}-{new_seq:04d}"`.
5. INSERT document with `registration_year`, `registration_seq`, `registration_number`.

The document INSERT and counter UPDATE commit atomically. Concurrent registrars block on `FOR UPDATE` for the same year.

### D3 — Idempotent replay

Foundation phase does not expose client-supplied idempotency keys. Safe replay is out of scope until a command-idempotency table is added (follow-up WP).

### D4 — No pre-reservation API

Numbers are issued only when a registration record is persisted. Preview/list endpoints never allocate sequences.

---

## Consequences

- Annual rollover is automatic (new counter row for new year).
- Uniqueness enforced at DB level on `registration_number` and `(registration_year, registration_seq)`.
- Tests must cover parallel registration (two connections, same year).
