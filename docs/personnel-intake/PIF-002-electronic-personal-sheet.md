# PIF-002 — Electronic Personal Sheet

## Status

**Active (Concept + partial implementation)** — concept initiated 2026-07-08; production electronic intake form **partially implemented** as of 2026-07-24.

| Field | Value |
|-------|-------|
| Parent | [PIF-001](./PIF-001-personnel-intake-framework.md) |
| Form engine (target) | [PIF-003](./PIF-003-dynamic-form-model.md) — metadata-driven |
| Form engine (production) | Static React wizard + `INTAKE_STEPS` in `corpsite-ui` |
| Ownership rules | [PIF-004](./PIF-004-data-ownership.md) |
| UX reference | [PIF-2A](./PIF-2A-electronic-intake-ux-specification.md) (target UX; production = 9 steps) |
| Photo / PDF | [PIF-PHOTO](./PIF-PHOTO-storage.md); preview-PDF at review (pre-commit) |

---

## 1. Назначение

**Electronic Personal Sheet (EPS)** — self-service электронная анкета для **нового сотрудника** (кандидата на приём), через которую кандидат вводит структурированные кадровые данные до выхода на работу.

EPS **не является** копией бумажного «Личного листка по учёту кадров». EPS — **intake-oriented projection** канонической модели данных ([PIF-001 §3.2](./PIF-001-personnel-intake-framework.md)), содержащая домены, релевантные этапу приёма (D1–D12 в production, включая воинский учёт; D13–D14 — после приёма).

| Aspect | Paper form | EPS |
|--------|------------|-----|
| Primary user | Candidate (paper) + HR (transcription) | Candidate (direct digital input) |
| Data destination | Document file | Canonical draft → `person_*` |
| Post-hire sections | Included on same form | **Excluded** — filled via HR Events / supplements |
| Language | Single print locale | **RU / KZ** bilingual |
| Validation | Manual HR check only | System + HR review |

---

## 2. Основные разделы (intake scope)

Разделы EPS сгруппированы по **каноническим доменам**, не по номерам бумажной формы:

| EPS Section | Canonical domain | Typical fields | Required at intake |
|-------------|------------------|----------------|---------------------|
| **S1 — Personal identity** | D1 Identity | Фамилия, имя, отчество; прежние ФИО; ИИН; пол; дата рождения; место рождения | ✅ Core |
| **S2 — Citizenship** | D2 | Гражданство, национальность | ✅ Core |
| **S3 — Contact & address** | D3 | Адрес проживания, телефон, email | ✅ Core |
| **S4 — Identity documents** | D4 | № удостоверения/паспорта, дата выдачи, орган; трудовая книжка (если применимо) | ✅ Core |
| **S5 — Photo** | D5 | Загрузка фото (рамка **3×4 см** в preview-PDF) | ⚠️ Recommended |
| **S6 — Education** | D6 | Табличный блок: учебное заведение, годы, специальность, квалификация, № диплома | ✅ Core |
| **S7 — Languages** | D7 | Язык, уровень владения | Optional |
| **S8 — Academic titles** | D8 | Учёная степень, учёное звание | Optional |
| **S9 — Employment history** | D9 | Места работы до приёма: организация, должность, период | ✅ Core |
| **S10 — Family** | D10 | Близкие родственники: ФИО, степень родства, место работы | ⚠️ Configurable |
| **S11 — Awards** | D11 | Награды до приёма | Optional |
| **S12 — Declarations** | D15 | Согласие на обработку ПДн; достоверность данных | ✅ Core (compliance) |
| **S13 — Military (production)** | D12 | Воинский учёт — базовый блок | ✅ In production intake |

**Explicitly excluded from EPS (conceptual target):**

- D13 In-org career — формируется после приёма через кадровые события;
- D14 Professional credentials — может поступать позже через PMF или document registry.

**Note:** D12 Military **is included** in the current production intake form (S13). Full Т-2 automation remains a separate contour.

### 2.1. Mapping к бумажной форме (informative)

| Official form § | EPS section |
|-----------------|-------------|
| Фото | S5 |
| §1–5 (ФИО, пол, DOB, место рождения) | S1 |
| §6–7 (национальность, гражданство) | S2 |
| §8 (образование) | S6 |
| §9 (языки) | S7 |
| §10 (учёные степени) | S8 |
| §12 (трудовая деятельность) | S9 |
| §13 (родственники) | S10 |
| §14 (награды) | S11 |
| §11 (воинский учёт) | S13 (production) |
| §16 (адрес, телефон) | S3 |

---

## 3. Жизненный цикл EPS

```text
                    ┌──────────────┐
                    │  INVITED     │  HR создал case; ссылка отправлена
                    └──────┬───────┘
                           │ candidate opens link
                           ▼
                    ┌──────────────┐
                    │  IN_PROGRESS │  кандидат заполняет форму
                    └──────┬───────┘
                           │ candidate submits
                           ▼
                    ┌──────────────┐
                    │  SUBMITTED   │  validation passed; awaiting HR
                    └──────┬───────┘
                           │
              ┌────────────┼────────────┐
              │            │            │
              ▼            ▼            ▼
       ┌──────────┐ ┌──────────┐ ┌──────────┐
       │ REVISION │ │ APPROVED │ │ REJECTED │
       │ REQUESTED│ │ (ready   │ │ (case    │
       │          │ │  commit) │ │  closed) │
       └────┬─────┘ └────┬─────┘ └──────────┘
            │            │
            │            ▼
            │     ┌──────────────┐
            └────►│  COMMITTED   │  → Personnel Card
                  └──────────────┘
```

| State | Description |
|-------|-------------|
| `INVITED` | Token issued; form not yet opened |
| `IN_PROGRESS` | Candidate editing; autosave to draft |
| `SUBMITTED` | Candidate finalized section submission; HR queue |
| `REVISION_REQUESTED` | HR returned with comments; candidate may re-edit |
| `APPROVED` | HR accepted; ready for commit |
| `COMMITTED` | Data written to canonical personnel store |
| `REJECTED` | Case closed without commit (withdrawn hire) |
| `EXPIRED` | Token/link expired before completion |

---

## 4. Сценарий использования (happy path)

### 4.1. Actors

| Actor | Role |
|-------|------|
| **HR Operator** | Creates invitation, reviews, approves, triggers commit |
| **Candidate** | Fills electronic form via personal link |
| **System** | Validates, persists draft, generates documents post-commit |

### 4.2. Flow

1. **HR** создаёт intake case для планируемого приёма (минимум: expected hire date, org unit, position reference).
2. **System** генерирует **персональную ссылку** и **одноразовый token** (с TTL).
3. **HR** отправляет ссылку кандидату (email / messenger — out of scope).
4. **Candidate** открывает ссылку, проходит идентификацию по token (без полноценного user account).
5. **Candidate** заполняет разделы S1–S12; система **автосохраняет черновик**.
6. **Candidate** нажимает «Отправить на проверку» → **Validation** → state `SUBMITTED`.
7. **HR** открывает case в «Кадровые процессы», просматривает данные, при необходимости:
   - исправляет поля (within HR edit policy);
   - или возвращает на доработку (`REVISION_REQUESTED` + comment).
8. **Candidate** (при revision) получает уведомление, редактирует, повторно submit.
9. **HR** подтверждает (`APPROVED`) и инициирует **Commit**.
10. **System** материализует Person (если не существует), пишет section data, эмитит record events.
11. **System (future PIF-7):** генерирует **Printed Personal Sheet PDF** из **canonical** data после commit.

**Production today (pre-commit):** на шаге «Проверка» кандидат и HR могут сформировать **preview personal-card PDF** из текущего draft (не canonical projection). См. [PIF-PHOTO](./PIF-PHOTO-storage.md) и [PIF-roadmap §PIF-7](./PIF-roadmap.md#pif-7-generated-documents).

---

## 5. Персональная ссылка и token

| Property | Policy |
|----------|--------|
| Link format | Opaque URL: `/intake/{case_ref}?t={token}` (exact path TBD) |
| Token type | Cryptographically random, single-case bound |
| Token usage | **One-time activation** for initial access; session thereafter |
| TTL | Configurable (default 14 days); extendable by HR |
| Revocation | HR may revoke and re-issue |
| Re-open after submit | Allowed in `REVISION_REQUESTED` and `under_review` with section rework (✅ production) |
| Security | HTTPS only; token never logged in plain text; rate limiting |

**Not in scope:** full candidate user account, SSO, eGov digital signature (future).

---

## 6. Черновики (Draft)

| Aspect | Policy |
|--------|--------|
| Autosave | On field blur / interval while `IN_PROGRESS` or `REVISION_REQUESTED` |
| Draft owner | Intake case (not Person until commit) |
| Partial completion | Allowed; required fields enforced only on submit |
| HR visibility | HR may view draft in read-only before submit |
| Versioning | Each submit creates draft snapshot version for audit |
| Conflict | Single candidate session; last-write-wins within session |

Draft storage architecture — [PIF-003](./PIF-003-dynamic-form-model.md) + PIF-2 Data Model.

---

## 7. Возврат на доработку

| Field | Behavior |
|-------|----------|
| Trigger | HR action «Вернуть на доработку» |
| Required | HR comment (min length); optional per-section flags |
| Candidate notification | Out of band (email/SMS — integration TBD) |
| Editable sections | HR may mark all or specific sections |
| Re-submit | Same validation pipeline as initial submit |
| Audit | `REVISION_REQUESTED` event with comment + actor |

---

## 8. Финальное подтверждение HR

Commit **не выполняется автоматически** после submit.

| Gate | Requirement |
|------|-------------|
| HR Review complete | All mandatory sections validated |
| Explicit approval | HR clicks «Подтвердить и зафиксировать» |
| Confirm dialog | Summary of domains to be written; irreversibility notice |
| Person linkage | If `person_id` exists (rehire) — link; else create Person shell (ADR-048) |
| Post-commit | Case → `COMMITTED`; token invalidated |

Detailed ownership matrix — [PIF-004](./PIF-004-data-ownership.md).

---

## 9. Двуязычность (RU / KZ)

| Element | Localization approach |
|---------|----------------------|
| Section titles | Dictionary-driven ([PIF-003](./PIF-003-dynamic-form-model.md)) |
| Field labels | RU + KZ parallel labels |
| Help text / hints | Localized per locale |
| Validation messages | Localized |
| Candidate UI language | User-selectable RU ↔ KZ; preference stored on case |
| Data values | **Not translated** — candidate enters in preferred language; canonical storage with locale tag where applicable (e.g. org names) |
| Generated PDF | HR selects output locale or bilingual template (PIF-7) |

---

## 10. Relationship to other forms

| Form | Relationship to EPS |
|------|---------------------|
| Printed Personal Sheet | **Output (post-commit target)** — generated from canonical data after commit (PIF-7 future) |
| Preview personal-card PDF | **Output (✅ production)** — draft projection at review step, pre-commit |
| Control Sheet Excel | **Output** — org roster; not intake input |
| PMF Import Profile | **Sibling input** — legacy path for education/certs from control list |
| Supplement (Приложение № 1) | **Post-hire** — HR Events, not EPS |

---

## 11. Non-goals

- Wireframes, component library, responsive layout (superseded by production UI for pilot scope).
- Full Т-2 military registration automation (production collects a basic military block only).
- Email/SMS notification implementation.
- eGov identity verification.

---

## 12. Related documents

| Document | Role |
|----------|------|
| [PIF-001](./PIF-001-personnel-intake-framework.md) | Framework and canonical domains |
| [PIF-003](./PIF-003-dynamic-form-model.md) | Dynamic form generation |
| [PIF-004](./PIF-004-data-ownership.md) | Edit and commit policy |
| [PIF-roadmap](./PIF-roadmap.md) | PIF-4 Electronic Form WP |
| [ADR-047 Appendix §2](../adr/ADR-047-appendix-four-layer-model.md) | Official form section analysis |
