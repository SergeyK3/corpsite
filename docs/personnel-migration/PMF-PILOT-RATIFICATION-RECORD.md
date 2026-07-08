# PMF Pilot Ratification Record

## Метаданные

| Поле | Значение |
|------|----------|
| Документ | PMF-PILOT-RATIFICATION-RECORD |
| Дата ratification | 2026-07-08 |
| Scope reviewed | PMF-4A → PMF-4E (Personnel Migration Wizard) |
| Pilot domain | Education (`education`, `training` normalized records) |
| Review artifact | [PMF-PILOT-READINESS-REVIEW.md](./PMF-PILOT-READINESS-REVIEW.md) |
| Checklist | [PMF-PILOT-CHECKLIST.md](./PMF-PILOT-CHECKLIST.md) |

---

## 1. Решение

### **Pilot Ready with Recommendations**

Personnel Migration Wizard **готов к контролируемому пилотному запуску** Education domain при соблюдении обязательного входа через **Import Review CTA** и acceptance known limitations (§4).

---

## 2. Обоснование

### Соответствует требованиям пилота

- Полный HR path: Review → Transfer → Bootstrap → Candidate → Review Summary → Commit → Success
- Auto Draft Run без ручных действий HR
- Commit через существующий PMF-3B API / Commit Engine
- HR-first UX для commit, confirm, success, errors
- ADR-PMF-001 core invariants (wizard-only commit, person_id gate, review separation)
- Unit tests и production build проходят

### Не блокирует пилот (deferred to PMF-4F+)

- Split-view mapping UI
- Education verification tab
- Migration Home employee selection
- Run History / audit UI
- Void / Supersede UX
- Reconciliation mode

### Критические дефекты

**Не выявлены.**

---

## 3. Классификация замечаний

### Critical — 0

*Нет блокеров пилота.*

### Major — 6 (не блокируют)

| ID | Описание | WP |
|----|----------|-----|
| M-01 | Нет split-view field mapping | PMF-4F |
| M-02 | Нет Education tab | PMF-4F |
| M-03 | Migration Home employee picker disabled | PMF-4F |
| M-04 | run_not_draft без Success replay | PMF-4F |
| M-05 | Thin test coverage workspace/bootstrap | PMF-4F |
| M-06 | sessionStorage resume вместо list-runs API | PMF-3C/4F |

### Minor — 6 (не блокируют)

| ID | Описание |
|----|----------|
| m-01 | Nav «Миграция» vs «Перенос» |
| m-02 | Person blocker без remediation CTA |
| m-03 | Unused `MigrationWorkspaceSkeleton` |
| m-04 | Static `education_kind: "other"` in auto payload |
| m-05 | ADR URL shape documentation drift |
| m-06 | Duplicate stepper in blocker shell |

### Editorial — 3

| ID | Описание |
|----|----------|
| E-01 | PMF-4A не тегирован в frontend |
| E-02 | Skeleton placeholder phase labels |
| E-03 | `migrated` vs `promoted` status naming |

---

## 4. Pilot Operating Constraints

Эксплуатация пилота **должна** соблюдать:

1. **Entry:** только через Import Review CTA (approved + bound employee)
2. **Verify:** личная карточка (`/directory/staff`) или DB/admin до Education tab
3. **Scope:** 1–2 pilot employees с `person_id`
4. **Не использовать:** Migration Home «Выбрать сотрудника» (disabled)
5. **Support:** Technical Details для диагностики; raw errors не показывать HR

---

## 5. Polish Applied in Review

| File | Изменение |
|------|-----------|
| `personnelMigrationHrLabels.ts` | Person blocker — HR wording |
| `MigrationCandidateSourcePanel.tsx` | «Ключ записи» |
| `MigrationCandidateList.tsx` | «Запись №» |
| `MigrationSessionWorkspace.tsx` | Stepper «Записи» during adding |

**Backend / API / Schema / Alembic:** не изменялись.

---

## 6. Ratification Conditions

| Condition | Status |
|-----------|--------|
| PMF-PILOT-READINESS-REVIEW.md published | Done |
| PMF-PILOT-CHECKLIST.md published | Done |
| PMF-PILOT-RATIFICATION-RECORD.md published | Done |
| Pilot checklist executed on target environment | Pending |
| HR pilot lead sign-off | Pending |

---

## 7. Next Work Package — PMF-4F (recommended scope)

| Priority | Item |
|----------|------|
| P0 | Run History UI + committed session replay |
| P0 | Education tab + post-commit verify link |
| P1 | Split-view mapping (or enhanced Review Summary with field preview) |
| P1 | Migration Home employee picker |
| P1 | Workspace/bootstrap integration tests |
| P2 | Person remediation CTA |
| P2 | list-runs API integration (replace sessionStorage-only) |
| P3 | Void / Supersede UI |
| P3 | Reconciliation mode hooks |

---

## 8. Approval

| Role | Decision | Date | Notes |
|------|----------|------|-------|
| Engineering Review | **Pilot Ready with Recommendations** | 2026-07-08 | Automated review session |
| Architecture | Pending | | |
| HR Pilot Lead | Pending | | Execute checklist §B–G |

---

## 9. Revision History

| Version | Date | Change |
|---------|------|--------|
| 1.0 | 2026-07-08 | Initial pilot readiness ratification |
