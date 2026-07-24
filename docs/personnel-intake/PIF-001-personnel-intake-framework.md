# PIF-001 — Personnel Intake Framework

## Status

**Active (Architecture + partial implementation)** — architecture initiated 2026-07-08; production intake **partially implemented** as of 2026-07-24.

This document is the **architecture baseline**. Where production code and this document diverge, reconcile the document to match shipped behaviour (see snapshot below).

| Field | Value |
|-------|-------|
| Program | Personnel Intake Framework (PIF) |
| Predecessor (frozen) | [PMF Pilot Freeze](../personnel-migration/PMF-PILOT-FREEZE.md) |
| Target aggregate | Personal File ([ADR-047](../adr/ADR-047-personnel-personal-file-architecture.md)) |
| Identity policy | [ADR-048](../adr/ADR-048-person-ownership-identity-creation-policy.md) |
| Implementation | **Partial** — invitation, draft, form, HR on-behalf, re-edit, photo, preview-PDF |

### Implementation snapshot (production)

| Capability | Status |
|------------|--------|
| Invitation / token / personal link | ✅ Implemented |
| Draft / autosave | ✅ Implemented |
| Candidate & HR on-behalf electronic form | ✅ Implemented (static React; [PIF-003](./PIF-003-dynamic-form-model.md)) |
| Applicant re-edit after HR return | ✅ Implemented |
| Employee photo (secure storage) | ✅ Implemented ([PIF-PHOTO](./PIF-PHOTO-storage.md)) |
| Preview personal-card PDF at review | ✅ Implemented (**pre-commit** draft projection) |
| Intake commit → canonical `person_*` | ❌ Not implemented |
| Post-commit auto-generated PDF | ❌ Future ([PIF-7](./PIF-roadmap.md#pif-7-generated-documents)) |
| Metadata-driven FormDefinition | ❌ Future ([PIF-003](./PIF-003-dynamic-form-model.md)) |

**PDF:** production exposes **preview-PDF** on the review step (candidate token + HR on-behalf). **Post-commit** PDF from canonical personnel data is a **future PIF-7** deliverable, not current runtime behaviour.

Fundamental architecture document for **Personnel Intake Framework (PIF)** — программа электронного приёма кадровых данных.

---

## 1. Problem Statement

### 1.1. Текущий процесс (as-is)

```text
Новый сотрудник
  → заполняет бумажный «Личный листок по учёту кадров»
  → HR вручную переносит данные в Excel (контрольный список)
  → HR повторно переносит данные в кадровую систему
```

**Следствия:**

| Problem | Impact |
|---------|--------|
| Двойной (тройной) ввод | Потеря времени HR; ошибки транскрипции |
| Бумага как «источник» | Данные живут в документе, а не в структурированной модели |
| Задержка материализации Person | ADR-048: `person_id` часто NULL после operational enrollment |
| Фрагментация данных | Import JSONB, staging, employee snapshot — нет единого intake path |
| Нет self-service для кандидата | Кандидат не участвует в цифровом контуре |

### 1.2. Целевой процесс (to-be)

```text
HR / система
  → создаёт приглашение (Invitation)
  → кандидат получает персональную ссылку
  → заполняет электронную форму (Electronic Personal Sheet)
  → система валидирует (Validation)
  → формируется черновик (Draft)
  → HR проверяет (HR Review)
  → commit в кадровые данные (Commit)
  → материализуется Personnel Card (Personal File)
  → генерируются документы (Generated Documents)
```

**HR больше не переносит данные вручную.** HR **проверяет и подтверждает** структурированный ввод кандидата.

---

## 2. Главный принцип

> **Источник истины — не документ, а структурированные кадровые данные. Документы являются производными.**

| Layer | Role |
|-------|------|
| **Canonical Personnel Data** | Source of truth — typed sections keyed by `person_id` |
| **Intake Draft** | Pre-commit mutable state; candidate + HR editable within policy |
| **Generated Documents** | PDF / Excel / control sheet — **projections** from canonical data |
| **Import / PMF staging** | Legacy bootstrap paths — **not** SoT after commit |

Этот принцип согласован с [ADR-047 Four-Layer Model](../adr/ADR-047-appendix-four-layer-model.md): Import Layer ≠ Personal File; Control Sheet = export, not input authority.

---

## 3. Анализ «Личного листка» → каноническая модель

### 3.1. Почему не копировать бумажную форму

Официальный «Личный листок по учёту кадров» (Приложение № 2, методические рекомендации РК) и внутренний «Контрольный список Excel» — **разные документы** с разным покрытием (~45% overlap — см. [ADR-047 Appendix §2](../adr/ADR-047-appendix-four-layer-model.md)).

Копирование бумажной формы 1:1 в UI приводит к:

- жёстко запрограммированным экранам, непереносимым на другие формы;
- смешению pre-hire (анкета кандидата) и post-hire (послужной список, приказы) данных;
- дублированию полей control list и personal file без единой семантики.

**PIF проектируется вокруг канонической модели кадровых данных.** Бумажные и Excel-формы — **views** на эту модель.

### 3.2. Канонические домены данных (Personnel Data Domains)

Логическая декомпозиция, не привязанная к номерам пунктов бумажной формы:

| Domain | Canonical content | Intake-eligible | Primary consumers |
|--------|-------------------|-----------------|-------------------|
| **D1 — Identity** | ИИН, ФИО (текущее и прежние), пол, дата/место рождения | ✅ Candidate | Person, все формы |
| **D2 — Citizenship & Origin** | Гражданство, национальность | ✅ Candidate | Person, личный листок §6–7 |
| **D3 — Contact & Residence** | Адрес, телефон, email | ✅ Candidate | Person, contacts |
| **D4 — Identity Documents** | Удостоверение, паспорт, трудовая книжка (номера, даты) | ✅ Candidate | Person documents |
| **D5 — Photo & Biometrics** | Фото для личного дела | ✅ Candidate (upload) | Person, PDF export — **рамка 3×4 см** в preview-PDF |
| **D6 — Education** | ВУЗ, годы, специальность, квалификация, диплом | ✅ Candidate | `person_education` |
| **D7 — Languages** | Иностранные языки, уровень | ✅ Candidate | Person section |
| **D8 — Academic Titles** | Учёная степень, учёное звание | ⚠️ Optional at intake | Person section |
| **D9 — Pre-hire Employment** | Трудовая деятельность до приёма | ✅ Candidate | External employment history |
| **D10 — Family & Relatives** | Близкие родственники | ✅ Candidate | Person section |
| **D11 — Awards (pre-hire)** | Гос. награды до приёма | ⚠️ Optional | Person section |
| **D12 — Military** | Воинский учёт (базовый блок анкеты) | ✅ Candidate | Production intake step; полная форма Т-2 — отдельный контур |
| **D13 — In-org Career** | Назначения, переводы, приказы | ❌ HR-only post-hire | `person_assignments`, events |
| **D14 — Professional Credentials** | Сертификаты, категории, ПК | ⚠️ Partial (if known) | PMF / documents |
| **D15 — Declarations & Compliance** | Декларации, мед. допуски | ⚠️ Phase later | Staging / compliance |

### 3.3. Mapping: канон → производные формы

```text
                    ┌─────────────────────────────┐
                    │  Canonical Personnel Data   │
                    │  (person_id anchor)         │
                    └──────────────┬──────────────┘
                                   │
         ┌─────────────────────────┼─────────────────────────┐
         ▼                         ▼                         ▼
  Electronic Personal      Printed Personal         Control Sheet
  Sheet (intake form)      Sheet (PDF)              (Excel export)
         │                         │                         │
         │              Preview PDF (pre-commit, ✅)          │
         │              Post-commit PDF (PIF-7, future)       │
         │                         ▼                         │
         │                  Service Record                   │
         │                  (projection)                     │
         └─────────────────────────┴─────────────────────────┘
                                   │
                                   ▼
                         Other HR reports / gov forms
```

| Output form | Source domains | Direction |
|-------------|----------------|-----------|
| Electronic Personal Sheet (intake) | D1–D12 (+ D15 declarations; D13–D14 post-hire) | **Write → canonical draft** |
| Printed Personal Sheet PDF | All person-scoped domains | **Read ← canonical** (post-commit target); **preview ← draft** at review (✅ production) |
| Control Sheet Excel | Org roster snapshot + PF subset | **Read ← canonical / registry** |
| PMF Education migration | D6 (+ training fragments from import) | **Write ← staging bridge** |

---

## 4. Intake Pipeline

Общий pipeline PIF (domain-agnostic):

```text
Invitation
  ↓
Electronic Form
  ↓
Validation
  ↓
Draft
  ↓
HR Review
  ↓
Commit
  ↓
Personnel Card
  ↓
Generated Documents
```

### 4.1. Stage definitions

| Stage | Actor | Purpose | Mutable by |
|-------|-------|---------|------------|
| **Invitation** | HR / system | Создание intake case; персональная ссылка + token | HR |
| **Electronic Form** | Candidate | Self-service data entry | Candidate (within draft policy) |
| **Validation** | System | Schema, business rules, dictionaries | — |
| **Draft** | System | Persisted pre-commit aggregate | Candidate + HR (policy) |
| **HR Review** | HR operator | Verify, correct, request revision | HR |
| **Commit** | System + HR confirm | Atomic write to `person_*` / Person shell | HR (trigger) |
| **Personnel Card** | System | Materialized Personal File view | Read-only (post-commit policy) |
| **Generated Documents** | System | Preview PDF from draft at review (✅); post-commit PDF (future PIF-7) | — |

### 4.2. Relationship to PMF Commit Engine

PIF **Commit** и PMF **Commit** — разные entry points, **общий принцип**:

- atomic transaction;
- provenance on every write;
- `person_id` as owner;
- business events in `personnel_record_events`.

PIF Commit **не заменяет** PMF Commit Engine для import staging. PMF остаётся bridge Import → `person_*`. PIF — bridge Intake Draft → `person_*` (+ Person shell creation per ADR-048).

**Reuse candidate (future engineering, not in scope now):** provenance writer patterns, record event emitter, transaction boundary conventions from PMF-2.

---

## 5. Position относительно PMF

PMF переходит из «главного активного направления» в **один из источников данных** в экосystem Personnel.

```text
Personnel Data Intake
├── PMF (Legacy Control Sheet)
│     Import → Review → Migration Session → Commit → person_*
├── Electronic Personal Sheet          ← PIF (primary new path)
│     Invitation → Form → Draft → HR Review → Commit → person_*
├── Future Excel Import
│     Bulk spreadsheet → staging → review → commit
├── Future External HRIS
│     API / file exchange → normalization → commit
└── Future Government Integration
      eGov / national ID verification → enrichment
```

| Source | When used | SoT after commit |
|--------|-----------|-----------------|
| **PIF — Electronic Sheet** | New hire primary path | `person_*` |
| **PMF — Control List** | Legacy monthly import; education/cert bootstrap | `person_*` (per domain) |
| **Manual HR correction** | Post-commit amendments | `person_*` + provenance |
| **HR Events** | In-org career changes | Events + projections |

PMF Pilot Freeze: см. [PMF-PILOT-FREEZE.md](../personnel-migration/PMF-PILOT-FREEZE.md). PMF architecture **stable**; PIF **does not modify** PMF.

---

## 6. Personnel architecture map (updated)

```text
┌─────────────────────────────────────────────────────────────────────┐
│                     PERSONNEL DOMAIN                                 │
├─────────────────────────────────────────────────────────────────────┤
│  Identity & Ownership (ADR-048)                                      │
│    Person → person_id (permanent)                                     │
│    Employee → operational shell (0..N)                                │
│    Assignment → canonical employment episodes                         │
├─────────────────────────────────────────────────────────────────────┤
│  DATA INTAKE (PIF — active program)                                   │
│    Invitation / Token / Draft / HR Review / Intake Commit           │
│    Electronic Personal Sheet (static React in production; dynamic target PIF-003) │
├─────────────────────────────────────────────────────────────────────┤
│  DATA MIGRATION (PMF — frozen, pilot-ready)                           │
│    Import Layer → Review → Migration Session → PMF Commit             │
│    Domain plugins: Education (pilot), Service Record (future)         │
├─────────────────────────────────────────────────────────────────────┤
│  PERSONAL FILE (ADR-047 — target aggregate)                           │
│    Canonical sections: D1–D15                                         │
│    Personnel Card UI (read) / HR Processes UI (write)                 │
├─────────────────────────────────────────────────────────────────────┤
│  OUTPUT / PROJECTIONS                                                 │
│    Personal Sheet PDF (preview ✅) │ Control Sheet Excel │ Service Record          │
│    Post-commit Generated Documents (PIF-7 — future)                   │
├─────────────────────────────────────────────────────────────────────┤
│  OPERATIONAL CONTOUR                                                  │
│    employee_events │ enrollment │ documents │ tasks / Telegram        │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 7. Non-goals (PIF program initiation)

- Не проектировать UI экранов (→ PIF-002 concept only).
- Не проектировать БД и Alembic (→ PIF-2 engineering).
- Не менять PMF code, API, Commit Engine.
- Не заменять control list import — PMF остаётся для legacy bootstrap.
- Не реализовывать eGov integration в первой фазе.

---

## 8. Related documents

| Document | Role |
|----------|------|
| [PIF-002](./PIF-002-electronic-personal-sheet.md) | Electronic form concept |
| [PIF-003](./PIF-003-dynamic-form-model.md) | Dynamic form architecture |
| [PIF-004](./PIF-004-data-ownership.md) | Ownership and edit policy |
| [PIF-roadmap](./PIF-roadmap.md) | Work package sequence |
| [ADR-047](../adr/ADR-047-personnel-personal-file-architecture.md) | Personal File target |
| [ADR-047 Four-Layer Model](../adr/ADR-047-appendix-four-layer-model.md) | Layer separation |
| [ADR-048](../adr/ADR-048-person-ownership-identity-creation-policy.md) | Person creation at intake |
| [ADR-PMF-001](../adr/ADR-PMF-001-personnel-migration-framework.md) | PMF (frozen sibling program) |
| [ADR-045](../adr/ADR-045-personnel-hr-processes-split.md) | UI contour: view vs mutate |

---

## 9. Open decisions (for PIF-2+)

| # | Decision | Default recommendation |
|---|----------|------------------------|
| 1 | Person creation timing | At Invitation (shell) or at Commit (full) — ADR-048 alignment |
| 2 | Intake case entity name | `personnel_intake_cases` (TBD in PIF-2) |
| 3 | Draft storage model | Hybrid: typed core + JSONB extensions |
| 4 | Commit engine reuse vs fork | Shared provenance/event patterns; separate intake commit orchestrator |
| 5 | Mandatory intake domains for pilot | D1, D3, D4, D6, D9 (minimal hire package) |
