# PC-CONCEPT-001 — Ratification Package

## Unified Position Cabinet Concept — Architecture Ratification

---

## Document metadata

| Field | Value |
|-------|-------|
| **Package ID** | PC-CONCEPT-001-RAT |
| **Subject document** | [PC-CONCEPT-001 — Unified Position Cabinet Concept](./PC-CONCEPT-001-unified-position-cabinet-concept.md) **v0.4** |
| **Status** | **Prepared for ratification** — 2026-07-08 |
| **Runtime effect** | **None** until Decision Record (§11) is completed. Ratification does **not** amend Accepted ADR, Reviewed ACCESS documents, code, schema, or API. |
| **Approval authority** | Architecture Review Board + designated architecture sponsor |
| **Related inputs** | [PC-CONCEPT-001-review-notes](./PC-CONCEPT-001-review-notes.md); Architecture Review report (session 2026-07-08); Review-of-Review (M-01, M-04 analysis) |

---

## 1. Purpose

### 1.1. Назначение ратификации

Настоящий пакет собирает материалы для **формального утверждения** концептуальной архитектуры единого пользовательского рабочего пространства Corpsite HRIS, зафиксированной в **PC-CONCEPT-001 v0.4**.

Ратификация подтверждает, что:

- концепция **согласована** с Accepted baseline (ARCH-001, ADR-050, ADR-051, ADR-053, GLOSS-B4-001);
- разделение **domain entity** (Position Cabinet) и **presentation composition** (Unified User Workspace) принято как **стабильная** архитектурная рамка;
- Architecture Review **завершён**; принятые замечания **закрыты** в v0.4;
- открытые вопросы **осознанно отложены** и не блокируют утверждение concept layer.

### 1.2. Что утверждается

| # | Subject |
|---|---------|
| 1 | **Position Cabinet** остаётся domain entity 1:1 с org-unique Position — без изменения ADR-050 |
| 2 | **Unified User Workspace** как composition shell (не entity, не data owner) — successor к Personal UI Shell / «личный кабинет» |
| 3 | **Двухконтурная модель UWS:** Work Context + Self Services |
| 4 | **Work Context** как session-level view одного Cabinet (включая mapping к ADR-051 Active Cabinet Context) |
| 5 | **Self Services** как Person/Employee-scoped contour, независимый от Work Context |
| 6 | **Self Visibility** как **proposed** архитектурный принцип, ортогональный ACCESS-001 |
| 7 | Architectural invariants **INV-PC-001…012** и non-goals **NG-PC-001…008** PC-CONCEPT-001 v0.4 |
| 8 | Canonical access chain: Person → **Employment** → Position → Position Cabinet; Work Context — UX-шаг |

### 1.3. Что не утверждается

| # | Exclusion | Owner |
|---|-----------|-------|
| 1 | Amendment или override Accepted **ADR-050**, **ADR-051**, **ADR-053** | — forbidden by NG-PC-001 |
| 2 | Amendment **ACCESS-001** или слияние с Self Visibility | NG-PC-004; future ADR |
| 3 | Normative register **Self Visibility** (категории, defaults, enforcement) | OQ-PC-001, OQ-PC-002 |
| 4 | SQL, API, UI routes, RBAC enforcement, feature flags | NG-PC-005 |
| 5 | Permission Template binding rows, OPS-030 execution | ADR-053 / ACCESS program |
| 6 | Формальная таблица PC-MOD-001 module → contour | OQ-PC-005 / PC-MOD-001 v0.2 |
| 7 | Glossary register UWS / Work Context / Self Visibility | OQ-PC-004, OQ-PC-010 |
| 8 | Немедленная миграция `users.role_id` | NG-PC-006 |
| 9 | Любая **новая** domain entity или изменение entity model | Explicitly out of scope |

---

## 2. Scope

### 2.1. In scope (ratification boundary)

| Area | Detail |
|------|--------|
| **Concept layer** | Unified User Workspace, two-contour model, Workspace Composer pattern |
| **Entity vs view** | Position Cabinet (entity) ≠ UWS ≠ Work Context (views) |
| **Access presentation** | Employment / acting as sole Cabinet access paths; exception grants as overlay only |
| **Ownership boundaries** | Position-owned (Work Context modules) vs Employee-owned (Self Services) |
| **History split** | Cabinet History vs Personnel History |
| **Notifications split** | Cabinet operational (Work Context) vs Person inbox (Self Services) |
| **Multi-Employment UX** | Single active Work Context; Self Services invariant |
| **Traceability** | Alignment statements to ARCH-001, GLOSS-B4-001, PC-MOD-001 (directional) |

### 2.2. Out of scope (remains downstream)

| Area | Detail |
|------|--------|
| Implementation | Schema, migrations, `/auth/me` shape, route guards, UI shell build |
| Policy ratification | ACCESS-001 Approved status, contour binding rows |
| Product specification | PC-MOD module prioritization, navigation design |
| Personnel Orders MVP | OQ-PC-007 |
| HR admin dual-contour UX detail | OQ-PC-006 |
| Non-Position workspaces | Future ADR if ever needed (§14 PC-CONCEPT-001) |
| Code, DB, API, UI changes | Forbidden by ratification boundary |

---

## 3. Evolution Summary

Краткая история — только ключевые архитектурные вехи.

| Phase | Version / event | Key architectural change |
|-------|-----------------|---------------------------|
| **Initial draft** | v0.1 | Единое пользовательское пространство; риск смешения Position Cabinet и user shell |
| **Entity split** | v0.2 | **Unified User Workspace** введён как composition layer; двухконтурная модель; Self Visibility proposed; invariants |
| **Alignment pass** | v0.3 | Entity vs session view усилены; relationship matrix; anti-confusion rules; access chain formalized |
| **Architecture Review** | 2026-07-08 | Independent ARB review; verdict **Requires revision**; Major findings M-01…M-06 |
| **Review of Review** | 2026-07-08 | M-01 confirmed (terminology); M-04 **Rejected** as PC-CONCEPT defect (orthogonal axes) |
| **Remediation** | v0.4 | Employment canonical term; §4.1 baseline mapping; notifications split; M-04 documented as Reject+Defer; Self Visibility marked non-normative |

**Stable since review:** domain entity model (Position, Cabinet, Employment, Acting) **не изменялась** — правки v0.4 касались terminology, presentation mapping и documentation clarity.

---

## 4. Final Architecture Summary

Итоговая модель PC-CONCEPT-001 v0.4 (ratification subject):

### Position Cabinet

- **Domain entity**, 1:1 с org-unique Position (ADR-050, GLOSS-B4-001).
- Владеет position-owned data, Permission Template, Cabinet History.
- Переживает vacancy, acting, смену Person; доступ via Employment / acting only.
- **Не** UX shell.

### Unified User Workspace (UWS)

- **Composition shell** после login — **не** domain entity.
- Агрегирует Work Context + Self Services в одной точке входа.
- Maps to **Personal UI Shell** / «личный кабинет» (ARCH-001 §8).
- **Workspace Composer** компонует модули; **не** владеет business data.

### Work Context

- **Session-level active view** одного Position Cabinet внутри UWS.
- Subsumes **Active Cabinet Context** (ADR-051 §7) + presentation T1/T2 modules.
- Переключается при multi-Employment / acting; **не** меняет Effective Permission Set (union).
- **Не** entity; **не** data owner.

### Self Services

- **Person / Employee-scoped** contour в UWS.
- Employee-owned data (профиль, кадровая история, T3 modules, Person notification inbox).
- **Не** переключается при смене Work Context (INV-PC-004).

### Self Visibility

- **Proposed** принцип self-read к собственным Person/Employee данным.
- **Ортогонален** ACCESS-001 (доступ к чужим данным).
- **Не normative** до OQ-PC-001; **не** блокирует ratification concept layer.
- **Не** кодируется в Permission Template (NG-PC-003).

```text
Person → Employment → Position → Position Cabinet (domain)
                                      │
                                      ▼
                    Unified User Workspace (composition)
                    ├── Work Context    → view of ONE Cabinet
                    └── Self Services   → Person scope (fixed)
```

---

## 5. Key Architectural Decisions

Решения, утверждаемые ратификацией PC-CONCEPT-001 v0.4. **Не вводят новых решений** — фиксируют содержание subject document.

| # | Decision | Motivation | Consequences |
|---|----------|------------|--------------|
| **KD-1** | Position Cabinet = domain entity; UWS = composition shell | Устранить v0.1 конфликт «единое пространство» vs «кабинет должности»; сохранить ADR-050 | Implementation привязывает ops-объекты к Cabinet, не к User; UI строится как shell поверх Cabinet |
| **KD-2** | Два ортогональных контура: Work Context + Self Services | Разделить position-operational и employee-personal без merge ownership | Composer обязан сохранять contour boundaries; acting не даёт чужой Self Services identity |
| **KD-3** | Work Context = view, not entity | Предотвратить entity collapse (OQ-B4-001 risk) | Session state хранит active Cabinet selection; Cabinet lifecycle независим |
| **KD-4** | Employment / Занятие должности — единственный permanent access path | ARCH-001 §3.2 terminology; ADR-051 resolver chain | Документация и UX используют Employment; «назначение» для occupancy не применяется |
| **KD-5** | Acting = access overlay, not ownership | INV-B4-002, ADR-036, ADR-051 R7 | Временный доступ без миграции данных; acting Work Context labeled |
| **KD-6** | Self Visibility ⊥ ACCESS-001 | Self-read не должен проходить через матрицу чужих данных | Требуется отдельный ADR/register (OQ-PC-001) перед Self Services expansion |
| **KD-7** | Cabinet operational notifications ≠ Person inbox | M-06; разный ownership и routing | Два канала в Composer; R6, INV-PC-012 |
| **KD-8** | PC-MOD tier ≠ PC-CONCEPT contour (T3 → Self Services) | M-04 Reject; employee-owned data не следует Work Context | Formal mapping deferred OQ-PC-005; ownership tier PC-MOD не меняется |
| **KD-9** | Presentation unity ≠ authorization unity | INV-PC-011; HR dual-role users | Single nav допустим; evaluation contours остаются раздельными |
| **KD-10** | Exception grants extend permissions only (ADR-051 R17) | SW-7 remediation; no direct Person→Cabinet | Break-glass не создаёт vacancy Work Context |

---

## 6. Architecture Review Outcome

### 6.1. Initial verdict

| Field | Value |
|-------|-------|
| **Review date** | 2026-07-08 |
| **Subject version** | PC-CONCEPT-001 v0.3 |
| **Overall assessment** | **Requires revision** |
| **Rationale** | Domain model sound; Major gaps in terminology, presentation mapping, notifications, Self Visibility normative status |

### 6.2. Accepted findings (closed in v0.4)

| ID | Subject | Resolution |
|----|---------|------------|
| **M-01** | Position Assignment / «назначение» vs Employment | Employment / Занятие должности — primary term |
| **M-02** | Work Context vs Active Cabinet Context / Personal UI Shell | §4.1 baseline mapping |
| **M-03** | SW-7 undefined «admin access» | Acting only; exception grants per ADR-051 R17 |
| **M-05** | Self Visibility without normative home | Non-normative banner; §8.5 illustrative only |
| **M-06** | Notifications undefined split | Cabinet operational vs Person inbox; INV-PC-012 |
| **m-01** | Cabinet Owner in matrix | Matrix expanded §11 |
| **m-02** | Leave access restriction | §6.2 lifecycle |
| **m-03** | Union vs Work Context switch | SW-2a; §4.1 |
| **m-05** | ARCH-001 traceability | Full ARCH-001 in normative inputs |

### 6.3. Rejected findings

| ID | Subject | Disposition |
|----|---------|-------------|
| **M-04** | T3 PC-MOD «inside Cabinet» vs Self Services in PC-CONCEPT | **Rejected** as architectural defect of PC-CONCEPT. Orthogonal axes: PC-MOD catalog tier vs PC-CONCEPT presentation contour. T3 placement in Self Services **retained**. |

### 6.4. Deferred findings

| ID | Subject | Deferred to |
|----|---------|-------------|
| **M-04** (formal mapping) | Module → contour table | **OQ-PC-005** / PC-MOD-001 v0.2 |
| **Editorial** | OQ-PC-004 / OQ-PC-010 overlap | GLOSS-B4-002 work package |

### 6.5. Post-v0.4 assessment

| Field | Value |
|-------|-------|
| **Subject version** | PC-CONCEPT-001 v0.4 |
| **Critical findings** | **None open** |
| **Major findings (accepted)** | **All closed** |
| **Domain model changes after review** | **None** |

---

## 7. Open Questions

### 7.1. Non-blocking OQ (do not block ratification)

| ID | Question | Blocks ratification? | Future ADR | Implementation | Documentation |
|----|----------|---------------------|------------|----------------|---------------|
| **OQ-PC-003** | Default Work Context for multi-Employment | **No** — ADR-051 §7.3 interim precedence | ADR-051 policy annex | Session default selection | — |
| **OQ-PC-004** | UWS as glossary term | **No** | — | — | GLOSS-B4-002 |
| **OQ-PC-005** | PC-MOD module → contour map | **No** — directional §7.4 exists | — | Composer routing | PC-MOD-001 v0.2 |
| **OQ-PC-006** | HR admin dual-contour UX | **No** | — | UI architecture WP | — |
| **OQ-PC-007** | Personnel Orders module ownership | **No** | Personnel ADR | Module binding | — |
| **OQ-PC-008** | ARCH-001 §8 cross-reference | **No** — §4.1 partial | — | — | ARCH-001 hygiene amendment |
| **OQ-PC-010** | Glossary register Work Context vs Cabinet | **No** — §4.1 partial | — | — | GLOSS-B4-002 |

### 7.2. Future Architecture Work (blocks specific downstream, not concept ratification)

| ID | Question | Blocks ratification? | Blocks what | Track |
|----|----------|---------------------|-------------|-------|
| **OQ-PC-001** | Self Visibility normative home | **No** (concept) / **Yes** (Self Services product expansion) | Self Services modules beyond stubs | **New ADR** or ACCESS register |
| **OQ-PC-002** | Confidentiality taxonomy for self-read | **No** (concept) / **Yes** (Self Services policy) | Self Visibility enforcement | ADR + legal review |
| **OQ-PC-009** | Retention / legal hold vs Self Visibility | **No** (concept) | Compliance Self Services | Compliance ADR |

### 7.3. OQ disposition summary

| Category | Count | Ratification impact |
|----------|-------|---------------------|
| Non-blocking | 7 | May ratify concept **with follow-up documentation** |
| Future Architecture Work | 3 | Explicitly deferred; tracked in §8 Downstream Impact |
| Partially addressed in v0.4 | 2 (OQ-PC-008, OQ-PC-010) | Sufficient for concept gate; full closure in GLOSS/ARCH hygiene |

---

## 8. Downstream Impact

Документы, которые **могут потребовать** изменений **вследствие** утверждения PC-CONCEPT-001. **Изменения не выполняются** данным пакетом.

| Document | Likely change type | Trigger | Priority |
|----------|-------------------|---------|----------|
| **[PC-MOD-001](../access/PC-MOD-001-position-cabinet-functional-composition.md)** | Amendment v0.2 — contour column per module; diagram note for T3 | OQ-PC-005; KD-8 | High |
| **GLOSS-B4-002** (new register) | UWS, Work Context, Self Services, Self Visibility terms | OQ-PC-004, OQ-PC-010 | High |
| **[GLOSS-B4-001](../access/GLOSS-B4-001-position-cabinet-vocabulary.md)** | Cross-reference only — no amendment required for ratification | Traceability | Low |
| **[ARCH-001](../architecture/ARCH-001-position-permission-model.md)** | Optional §8 cross-reference to PC-CONCEPT-001 — **not** entity model change | OQ-PC-008 | Medium |
| **New ADR — Self Visibility** | Normative model, confidentiality binding | OQ-PC-001, OQ-PC-002 | High (before Self Services expansion) |
| **[ADR-051](../adr/ADR-051-cabinet-access-resolution.md)** | Policy annex — default Work Context selection | OQ-PC-003 | Medium |
| **Personal UI Shell ADR / WP** | Implementation of UWS, Composer, contour nav | Implementation phase | High (implementation) |
| **[ACCESS-001](../access/ACCESS-001-organizational-permission-matrix.md)** | **No amendment** until Self Visibility ADR reviewed (NG-PC-004) | OQ-PC-001 | — deferred |
| **ADR-050, ADR-053** | **No amendment** — concept preserves contracts | NG-PC-001 | None |
| **Personnel / Orders architecture** | Confirm Organization ownership for Work Context module | OQ-PC-007 | Medium |
| **Compliance ADR** | Retention vs Self Visibility | OQ-PC-009 | Low (until Self Services) |

---

## 9. Ratification Recommendation

### Recommendation: **Approved with follow-up documentation**

| Criterion | Assessment |
|-----------|------------|
| Architecture Review completed | **Yes** |
| Accepted findings resolved in v0.4 | **Yes** |
| Domain model stable | **Yes** — unchanged after review |
| Critical findings open | **None** |
| Accepted ADR contradiction | **None** |
| Open Questions reviewed | **Yes** — classified §7 |
| Downstream work identified | **Yes** — §8 |

### Обоснование

1. **PC-CONCEPT-001 v0.4** закрывает все принятые Major-замечания без изменения domain entity model.
2. Концепция **согласована** с ADR-050/051/053 и GLOSS-B4-001; вводит только **presentation/composition layer**, явно marked non-entity.
3. **Self Visibility** и formal PC-MOD mapping **сознательно отложены** — не блокируют утверждение concept layer, но требуют follow-up ADR и PC-MOD/GLOSS work **до** Self Services product expansion.
4. **M-04** отклонён как дефект PC-CONCEPT — ratification **не должна** менять T3 → Self Services placement.
5. **«Approved»** без оговорки было бы преждевременно из-за открытых OQ-PC-001/002 (Self Visibility) и OQ-PC-005 (PC-MOD formal map) — hence **with follow-up documentation**.

### Not recommended

| Verdict | Why not |
|---------|---------|
| **Deferred** | Review complete; no open critical findings; v0.4 addresses all accepted Major items |
| **Approved** (unconditional) | Self Visibility non-normative; GLOSS/PC-MOD formal alignment pending |
| **Rejected** | No remaining architectural contradiction with Accepted baseline |

---

## 10. Ratification Checklist

Complete before recording §11 Decision.

| # | Checklist item | Status |
|---|----------------|--------|
| 1 | Architecture Review completed | ☐ |
| 2 | Review-of-Review completed (M-01, M-04) | ☐ |
| 3 | Accepted findings resolved in PC-CONCEPT-001 v0.4 | ☐ |
| 4 | Domain model stable (no post-review entity changes) | ☐ |
| 5 | No unresolved **Critical** findings | ☐ |
| 6 | No unresolved **Major** findings (accepted scope) | ☐ |
| 7 | M-04 recorded as **Rejected + Deferred** — no T3 placement change | ☐ |
| 8 | Open Questions reviewed and classified (§7) | ☐ |
| 9 | Non-blocking OQ acknowledged by Review Board | ☐ |
| 10 | Downstream impact documents identified (§8) | ☐ |
| 11 | Ratification does **not** authorize implementation | ☐ |
| 12 | Ratification does **not** amend Accepted ADR or ACCESS-001 | ☐ |
| 13 | Subject document PC-CONCEPT-001 v0.4 reviewed as ratification artifact | ☐ |
| 14 | Approval authority identified | ☐ |

---

## 11. Decision Record

> **Template — to be completed upon ratification session.**

| Field | Value |
|-------|-------|
| **Decision** | |
| **Date** | |
| **Subject** | PC-CONCEPT-001 — Unified Position Cabinet Concept **v0.4** |
| **Package** | PC-CONCEPT-001-RAT (this document) |
| **Review participants** | |
| **Approved by** | |
| **Notes** | |

### Decision options (for session)

- ☐ **Approved** — PC-CONCEPT-001 v0.4 ratified as Architecture **Accepted** concept document
- ☐ **Approved with follow-up documentation** — ratified; §8 items tracked as mandatory follow-up (recommended)
- ☐ **Deferred** — reason: _______________
- ☐ **Rejected** — reason: _______________

### Upon approval — status change (manual)

| Artifact | New status (suggested) |
|----------|------------------------|
| PC-CONCEPT-001 v0.4 | Architecture **Accepted** (concept — no runtime effect) |
| This package | Decision recorded |

---

## Document history

| Date | Version | Change |
|------|---------|--------|
| 2026-07-08 | 0.1 | Initial ratification package — PC-CONCEPT-001 v0.4 |

---

## Traceability

| Artifact | Relationship |
|----------|--------------|
| [PC-CONCEPT-001 v0.4](./PC-CONCEPT-001-unified-position-cabinet-concept.md) | **Subject** — ratification artifact |
| [PC-CONCEPT-001-review-notes](./PC-CONCEPT-001-review-notes.md) | Pre-review backlog — largely superseded |
| [WP-B4-RATIFICATION-PACKAGE](../access/WP-B4-RATIFICATION-PACKAGE.md) | Structural reference for package format |
| [ARCHITECTURE_GOVERNANCE](../architecture/ARCHITECTURE_GOVERNANCE.md) | Baseline principles — unchanged by ratification |
