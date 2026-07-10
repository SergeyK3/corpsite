# PE-003 Personnel Change Set Model

**Status:** Draft  
**Version:** 0.1

## Purpose

Define a universal representation of personnel changes.

A Change Set describes **what changed**, independent of the Personnel Event type.

---

# 1. Architecture

```
Personnel Event
      │
      ▼
Change Set
      │
      ├── Change #1
      ├── Change #2
      └── Change #N
```

One Personnel Event may contain multiple changes.

---

# 2. Change Record

Each change contains:

- field_name
- previous_value
- new_value
- effective_from
- effective_to
- source_event_id

---

# 3. Examples

## Transfer

| Field | Old | New |
|------|------|------|
| Department | Surgery | Cardiology |
| Position | Doctor | Head of Department |

## Rate Change

| Field | Old | New |
|------|------|------|
| FTE | 0.5 | 1.0 |

## Personal Data

| Field | Old | New |
|------|------|------|
| Surname | Ivanova | Petrova |

## Qualification

| Field | Old | New |
|------|------|------|
| Category | First | Highest |

---

# 4. Related Events

Change Sets may be linked through:

- Parent Event
- Related Event
- Generated Event

Example:

Leave
→ Temporary Assignment
→ Allowance

---

# 5. Principles

1. Every Personnel Event owns one Change Set.
2. A Change Set contains one or more atomic changes.
3. Change Sets reconstruct Personnel State.
4. Orders document Change Sets but do not replace them.
5. The model is extensible without database redesign.

---

# Relationship

```
Personnel Event
        │
        ▼
Personnel Change Set
        │
        ▼
Personnel State
```

---

# Revision History

- v0.1 Initial draft.
