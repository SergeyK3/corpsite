--------------------------------------------------

Document Status

Document:
WP-PPR-CARD-COORDINATION-001

Title:
PPR Card ↔ Intake — Field and Format Inventory

Type:
Architecture Work Package (inventory / gap analysis only)

Status:
Draft — HR Q1–Q7 approved; Q8 deferred (non-blocking)

Revision:
6

Date:
2026-07-24

Depends on:
WP-PR-003, WP-HR-CARD-002, ARCH-002, ARCH-003, ADR-054, WP-PPR-INTAKE-001/002 (implementation)

Purpose:
Полная инвентаризация полей, форматов, преобразований и расхождений между intake-анкетой и canonical PPR «Личной карточкой». Без реализации.

Out of scope:
Редактирование PPR из карточки, изменение API/БД/frontend, миграции, commit.

Reference dataset:
`tests/fixtures/ppr_reference_person.json` (fictional `telegram_ref_person_001`).

Evidence baseline:
Код и миграции на дату 2026-07-24; WP-PR-003 rev.2; WP-HR-CARD-002 rev.3; `docs-work/UEPC-Ubiquitous-Language.md`.

--------------------------------------------------

# WP-PPR-CARD-COORDINATION-001 — Field and Format Inventory

## 1. Назначение и границы

### 1.1 Роли представлений

| Представление | Роль | Каноничность |
|---------------|------|--------------|
| **Intake-анкета** (`corpsite-ui/app/intake/[token]/page.tsx`) | Канал ввода заявленных сведений сотрудником | **Не SoT**; JSONB `personnel_intake_drafts.payload` |
| **Intake кадровиком** (`corpsite-ui/app/directory/personnel/_components/PersonnelApplicationIntakeOnBehalfDrawer.tsx`) | Заполнение той же intake-анкеты от имени сотрудника | **Не SoT**; тот же payload + audit `LIFECYCLE_ACTION_INTAKE_EDITED_ON_BEHALF` |
| **Canonical PPR — Личная карточка** (`corpsite-ui/app/directory/personnel/persons/[personId]/card/page.tsx`) | Интерактивное представление подтверждённых person-owned кадровых фактов | **SoT** для materialized sections |
| **HR review / transfer** (`corpsite-ui/app/directory/personnel/_components/PersonnelApplicationIntakeReviewDrawer.tsx`) | Поэтапное принятие разделов и перенос в PPR | Промежуточный gate; audit `personnel_intake_transfers` |

### 1.2 Зафиксированные границы этапа

- Intake — proposal channel (`personnel_intake_drafts.payload` JSONB), не SoT.
- Canonical PPR — SoT после HR accept + `transfer_intake_to_ppr` (`app/personnel_intake/application/transfer_service.py`).
- On-behalf edit — тот же intake payload (`save_on_behalf_intake_draft` in `app/personnel_intake/application/on_behalf_edit_service.py`), не PPR mutation.
- Карточка: read via `GET /api/ppr/persons/{person_id}` (`app/api/ppr_router.py` → `PprQueryApplicationService.load_by_person_id`); partial write via `app/api/ppr_command_router.py` (employment biography, military).
- Данный WP — только инвентаризация и gap analysis; унификация UI и изменение контрактов — вне scope.

### 1.3 Расхождение документации и кода

| Тема | Архитектура | Реализация | Evidence |
|------|-------------|------------|----------|
| `PPR-GENERAL` extended attrs | WP-PR-003 §2.2 | `persons` без birth_place/citizenship/nationality/sex | `alembic/versions/u3v4w5x6y7z8_adr042_phase_b2_1_schema.py` CREATE TABLE persons |
| Contacts | `PPR-CONTACTS` | `personnel_applications.contact_mobile_phone`, `contact_email` | `docs/architecture/WP-PPR-APPLICANT-001A-personnel-application-data-model.md` §5.1 |
| UEPC Unified Spec file | Expected standalone spec | Not in repo | **Doc gap GAP-018**; formal replacement **deferred** (HR Q8, non-blocking) — see §12 |

---

## 2. Карта пользовательских представлений

| Представление | Route / component | Read source | Write handler | Evidence |
|---------------|-------------------|-------------|---------------|----------|
| Intake (applicant) | `corpsite-ui/app/intake/[token]/page.tsx` → `IntakePageClient` → `IntakeDraftFormEditor` | `open_intake_session` | `autosave_intake_draft`, `submit_intake_draft` | `app/api/personnel_intake_public_router.py` |
| Intake on-behalf | `corpsite-ui/app/directory/personnel/_components/PersonnelApplicationIntakeOnBehalfDrawer.tsx` | `load_on_behalf_edit_session` | `save_on_behalf_intake_draft` | `app/directory/personnel_intake_routes.py` |
| Intake review/transfer | `corpsite-ui/app/directory/personnel/_components/PersonnelApplicationIntakeReviewDrawer.tsx` | `load_intake_review_state` | `transfer_intake_to_ppr` | `app/personnel_intake/application/review_service.py`, `app/personnel_intake/application/transfer_service.py` |
| Canonical card | `corpsite-ui/app/directory/personnel/persons/[personId]/card/page.tsx` → `PprPersonalCardPageClient` | `PprQueryApplicationService.load_by_person_id` | `app/api/ppr_command_router.py` (partial) | `app/api/ppr_router.py`, `app/api/ppr_command_router.py` |

**Intake steps:** `INTAKE_STEPS` in `corpsite-ui/app/intake/_lib/intakeApi.client.ts` (9 entries).
**Card tabs:** `PPR_CARD_SECTIONS` in `corpsite-ui/lib/pprCardSections.ts` (13 entries).

**Tab visibility** (`PprPersonalCardPageClient.visibleCardSections`):

| Tab | Applicant (`hr_relationship_context === CANDIDATE`) | Employee (`resolvedEmployeeId` set) |
|-----|------------------------------------------------------|-------------------------------------|
| `intended_employment` | shown | hidden |
| `assignment`, `orders`, `onboarding` | hidden | shown |
| other tabs | shown | shown |

---

## 3. Матрица разделов

| Код раздела (domain) | Intake-шаг | Раздел canonical-карточки | Есть в intake | Есть в PPR UI | Есть в PPR-модели | Тип раздела | Расхождение |
|----------------------|------------|---------------------------|---------------|---------------|-------------------|-------------|-------------|
| `PPR-GENERAL` (partial) | `personal` | `general` | ✓ | ✓ partial | ✓ `persons` partial | Общие данные | Transfer пишет `full_name`, `birth_date`; не переносит birth_place/gender/citizenship/nationality |
| `PPR-PHOTO` | `personal.photo_file_id` | — | ✓ | ✗ | ✗ | Заполняемые сотрудником | Photo file storage only |
| `PPR-CONTACTS` | `contacts` phone/email | — | ✓ | ✗ | ✗ PPR; ✓ `personnel_applications` | Заполняемые + HR review | Episode snapshot (001A), не PPR column |
| `PPR-ADDRESSES` | `contacts` addresses | — | ✓ | ✗ | ✗ | Заполняемые | Intake JSONB only |
| `PPR-EDUCATION` | `education` | `education` | ✓ | ✓ | ✓ `person_education` | Заполняемые + HR review | Fingerprint `(education_kind, institution_name)`; card display year-only |
| `PPR-TRAINING` | `training` | `training` | ✓ | ✓ | ✓ `person_training` | Заполняемые + HR review | Transfer fixes `training_kind=course` |
| `PPR-FAMILY` | `relatives` | `family` | ✓ | ✓ | ✓ `person_relatives` | Заполняемые + HR review | Free-text relationship → enum via `map_relationship_type` (`app/personnel_intake/application/intake_mapper.py`) |
| `PPR-EMPLOYMENT-BIOGRAPHY` | `employment_biography` | `employment_biography` | ✓ | ✓ editable | ✓ `person_external_employment` | Заполняемые + HR review | No duplicate guard on add |
| `PPR-MILITARY` | `military` | `military` | ✓ | ✓ editable | ✓ `person_military_service` | Заполняемые + HR review | One active record; second create blocked |
| Additional JSONB | `additional.*` | `additional` | ✓ | ✓ | ✓ `personnel_record_metadata.additional_profile` | Заполняемые + HR review | Read merge order metadata-first |
| `AGGREGATE-ENVELOPE` | — | header + `general` | — | ✓ | ✓ `personnel_record_metadata` | Служебные | lifecycle, hr_relationship |
| Projections | — | `intended_employment`, `assignment`, `orders`, `applications`, `onboarding`, `changes` | ✗ | see §4.10–§4.15 | adjacent BC | Проекционные / аудиторские | Separate APIs; visibility by HR context |
| Planned (arch only) | ✗ | ✗ | ✗ | ✗ | ✗ | Отсутствующие | `PPR-IDENTITY-DOCUMENTS`, `PPR-NAME-HISTORY`, `PPR-MARITAL-STATUS` |

**Section count:** 9 intake steps + 13 card tabs + 8 PPR transfer sections + 6 projection tabs.

---

## 4. Реестр полей

**Правило:** одно бизнес-поле — одна строка.
**Cardinality:** `1` scalar; `0..N` per collection item; `derived` UI-only.
**Evidence column:** repo-relative path → function/class/DTO/table.column.
**Coverage claim:** реестр считается покрывающим перечисленные вкладки только если каждая вкладка представлена строками ниже либо явно помечена как недоступная в текущей реализации (hidden tab / API-only / unavailable).

### 4.1 `personal` → `PPR-GENERAL` / envelope (15 rows)

| # | Section | Business field | UI label | Intake path | PPR path | DB table.column | Card. | Intake ed. | HR ed. | Canonical | Required | Evidence |
|---|---------|----------------|----------|-------------|----------|-----------------|-------|------------|--------|-----------|----------|----------|
| 1 | personal | Photo file id | *(upload)* | `personal.photo_file_id` | — | photo storage (`PersonnelIntakePhoto`) | 1 | ✓ | ✓ | Not PPR | Optional | `corpsite-ui/app/intake/_components/IntakePhotoUpload.tsx` → `app/personnel_intake/application/photo_service.py` `save_intake_photo` |
| 2 | personal | Last name | Фамилия | `personal.last_name` | `PprGeneralResponse.last_name` | `public.persons.last_name` | 1 | ✓ | ✓ | `persons.full_name` via transfer only | Submit required | `corpsite-ui/app/intake/_components/IntakeDraftFormEditor.tsx` `StepPersonal` → `IntakeDraftPayload` (`corpsite-ui/app/intake/_lib/intakeApi.client.ts`) → `_validate_submit_payload` (`app/personnel_intake/application/intake_service.py`) → `_transfer_general_and_contacts` (`app/personnel_intake/application/transfer_service.py`) |
| 3 | personal | First name | Имя | `personal.first_name` | `PprGeneralResponse.first_name` | `public.persons.first_name` | 1 | ✓ | ✓ | Not updated on transfer | Submit required | `corpsite-ui/app/intake/_components/IntakeDraftFormEditor.tsx` `StepPersonal` → `_validate_submit_payload` (`app/personnel_intake/application/intake_service.py`) |
| 4 | personal | Middle name | Отчество | `personal.middle_name` | `PprGeneralResponse.middle_name` | `public.persons.middle_name` | 1 | ✓ | ✓ | Not updated on transfer | Optional | `corpsite-ui/app/intake/_components/IntakeDraftFormEditor.tsx` `StepPersonal` → `_validate_submit_payload` (`app/personnel_intake/application/intake_service.py`) |
| 5 | personal | Full name | ФИО | derived | `PprGeneralResponse.full_name` | `public.persons.full_name` | derived | — | — | `persons.full_name` | Derived | `app/personnel_intake/application/intake_mapper.py` `build_full_name` → `_transfer_general_and_contacts` (`app/personnel_intake/application/transfer_service.py`) |
| 6 | personal | Birth date | Дата рождения | `personal.birth_date` | `PprGeneralResponse.birth_date` | `public.persons.birth_date` DATE | 1 | ✓ | ✓ | `persons.birth_date` | Full day submit | `corpsite-ui/app/intake/_components/IntakeFormFields.tsx` `IntakeDateField` → `collect_intake_date_validation_errors` (`app/personnel_intake/domain/date_validation.py`) → `parse_date_value` (`app/personnel_intake/application/intake_mapper.py`) → `corpsite-ui/app/directory/personnel/_components/PprCardGeneralSection.tsx` `formatPprDate` |
| 7 | personal | Birth place | Место рождения | `personal.birth_place` | — | — | 1 | ✓ | ✓ | Intake JSONB only | Optional | `corpsite-ui/app/intake/_components/IntakeDraftFormEditor.tsx` `StepPersonal`; absent in `transfer_service._transfer_general_and_contacts` |
| 8 | personal | Gender | Пол | `personal.gender` | — | — | 1 | ✓ | ✓ | Intake JSONB only | Optional | `IntakeSelectField` + `INTAKE_GENDER_OPTIONS` in `corpsite-ui/app/intake/_lib/intakePersonalDictionary.ts` |
| 9 | personal | Citizenship | Гражданство | `personal.citizenship` | — | — | 1 | ✓ | ✓ | Intake JSONB only | Optional | `IntakeDictionaryCombobox` + `INTAKE_CITIZENSHIP_CATALOG` in `corpsite-ui/app/intake/_lib/intakePersonalDictionary.ts` |
| 10 | personal | Nationality | Национальность | `personal.nationality` | — | — | 1 | ✓ | ✓ | Intake JSONB only | Optional | `IntakeDictionaryCombobox` + `INTAKE_NATIONALITY_CATALOG` in `corpsite-ui/app/intake/_lib/intakePersonalDictionary.ts` |
| 11 | personal | Personnel number | Табельный номер | `personal.personnel_number` | — | — | 1 | HR-only | ✓ | Intake JSONB + photo filename | HR-only | `shouldShowIntakePersonnelNumberField` in `corpsite-ui/app/intake/_lib/intakePersonalFields.ts`; `build_intake_photo_archive_filename` in `app/personnel_intake/domain/photo_archive_name.py` |
| 12 | personal | Surname alphabet | Алфавит | derived | derived | — | derived | — | — | UI only | — | `deriveIntakeSurnameAlphabet` in `corpsite-ui/app/intake/_lib/intakePersonalFields.ts`; `corpsite-ui/app/directory/personnel/_components/PprCardGeneralSection.tsx` |
| 13 | envelope | IIN | ИИН | — | `PprGeneralResponse.iin` | `public.persons.iin` | 1 | ✗ | ✗ | `persons.iin` | CHECK 12 digits | `app/api/ppr_schemas.py` `PprGeneralResponse`; `chk_persons_iin_format` in `alembic/versions/u3v4w5x6y7z8_adr042_phase_b2_1_schema.py` |
| 14 | envelope | PPR lifecycle | Статус личной карточки | — | `PprMaterializationResponse.lifecycle_state` | `personnel_record_metadata.ppr_lifecycle_state` | 1 | ✗ | ✗ | Envelope | System | `corpsite-ui/app/directory/personnel/_components/PprCardGeneralSection.tsx`; `app/db/models/personnel_record_metadata.py` |
| 15 | envelope | HR relationship | Кадровая связь | — | `PprMaterializationResponse.hr_relationship_context` | `personnel_record_metadata.hr_relationship_context` | 1 | ✗ | ✗ | Envelope | System | `corpsite-ui/app/directory/personnel/_components/PprCardGeneralSection.tsx` `hrRelationshipLabel`; `app/ppr/domain/models.py` `HR_RELATIONSHIP_*` |

### 4.2 `contacts` (4 rows)

| # | Business field | UI label | Intake path | PPR path | DB table.column | Card. | Canonical | Required | Evidence |
|---|----------------|----------|-------------|----------|-----------------|-------|-----------|----------|----------|
| 16 | Mobile phone | Мобильный телефон | `contacts.mobile_phone` | — | `personnel_applications.contact_mobile_phone` | 1 | Episode snapshot | Submit required | `corpsite-ui/app/intake/_components/IntakeDraftFormEditor.tsx` `StepContacts` → `_validate_submit_payload` (`app/personnel_intake/application/intake_service.py`) → `_transfer_general_and_contacts` (`app/personnel_intake/application/transfer_service.py`) |
| 17 | Email | Email | `contacts.email` | — | `personnel_applications.contact_email` | 1 | Episode snapshot | Optional | `corpsite-ui/app/intake/_components/IntakeDraftFormEditor.tsx` `StepContacts` → `_transfer_general_and_contacts` (`app/personnel_intake/application/transfer_service.py`); `corpsite-ui/app/directory/personnel/_components/PersonnelApplicationDetailDrawer.tsx` |
| 18 | Registration address | Адрес регистрации | `contacts.registration_address` | — | — | 1 | Intake JSONB | Optional | `IntakeTextField` in `corpsite-ui/app/intake/_components/IntakeDraftFormEditor.tsx` `StepContacts` |
| 19 | Residence address | Адрес проживания | `contacts.residence_address` | — | — | 1 | Intake JSONB | Optional | `IntakeTextField` in `StepContacts`; `applyRegistrationToResidence` in `corpsite-ui/app/intake/_lib/intakeContactHelpers.ts` |

### 4.3 `education[]` → `PPR-EDUCATION` (11 rows)

| # | Business field | UI label | Intake path | PPR path | DB column | Card. | Evidence |
|---|----------------|----------|-------------|----------|-----------|-------|----------|
| 20 | Education kind | Вид образования | `education[i].education_type` | `PprEducationRecordResponse.education_kind` | `person_education.education_kind` | 0..N | `corpsite-ui/app/intake/_components/IntakeEducationTable.tsx` → `resolve_intake_education_kind` (`app/personnel_intake/domain/education_type.py`) → `map_education_records` (`app/personnel_intake/application/intake_mapper.py`) |
| 21 | Institution | Учебное заведение | `education[i].institution` | `institution_name` | `person_education.institution_name` | 0..N | `map_education_records` in `app/personnel_intake/application/intake_mapper.py` |
| 22 | Period start | Дата поступления | `education[i].year_from` | `started_at` | `person_education.started_at` | 0..N | `is_incomplete_intake_period_date` (`app/personnel_intake/domain/date_validation.py`) → `parse_date_value` (`app/personnel_intake/application/intake_mapper.py`) → `handle_add_education_record` (`app/ppr/domain/section_handlers.py`) |
| 23 | Period end | Дата окончания | `education[i].year_to` | `completed_at` | `person_education.completed_at` | 0..N | `is_incomplete_intake_period_date` (`app/personnel_intake/domain/date_validation.py`) → `parse_date_value` (`app/personnel_intake/application/intake_mapper.py`) → `handle_add_education_record` (`app/ppr/domain/section_handlers.py`) |
| 24 | Specialty | Специальность | `education[i].specialty` | `specialty` | `person_education.specialty` | 0..N | `corpsite-ui/app/directory/personnel/_components/PprCardEducationSection.tsx` |
| 25 | Qualification | Квалификация | `education[i].qualification` | `qualification` | `person_education.qualification` | 0..N | `corpsite-ui/app/directory/personnel/_components/PprCardEducationSection.tsx` |
| 26 | Document type | Документ | `education[i].document_type` | `metadata.document_type` | `person_education.metadata` JSONB | 0..N | `map_education_records` (`app/personnel_intake/application/intake_mapper.py`) metadata |
| 27 | Diploma number | № документа | `education[i].diploma_number` | `diploma_number` | `person_education.diploma_number` | 0..N | `PprEducationRecordResponse` in `app/api/ppr_schemas.py`; not rendered in `corpsite-ui/app/directory/personnel/_components/PprCardEducationSection.tsx` |
| 28 | Institution type | — | — | `institution_type` | `person_education.institution_type` | 0..N | `PprEducationRecordResponse` in `app/api/ppr_schemas.py`; no intake field |
| 29 | Document date | — | — | `document_date` | `person_education.document_date` | 0..N | `PprEducationRecordResponse` in `app/api/ppr_schemas.py`; no intake field |
| 30 | Lifecycle status | Статус | — | `lifecycle_status` | `person_education.lifecycle_status` | 0..N | `corpsite-ui/app/directory/personnel/_components/PprCardEducationSection.tsx` |

### 4.4 `training[]` → `PPR-TRAINING` (10 rows)

| # | Business field | Intake path | PPR path | DB column | Card. | Evidence |
|---|----------------|-------------|----------|-----------|-------|----------|
| 31 | Course name | `training[i].course_name` | `PprTrainingRecordResponse.title` | `person_training.title` | 0..N | `corpsite-ui/app/intake/_components/IntakeTrainingTable.tsx` → `map_training_records` (`app/personnel_intake/application/intake_mapper.py`) |
| 32 | Organization | `training[i].institution` | `organization_name` | `person_training.organization_name` | 0..N | `map_training_records` (`app/personnel_intake/application/intake_mapper.py`) |
| 33 | Period start | `training[i].year_from` | `started_at` | `person_training.started_at` | 0..N | `collect_intake_date_validation_errors` (`app/personnel_intake/domain/date_validation.py`) → `parse_date_value` (`app/personnel_intake/application/intake_mapper.py`) |
| 34 | Period end | `training[i].year_to` | `completed_at` | `person_training.completed_at` | 0..N | `resolveIntakeTrainingYearTo` in `corpsite-ui/app/intake/_lib/intakeTraining.ts`; `collect_intake_date_validation_errors` also reads legacy `year` |
| 35 | Legacy period end | `training[i].year` | maps to `completed_at` | — | 0..N | `map_training_records` (`app/personnel_intake/application/intake_mapper.py`) reads `year_to` or `year` |
| 36 | Document type | `training[i].document_type` | `metadata.document_type` | `person_training.metadata` JSONB | 0..N | `map_training_records` (`app/personnel_intake/application/intake_mapper.py`) defaults `"certificate"` |
| 37 | Document number | `training[i].document_number` | `certificate_number` | `person_training.certificate_number` | 0..N | `map_training_records` (`app/personnel_intake/application/intake_mapper.py`) |
| 38 | Hours | `training[i].hours` | `hours` | `person_training.hours` NUMERIC | 0..N | `Decimal(str(hours_raw))` in `map_training_records` (`app/personnel_intake/application/intake_mapper.py`) |
| 39 | Hours manual flag | `training[i].hours_is_manual` | `metadata.hours_is_manual` | `person_training.metadata` JSONB | 0..N | `resolveTrainingHoursState` in `corpsite-ui/app/intake/_lib/intakeTraining.ts` |
| 40 | Training kind | — *(fixed on transfer)* | `training_kind` | `person_training.training_kind` | 0..N | `TRAINING_KIND_COURSE` in `map_training_records` (`app/personnel_intake/application/intake_mapper.py`) |

### 4.5 `relatives[]` → `PPR-FAMILY` (7 rows)

| # | Business field | Intake path | PPR path | DB column | Card. | Evidence |
|---|----------------|-------------|----------|-----------|-------|----------|
| 41 | Relationship | `relatives[i].relationship` | `relationship_type` | `person_relatives.relationship_type` | 0..N | `corpsite-ui/app/intake/_components/IntakeRelativesTable.tsx` → `map_relationship_type` (`app/personnel_intake/application/intake_mapper.py`) |
| 42 | Full name | `relatives[i].full_name` | `full_name` | `person_relatives.full_name` | 0..N | `validate_relative_record` in `app/ppr/domain/section_record_validation.py` |
| 43 | Birth date | `relatives[i].birth_year` | `birth_date` | `person_relatives.birth_date` | 0..N | `map_relative_records` (`app/personnel_intake/application/intake_mapper.py`); path name mismatch (GAP-017) |
| 44 | Work place | `relatives[i].work_place` | `organization_name` | `person_relatives.organization_name` | 0..N | `corpsite-ui/app/directory/personnel/_components/PprCardFamilySection.tsx` |
| 45 | Birth place | — | `birth_place` | `person_relatives.birth_place` | 0..N | `corpsite-ui/app/directory/personnel/_components/PprCardFamilySection.tsx`; no intake |
| 46 | Residence address | — | `residence_address` | `person_relatives.residence_address` | 0..N | `corpsite-ui/app/directory/personnel/_components/PprCardFamilySection.tsx`; no intake |
| 47 | Notes | — | `notes` | `person_relatives.notes` | 0..N | `corpsite-ui/app/directory/personnel/_components/PprCardFamilySection.tsx`; no intake |

### 4.6 `employment_biography[]` → `PPR-EMPLOYMENT-BIOGRAPHY` (12 rows)

| # | Business field | Intake path | PPR path | DB column | Card. | Evidence |
|---|----------------|-------------|----------|-----------|-------|----------|
| 48 | Organization | `employment_biography[i].organization` | `employer_name` | `person_external_employment.employer_name` | 0..N | `corpsite-ui/app/intake/_components/IntakeEmploymentBiographyTable.tsx` → `map_employment_records` (`app/personnel_intake/application/intake_mapper.py`) |
| 49 | Position | `employment_biography[i].position` | `position_title` | `person_external_employment.position_title` | 0..N | `map_employment_records` (`app/personnel_intake/application/intake_mapper.py`) |
| 50 | Period start | `employment_biography[i].year_from` | `started_at` | `person_external_employment.started_at` | 0..N | `PersonnelDayDateField` in `corpsite-ui/app/intake/_components/IntakeEmploymentBiographyTable.tsx` |
| 51 | Period end | `employment_biography[i].year_to` | `ended_at` | `person_external_employment.ended_at` | 0..N | checkbox clears end in `corpsite-ui/app/intake/_components/IntakeEmploymentBiographyTable.tsx` |
| 52 | Termination reason | `employment_biography[i].reason_for_leaving` | `termination_reason` | `person_external_employment.termination_reason` | 0..N | `map_employment_records` (`app/personnel_intake/application/intake_mapper.py`) |
| 53 | Tenure record id | `employment_biography[i].record_id` | — | — | 0..N | `ensureEmploymentBiographyRecordId` in `corpsite-ui/app/intake/_lib/intakeEmploymentBiography.ts` |
| 54 | Record kind | fixed `episode` on transfer | `record_kind` | `person_external_employment.record_kind` | 0..N | `EXTERNAL_EMPLOYMENT_RECORD_KIND_EPISODE` in `map_employment_records` (`app/personnel_intake/application/intake_mapper.py`) |
| 55 | Department | — | `department_name` | `person_external_employment.department_name` | 0..N | `corpsite-ui/app/directory/personnel/_lib/pprEmploymentBiographyForm.ts`; card edit only |
| 56 | Employment type | — | `employment_type` | `person_external_employment.employment_type` | 0..N | `validate_external_employment_record` (`app/ppr/domain/section_record_validation.py`) |
| 57 | Document reference | — | `document_reference` | `person_external_employment.document_reference` | 0..N | `PprExternalEmploymentRecordResponse` in `app/api/ppr_schemas.py` |
| 58 | Source system | — | `source_system` | `person_external_employment.source_system` | 0..N | `app/db/models/personnel_migration.py` `PersonExternalEmployment` |
| 59 | Provenance | — | `provenance` | `person_external_employment.provenance` JSONB | 0..N | `PersonExternalEmployment.provenance` |

### 4.7 `military` → `PPR-MILITARY` (19 rows)

| # | Business field | Intake path | PPR path | DB column | Evidence |
|---|----------------|-------------|----------|-----------|----------|
| 60 | Registration status (intake label «Статус») | `military.status` | `registration_status` | `person_military_service.registration_status` | `IntakeMilitaryCombobox` → `map_military_record` (`app/personnel_intake/application/intake_mapper.py`) |
| 61 | Military rank | `military.rank` | `military_rank` | `person_military_service.military_rank` | `StepMilitary` in `corpsite-ui/app/intake/_components/IntakeDraftFormEditor.tsx` |
| 62 | Registration category (intake «Категория») | `military.category` | `registration_category` | `person_military_service.registration_category` | `map_military_record` (`app/personnel_intake/application/intake_mapper.py`) also reads `military.registration_category` |
| 63 | Personnel composition | `military.composition` | `personnel_composition` | `person_military_service.personnel_composition` | `INTAKE_MILITARY_COMPOSITION_CATALOG` in `corpsite-ui/app/intake/_lib/intakeMilitaryDictionary.ts` |
| 64 | VUS code | `military.specialty_code` | `military_specialty_code` | `person_military_service.military_specialty_code` | `sanitizeMilitarySpecialtyCodeInput` in `corpsite-ui/lib/militarySpecialtyCode.ts` |
| 65 | VUS name | `military.specialty_name` | `metadata.specialty_name` | `person_military_service.metadata` JSONB | `corpsite-ui/app/intake/_lib/intakeDraftReconcile.ts`; not in `StepMilitary` UI (GAP-019) |
| 66 | Fitness category | `military.fitness_category` | `fitness_category` | `person_military_service.fitness_category` | `IntakeMilitaryCombobox` in `corpsite-ui/app/intake/_components/IntakeDraftFormEditor.tsx` |
| 67 | Commissariat | `military.commissariat` | `commissariat_name` | `person_military_service.commissariat_name` | `StepMilitary` in `corpsite-ui/app/intake/_components/IntakeDraftFormEditor.tsx` |
| 68 | Registration group | `military.registration_group` | `metadata.registration_group` | `person_military_service.metadata` JSONB | `map_military_record` (`app/personnel_intake/application/intake_mapper.py`) metadata |
| 69 | Registration category (intake duplicate key) | `military.registration_category` | merged to `registration_category` | — | `map_military_record` (`app/personnel_intake/application/intake_mapper.py`) |
| 70 | Record kind | derived in mapper | `record_kind` | `person_military_service.record_kind` | `map_military_record` (`app/personnel_intake/application/intake_mapper.py`); `MILITARY_RECORD_KIND_*` in `app/personnel_intake/application/intake_mapper.py` |
| 71 | Obligation status | — | `obligation_status` | `person_military_service.obligation_status` | `corpsite-ui/app/directory/personnel/_lib/pprMilitaryServiceForm.ts`; card edit |
| 72 | Registered at | — | `registered_at` | `person_military_service.registered_at` | `corpsite-ui/app/directory/personnel/_components/PprCardMilitarySection.tsx` |
| 73 | Deregistered at | — | `deregistered_at` | `person_military_service.deregistered_at` | `corpsite-ui/app/directory/personnel/_components/PprCardMilitarySection.tsx` |
| 74 | Military ID book series | — | `military_id_book_series` | `person_military_service.military_id_book_series` | redacted read: `app/ppr/application/ppr_query_access_service.py` |
| 75 | Military ID book number | — | `military_id_book_number` | `person_military_service.military_id_book_number` | redacted read: `app/ppr/application/ppr_query_access_service.py` |
| 76 | Registration certificate series | — | `registration_certificate_series` | `person_military_service.registration_certificate_series` | redacted read: `app/ppr/application/ppr_query_access_service.py` |
| 77 | Registration certificate number | — | `registration_certificate_number` | `person_military_service.registration_certificate_number` | redacted read: `app/ppr/application/ppr_query_access_service.py` |
| 78 | Notes | — | `notes` | `person_military_service.notes` | `corpsite-ui/app/directory/personnel/_components/PprCardMilitarySection.tsx` |

### 4.8 `additional` → JSONB (26 rows)

| # | Business field | Intake path | PPR JSON path | Evidence |
|---|----------------|-------------|---------------|----------|
| 79 | Foreign language | `additional.foreign_languages[i].language` | `foreign_languages[].language` | `corpsite-ui/app/intake/_components/IntakeForeignLanguagesTable.tsx` → `normalize_foreign_language_entry` (`app/personnel_intake/domain/additional_profile.py`) |
| 80 | Language proficiency | `additional.foreign_languages[i].proficiency` | `foreign_languages[].proficiency` | `corpsite-ui/app/intake/_components/IntakeForeignLanguagesTable.tsx` |
| 81 | Languages none flag | `additional.foreign_languages_none` | `foreign_languages_none` | `corpsite-ui/app/intake/_components/IntakeAdditionalStep.tsx` |
| 82 | Award category | `additional.awards[i].category` | `awards[].category` | `corpsite-ui/app/intake/_components/IntakeAwardsTable.tsx` → `normalize_award_entry` (`app/personnel_intake/domain/additional_profile.py`) |
| 83 | Award name | `additional.awards[i].name` | `awards[].name` | `corpsite-ui/app/intake/_components/IntakeAwardsTable.tsx` |
| 84 | Award issued by | `additional.awards[i].issued_by` | `awards[].issued_by` | `corpsite-ui/app/intake/_components/IntakeAwardsTable.tsx` |
| 85 | Award date | `additional.awards[i].awarded_at` | `awards[].awarded_at` | `corpsite-ui/app/intake/_components/IntakeAwardsTable.tsx` |
| 86 | Award document number | `additional.awards[i].document_number` | `awards[].document_number` | `corpsite-ui/app/intake/_components/IntakeAwardsTable.tsx` |
| 87 | Award legacy title | `additional.awards[i].title` | migrated to category/name | `normalize_award_entry` in `app/personnel_intake/domain/additional_profile.py` |
| 88 | Awards none flag | `additional.awards_none` | `awards_none` | `corpsite-ui/app/intake/_components/IntakeAdditionalStep.tsx` |
| 89 | Academic degree | `additional.academic_degrees[i].degree` | `academic_degrees[].degree` | `corpsite-ui/app/intake/_components/IntakeAcademicDegreesTable.tsx` |
| 90 | Degree other | `additional.academic_degrees[i].degree_other` | `academic_degrees[].degree_other` | `corpsite-ui/app/intake/_components/IntakeAcademicDegreesTable.tsx` |
| 91 | Degree field of science | `additional.academic_degrees[i].field_of_science` | `academic_degrees[].field_of_science` | `corpsite-ui/app/intake/_components/IntakeAcademicDegreesTable.tsx` |
| 92 | Degree completed at | `additional.academic_degrees[i].completed_at` | `academic_degrees[].completed_at` | `corpsite-ui/app/intake/_components/IntakeAcademicDegreesTable.tsx` |
| 93 | Degree document number | `additional.academic_degrees[i].document_number` | `academic_degrees[].document_number` | `corpsite-ui/app/intake/_components/IntakeAcademicDegreesTable.tsx` |
| 94 | Degree legacy label | `additional.academic_degrees[i].label` | migrated on read | `corpsite-ui/app/intake/_lib/intakeAdditional.ts` |
| 95 | Degree legacy type | `additional.academic_degrees[i].degree_type` | migrated to field_of_science | `corpsite-ui/app/intake/_lib/intakeAdditional.ts` |
| 96 | Academic degrees none | `additional.academic_degrees_none` | `academic_degrees_none` | `corpsite-ui/app/intake/_components/IntakeAdditionalStep.tsx` |
| 97 | Academic title | `additional.academic_titles[i].academic_title` | `academic_titles[].academic_title` | `corpsite-ui/app/intake/_components/IntakeAcademicTitlesTable.tsx` |
| 98 | Title other | `additional.academic_titles[i].academic_title_other` | `academic_titles[].academic_title_other` | `corpsite-ui/app/intake/_components/IntakeAcademicTitlesTable.tsx` |
| 99 | Title field of science | `additional.academic_titles[i].field_of_science` | `academic_titles[].field_of_science` | `corpsite-ui/app/intake/_components/IntakeAcademicTitlesTable.tsx` |
| 100 | Title completed at | `additional.academic_titles[i].completed_at` | `academic_titles[].completed_at` | `corpsite-ui/app/intake/_components/IntakeAcademicTitlesTable.tsx` |
| 101 | Title document number | `additional.academic_titles[i].document_number` | `academic_titles[].document_number` | `corpsite-ui/app/intake/_components/IntakeAcademicTitlesTable.tsx` |
| 102 | Title legacy label | `additional.academic_titles[i].label` | migrated on read | `corpsite-ui/app/intake/_lib/intakeAdditional.ts` |
| 103 | Title legacy degree_type | `additional.academic_titles[i].degree_type` | migrated on read | `corpsite-ui/app/intake/_lib/intakeAdditional.ts` |
| 104 | Academic titles none | `additional.academic_titles_none` | `academic_titles_none` | `corpsite-ui/app/intake/_components/IntakeAdditionalStep.tsx` |

### 4.9 Wizard meta (1 row)

| # | Business field | Intake path | Evidence |
|---|----------------|-------------|----------|
| 105 | Current wizard step | `current_step` | `corpsite-ui/app/intake/_components/IntakeDraftFormEditor.tsx`; persisted by `autosave_intake_draft` in `app/personnel_intake/application/intake_service.py` |

### 4.10 Projection — `intended_employment` (7 rows)

**Availability:** shown only for applicant (`PprPersonalCardPageClient.visibleCardSections`); hidden for employee.

| # | Business field | UI label | API/DTO path | DB / source | Card UI | Evidence |
|---|----------------|----------|--------------|-------------|---------|----------|
| 106 | Org group id | Группа подразделений | `PprIntendedEmploymentResponse.org_group_id` | `personnel_record_metadata.intended_org_group_id` | rendered | `corpsite-ui/app/directory/personnel/_components/PprCardIntendedEmploymentSection.tsx`; `PATCH /api/ppr/persons/{id}/intended-employment` |
| 107 | Org group name | Группа подразделений | `org_group_name` | join projection | rendered | `app/api/ppr_schemas.py` `PprIntendedEmploymentResponse` |
| 108 | Org unit id | Подразделение | `org_unit_id` | `personnel_record_metadata.intended_org_unit_id` | rendered | `app/api/ppr_schemas.py` `PprIntendedEmploymentResponse` |
| 109 | Org unit name | Подразделение | `org_unit_name` | join projection | rendered | `app/api/ppr_schemas.py` `PprIntendedEmploymentResponse` |
| 110 | Position id | Должность | `position_id` | `personnel_record_metadata.intended_position_id` | rendered | `app/api/ppr_schemas.py` `PprIntendedEmploymentResponse` |
| 111 | Position name | Должность | `position_name` | join projection | rendered | `app/api/ppr_schemas.py` `PprIntendedEmploymentResponse` |
| 112 | Employment rate | Размер ставки | `employment_rate` | `personnel_record_metadata.intended_employment_rate` NUMERIC(4,2) | rendered | `PprIntendedEmploymentUpdateRequest` in `app/api/ppr_schemas.py` |

### 4.11 Projection — `applications` (24 rows)

**Availability:** tab always listed when person resolved. Card uses `GET /api/ppr/persons/{person_id}/applications` (`getPersonApplicationsHistory` in `corpsite-ui/app/directory/personnel/_lib/personnelApplicationsApi.client.ts`) → `PprPersonnelApplicationItemResponse` (`app/api/ppr_schemas.py`). UI also reads name fields that are **not** in that response model.

| # | Business field | UI label | API/DTO path | DB / source | Card UI | Evidence |
|---|----------------|----------|--------------|-------------|---------|----------|
| 113 | Application status | Статус | `PprPersonnelApplicationItemResponse.status` | `personnel_applications.status` | rendered | `corpsite-ui/app/directory/personnel/_components/PprCardApplicationsSection.tsx` + `PersonnelApplicationStatusBadge` |
| 114 | Application received date | Дата | `application_received_at` | `personnel_applications.application_received_at` DATE | rendered | `formatPersonnelApplicationDate` in `corpsite-ui/app/directory/personnel/_lib/personnelApplicationLabels.ts` |
| 115 | Intended org group id | *(placement ids)* | `intended_org_group_id` | `personnel_applications.intended_org_group_id` | API-only on card | `PprPersonnelApplicationItemResponse` |
| 116 | Intended org unit id | *(placement ids)* | `intended_org_unit_id` | `personnel_applications.intended_org_unit_id` | API-only on card | `PprPersonnelApplicationItemResponse` |
| 117 | Intended position id | *(placement ids)* | `intended_position_id` | `personnel_applications.intended_position_id` | API-only on card | `PprPersonnelApplicationItemResponse` |
| 118 | Intended org group name | Предполагаемое место работы | UI expects `intended_org_group_name` | join name | **unavailable** on this endpoint | `formatIntendedPlacement` in `corpsite-ui/app/directory/personnel/_components/PprCardApplicationsSection.tsx`; name not in `PprPersonnelApplicationItemResponse` |
| 119 | Intended org unit name | Предполагаемое место работы | UI expects `intended_org_unit_name` | join name | **unavailable** on this endpoint | `formatIntendedPlacement`; usually shows «—» |
| 120 | Intended position name | Предполагаемое место работы | UI expects `intended_position_name` | join name | **unavailable** on this endpoint | `formatIntendedPlacement`; usually shows «—» |
| 121 | Registered by user id | HR | `registered_by_user_id` | `personnel_applications.registered_by_user_id` | rendered as `#id` fallback | `corpsite-ui/app/directory/personnel/_components/PprCardApplicationsSection.tsx` |
| 122 | Registered by name | HR | UI expects `registered_by_name` | users join | **unavailable** on this endpoint | `corpsite-ui/app/directory/personnel/_components/PprCardApplicationsSection.tsx`; name not in `PprPersonnelApplicationItemResponse` |
| 123 | Registered at | HR (subline) | `registered_at` | `personnel_applications.registered_at` TIMESTAMPTZ | rendered | `formatPersonnelApplicationDateTime` |
| 124 | Application id | Открыть | `application_id` | `personnel_applications.application_id` | link only | `buildPersonnelApplicationsJournalHref` |
| 125 | Episode mobile phone | — | `contact_mobile_phone` | `personnel_applications.contact_mobile_phone` | API-only (not card column) | `PprPersonnelApplicationItemResponse` |
| 126 | Episode email | — | `contact_email` | `personnel_applications.contact_email` | API-only | `PprPersonnelApplicationItemResponse` |
| 127 | Application source | — | `application_source` | `personnel_applications.application_source` | API-only | `PprPersonnelApplicationItemResponse` |
| 128 | Vacancy check status | — | `vacancy_check_status` | `personnel_applications.vacancy_check_status` | API-only | `PprPersonnelApplicationItemResponse` |
| 129 | Vacancy checked at | — | `vacancy_checked_at` | `personnel_applications.vacancy_checked_at` | API-only | `PprPersonnelApplicationItemResponse` |
| 130 | Vacancy checked by | — | `vacancy_checked_by_user_id` | `personnel_applications.vacancy_checked_by_user_id` | API-only | `PprPersonnelApplicationItemResponse` |
| 131 | Intended employment rate | — | `intended_employment_rate` | `personnel_applications.intended_employment_rate` | API-only | `PprPersonnelApplicationItemResponse` |
| 132 | Intended vacancy text | — | `intended_vacancy_text` | `personnel_applications.intended_vacancy_text` | API-only | `PprPersonnelApplicationItemResponse` |
| 133 | Director resolution status | — | `director_resolution_status` | `personnel_applications.director_resolution_status` | API-only | `PprPersonnelApplicationItemResponse` |
| 134 | Director resolution at | — | `director_resolution_at` | `personnel_applications.director_resolution_at` | API-only | `PprPersonnelApplicationItemResponse` |
| 135 | Director resolution by | — | `director_resolution_by_user_id` | `personnel_applications.director_resolution_by_user_id` | API-only | `PprPersonnelApplicationItemResponse` |
| 136 | Director resolution note | — | `director_resolution_note` | `personnel_applications.director_resolution_note` | API-only | `PprPersonnelApplicationItemResponse` |

### 4.12 Projection — `changes` (8 rows)

**Availability:** always with PPR composite; list limited to last 10 (`PprEventSummaryReader.DEFAULT_LIMIT`).

| # | Business field | UI label | API/DTO path | DB / source | Card UI | Evidence |
|---|----------------|----------|--------------|-------------|---------|----------|
| 137 | Event type | *(title)* | `PprEventSummaryItemResponse.event_type` | `personnel_record_events.event_type` | rendered | `pprEventTypeLabel` in `corpsite-ui/app/directory/personnel/_lib/pprCardPresentation.ts` |
| 138 | Event timestamp | *(subline)* | `occurred_at` | `personnel_record_events.event_at` TIMESTAMPTZ | rendered | `formatPprDateTime` in `corpsite-ui/app/directory/personnel/_lib/pprCardPresentation.ts`; `app/ppr/read/event_summary_reader.py` |
| 139 | Section code | *(subline suffix)* | `section_code` | `personnel_record_events.event_payload` JSONB | rendered if present | `corpsite-ui/app/directory/personnel/_components/PprCardEventHistorySection.tsx` |
| 140 | Event id | — | `event_id` | `personnel_record_events.event_id` | API-only (React key) | `PprEventSummaryItemResponse` |
| 141 | Category | — | `category` | `personnel_record_events` / payload | API-only | `PprEventSummaryItemResponse` |
| 142 | Record table | — | `record_table_name` | `personnel_record_events.record_table_name` | API-only | `PprEventSummaryItemResponse` |
| 143 | Record id | — | `record_id` | `personnel_record_events.record_id` | API-only | `PprEventSummaryItemResponse` |
| 144 | Domain code | — | `domain_code` | event payload | API-only | `PprEventSummaryItemResponse` |

### 4.13 Projection — `assignment` (10 rows)

**Availability:** employee tab only (`!isApplicant && resolvedEmployeeId`); hidden for applicant. Not PPR SoT — Operational Directory / Employment BC.

| # | Business field | UI label | API/DTO path | DB / source | Card UI | Evidence |
|---|----------------|----------|--------------|-------------|---------|----------|
| 145 | Org group name | Группа отделений | derived `groupName` | `department_groups.group_name` via org tree | rendered | `corpsite-ui/app/directory/personnel/_components/EmployeeOperationalAssignmentSection.tsx` + `findOrgGroupIdForUnit` (`corpsite-ui/lib/userCreateOrgScope.ts`) + `fetchDepartmentGroups` (`corpsite-ui/lib/orgScope.ts`) |
| 146 | Org unit name | Отделение | `EmployeeDetails.org_unit.name` | `employees.org_unit_id` → `org_units` | rendered | `employeeOrgUnitLabel` in `corpsite-ui/lib/employeeOperationalAssignment.ts` |
| 147 | Position name | Кадровая должность | `EmployeeDetails.position.name` | `employees.position_id` → `positions` | rendered | `employeePositionLabel` in `corpsite-ui/lib/employeeOperationalAssignment.ts` |
| 148 | Enrollment status | Статус зачисления в Operational Directory | derived from org_unit+position+`status` | `employees.*` | rendered | `enrollmentStatusLabel` / `isOperationallyEnrolled` / `isActiveEmployee` in `corpsite-ui/app/directory/personnel/_components/EmployeeOperationalAssignmentSection.tsx` |
| 149 | Org unit id | Подразделение * (correction) | correction payload `org_unit_id` | `employees.org_unit_id` | correction drawer | `corpsite-ui/app/directory/personnel/_components/EmployeeAssignmentCorrectionDrawer.tsx` → `correctEmployee` |
| 150 | Position id | Должность * (correction) | `position_id` | `employees.position_id` | correction drawer | `corpsite-ui/app/directory/personnel/_components/EmployeeAssignmentCorrectionDrawer.tsx` |
| 151 | Employment rate | Ставка * (correction) | `employment_rate` ← `details.rate` | `employees.rate` | correction drawer | `corpsite-ui/app/directory/personnel/_components/EmployeeAssignmentCorrectionDrawer.tsx` |
| 152 | Assignment date from | Дата начала (correction) | `date_from` | `employees.date_from` | correction drawer | `corpsite-ui/app/directory/personnel/_components/EmployeeAssignmentCorrectionDrawer.tsx` |
| 153 | Assignment date to | Дата окончания (correction) | `date_to` | `employees.date_to` | correction drawer | `corpsite-ui/app/directory/personnel/_components/EmployeeAssignmentCorrectionDrawer.tsx` |
| 154 | Enroll-from-card workflow | Зачисление | import normalized record | import batch | **unavailable on PPR card path** when `batchId={null}` | `EmployeeOperationalAssignmentSection.handleOpenEnrollDrawer` message «Не удалось определить batch…» |

### 4.14 Projection — `orders` (17 rows)

**Availability:** employee tab only; hidden for applicant. Empty state is not a stub («Приказов по этому сотруднику пока нет…»).

| # | Business field | UI label | API/DTO path | DB / source | Card UI | Evidence |
|---|----------------|----------|--------------|-------------|---------|----------|
| 155 | Order number | № приказа | `PersonnelOrderListItem.order_number` | `personnel_orders.order_number` | rendered when present; else UI falls back to row 156 | `corpsite-ui/app/directory/personnel/_components/EmployeeCardOrdersSection.tsx`; `listPersonnelOrders` in `corpsite-ui/app/directory/personnel/_lib/personnelOrdersApi.client.ts` |
| 156 | Order id | `Приказ #{id}` (fallback label) | `PersonnelOrderListItem.order_id` | `personnel_orders.order_id` | rendered as fallback when `order_number` empty | `corpsite-ui/app/directory/personnel/_components/EmployeeCardOrdersSection.tsx`; `listPersonnelOrders` in `corpsite-ui/app/directory/personnel/_lib/personnelOrdersApi.client.ts` |
| 157 | Order date | от {date} | `PersonnelOrderListItem.order_date` | `personnel_orders.order_date` DATE | rendered | `formatPersonnelOrderDate` in `corpsite-ui/app/directory/personnel/_lib/personnelOrdersApi.client.ts` |
| 158 | Order type | Тип (Приём / …) | `PersonnelOrderListItem.order_type_code` | `personnel_orders.order_type_code` | rendered | `orderTypeLabel` in `corpsite-ui/app/directory/personnel/_components/EmployeeCardOrdersSection.tsx` |
| 159 | Order status | Статус | `PersonnelOrderListItem.status` | `personnel_orders.status` | rendered | `personnelOrderStatusLabel` in `corpsite-ui/app/directory/personnel/_lib/personnelOrdersApi.client.ts` |
| 160 | Order class | — | `PersonnelOrderListItem.order_class` | `personnel_orders.order_class` | API-only | `PersonnelOrderListItem` in `corpsite-ui/app/directory/personnel/_lib/personnelOrdersApi.client.ts` |
| 161 | Source mode | — | `PersonnelOrderListItem.source_mode` | `personnel_orders.source_mode` | API-only | `PersonnelOrderListItem` in `corpsite-ui/app/directory/personnel/_lib/personnelOrdersApi.client.ts` |
| 162 | Legal basis article | — | `PersonnelOrderListItem.legal_basis_article` | `personnel_orders.legal_basis_article` | API-only | `PersonnelOrderListItem` in `corpsite-ui/app/directory/personnel/_lib/personnelOrdersApi.client.ts` |
| 163 | Signed by name | — | `PersonnelOrderListItem.signed_by_name` | order signer join fields | API-only | `PersonnelOrderListItem` in `corpsite-ui/app/directory/personnel/_lib/personnelOrdersApi.client.ts` |
| 164 | Signed by position | — | `PersonnelOrderListItem.signed_by_position` | order signer join fields | API-only | `PersonnelOrderListItem` in `corpsite-ui/app/directory/personnel/_lib/personnelOrdersApi.client.ts` |
| 165 | Executor name | — | `PersonnelOrderListItem.executor_name` | `personnel_orders.executor_name` | API-only | `PersonnelOrderListItem` in `corpsite-ui/app/directory/personnel/_lib/personnelOrdersApi.client.ts` |
| 166 | Basis summary | — | `PersonnelOrderListItem.basis_summary` | `personnel_orders.basis_summary` | API-only | `PersonnelOrderListItem` in `corpsite-ui/app/directory/personnel/_lib/personnelOrdersApi.client.ts` |
| 167 | Comment | — | `PersonnelOrderListItem.comment` | `personnel_orders.comment` | API-only | `PersonnelOrderListItem` in `corpsite-ui/app/directory/personnel/_lib/personnelOrdersApi.client.ts` |
| 168 | Void reason | — | `PersonnelOrderListItem.void_reason` | `personnel_orders.void_reason` | API-only | `PersonnelOrderListItem` in `corpsite-ui/app/directory/personnel/_lib/personnelOrdersApi.client.ts` |
| 169 | Item count | — | `PersonnelOrderListItem.item_count` | derived count | API-only | `PersonnelOrderListItem` in `corpsite-ui/app/directory/personnel/_lib/personnelOrdersApi.client.ts` |
| 170 | Archived flag | — | `PersonnelOrderListItem.is_archived` | `personnel_orders` archive flags | API-only | `PersonnelOrderListItem` in `corpsite-ui/app/directory/personnel/_lib/personnelOrdersApi.client.ts` |
| 171 | Created at | — | `PersonnelOrderListItem.created_at` | `personnel_orders.created_at` TIMESTAMPTZ | API-only | `PersonnelOrderListItem` in `corpsite-ui/app/directory/personnel/_lib/personnelOrdersApi.client.ts` |

### 4.15 Projection — `onboarding` (22 rows)

**Availability:** employee tab only; hidden for applicant. Empty: «Программа адаптации ещё не создана.» (not a stub).

| # | Business field | UI label | API/DTO path | DB / source | Card UI | Evidence |
|---|----------------|----------|--------------|-------------|---------|----------|
| 172 | Onboarding status | Статус | `EmployeeOnboardingDetail.status` | `employee_onboardings.status` | rendered | `onboardingStatusLabel` in `corpsite-ui/app/directory/personnel/_lib/employeeOnboardingApi.client.ts`; `corpsite-ui/app/directory/personnel/_components/EmployeeOnboardingSection.tsx` |
| 173 | Progress percent | Прогресс | `progress_percent` | derived from checklist | rendered | `corpsite-ui/app/directory/personnel/_components/EmployeeOnboardingSection.tsx` |
| 174 | Overdue count | Просрочки | `overdue_count` | derived | rendered | `corpsite-ui/app/directory/personnel/_components/EmployeeOnboardingSection.tsx` |
| 175 | Planned end at | Плановое завершение | `planned_end_at` | `employee_onboardings.planned_end_at` | rendered | `corpsite-ui/app/directory/personnel/_components/EmployeeOnboardingSection.tsx` |
| 176 | Checklist item title | Пункт | `checklist_items[].title` | `employee_onboarding_checklist_items.title` | rendered | `corpsite-ui/app/directory/personnel/_components/EmployeeOnboardingSection.tsx` table |
| 177 | Checklist due date | Срок | `checklist_items[].due_date` | `employee_onboarding_checklist_items.due_date` | rendered | `formatDueDate` in `corpsite-ui/app/directory/personnel/_lib/employeeOnboardingApi.client.ts` |
| 178 | Checklist assignee kind | Ответственный | `assignee_kind` | `employee_onboarding_checklist_items.assignee_kind` | rendered | `onboardingAssigneeLabel` in `corpsite-ui/app/directory/personnel/_lib/employeeOnboardingApi.client.ts` |
| 179 | Checklist priority | Приоритет | `priority` | `employee_onboarding_checklist_items.priority` | rendered | `onboardingPriorityLabel` in `corpsite-ui/app/directory/personnel/_lib/employeeOnboardingApi.client.ts` |
| 180 | Checklist item status | Статус | `checklist_items[].status` | `employee_onboarding_checklist_items.status` | rendered | `onboardingChecklistStatusLabel` in `corpsite-ui/app/directory/personnel/_lib/employeeOnboardingApi.client.ts` |
| 181 | Checklist comment | Комментарий | `comment` | `employee_onboarding_checklist_items.comment` | rendered | `corpsite-ui/app/directory/personnel/_components/EmployeeOnboardingSection.tsx` |
| 182 | Checklist overdue flag | *(calendar / row style)* | `is_overdue` | derived | rendered | due calendar + row class in `corpsite-ui/app/directory/personnel/_components/EmployeeOnboardingSection.tsx` |
| 183 | Attachment file URL | вложение | `attachments[].file_url` | `employee_onboarding_checklist_attachments.file_url` | rendered link | `addOnboardingChecklistAttachment` in `corpsite-ui/app/directory/personnel/_lib/employeeOnboardingApi.client.ts` / list render in `corpsite-ui/app/directory/personnel/_components/EmployeeOnboardingSection.tsx` |
| 184 | Audit timestamp | История | `audit[].created_at` | onboarding task audit via `getOnboardingTaskAudit` | lazy rendered | `getOnboardingTaskAudit` in `corpsite-ui/app/directory/personnel/_lib/employeeOnboardingApi.client.ts` |
| 185 | Audit action | История | `audit[].action` | onboarding task audit via `getOnboardingTaskAudit` | lazy rendered | `onboardingTaskAuditLabel` in `corpsite-ui/app/directory/personnel/_lib/employeeOnboardingApi.client.ts` |
| 186 | Audit actor name | История | `audit[].actor_name` | join | lazy rendered | `EmployeeOnboardingSection.toggleAudit` (`corpsite-ui/app/directory/personnel/_components/EmployeeOnboardingSection.tsx`) |
| 187 | Onboarding id | — | `onboarding_id` | `employee_onboardings.onboarding_id` | API-only | `EmployeeOnboardingDetail` in `corpsite-ui/app/directory/personnel/_lib/employeeOnboardingApi.client.ts` |
| 188 | Started at | — | `started_at` | `employee_onboardings.started_at` | API-only | `EmployeeOnboardingDetail` in `corpsite-ui/app/directory/personnel/_lib/employeeOnboardingApi.client.ts` |
| 189 | Completed at (program) | — | `completed_at` | `employee_onboardings.completed_at` | API-only | `EmployeeOnboardingDetail` in `corpsite-ui/app/directory/personnel/_lib/employeeOnboardingApi.client.ts` |
| 190 | Responsible HR id | — | `responsible_hr_id` | `employee_onboardings.responsible_hr_id` | API-only | `EmployeeOnboardingDetail` in `corpsite-ui/app/directory/personnel/_lib/employeeOnboardingApi.client.ts` |
| 191 | Mentor employee id | — | `mentor_employee_id` | `employee_onboardings.mentor_employee_id` | API-only | `EmployeeOnboardingDetail` in `corpsite-ui/app/directory/personnel/_lib/employeeOnboardingApi.client.ts` |
| 192 | Program notes | — | `notes` | `employee_onboardings.notes` | API-only (used by complete action) | `completeEmployeeOnboarding` in `corpsite-ui/app/directory/personnel/_lib/employeeOnboardingApi.client.ts` |
| 193 | Read-only flag | — | `is_read_only` | derived | controls actions, not labeled field | `corpsite-ui/app/directory/personnel/_components/EmployeeOnboardingSection.tsx` |

**Подсчёт строк реестра §4:**

| Subsection | Rows | Row # range | Tab coverage note |
|------------|------|-------------|-------------------|
| §4.1 personal/envelope | 15 | 1–15 | card `general` |
| §4.2 contacts | 4 | 16–19 | intake; not PPR contacts tab |
| §4.3 education | 11 | 20–30 | card `education` |
| §4.4 training | 10 | 31–40 | card `training` |
| §4.5 family | 7 | 41–47 | card `family` |
| §4.6 employment biography | 12 | 48–59 | card `employment_biography` |
| §4.7 military | 19 | 60–78 | card `military` |
| §4.8 additional | 26 | 79–104 | card `additional` |
| §4.9 meta | 1 | 105 | intake wizard only |
| §4.10 intended_employment | 7 | 106–112 | card tab (applicant) |
| §4.11 applications | 24 | 113–136 | card tab; name projections marked unavailable |
| §4.12 changes | 8 | 137–144 | card tab |
| §4.13 assignment | 10 | 145–154 | card tab (employee); enroll marked unavailable on card path |
| §4.14 orders | 17 | 155–171 | card tab (employee) |
| §4.15 onboarding | 22 | 172–193 | card tab (employee) |
| **Total** | **193** | | All 13 card tabs + intake sections represented or explicitly marked unavailable |

---

## 5. Реестр типов и форматов

Каждая строка §4 покрыта одним или несколькими правилами `RULE-FMT-*` (см. `Applies to`) и/или записью §5.2. Правила **могут быть композиционными**: одна строка может входить в несколько `Applies to`, когда слои формата ортогональны (например storage trim + semantic map, или API-only presence + typed rate/datetime). Ниже явно перечислены допустимые пересечения; date/datetime-поля не оставляются под неопределённым «per type».

### 5.1 Общие правила

| Rule ID | Applies to (row #) | Business datatype | UI type | API/DTO type | DB type | Canonical precision | Display format | Accepted input | Null/unknown | Transformation | Format verdict |
|---------|--------------------|-------------------|---------|--------------|---------|---------------------|----------------|----------------|--------------|----------------|----------------|
| RULE-FMT-TEXT-TRIM | 2,3,4,7,9,10,11,18,19,21,24,25,27,31,32,37,41,42,44,48,49,52,60,61,62,63,66,67,69,79,80,82,83,84,86,89,90,91,93,97,98,99,101 | text | `IntakeTextField` / combobox text | `string` | TEXT | n/a | as stored (trim) | free text | `""` → omit/NULL | trim on map | **LOSSLESS_TRANSFORM** |
| RULE-FMT-PHOTO-ID | 1 | opaque file id | upload control | `string` | photo storage key | n/a | thumbnail/file | upload binary → id | null = no photo | `save_intake_photo` (`app/personnel_intake/application/photo_service.py`) | **EXACT_MATCH** (intake storage) |
| RULE-FMT-DERIVED-FIO | 5 | derived text | read-only | `string` | `persons.full_name` TEXT | n/a | space-joined | n/a | empty parts skipped | `build_full_name` (`app/personnel_intake/application/intake_mapper.py`) | **LOSSLESS_TRANSFORM** |
| RULE-FMT-DERIVED-ALPHA | 12 | derived grapheme | read-only | `string` | — | n/a | upper first grapheme | n/a | «—» | `deriveIntakeSurnameAlphabet` (`corpsite-ui/app/intake/_lib/intakePersonalFields.ts`) | **LOSSLESS_TRANSFORM** |
| RULE-FMT-ENUM-RU-LABEL | 8 | categorical RU | `IntakeSelectField` | `string` | — (intake JSONB) | n/a | RU label | catalog option | empty optional | none to PPR | **MISSING_TARGET** |
| RULE-FMT-ENUM-EDUCATION | 20 | education kind enum | select | `IntakeEducationType` / `string` | `person_education.education_kind` TEXT | n/a | RU/kind label | allowed kinds | blank → `basic` via normalize | `resolve_intake_education_kind` (`app/personnel_intake/domain/education_type.py`) | **EXACT_MATCH** (after resolve) |
| RULE-FMT-PHONE-FREE | 16 | phone text | tel input | `string` | `personnel_applications.contact_mobile_phone` TEXT | n/a | as entered | free text | required non-empty on submit | transfer UPDATE application | **By-design episode** (GAP-002) |
| RULE-FMT-EMAIL-FREE | 17 | email text | email input | `string` | `personnel_applications.contact_email` TEXT | n/a | as entered | free text | empty optional | transfer UPDATE application | **By-design episode** |
| RULE-FMT-IIN | 13 | 12-digit id | card read | masked string | `persons.iin` + CHECK | n/a | masked | — (no intake) | NULL | mask in PPR mappers | **MISSING_SOURCE** in intake |
| RULE-FMT-HOURS-DECIMAL | 38 | decimal hours | numeric string | `string` → `Decimal` | `person_training.hours` NUMERIC | scale of Decimal | number | numeric string | empty → NULL | `Decimal(str(hours_raw))` in `map_training_records` (`app/personnel_intake/application/intake_mapper.py`) | **LOSSLESS_TRANSFORM** |
| RULE-FMT-VUS-CODE | 64 | VUS code ≤7 | masked input | `string` | TEXT | n/a | uppercase code | sanitized chars | empty optional | `sanitizeMilitarySpecialtyCodeInput` (`corpsite-ui/lib/militarySpecialtyCode.ts`) | **EXACT_MATCH** |
| RULE-FMT-RELATIONSHIP | 41 | free text → enum | text/combobox | `string` | `relationship_type` enum | n/a | enum/RU | free text | empty optional intake | `map_relationship_type` (`app/personnel_intake/application/intake_mapper.py`) → often `other_close` | **LOSSY_TRANSFORM** (GAP-009) |
| RULE-FMT-TRAINING-KIND | 40 | taxonomy | — | — | `person_training.training_kind` | n/a | kind label | not captured | forced `course` | `TRAINING_KIND_COURSE` in `map_training_records` (`app/personnel_intake/application/intake_mapper.py`) | **SEMANTIC_MISMATCH** (GAP-008) |
| RULE-FMT-BOOL | 39,81,88,96,104 | boolean | checkbox | `boolean` | JSONB boolean | n/a | checked/unchecked | true/false | false default | passthrough / normalize | **EXACT_MATCH** |
| RULE-FMT-DATE-BIRTH | 6 | calendar day | `IntakeDateField` birth | ISO `string` | `persons.birth_date` DATE | day | `дд.мм.гггг` | full day; Jan 1 allowed | empty / incomplete blocked | `parse_date_value` | **EXACT_MATCH** if full |
| RULE-FMT-DATE-PERIOD | 22,23,33,34,35,43,50,51,85,92,100 | calendar day | `IntakeDateField` document / `PersonnelDayDateField` | ISO `string` | DATE or JSONB string | day | `дд.мм.гггг` (card education may year-truncate) | full day; Jan 1 blocked as year-only heuristic | empty optional; incomplete → submit error | `parse_date_value` / normalize | See §6; **GAP-021** / **GAP-012** |
| RULE-FMT-DATE-PPR-ONLY | 29,72,73 | calendar day | card edit / absent | ISO date | DATE | day | `дд.мм.гггг` | PPR form | NULL | PPR command handlers | **MISSING_SOURCE** in intake |
| RULE-FMT-DATETIME-AUDIT | 123,129,134,138,171,184,188,189 | instant | read-only / API-only | ISO datetime | TIMESTAMPTZ | datetime | locale datetime or n/a on card | system / BC | NULL | none | N/A display (card may omit API-only) |
| RULE-FMT-RATE | 112,131,151 | rate 0–2 | numeric | number/`Decimal` | NUMERIC(4,2) / employee rate | 2 dp | decimal | gt 0 le 2 (intended PATCH); employee correction uses `employees.rate` | NULL | PATCH / `correctEmployee` validate | **EXACT_MATCH** (intended); employee rate Employment BC |
| RULE-FMT-LEGACY-MIGRATE | 35,87,94,95,102,103 | legacy string | hidden/reconcile | optional string | — / JSONB | n/a | migrated shape | legacy keys | absent if modern | read-time migrate | **LOSSLESS_TRANSFORM** on read |
| RULE-FMT-ENUM-STATUS | 14,15,30,113,159,172,180 | lifecycle/status enum | badge/label | `string` | TEXT/enum | n/a | RU label map | system / domain | — | label maps | **EXACT_MATCH** storage |
| RULE-FMT-ID-INT | 106,108,110,115,116,117,121,124,140,143,149,150,156,187,190,191 | integer id | select/hidden | `int` | INTEGER/BIGINT | n/a | id or joined name | positive int | NULL | joins for names | **EXACT_MATCH** |
| RULE-FMT-ORDER-NUMBER | 155 | order number text | list label | `string` or null | `personnel_orders.order_number` TEXT | n/a | `№ {order_number}` | BC-owned | null → fallback row 156 | none | **EXACT_MATCH** |
| RULE-FMT-NAME-JOIN | 107,109,111,145,146,147 | display name | read-only / select label | `string` | join TEXT | n/a | name | via id select | «—» | join projection | **EXACT_MATCH** when join present |
| RULE-FMT-UNAVAILABLE-NAME | 118,119,120,122 | display name | table cell | expected on FE, absent in DTO | join | n/a | «—» / `#id` | n/a | always missing on card API | none | **MISSING_TARGET** on card endpoint |
| RULE-FMT-PROJECTION-TEXT | 137,139,158,160,161,162,163,164,165,166,167,168,176,178,179,181,185,186 | text/enum projection | list/table | `string` | TEXT | n/a | label or raw | BC-owned | null → omit/«—» | none (projection) | **EXACT_MATCH** projection |
| RULE-FMT-PROJECTION-DERIVED | 148,173,174,182,193 | derived metric/flag | read-only | number/bool/string | derived | n/a | % / count / label | n/a | 0 / false | client/server derive | **LOSSLESS_TRANSFORM** |
| RULE-FMT-PROJECTION-DATE | 114,152,153,157,175,177 | calendar day | read-only | ISO date | DATE (or date portion of timestamptz for planned_end) | day | `дд.мм.гггг` / locale | BC-owned | «—» | format helpers | **EXACT_MATCH** |
| RULE-FMT-URL | 183 | URL string | link | `string` | TEXT | n/a | link text | URL string | no attachment | store URL | **EXACT_MATCH** |
| RULE-FMT-WIZARD-STEP | 105 | step id | wizard state | `string` | JSONB payload | n/a | step UI | step key | default first step | autosave | **EXACT_MATCH** |
| RULE-FMT-META-JSON | 26,36,65,68 | metadata string | text / hidden | `string` | JSONB field | n/a | if shown | free text | null | nest in metadata | **EXACT_MATCH** storage |
| RULE-FMT-FIXED-ENUM | 54,70 | forced/derived enum | — | enum string | TEXT | n/a | enum | not user-picked (or via status) | n/a | mapper default/branch | **SEMANTIC_DEFAULT** / **LOSSLESS** from status |
| RULE-FMT-PPR-TEXT-ONLY | 28,45,46,47,55,56,57,58,59,71,74,75,76,77,78 | PPR-only text/enum/json | card / absent | `string`/JSONB | TEXT/JSONB | n/a | as stored / redacted | PPR edit or none | NULL | none from intake | **MISSING_SOURCE** or redacted **EXACT_MATCH** |
| RULE-FMT-CLIENT-ID | 53 | client record id | hidden | `string` | — | n/a | n/a | generated uuid-like | always set in UI | `ensureEmploymentBiographyRecordId` (`corpsite-ui/app/intake/_lib/intakeEmploymentBiography.ts`) | N/A (intake-only) |
| RULE-FMT-API-ONLY-SCALAR | 125,126,127,128,130,132,133,135,136,141,142,144,169,170,192 | non-date BC scalar | not on card columns | per DTO field type (text/enum/id/bool/int — not date/datetime) | matching column type | n/a | n/a on card | BC APIs | NULL | none | **EXACT_MATCH** API; card non-render |
| RULE-FMT-UNAVAILABLE-WORKFLOW | 154 | workflow handle | drawer | import record | import BC | n/a | error message | requires `batchId` | blocked | none on card | **UNAVAILABLE** on PPR card path |

### 5.2 Per-field supplements and allowed compositional intersections

| Row # | Field path | Extra detail | Format verdict (authoritative with rule) |
|-------|------------|--------------|------------------------------------------|
| 20 | `education[i].education_type` blank | `normalize_intake_education_type` → `basic` | **Default** (business), not format loss |
| 27 | `diploma_number` | stored; not rendered in `corpsite-ui/app/directory/personnel/_components/PprCardEducationSection.tsx` | **EXACT_MATCH** storage / UI gap |
| 35 | `training[i].year` legacy | **Composition:** RULE-FMT-DATE-PERIOD (day precision / validation) + RULE-FMT-LEGACY-MIGRATE (key coalesce year_to or year) | dual-rule OK |
| 41 | `relatives[i].relationship` | **Composition:** RULE-FMT-TEXT-TRIM (storage trim) + RULE-FMT-RELATIONSHIP (free text → enum, GAP-009) | dual-rule OK |
| 62 vs 69 | `category` vs `registration_category` | mapper merges keys into one PPR column | **LOSSLESS** merge; duplicate intake keys |
| 65 | `specialty_name` | metadata only; not in `StepMilitary` UI | **MISSING_TARGET** in UI (GAP-019) |
| 74,75,76,77 | restricted military ids | redacted by `app/ppr/application/ppr_query_access_service.py` | storage **EXACT_MATCH**; read redaction OK |
| 118,119,120,122 | application name projections | FE reads fields absent from `PprPersonnelApplicationItemResponse` | **MISSING_TARGET** on card endpoint |
| 131 | `intended_employment_rate` on applications DTO | **Composition:** RULE-FMT-RATE (NUMERIC rate semantics) — not listed under RULE-FMT-API-ONLY-SCALAR; API-only **card non-render** noted in §4.11 | typed rate, not «per type» |
| 129,134,171,188,189 | API-only datetimes | **Composition:** RULE-FMT-DATETIME-AUDIT owns type/precision/display; §4 marks card non-render | not under API-ONLY-SCALAR |
| 154 | enroll-from-card | `batchId={null}` on PPR card | **UNAVAILABLE** |

**Coverage check:** rows 1–193 each appear in at least one RULE-FMT-* `Applies to` list and/or §5.2. Multiple rules per row are allowed only for the compositional cases above (legacy date, relationship text→enum, typed API-only rate/datetime). RULE-FMT-API-ONLY-SCALAR excludes all date/datetime rows.

---

## 6. Политика дат и реестр всех дат

### 6.1 Нормативные правила

1. Кадровые расчётные даты — точность **до дня** (`DATE` or full-day JSONB string).
2. Display — `дд.мм.гггг` via `formatPersonnelDayDateForDisplay` (`corpsite-ui/lib/personnelDayDate.ts`) / `formatPprDate` (`corpsite-ui/app/directory/personnel/_lib/pprCardPresentation.ts`).
3. API — ISO `YYYY-MM-DD` for DATE columns.
4. Year-only ≠ full date; auto-fill `01.01.YYYY` **запрещён** without HR rule.
5. Precision **cannot** be inferred from `YYYY-01-01` alone without `precision_marker` / provenance. `_is_year_only_iso` (`app/personnel_intake/domain/date_validation.py`) is intake validation heuristic only.

### 6.2 Реестр всех date/datetime-полей из §4

Сверка: каждое поле §4 с типом DATE / TIMESTAMPTZ / calendar-day JSONB string / datetime audit входит в таблицу ниже (после split row 155 → 193 rows total).

| Row # | Field path | Precision | API/DB type | Display | Null / default | RULE-FMT |
|-------|------------|-----------|-------------|---------|----------------|----------|
| 6 | `personal.birth_date` | day | `persons.birth_date` DATE / ISO string DTO | `дд.мм.гггг` via `formatPprDate` | empty blocked at submit; transfer skips UPDATE if `parse_date_value` None | RULE-FMT-DATE-BIRTH |
| 22 | `education[i].year_from` → `started_at` | day | `person_education.started_at` DATE | `дд.мм.гггг` (card may year-truncate — GAP-012) | empty optional; incomplete → submit error | RULE-FMT-DATE-PERIOD |
| 23 | `education[i].year_to` → `completed_at` | day | `person_education.completed_at` DATE | `дд.мм.гггг` (card may year-truncate) | empty optional; incomplete → submit error | RULE-FMT-DATE-PERIOD |
| 29 | `person_education.document_date` | day | DATE | `дд.мм.гггг` when shown | NULL; no intake | RULE-FMT-DATE-PPR-ONLY |
| 33 | `training[i].year_from` → `started_at` | day | `person_training.started_at` DATE | `дд.мм.гггг` | empty optional; incomplete → submit error | RULE-FMT-DATE-PERIOD |
| 34 | `training[i].year_to` → `completed_at` | day | `person_training.completed_at` DATE | `дд.мм.гггг` | empty optional; incomplete → submit error | RULE-FMT-DATE-PERIOD |
| 35 | `training[i].year` legacy → `completed_at` | day if ISO | maps into `completed_at` DATE | via row 34 after coalesce | absent if modern `year_to` present | RULE-FMT-DATE-PERIOD + RULE-FMT-LEGACY-MIGRATE |
| 43 | `relatives[i].birth_year` → `birth_date` | day | `person_relatives.birth_date` DATE | `дд.мм.гггг` | empty optional; incomplete → submit error | RULE-FMT-DATE-PERIOD |
| 50 | `employment_biography[i].year_from` → `started_at` | day | `person_external_employment.started_at` DATE | `дд.мм.гггг` | empty optional; incomplete → submit error | RULE-FMT-DATE-PERIOD |
| 51 | `employment_biography[i].year_to` → `ended_at` | day | `person_external_employment.ended_at` DATE | `дд.мм.гггг` | empty = current job | RULE-FMT-DATE-PERIOD |
| 72 | `person_military_service.registered_at` | day | DATE | `дд.мм.гггг` | NULL; card/PPR edit | RULE-FMT-DATE-PPR-ONLY |
| 73 | `person_military_service.deregistered_at` | day | DATE | `дд.мм.гггг` | NULL; card/PPR edit | RULE-FMT-DATE-PPR-ONLY |
| 85 | `additional.awards[i].awarded_at` | day | JSONB string (ISO day) | `дд.мм.гггг` | empty optional; incomplete → submit error | RULE-FMT-DATE-PERIOD |
| 92 | `additional.academic_degrees[i].completed_at` | day | JSONB string (ISO day) | `дд.мм.гггг` | empty optional; incomplete → submit error | RULE-FMT-DATE-PERIOD |
| 100 | `additional.academic_titles[i].completed_at` | day | JSONB string (ISO day) | `дд.мм.гггг` | empty optional; incomplete → submit error | RULE-FMT-DATE-PERIOD |
| 114 | `personnel_applications.application_received_at` | day | DATE | `formatPersonnelApplicationDate` | server/registration default | RULE-FMT-PROJECTION-DATE |
| 123 | `personnel_applications.registered_at` | datetime | TIMESTAMPTZ | `formatPersonnelApplicationDateTime` | system set | RULE-FMT-DATETIME-AUDIT |
| 129 | `personnel_applications.vacancy_checked_at` | datetime | TIMESTAMPTZ (`PprPersonnelApplicationItemResponse.vacancy_checked_at`) | n/a on card (API-only) | NULL until vacancy check | RULE-FMT-DATETIME-AUDIT |
| 134 | `personnel_applications.director_resolution_at` | datetime | TIMESTAMPTZ (`PprPersonnelApplicationItemResponse.director_resolution_at`) | n/a on card (API-only) | NULL until resolution | RULE-FMT-DATETIME-AUDIT |
| 138 | `personnel_record_events.event_at` → `occurred_at` | datetime | TIMESTAMPTZ | `formatPprDateTime` in `corpsite-ui/app/directory/personnel/_lib/pprCardPresentation.ts` | system | RULE-FMT-DATETIME-AUDIT |
| 152 | `employees.date_from` (correction) | day | DATE | locale/day display in correction drawer | required on correction submit (Employment BC) | RULE-FMT-PROJECTION-DATE |
| 153 | `employees.date_to` (correction) | day | DATE | locale/day display | NULL = open-ended | RULE-FMT-PROJECTION-DATE |
| 157 | `personnel_orders.order_date` | day | DATE | `formatPersonnelOrderDate` | may be null in list DTO | RULE-FMT-PROJECTION-DATE |
| 171 | `personnel_orders.created_at` | datetime | TIMESTAMPTZ | n/a on card (API-only) | system default on insert | RULE-FMT-DATETIME-AUDIT |
| 175 | `employee_onboardings.planned_end_at` | day (displayed as date) | timestamptz/date in onboarding DTO | `toLocaleDateString("ru-RU")` in `corpsite-ui/app/directory/personnel/_components/EmployeeOnboardingSection.tsx` | «—» if null | RULE-FMT-PROJECTION-DATE |
| 177 | `employee_onboarding_checklist_items.due_date` | day | DATE | `formatDueDate` in `corpsite-ui/app/directory/personnel/_lib/employeeOnboardingApi.client.ts` | «—» if null | RULE-FMT-PROJECTION-DATE |
| 184 | onboarding audit `created_at` | datetime | TIMESTAMPTZ via `getOnboardingTaskAudit` | locale datetime in audit panel | system | RULE-FMT-DATETIME-AUDIT |
| 188 | `employee_onboardings.started_at` | datetime | TIMESTAMPTZ | n/a on card (API-only) | system on program start | RULE-FMT-DATETIME-AUDIT |
| 189 | `employee_onboardings.completed_at` | datetime | TIMESTAMPTZ | n/a on card (API-only) | NULL until complete | RULE-FMT-DATETIME-AUDIT |

### 6.3 GAP-021 — `_is_year_only_iso`

| Check | Result | Evidence |
|-------|--------|----------|
| Period `2018-01-01` incomplete? | **Yes** | `test_incomplete_period_dates` in `tests/personnel_intake/test_intake_date_validation.py` |
| Birth `1990-01-01` incomplete? | **No** | `test_incomplete_birth_date_allows_january_first` in `tests/personnel_intake/test_intake_date_validation.py` |
| Frontend period | blocked | `isIncompletePersonnelDocumentDate` → `isYearOnlyIsoDate` in `corpsite-ui/lib/personnelDayDate.ts` |
| `parse_date_value("2018-01-01")` | returns `date(2018,1,1)` | `app/personnel_intake/application/intake_mapper.py` — no year-only check |
| Achievable wrong PPR on standard path? | **No** — submit blocks period Jan 1 | `_validate_submit_payload` (`app/personnel_intake/application/intake_service.py`) |
| Achievable harm | **Blocks valid Jan 1 period start** | **P1** GAP-021 |

---

## 7. Реестр преобразований

| Source field/value | Transformation location | Transformation | Target | Lossless | Validation before | Error behavior | Provenance preserved | Assessment |
|--------------------|-------------------------|----------------|--------|----------|-------------------|----------------|----------------------|------------|
| `personal.*` name parts | `app/personnel_intake/application/intake_mapper.py` `build_full_name` | join trimmed parts | `persons.full_name` | Yes | submit required names (`_validate_submit_payload` in `app/personnel_intake/application/intake_service.py`) | — | intake JSONB retained | OK |
| `personal.birth_date` string | `parse_date_value` (`app/personnel_intake/application/intake_mapper.py`) via `transfer_service._transfer_general_and_contacts` | ISO → `date` | `persons.birth_date` | Only if full ISO | `collect_intake_date_validation_errors` birth mode (`app/personnel_intake/domain/date_validation.py`) | skip UPDATE if None | raw in intake only | Risk: silent NULL if bypass (GAP-005) |
| Incomplete date any | `parse_date_value` | return None | PPR DATE left unchanged / NULL | No | submit blocks intake | transfer accepts already-validated payload | raw JSONB | Defense gap GAP-005 **P1** |
| `education_type` empty | `normalize_intake_education_type` (`app/personnel_intake/domain/education_type.py`) | default `basic` | `education_kind` | N/A | — | — | — | Business default — may collapse distinct rows |
| `education_type` | `resolve_intake_education_kind` (`app/personnel_intake/domain/education_type.py`) | enum map | `education_kind` | Yes | submit enum check | ValueError on transfer | `metadata.source` | OK |
| `training.*` | `map_training_records` (`app/personnel_intake/application/intake_mapper.py`) | force `training_kind=course` | `person_training` | No | period dates at submit | transfer/domain errors | metadata | **P1** semantic loss GAP-008 |
| `training[i].year` legacy | `map_training_records` (`app/personnel_intake/application/intake_mapper.py`) | `year_to \|\| year` → `completed_at` | `person_training.completed_at` | If ISO | `collect_intake_date_validation_errors` coalesces `year_to \|\| year` | — | — | OK migrate |
| `training[i].hours` | `map_training_records` (`app/personnel_intake/application/intake_mapper.py`) | `Decimal(str)` | `person_training.hours` | Yes if numeric | — | Decimal parse error | metadata.hours_is_manual | OK |
| `relationship` free text | `map_relationship_type` (`app/personnel_intake/application/intake_mapper.py`) | dictionary / `other_close` | `person_relatives.relationship_type` | No | none intake | — | metadata | **P1** GAP-009 |
| `military.status` «не состоит» | `map_military_record` (`app/personnel_intake/application/intake_mapper.py`) | `record_kind=not_applicable` | `person_military_service` | Yes | — | — | metadata | OK |
| `military.status` other | `map_military_record` (`app/personnel_intake/application/intake_mapper.py`) | copied to `registration_status`; `record_kind=registration` | PPR military | Partial | `validate_military_service_record` (`app/ppr/domain/section_record_validation.py`) | transfer/domain error | metadata | Semantic overlap GAP-010 |
| `military.category` / `registration_category` | `map_military_record` (`app/personnel_intake/application/intake_mapper.py`) | merge keys | `registration_category` | Yes | — | — | — | OK merge |
| `contacts.mobile_phone` / `email` | `transfer_service._transfer_general_and_contacts` | UPDATE application | `personnel_applications.contact_*` | Yes | submit requires phone | COALESCE keep old | not PPR | By-design episode GAP-002 **P1** |
| `additional` blob | `save_person_additional_profile` / `normalize_additional_profile` (`app/personnel_intake/domain/additional_profile.py`) | normalize JSONB | `personnel_record_metadata.additional_profile` | Mostly | normalize | — | merge reader may pull intake | Dual source read GAP-011 **P2** |
| Gender / citizenship / nationality / birth_place | — | none | — | — | — | — | intake JSONB only | **MISSING** GAP-001 |
| Addresses | — | none | — | — | — | — | intake JSONB only | **MISSING** GAP-003 |
| Photo file id | — | none to PPR | — | — | — | — | photo storage | **MISSING** GAP-004 |
| `persons.last_name` / `first_name` / `middle_name` | `_transfer_general_and_contacts` | **not updated** | only `full_name` (+ birth_date) | No | — | — | — | **P1** split names drift GAP-007 |
| Education period display | `formatPersonnelDateRange` with `{precision:"year"}` in `corpsite-ui/app/directory/personnel/_components/PprCardEducationSection.tsx` | truncate display | UI only | No (visual) | — | — | — | **P2** GAP-012 |
| IIN read | PPR mappers / card | mask | API response | N/A | — | — | — | security OK |
| Military restricted ids | `app/ppr/application/ppr_query_access_service.py` | redact fields | API | N/A | ACL | omit | — | OK |
| Intake draft reconcile | `corpsite-ui/app/intake/_lib/intakeDraftReconcile.ts` | normalize all sections | client state | varies | on load | — | — | OK |
| Award legacy `title` | `normalize_award_entry` (`app/personnel_intake/domain/additional_profile.py`) / `corpsite-ui/app/intake/_lib/intakeAdditional.ts` | split category/name | modern shape | Yes | on read | — | — | OK |
| Degree/title legacy `label` / `degree_type` | `corpsite-ui/app/intake/_lib/intakeAdditional.ts` | migrate on read | modern shape | Yes | on read | — | — | OK |
| Employment `record_kind` | `map_employment_records` | force `episode` | `person_external_employment.record_kind` | N/A | — | — | metadata | Semantic default |
| Projection joins (intended / assignment / orders / onboarding) | `load_intended_employment` / `getEmployee` / `list_personnel_orders` / `getEmployeeOnboardingByEmployeeId` (see Appendix A) | id → name / derived metrics | card DTO | Yes when join present | owning BC validators | empty «—» | BC-owned | OK projection; applications name fields missing on PPR history DTO |

---

## 8. Сопоставление validation

**Общие правила (переиспользуются; `Applies to` перечисляет номера строк):**

| Rule ID | Mechanism | Evidence | Applies to (row #) |
|---------|-----------|----------|--------------------|
| RULE-VAL-SUBMIT-REQUIRED | `_validate_submit_payload` non-empty checks | `app/personnel_intake/application/intake_service.py` | 2, 3, 16 |
| RULE-VAL-DATE-FULL-BIRTH | `collect_intake_date_validation_errors` birth mode | `app/personnel_intake/domain/date_validation.py` | 6 |
| RULE-VAL-DATE-FULL-DOC | `collect_intake_date_validation_errors` document/period mode | `app/personnel_intake/domain/date_validation.py` | 22, 23, 33, 34, 35, 43, 50, 51, 85, 92, 100 |
| RULE-VAL-ON-BEHALF | `_validate_on_behalf_save_payload` | `app/personnel_intake/application/on_behalf_edit_service.py` | intake payload fields validated on on-behalf save (mirrors submit-path field set for draft content) |
| RULE-VAL-PPR-EDU-DUP | `_assert_no_duplicate_education` | `app/ppr/domain/section_handlers.py` | 20, 21 (fingerprint inputs); blocks transfer add for education rows 20–30 |
| RULE-VAL-PPR-TRN-DUP | `_assert_no_duplicate_training` | `app/ppr/domain/section_handlers.py` | 31, 32, 40 (fingerprint); blocks transfer add for training rows 31–40 |
| RULE-VAL-PPR-EMP | `validate_external_employment_record` | `app/ppr/domain/section_record_validation.py` | 48–59 on PPR mutate/transfer insert |
| RULE-VAL-PPR-MIL | `validate_military_service_record` | `app/ppr/domain/section_record_validation.py` | 60–78 on PPR mutate/transfer |
| RULE-VAL-PPR-MIL-ONE | `handle_create_military_service_record` active guard | `app/ppr/domain/section_handlers.py` `MILITARY_ACTIVE_RECORD_ALREADY_EXISTS` | 60–78 create path |
| RULE-VAL-PPR-REL | `validate_relative_record` | `app/ppr/domain/section_record_validation.py` | 41–47 |
| RULE-VAL-OPTIONAL | no intake required check | — | fields marked optional below |
| RULE-VAL-FE-VUS | `sanitizeMilitarySpecialtyCodeInput` | `corpsite-ui/lib/militarySpecialtyCode.ts` | 64 |
| RULE-VAL-NORM-ADD | `normalize_additional_profile` | `app/personnel_intake/domain/additional_profile.py` | 79–104 |
| RULE-VAL-PROJ-BC | owning BC validators | `list_personnel_orders` (`app/services/personnel_orders_query_service.py`); employee-onboarding routes; `correctEmployee` / employee API; `PprIntendedEmploymentUpdateRequest`; personnel application history read | 106–193 as noted in §8.2 |
| RULE-VAL-NONE | no domain validation | — | derived / system / unavailable |

### 8.1 Per-row validation binding (rows 1–105)

| Row # | Field path | Intake validation | PPR/domain validation | DB constraint | Mismatch | User message / error | Alignment |
|-------|------------|-------------------|----------------------|---------------|----------|----------------------|-----------|
| 1 | `personal.photo_file_id` | upload service rules | — | file storage | not in PPR | photo service errors | GAP-004 |
| 2 | `personal.last_name` | RULE-VAL-SUBMIT-REQUIRED | — | `chk_persons_full_name_nonempty` (via full_name) | split columns not updated | `PersonnelIntakeValidationError` | GAP-007 |
| 3 | `personal.first_name` | RULE-VAL-SUBMIT-REQUIRED | — | — | not updated on transfer | `PersonnelIntakeValidationError` | GAP-007 |
| 4 | `personal.middle_name` | RULE-VAL-OPTIONAL | — | — | not updated on transfer | — | GAP-007 |
| 5 | derived full_name | derived | — | `chk_persons_full_name_nonempty` | — | — | OK |
| 6 | `personal.birth_date` | RULE-VAL-DATE-FULL-BIRTH | — | DATE | — | RU `INTAKE_INCOMPLETE_DATE_MESSAGE` / FE hint | OK |
| 7 | `personal.birth_place` | RULE-VAL-OPTIONAL | — | — | not transferred | — | GAP-001 |
| 8 | `personal.gender` | RULE-VAL-OPTIONAL (catalog UI) | — | — | not transferred | — | GAP-001 |
| 9 | `personal.citizenship` | RULE-VAL-OPTIONAL | — | — | not transferred | — | GAP-001 |
| 10 | `personal.nationality` | RULE-VAL-OPTIONAL | — | — | not transferred | — | GAP-001 |
| 11 | `personal.personnel_number` | HR-only UI gate | — | — | not on Employee | — | GAP-014 |
| 12 | surname alphabet | RULE-VAL-NONE | — | — | UI only | — | OK |
| 13 | IIN | RULE-VAL-NONE intake | CHECK format | `chk_persons_iin_format` | missing intake source | — | GAP / MISSING_SOURCE |
| 14 | lifecycle_state | RULE-VAL-NONE | system | enum/text | — | — | OK |
| 15 | hr_relationship_context | RULE-VAL-NONE | system | enum/text | — | — | OK |
| 16 | `contacts.mobile_phone` | RULE-VAL-SUBMIT-REQUIRED | — | — | not PPR contacts | `PersonnelIntakeValidationError` | GAP-002 |
| 17 | `contacts.email` | RULE-VAL-OPTIONAL | — | — | not PPR contacts | — | GAP-002 |
| 18 | `contacts.registration_address` | RULE-VAL-OPTIONAL | — | — | not transferred | — | GAP-003 |
| 19 | `contacts.residence_address` | RULE-VAL-OPTIONAL | — | — | not transferred | — | GAP-003 |
| 20 | `education[i].education_type` | enum + duplicate fingerprint at submit | RULE-VAL-PPR-EDU-DUP | NOT NULL kind | blank→basic; fingerprint narrow | EN duplicate on submit/transfer | GAP-006 **P1** |
| 21 | `education[i].institution` | part of fingerprint | RULE-VAL-PPR-EDU-DUP | — | — | duplicate error | GAP-006 |
| 22 | `education[i].year_from` | RULE-VAL-DATE-FULL-DOC | date ordering in handlers | DATE | display year-only | RU incomplete hint | GAP-012 / GAP-021 |
| 23 | `education[i].year_to` | RULE-VAL-DATE-FULL-DOC | date ordering in handlers | DATE | display year-only | RU incomplete hint | GAP-012 / GAP-021 |
| 24 | `education[i].specialty` | RULE-VAL-OPTIONAL | — | — | — | — | OK |
| 25 | `education[i].qualification` | RULE-VAL-OPTIONAL | — | — | — | — | OK |
| 26 | `education[i].document_type` | RULE-VAL-OPTIONAL | metadata | JSONB | — | — | OK |
| 27 | `education[i].diploma_number` | RULE-VAL-OPTIONAL | — | — | not rendered on card | — | UI gap |
| 28 | `institution_type` | RULE-VAL-NONE intake | optional PPR | TEXT | no intake | — | MISSING_SOURCE |
| 29 | `document_date` | RULE-VAL-NONE intake | optional PPR | DATE | no intake | — | MISSING_SOURCE |
| 30 | `lifecycle_status` | RULE-VAL-NONE | section lifecycle | TEXT | — | — | OK |
| 31 | `training[i].course_name` | RULE-VAL-OPTIONAL | RULE-VAL-PPR-TRN-DUP (title part) | — | empty title allowed intake | duplicate on transfer if fingerprint hits | OK/partial |
| 32 | `training[i].institution` | RULE-VAL-OPTIONAL | RULE-VAL-PPR-TRN-DUP (org part) | — | — | duplicate error | OK/partial |
| 33 | `training[i].year_from` | RULE-VAL-DATE-FULL-DOC; ordering vs end | started_at optional in PPR | DATE | — | RU hint; may flag `year_from` if start>end | GAP-021 |
| 34 | `training[i].year_to` | RULE-VAL-DATE-FULL-DOC (`year_to\|\|year`) | completed_at optional | DATE | FE `resolveIntakeTrainingYearTo` | RU hint | GAP-021 |
| 35 | `training[i].year` legacy | validated only via coalesce into year_to path | maps to completed_at | — | dual keys | — | legacy OK |
| 36 | `training[i].document_type` | RULE-VAL-OPTIONAL; mapper default `certificate` | metadata | JSONB | default injection | — | OK |
| 37 | `training[i].document_number` | RULE-VAL-OPTIONAL | — | TEXT | — | — | OK |
| 38 | `training[i].hours` | RULE-VAL-OPTIONAL; Decimal on map | NUMERIC | NUMERIC | invalid decimal → transfer error | Decimal/`InvalidOperation` | OK |
| 39 | `training[i].hours_is_manual` | RULE-VAL-OPTIONAL bool | metadata bool | JSONB | — | — | OK |
| 40 | `training_kind` | RULE-VAL-NONE intake (not captured) | RULE-VAL-PPR-TRN-DUP uses forced `course` | NOT NULL kind | always `course` | — | GAP-008 **P1** |
| 41 | `relatives[i].relationship` | RULE-VAL-OPTIONAL | enum in RULE-VAL-PPR-REL | NOT NULL type | free text → `other_close` | PPR enum errors rare | GAP-009 **P1** |
| 42 | `relatives[i].full_name` | RULE-VAL-OPTIONAL | `_require_non_empty` in RULE-VAL-PPR-REL | NOT NULL | intake allows empty row | PPR error on add | align intake |
| 43 | `relatives[i].birth_year` | RULE-VAL-DATE-FULL-DOC | — | DATE | path name | RU hint | GAP-017 **P2** |
| 44 | `relatives[i].work_place` | RULE-VAL-OPTIONAL | — | — | — | — | OK |
| 45 | `birth_place` (family) | RULE-VAL-NONE intake | optional | TEXT | no intake | — | MISSING_SOURCE |
| 46 | `residence_address` (family) | RULE-VAL-NONE intake | optional | TEXT | no intake | — | MISSING_SOURCE |
| 47 | `notes` (family) | RULE-VAL-NONE intake | optional | TEXT | no intake | — | MISSING_SOURCE |
| 48 | `employment_biography[i].organization` | RULE-VAL-OPTIONAL | RULE-VAL-PPR-EMP requires employer for episode | TEXT | intake may be empty; PPR requires | `mapPprMutationError` / transfer validation | mismatch on empty episode |
| 49 | `employment_biography[i].position` | RULE-VAL-OPTIONAL | RULE-VAL-PPR-EMP requires position for episode | TEXT | intake may be empty; PPR requires | mutation/transfer error | mismatch on empty episode |
| 50 | `employment_biography[i].year_from` | RULE-VAL-DATE-FULL-DOC | RULE-VAL-PPR-EMP ordering; episode needs start or notes | DATE | — | RU hint | OK |
| 51 | `employment_biography[i].year_to` | RULE-VAL-DATE-FULL-DOC; empty = current | `ended_at >= started_at` | DATE | checkbox clears end | RU hint | OK |
| 52 | `reason_for_leaving` | RULE-VAL-OPTIONAL | optional | TEXT | — | — | OK |
| 53 | `record_id` (client) | RULE-VAL-NONE | not persisted to PPR | — | client-only | — | OK |
| 54 | `record_kind` | RULE-VAL-NONE intake (forced) | RULE-VAL-PPR-EMP enum | CHECK/enum | always episode | — | OK default |
| 55 | `department_name` | RULE-VAL-NONE intake | optional PPR | TEXT | card edit only | mutation errors | OK |
| 56 | `employment_type` | RULE-VAL-NONE intake | enum if set | CHECK | card/PPR only | mutation errors | OK |
| 57 | `document_reference` | RULE-VAL-NONE intake | optional | TEXT | — | — | OK |
| 58 | `source_system` | RULE-VAL-NONE intake | enum required on PPR record | CHECK | set by handlers | — | OK |
| 59 | `provenance` | RULE-VAL-NONE intake | optional JSONB | JSONB | — | — | OK |
| 60 | `military.status` | RULE-VAL-OPTIONAL catalog | RULE-VAL-PPR-MIL (+ kind branch) | — | label «Статус» vs registration_status | mutation RU | GAP-010 **P1** |
| 61 | `military.rank` | RULE-VAL-OPTIONAL | optional text | TEXT | — | — | OK |
| 62 | `military.category` | RULE-VAL-OPTIONAL | optional | TEXT | merges with row 69 | — | OK |
| 63 | `military.composition` | RULE-VAL-OPTIONAL catalog | optional | TEXT | — | — | OK |
| 64 | `military.specialty_code` | RULE-VAL-FE-VUS | optional | TEXT | — | FE sanitize | OK |
| 65 | `military.specialty_name` | RULE-VAL-OPTIONAL; not in StepMilitary UI | metadata | JSONB | hidden field | — | GAP-019 |
| 66 | `military.fitness_category` | RULE-VAL-OPTIONAL | optional | TEXT | — | — | OK |
| 67 | `military.commissariat` | RULE-VAL-OPTIONAL | optional | TEXT | — | — | OK |
| 68 | `military.registration_group` | RULE-VAL-OPTIONAL | metadata | JSONB | — | — | OK |
| 69 | `military.registration_category` | RULE-VAL-OPTIONAL duplicate key | merged in mapper | — | dual keys | — | OK merge |
| 70 | `record_kind` (military) | derived from status | RULE-VAL-PPR-MIL enum; RULE-VAL-PPR-MIL-ONE on create | enum | — | `MILITARY_ACTIVE_RECORD_ALREADY_EXISTS` | GAP-020F |
| 71 | `obligation_status` | RULE-VAL-NONE intake | card/PPR form | TEXT | — | mutation errors | OK |
| 72 | `registered_at` | RULE-VAL-NONE intake | ordering vs deregistered | DATE | — | mutation errors | OK |
| 73 | `deregistered_at` | RULE-VAL-NONE intake | ordering | DATE | — | mutation errors | OK |
| 74–77 | military id / certificate series-number | RULE-VAL-NONE intake | optional; redacted read | TEXT | ACL redact | omit when unauthorized | OK |
| 78 | `notes` (military) | RULE-VAL-NONE intake | optional | TEXT | — | — | OK |
| 79 | `foreign_languages[i].language` | RULE-VAL-OPTIONAL; RULE-VAL-NORM-ADD | JSONB normalize | JSONB | — | — | OK |
| 80 | `foreign_languages[i].proficiency` | RULE-VAL-OPTIONAL; RULE-VAL-NORM-ADD | JSONB | JSONB | — | — | OK |
| 81 | `foreign_languages_none` | RULE-VAL-OPTIONAL bool | JSONB | JSONB | — | — | OK |
| 82 | `awards[i].category` | RULE-VAL-OPTIONAL; RULE-VAL-NORM-ADD | JSONB | JSONB | — | — | OK |
| 83 | `awards[i].name` | RULE-VAL-OPTIONAL; RULE-VAL-NORM-ADD | JSONB | JSONB | — | — | OK |
| 84 | `awards[i].issued_by` | RULE-VAL-OPTIONAL; RULE-VAL-NORM-ADD | JSONB | JSONB | — | — | OK |
| 85 | `awards[i].awarded_at` | RULE-VAL-DATE-FULL-DOC; RULE-VAL-NORM-ADD | JSONB string | JSONB | — | RU hint | OK |
| 86 | `awards[i].document_number` | RULE-VAL-OPTIONAL; RULE-VAL-NORM-ADD | JSONB | JSONB | — | — | OK |
| 87 | `awards[i].title` legacy | migrate on read; RULE-VAL-NORM-ADD | — | — | legacy only | — | OK |
| 88 | `awards_none` | RULE-VAL-OPTIONAL bool | JSONB | JSONB | — | — | OK |
| 89 | `academic_degrees[i].degree` | RULE-VAL-OPTIONAL; RULE-VAL-NORM-ADD | JSONB | JSONB | — | — | OK |
| 90 | `degree_other` | RULE-VAL-OPTIONAL; RULE-VAL-NORM-ADD | JSONB | JSONB | — | — | OK |
| 91 | `field_of_science` (degree) | RULE-VAL-OPTIONAL; RULE-VAL-NORM-ADD | JSONB | JSONB | — | — | OK |
| 92 | `academic_degrees[i].completed_at` | RULE-VAL-DATE-FULL-DOC; RULE-VAL-NORM-ADD | JSONB | JSONB | — | RU hint | OK |
| 93 | degree `document_number` | RULE-VAL-OPTIONAL; RULE-VAL-NORM-ADD | JSONB | JSONB | — | — | OK |
| 94 | degree legacy `label` | migrate on read | — | — | legacy | — | OK |
| 95 | degree legacy `degree_type` | migrate on read | — | — | legacy | — | OK |
| 96 | `academic_degrees_none` | RULE-VAL-OPTIONAL bool | JSONB | JSONB | — | — | OK |
| 97 | `academic_titles[i].academic_title` | RULE-VAL-OPTIONAL; RULE-VAL-NORM-ADD | JSONB | JSONB | — | — | OK |
| 98 | `academic_title_other` | RULE-VAL-OPTIONAL; RULE-VAL-NORM-ADD | JSONB | JSONB | — | — | OK |
| 99 | title `field_of_science` | RULE-VAL-OPTIONAL; RULE-VAL-NORM-ADD | JSONB | JSONB | — | — | OK |
| 100 | title `completed_at` | RULE-VAL-DATE-FULL-DOC; RULE-VAL-NORM-ADD | JSONB | JSONB | — | RU hint | OK |
| 101 | title `document_number` | RULE-VAL-OPTIONAL; RULE-VAL-NORM-ADD | JSONB | JSONB | — | — | OK |
| 102 | title legacy `label` | migrate on read | — | — | legacy | — | OK |
| 103 | title legacy `degree_type` | migrate on read | — | — | legacy | — | OK |
| 104 | `academic_titles_none` | RULE-VAL-OPTIONAL bool | JSONB | JSONB | — | — | OK |
| 105 | `current_step` | RULE-VAL-OPTIONAL | — | JSONB | — | — | OK |

**Cross-cutting gates (not single field rows):**

| Gate | Binding | Evidence | Error |
|------|---------|----------|-------|
| Transfer eligibility | all accepted sections | `_evaluate_can_transfer` / `transfer_intake_to_ppr` (`app/personnel_intake/application/transfer_service.py`) | `TRANSFER_NOT_ALLOWED` |
| On-behalf concurrency | draft | `expected_updated_at` in `app/personnel_intake/application/on_behalf_edit_service.py` | 409 `DRAFT_VERSION_CONFLICT` |

### 8.2 Per-row validation binding (projection rows 106–193)

| Row # | Field path | Validation | Mismatch / notes | Alignment |
|-------|------------|------------|------------------|-----------|
| 106,107,108,109,110,111,112 | intended employment | `PprIntendedEmploymentUpdateRequest` Field constraints (`gt=0, le=2` rate; ids ≥1); applicant-only PATCH | hidden for employee | OK |
| 113,114,115,116,117,121,123,124,125,126,127,128,129,130,131,132,133,134,135,136 | applications DTO fields present on `PprPersonnelApplicationItemResponse` | application BC status machine; read-only on card | card is history read | OK |
| 118,119,120,122 | name projections expected by UI | **no validation** — fields absent from `PprPersonnelApplicationItemResponse` | UI shows «—» / `#id` | **unavailable on endpoint** |
| 137,138,139,140,141,142,143,144 | changes/events | append-only event writer; read limit 10 (`PprEventSummaryReader.DEFAULT_LIMIT` in `app/ppr/read/event_summary_reader.py`) | no field-level diff | GAP-016 |
| 145,146,147,148,149,150,151,152,153 | assignment summary/correction | `correctEmployee` (`corpsite-ui/app/directory/employees/_lib/api.client.ts`) + employee validators | enroll separate | OK Employment BC |
| 154 | enroll-from-card | blocked without `batchId` | unavailable on PPR card | documented unavailable |
| 155,156,157,158,159 | orders fields rendered on card (`order_number`, `order_id`, `order_date`, `order_type_code`, `status`) | list filters via `listPersonnelOrders` (`corpsite-ui/app/directory/personnel/_lib/personnelOrdersApi.client.ts`) → `list_personnel_orders` (`app/services/personnel_orders_query_service.py`) | — | OK projection |
| 160,161,162,163,164,165,166,167,168,169,170,171 | orders list API-only fields including `created_at` (171) | returned by `PersonnelOrderListItem`; not validated on card tab | not rendered on card | OK projection |
| 172,173,174,175,176,177,178,179,180,181,182,183,184,185,186 | onboarding fields rendered / lazy audit | onboarding complete/skip/cancel validators; `is_read_only` gates writes | empty program message not a stub | OK projection |
| 187,188,189,190,191,192,193 | onboarding API-only / control flags | used by actions or detail DTO; not labeled summary fields | — | OK projection |

---

## 9. Права, подтверждение и аудит

### 9.1 Матрица прав (as-is)

| Section/field | Employee propose | HR on-behalf intake | HR accept before PPR | HR direct PPR edit (today / future) | Read-only on card | Other BC |
|---------------|------------------|---------------------|----------------------|-------------------------------------|-------------------|----------|
| personal/contacts | ✓ propose | ✓ via on-behalf intake drawer (`corpsite-ui/app/directory/personnel/_components/PersonnelApplicationIntakeOnBehalfDrawer.tsx`) | ✓ required (personal, contacts, education per review rules) | general **planned**; contacts not PPR | general RO | application episode contacts |
| education/training/relatives/additional | ✓ | ✓ | per-section accept/skip | mostly planned; today RO on card | ✓ RO | — |
| employment_biography / military | ✓ | ✓ | per-section accept/skip | ✓ today via `app/api/ppr_command_router.py` | editable when ACL | — |
| Photo | ✓ upload | ✓ | — | planned PPR-PHOTO | — | `app/personnel_intake/application/photo_service.py` storage |
| Addresses, gender, birth_place, citizenship, nationality | ✓ propose | ✓ | optional accept personal | planned PPR-GENERAL | not shown as PPR fields | intake JSONB |
| Intended employment | ✗ | ✗ | — | ✓ `PATCH /api/ppr/persons/{person_id}/intended-employment` today | applicant tab | `personnel_record_metadata.intended_*` |
| Assignment / orders / onboarding | ✗ | ✗ | — | ✗ from PPR card (BC UIs) | ✓ projection tabs (employee) | Employment / Orders / Onboarding BC |
| Applications tab | ✗ | ✗ | registration/lifecycle elsewhere | ✗ | ✓ history | Personnel Application BC |
| Changes tab | ✗ | ✗ | — | auto on PPR mutation | ✓ last 10 | `personnel_record_events` |

### 9.2 Audit surfaces (as-is)

| Event | Storage | Evidence |
|-------|---------|----------|
| Intake autosave/submit | draft status, timestamps | `personnel_intake_drafts` via `app/personnel_intake/application/intake_service.py` |
| On-behalf edit | lifecycle audit | `app/personnel_intake/application/on_behalf_edit_service.py` → `append_lifecycle_audit` |
| Section review | `personnel_intake_section_reviews` | `app/personnel_intake/application/review_service.py` |
| Transfer | `personnel_intake_transfers` (sections, command_ids) | `app/personnel_intake/application/transfer_service.py` |
| PPR section mutation | `personnel_record_events` | `app/ppr/infrastructure/ppr_event_repository.py`; card shows last 10 via `app/ppr/read/event_summary_reader.py` |
| Direct military/emp edit | PPR events | `app/api/ppr_command_router.py` |
| Orders / onboarding / assignment writes | owning BC audit tables | personnel orders lifecycle audit; onboarding task audit; employee correction |

### 9.3 Gaps for future direct PPR editing

| Requirement | Status |
|-------------|--------|
| Author (`actor_id`) | ✓ in PPR events |
| Timestamp | ✓ `event_at` |
| Reason for change | **✗ not required** today (except some void/supersede commands) |
| Before/after values | partial in `event_payload` |
| Source (intake vs HR direct) | partial `metadata.source` on rows |
| Link to intake/evidence | **✗ no stable link** post-transfer |
| History tab completeness | **✗ limit 10**, no field-level diff UI (GAP-016) |
| Bypass domain validation | prevented by handlers |

---

## 10. Gap analysis

### 10.0 Критерий P0

**P0** — только при **полном достижимом** trace или **интеграционном тесте**, доказывающем запись **неверного** или **необратимо потерянного** canonical PPR значения. Code-only structural risk without demonstrated path → **P1** «potential wrong write».

### 10.1 Verified invariants (не gaps)

| Invariant ID | Behavior | Evidence |
|--------------|----------|----------|
| **INV-TRANSFER-020A** | Repeat `POST .../intake/transfer` after completed transfer → `idempotent_replay=True`; no new PPR section inserts | `transfer_intake_to_ppr` in `app/personnel_intake/application/transfer_service.py`; `test_transfer_success_idempotent_audit_and_draft_immutable` in `tests/personnel_intake/test_intake_review_api.py` |
| **INV-TRANSFER-020B** | Re-review/re-transfer same application after `review_completed` → blocked | `POST .../accept` → `422 REVIEW_ALREADY_COMPLETED`; on-behalf blocked via `evaluate_on_behalf_edit_eligibility` in `app/personnel_intake/domain/on_behalf_edit.py` |
| **INV-APP-020C** | At most one **active** (non-terminal) personnel application per person — unique partial index / domain rule | `test_rejects_second_active_application_per_person` in `tests/personnel_applications/test_wp_ppr_applicant_001b_migration.py`; `is_active_application_status` / `TERMINAL_APPLICATION_STATUSES` in `app/personnel_applications/domain/status.py`; lifecycle model `docs/architecture/WP-PPR-APPLICANT-001A-personnel-application-data-model.md` (active vs terminal predicates) |

### 10.2 Доказательный разбор GAP-020D

| Step | Claim | Proven? | Evidence |
|------|-------|---------|----------|
| 1 | `handle_add_external_employment_record` has no duplicate guard | **Yes** (code) | `app/ppr/domain/section_handlers.py` `handle_add_external_employment_record` — no `_assert_no_duplicate_external_employment` |
| 2 | Second application allowed after terminal prior app | **Yes** (DB) | `test_terminal_status_allows_new_application` in `tests/personnel_applications/test_wp_ppr_applicant_001b_migration.py` |
| 3 | Blocked while prior app active (`review_completed` is active, not terminal) | **Yes** | INV-APP-020C; `review_completed` ∉ `TERMINAL_APPLICATION_STATUSES` |
| 4 | Full path: terminal → new app → intake → transfer emp_bio → **duplicate rows** | **No E2E test** | No test in `tests/personnel_intake/` or `tests/ppr/` covering re-transfer employment_biography |
| **Verdict** | Potential wrong write from code structure | **P1**, not P0 |

### 10.3 Доказательный разбор GAP-020E / GAP-020F (re-application after terminal)

| Step | Claim | Proven? | Evidence |
|------|-------|---------|----------|
| 1 | New application after terminal prior app is **allowed** | **Yes** | `test_terminal_status_allows_new_application` |
| 2 | No separate business rule forbids re-transfer of education/military after that | **Yes** (absence) | No ops rule in `docs/architecture/WP-PPR-APPLICANT-001A-personnel-application-data-model.md` / intake transfer docs that says «education/military transfer forbidden after prior materialization» |
| 3 | Education re-transfer blocked by duplicate fingerprint guard | **Yes** (code) | `_assert_no_duplicate_education` in `app/ppr/domain/section_handlers.py` |
| 4 | Military re-create blocked by one-active-record guard | **Yes** (code) | `MILITARY_ACTIVE_RECORD_ALREADY_EXISTS` in `handle_create_military_service_record` |
| **Verdict** | Allowable lifecycle (new app after terminal) is **blocked at transfer** by protective guards without match/supersede path | **P1** for both GAP-020E and GAP-020F |

### 10.4 Сводная таблица gaps

| Gap ID | Section/field | Current behavior | Risk if achievable | Evidence | Target rule | Priority |
|--------|---------------|------------------|----------------------|----------|-------------|----------|
| GAP-001 | General attrs | Not in PPR/card | Incomplete vs WP-PR-003 | `transfer_service._transfer_general_and_contacts` (`app/personnel_intake/application/transfer_service.py`); `corpsite-ui/app/directory/personnel/_components/PprCardGeneralSection.tsx` | Materialize PPR-GENERAL; gender normalize+transfer on accept, non-blocking (HR Q6) | **P1** |
| GAP-002 | Contacts | Episode on application | Card lacks accepted contacts | `transfer_service._transfer_general_and_contacts` (`app/personnel_intake/application/transfer_service.py`); `docs/architecture/WP-PPR-APPLICANT-001A-personnel-application-data-model.md` §5.1 | On accept → canonical PPR-CONTACTS; application retains historical snapshot (HR Q2) | **P1** |
| GAP-003 | Addresses | Intake JSONB only | Not canonical | no transfer path | PPR-ADDRESSES | **P1** |
| GAP-004 | Photo | File storage | PPR-PHOTO missing | `app/personnel_intake/application/photo_service.py` | Link PPR-PHOTO | **P1** |
| GAP-005 | Transfer dates | No re-validation at transfer | Defense gap | `parse_date_value` (`app/personnel_intake/application/intake_mapper.py`); submit tests in `tests/personnel_intake/` | Re-validate in transfer | **P1** |
| GAP-006 | Education fingerprint | `(kind, institution)` | Submit/transfer fail on dup | `tests/personnel_intake/test_intake_education_type.py` | Richer fingerprint if HR rule | **P1** |
| GAP-007 | Name parts | Only `full_name` UPDATE | Stale split columns | SQL in `_transfer_general_and_contacts` | Update all name columns | **P1** |
| GAP-008 | Training kind | Always `course` | Taxonomy loss | `map_training_records` (`app/personnel_intake/application/intake_mapper.py`) | No default `course`; HR classify before canonical (HR Q4) | **P1** |
| GAP-009 | Relationship | → `other_close` | Lossy enum | `map_relationship_type` (`app/personnel_intake/application/intake_mapper.py`) | Controlled vocabulary | **P1** |
| GAP-010 | Military semantics | status→registration_status | HR confusion | `map_military_record` (`app/personnel_intake/application/intake_mapper.py`) | Field catalog | **P1** |
| GAP-011 | Additional read | Intake if metadata empty | Proposal as canonical UI | `merge_additional_profiles` in `app/personnel_intake/domain/additional_profile.py` | After transfer: no draft merge into card; show in application history (HR Q5) | **P2** |
| GAP-012 | Education display | Year-only range | Misread precision | `corpsite-ui/app/directory/personnel/_components/PprCardEducationSection.tsx` | Precision badge | **P2** |
| GAP-013 | General RO | No edit | Blocks coordination | `corpsite-ui/app/directory/personnel/_components/PprCardGeneralSection.tsx` | Edit WP | **P2** |
| GAP-014 | Personnel number | Intake JSONB only | Not on Employee | no ORM column | Employee/employment BC, not Person (HR Q1) | **P2** |
| GAP-015 | Identity docs | Not implemented | Arch gap | WP-PR-003 | PPR-IDENTITY-DOCUMENTS | **P1** |
| GAP-016 | History tab | Last 10 events | Weak audit | `PprEventSummaryReader.DEFAULT_LIMIT` (`app/ppr/read/event_summary_reader.py`) | Full history | **P2** |
| GAP-017 | `birth_year` path | Misnamed | Integration confusion | `IntakeDraftPayload` in `corpsite-ui/app/intake/_lib/intakeApi.client.ts` | Rename | **P2** |
| GAP-018 | UEPC Unified Spec | Missing file | Traceability | glob search | Formal replacement deferred; stop only dependent WP slice (HR Q8) | **P3** |
| GAP-019 | `specialty_name` | Not in UI | Hidden field | `corpsite-ui/app/intake/_lib/intakeDraftReconcile.ts` | Show or drop | **P3** |
| GAP-020D | Re-app emp_bio duplicate | No dup guard (code) | **Potential** duplicate rows | `handle_add_external_employment_record` (`app/ppr/domain/section_handlers.py`); **no E2E test** | No blind append; match + add/update-version/supersede/manual review (HR Q7) | **P1** |
| GAP-020E | Re-app education transfer | Transfer fails on duplicate fingerprint after allowed new app | Blocks allowable re-intake materialization | `_assert_no_duplicate_education` (`app/ppr/domain/section_handlers.py`); `test_terminal_status_allows_new_application` | No auto-merge/delete; HR decides via match + actions (HR Q3/Q7) | **P1** |
| GAP-020F | Re-app military transfer | Transfer/create fails when active military exists after allowed new app | Blocks allowable re-intake materialization | `MILITARY_ACTIVE_RECORD_ALREADY_EXISTS` (`app/ppr/domain/section_handlers.py`); terminal→new app allowed | No blind append; match + add/update-version/supersede/manual review (HR Q7) | **P1** |
| GAP-021 | Period Jan 1 | Blocked at submit | Valid dates rejected | `test_incomplete_period_dates` | Precision marker | **P1** |

**Автоматический пересчёт:** **P0: 0** | **P1: 15** | **P2: 6** | **P3: 2**

*(P1: GAP-001…010, GAP-015, GAP-020D, GAP-020E, GAP-020F, GAP-021 = 15; P2: GAP-011…014, GAP-016, GAP-017 = 6; P3: GAP-018, GAP-019 = 2. Former GAP-020C → INV-APP-020C.)*

---

## 11. Целевая координационная модель

Направление (без реализации в этом WP):

1. **Единый каталог бизнес-полей** — codify from WP-PR-003 section codes + this inventory; intake paths as `proposal.*`, PPR as `canonical.*`; projection tabs as `projection.*` with explicit owning BC.
2. **Shared labels/dictionaries/validators** where semantics match (dates, education kinds, military catalogs already partially shared via `@/lib/militaryDictionary`, `intakeAdditional` reused in card).
3. **Separate write contracts:** `IntakeProposalPatch` ≠ `PprSectionCommand`; mapping layer explicit (`intake_mapper` evolution), never raw payload → PPR without ACL + HR accept.
4. **Presentation formatters** must expose precision (day vs year vs unknown), not hide via uniform `year` display; date precision markers mandatory where year-only is legitimate.
5. **Card editing** — section-scoped drawers/commands (pattern: employment_biography, military), not full intake wizard for hired employees.
6. **Collections:** stable record identity (server ids); **re-application after terminal** forbids blind append — each record needs match and an explicit action: add / update-version / supersede / manual review (HR Q7).
7. **Audit/provenance:** every canonical change → `personnel_record_events` with reason, before/after, source enum (`intake_transfer`, `hr_direct`, `import`).
8. **UI component sharing** — decision deferred until field catalog stable; prioritize schema/dictionary alignment first.
9. **Projection tabs** remain BC-owned; card shows summary fields only; unavailable joins/workflows must be explicit (as in §4.11 name fields, §4.13 enroll-without-batch).
10. **HR decisions Q1–Q7** (see §12) constrain future implementation WPs; they do not by themselves reopen inventory gap priorities without new runtime evidence.

---

## 12. HR decisions (Q1–Q8)

| # | HR decision (normative for future WPs) | Status |
|---|----------------------------------------|--------|
| **Q1** | Табельный номер относится к **Employee / трудоустройству**, не к Person. В intake — только provisional; канон — Employment/Employee BC. | **Approved** |
| **Q2** | После одобрения контакты переносятся в canonical **PPR-CONTACTS**. Анкета / application `contact_*` сохраняется как **исторический snapshot** episode. | **Approved** |
| **Q3** | Неоднозначные записи об образовании **автоматически не объединять и не удалять** — решение принимает кадровик (match / manual review; см. также Q7). | **Approved** |
| **Q4** | Не подставлять `training_kind=course` при отсутствии значения. Без классификации кадровиком запись **не становится canonical**. | **Approved** |
| **Q5** | После canonical transfer черновые additional-сведения **не подмешивать** в карточку; показывать отдельно в **истории заявления**. | **Approved** |
| **Q6** | Пол не влияет на кадровые решения и **не блокирует** обработку. При одобрении — нормализовать и переносить в canonical; расхождение кадровик может исправить. | **Approved** |
| **Q7** | При повторной анкете **запрещён blind append**: для каждой записи нужны match и действие **add / update-version / supersede / manual review**. | **Approved** |
| **Q8** | Формальная замена отсутствующего UEPC Unified Spec **отложена**. До решения разработчик не додумывает отсутствующие правила; при реальной зависимости останавливается только спорная часть WP и формулируется конкретный вопрос. Пока опора: WP-PR-003 + `docs-work/UEPC-Ubiquitous-Language.md` + `tests/fixtures/ppr_reference_person.json` (GAP-018 остаётся **P3**). | **Deferred / non-blocking** |

**Summary:** Q1–Q7 **approved**; Q8 **deferred (non-blocking)**. Inventory gap priorities (§10.4) unchanged in this revision.

---

## 13. Review resolution

### 13.1 Editorial pass (rev.5) — retained

| Review remark | Change in rev.5 | Status |
|---------------|-----------------|--------|
| §6 missing date/datetime fields (incl. 129, 134, orders `created_at`) | §6.2 rebuilt from full §4 sweep | Recorded in rev.5 |
| Row 155 combined `order_number` + `order_id` | Split; total **193** rows | Recorded in rev.5 |
| §5 compositional rules | Coverage claim + allowed intersections | Recorded in rev.5 |
| Evidence / INV-APP-020C citation | Expanded paths; WP-PPR-APPLICANT-001A | Recorded in rev.5 |
| Gap priorities | **P0:0 / P1:15 / P2:6 / P3:2** | **Unchanged** (no new runtime evidence in rev.5–6) |

### 13.2 HR review (rev.6)

| Item | Outcome |
|------|---------|
| Q1–Q7 | **Approved** — decisions recorded in §12; §11 item 6/10 aligned |
| Q8 | **Deferred / non-blocking** — no formal UEPC Unified Spec replacement; stop-on-dependency rule for implementers |
| Architecture verdicts / gap priorities | **Not changed** in rev.6 (HR product rules ≠ new runtime proof for priority recalculation) |

**Still out of inventory scope (implementation WP):**

- Materialization of GAP-001…021 and HR Q1–Q7 rules in code.
- E2E proof that GAP-020D produces duplicate employment rows.
- Enrichment of `PprPersonnelApplicationItemResponse` with placement/HR names.
- Formal UEPC Unified Spec registry decision (Q8).

---

## Appendix A — Evidence index

| Layer | Path |
|-------|------|
| Intake UI | `corpsite-ui/app/intake/_components/IntakeDraftFormEditor.tsx` |
| Intake DTO | `corpsite-ui/app/intake/_lib/intakeApi.client.ts` |
| PPR card UI | `corpsite-ui/app/directory/personnel/_components/PprPersonalCardPageClient.tsx` |
| PPR DTO | `corpsite-ui/app/directory/personnel/_lib/pprQueryTypes.ts`; `app/api/ppr_schemas.py` |
| Transfer | `app/personnel_intake/application/transfer_service.py`, `app/personnel_intake/application/intake_mapper.py` |
| PPR domain | `app/ppr/domain/section_handlers.py`, `app/ppr/domain/section_record_validation.py` |
| Orders projection | `corpsite-ui/app/directory/personnel/_components/EmployeeCardOrdersSection.tsx`; `app/services/personnel_orders_query_service.py` `list_personnel_orders` |
| Onboarding projection | `corpsite-ui/app/directory/personnel/_components/EmployeeOnboardingSection.tsx`; `corpsite-ui/app/directory/personnel/_lib/employeeOnboardingApi.client.ts` |
| Assignment projection | `corpsite-ui/app/directory/personnel/_components/EmployeeOperationalAssignmentSection.tsx` |
| Tests | `tests/personnel_intake/test_intake_review_api.py`, `tests/personnel_intake/test_intake_education_type.py`, `tests/personnel_intake/test_intake_date_validation.py`, `tests/personnel_applications/test_wp_ppr_applicant_001b_migration.py` |

---

*End of inventory document rev.6. HR Q1–Q7 approved; Q8 deferred. Implementation deliberately not started.*
