"use client";

import * as React from "react";

import IntakeDictionaryCombobox from "./IntakeDictionaryCombobox";
import IntakeMilitaryCombobox from "./IntakeMilitaryCombobox";
import {
  INTAKE_CITIZENSHIP_CATALOG,
  INTAKE_CITIZENSHIP_POPULAR,
  INTAKE_NATIONALITY_CATALOG,
  INTAKE_NATIONALITY_POPULAR,
} from "../_lib/intakePersonalDictionary";
import {
  applyIntakeMilitaryCompositionChange,
  getIntakeMilitaryRankOptions,
  INTAKE_MILITARY_COMPOSITION_CATALOG,
  normalizeIntakeMilitaryComposition,
  reconcileIntakeMilitaryDraftOnLoad,
} from "../_lib/intakeMilitaryDictionary";
import {
  INTAKE_EDUCATION_TYPE_OPTIONS,
  INTAKE_STEPS,
  emptyIntakeDraftPayload,
  type IntakeDraftPayload,
  type IntakeEducation,
} from "../_lib/intakeApi.client";
import {
  applyContactsRegistrationAddressChange,
  applyContactsResidenceMirror,
  contactsMirrorResidence,
  formatIntakeFullName,
} from "../_lib/intakeContactHelpers";
import PersonnelDayDateField from "@/lib/PersonnelDayDateField";
import {
  formatIntakeBirthDateForDisplay,
  formatIntakeEducationReviewLine,
  formatIntakeEmploymentReviewLine,
  formatIntakeRelativeReviewLine,
  formatIntakeTrainingReviewLine,
} from "../_lib/intakePeriodFormat";
import {
  collectIntakeDateValidationIssues,
  resolveIntakeDateIssueStepIndex,
  type IntakeDateFieldKind,
  type IntakeDateValidationIssue,
} from "../_lib/intakeDateValidation";
import { sanitizeMilitarySpecialtyCodeInput } from "@/lib/militarySpecialtyCode";

function SelectField<V extends string>({
  label,
  value,
  onChange,
  readOnly,
  required = false,
  options,
}: {
  label: string;
  value: V;
  onChange: (v: V) => void;
  readOnly?: boolean;
  required?: boolean;
  options: ReadonlyArray<{ value: V; label: string }>;
}) {
  return (
    <label className="block">
      <span className="text-sm font-medium text-zinc-700 dark:text-zinc-300">
        {label}
        {required ? " *" : ""}
      </span>
      <select
        value={value}
        disabled={readOnly}
        onChange={(e) => {
          const selected = options.find((option) => option.value === e.target.value);
          if (selected) onChange(selected.value);
        }}
        className="mt-1 w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm disabled:bg-zinc-50 dark:border-zinc-700 dark:bg-zinc-950 dark:disabled:bg-zinc-900"
      >
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </label>
  );
}

function Field({
  label,
  value,
  onChange,
  readOnly,
  type = "text",
  required = false,
  testId,
  maxLength,
  inputMode,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  readOnly?: boolean;
  type?: string;
  required?: boolean;
  testId?: string;
  maxLength?: number;
  inputMode?: React.HTMLAttributes<HTMLInputElement>["inputMode"];
}) {
  return (
    <label className="block">
      <span className="text-sm font-medium text-zinc-700 dark:text-zinc-300">
        {label}
        {required ? " *" : ""}
      </span>
      <input
        type={type}
        value={value}
        readOnly={readOnly}
        data-testid={testId}
        maxLength={maxLength}
        inputMode={inputMode}
        onChange={(e) => onChange(e.target.value)}
        className="mt-1 w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm read-only:bg-zinc-50 dark:border-zinc-700 dark:bg-zinc-950 dark:read-only:bg-zinc-900"
      />
    </label>
  );
}

function IntakeDateField({
  label,
  value,
  onChange,
  readOnly,
  kind,
  required = false,
  testId,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  readOnly?: boolean;
  kind: IntakeDateFieldKind;
  required?: boolean;
  testId?: string;
}) {
  return (
    <PersonnelDayDateField
      label={label}
      value={value}
      onChange={onChange}
      readOnly={readOnly}
      required={required}
      testId={testId}
      mode={kind}
    />
  );
}

function StepPersonal({
  payload,
  onChange,
  readOnly,
}: {
  payload: IntakeDraftPayload;
  onChange: (p: IntakeDraftPayload) => void;
  readOnly?: boolean;
}) {
  const p = payload.personal;
  const set = (key: keyof typeof p, value: string) =>
    onChange({ ...payload, personal: { ...p, [key]: value } });
  return (
    <div className="grid gap-4 sm:grid-cols-2">
      <Field label="Фамилия" value={p.last_name} onChange={(v) => set("last_name", v)} readOnly={readOnly} required />
      <Field label="Имя" value={p.first_name} onChange={(v) => set("first_name", v)} readOnly={readOnly} required />
      <Field label="Отчество" value={p.middle_name} onChange={(v) => set("middle_name", v)} readOnly={readOnly} />
      <IntakeDateField
        label="Дата рождения"
        value={p.birth_date}
        onChange={(v) => set("birth_date", v)}
        readOnly={readOnly}
        kind="birth"
        testId="intake-birth-date"
      />
      <Field label="Место рождения" value={p.birth_place} onChange={(v) => set("birth_place", v)} readOnly={readOnly} />
      <Field label="Пол" value={p.gender} onChange={(v) => set("gender", v)} readOnly={readOnly} />
      <IntakeDictionaryCombobox
        label="Гражданство"
        value={p.citizenship}
        onChange={(v) => set("citizenship", v)}
        readOnly={readOnly}
        popular={INTAKE_CITIZENSHIP_POPULAR}
        catalog={INTAKE_CITIZENSHIP_CATALOG}
        testId="intake-citizenship"
      />
      <IntakeDictionaryCombobox
        label="Национальность"
        value={p.nationality}
        onChange={(v) => set("nationality", v)}
        readOnly={readOnly}
        popular={INTAKE_NATIONALITY_POPULAR}
        catalog={INTAKE_NATIONALITY_CATALOG}
        testId="intake-nationality"
      />
    </div>
  );
}

function StepContacts({
  payload,
  onChange,
  readOnly,
}: {
  payload: IntakeDraftPayload;
  onChange: (p: IntakeDraftPayload) => void;
  readOnly?: boolean;
}) {
  const c = payload.contacts;
  const [mirrorResidence, setMirrorResidence] = React.useState(() => contactsMirrorResidence(c));

  const set = (key: keyof typeof c, value: string) =>
    onChange({ ...payload, contacts: { ...c, [key]: value } });

  return (
    <div className="grid gap-4">
      <Field label="Мобильный телефон" value={c.mobile_phone} onChange={(v) => set("mobile_phone", v)} readOnly={readOnly} required />
      <Field label="Email" value={c.email} onChange={(v) => set("email", v)} readOnly={readOnly} type="email" />
      <Field
        label="Адрес регистрации"
        value={c.registration_address}
        onChange={(v) =>
          onChange({
            ...payload,
            contacts: applyContactsRegistrationAddressChange(c, v, mirrorResidence),
          })
        }
        readOnly={readOnly}
      />
      {!readOnly ? (
        <label className="flex items-center gap-2 text-sm text-zinc-700 dark:text-zinc-300">
          <input
            type="checkbox"
            checked={mirrorResidence}
            data-testid="intake-residence-mirror"
            onChange={(e) => {
              const checked = e.target.checked;
              setMirrorResidence(checked);
              onChange({
                ...payload,
                contacts: applyContactsResidenceMirror(c, checked),
              });
            }}
          />
          Адрес проживания совпадает с адресом регистрации
        </label>
      ) : null}
      <Field
        label="Адрес проживания"
        value={c.residence_address}
        testId="intake-residence-address"
        onChange={(v) => {
          setMirrorResidence(false);
          set("residence_address", v);
        }}
        readOnly={readOnly || mirrorResidence}
      />
    </div>
  );
}

type CardListFieldDef<T extends Record<string, string>> = {
  [K in keyof T]: {
    key: K;
    label: string;
    required?: boolean;
    dateKind?: IntakeDateFieldKind;
    testId?: string;
    options?: ReadonlyArray<{ value: Extract<T[K], string>; label: string }>;
  };
}[keyof T];

function CardListStep<T extends Record<string, string>>({
  title,
  items,
  emptyItem,
  fields,
  readOnly,
  onChange,
}: {
  title: string;
  items: T[];
  emptyItem: T;
  fields: CardListFieldDef<T>[];
  readOnly?: boolean;
  onChange: (items: T[]) => void;
}) {
  return (
    <div className="space-y-4">
      {items.length === 0 ? (
        <p className="text-sm text-zinc-500">Записей пока нет.</p>
      ) : (
        items.map((item, index) => (
          <div key={index} className="rounded-xl border border-zinc-200 p-4 dark:border-zinc-800">
            <div className="grid gap-3 sm:grid-cols-2">
              {fields.map((f) =>
                f.options ? (
                  <SelectField
                    key={String(f.key)}
                    label={f.label}
                    value={String(item[f.key] ?? f.options[0]?.value ?? "")}
                    readOnly={readOnly}
                    required={f.required}
                    options={f.options}
                    onChange={(v) => {
                      const next = [...items];
                      next[index] = { ...item, [f.key]: v };
                      onChange(next);
                    }}
                  />
                ) : f.dateKind ? (
                  <IntakeDateField
                    key={String(f.key)}
                    label={f.label}
                    value={String(item[f.key] ?? "")}
                    readOnly={readOnly}
                    required={f.required}
                    kind={f.dateKind}
                    testId={f.testId ? `${f.testId}-${index}` : undefined}
                    onChange={(v) => {
                      const next = [...items];
                      next[index] = { ...item, [f.key]: v };
                      onChange(next);
                    }}
                  />
                ) : (
                  <Field
                    key={String(f.key)}
                    label={f.label}
                    value={String(item[f.key] ?? "")}
                    readOnly={readOnly}
                    required={f.required}
                    onChange={(v) => {
                      const next = [...items];
                      next[index] = { ...item, [f.key]: v };
                      onChange(next);
                    }}
                  />
                ),
              )}
            </div>
            {!readOnly ? (
              <button
                type="button"
                className="mt-3 text-sm text-red-600 hover:underline"
                onClick={() => onChange(items.filter((_, i) => i !== index))}
              >
                Удалить
              </button>
            ) : null}
          </div>
        ))
      )}
      {!readOnly ? (
        <button
          type="button"
          className="rounded-lg border border-dashed border-zinc-300 px-4 py-2 text-sm text-zinc-700 hover:bg-zinc-50 dark:border-zinc-700 dark:text-zinc-300"
          onClick={() => onChange([...items, { ...emptyItem }])}
        >
          Добавить {title.toLowerCase()}
        </button>
      ) : null}
    </div>
  );
}

export function reconcileIntakeDraftPayload(payload: IntakeDraftPayload): IntakeDraftPayload {
  const military = {
    ...emptyIntakeDraftPayload().military,
    ...payload.military,
    specialty_name: payload.military?.specialty_name ?? "",
  };
  return {
    ...payload,
    military: reconcileIntakeMilitaryDraftOnLoad(military),
  };
}

function StepMilitary({
  payload,
  onChange,
  readOnly,
}: {
  payload: IntakeDraftPayload;
  onChange: (p: IntakeDraftPayload) => void;
  readOnly?: boolean;
}) {
  const m = payload.military;
  const composition = normalizeIntakeMilitaryComposition(m.composition);
  const rankOptions = React.useMemo(
    () => getIntakeMilitaryRankOptions(composition),
    [composition],
  );
  const set = (key: keyof typeof m, value: string) =>
    onChange({ ...payload, military: { ...m, [key]: value } });

  return (
    <div className="grid gap-4 sm:grid-cols-2">
      <IntakeMilitaryCombobox
        label="Состав"
        value={composition}
        onChange={(nextComposition) =>
          onChange({
            ...payload,
            military: {
              ...m,
              ...applyIntakeMilitaryCompositionChange(nextComposition, m.rank),
            },
          })
        }
        options={INTAKE_MILITARY_COMPOSITION_CATALOG}
        readOnly={readOnly}
        testId="intake-military-composition"
      />
      <IntakeMilitaryCombobox
        label="Воинское звание"
        value={m.rank}
        onChange={(v) => set("rank", v)}
        options={rankOptions}
        readOnly={readOnly}
        disabled={!composition}
        allowFreeText={composition === "other"}
        testId="intake-military-rank"
      />
      <Field label="Статус" value={m.status} onChange={(v) => set("status", v)} readOnly={readOnly} />
      <Field label="Категория" value={m.category} onChange={(v) => set("category", v)} readOnly={readOnly} />
      <Field
        label="Номер ВУС"
        value={m.specialty_code}
        onChange={(v) => set("specialty_code", sanitizeMilitarySpecialtyCodeInput(v))}
        readOnly={readOnly}
        testId="intake-military-specialty-code"
        maxLength={7}
        inputMode="numeric"
      />
      <Field label="Категория годности" value={m.fitness_category} onChange={(v) => set("fitness_category", v)} readOnly={readOnly} />
      <Field label="Военкомат" value={m.commissariat} onChange={(v) => set("commissariat", v)} readOnly={readOnly} />
      <Field label="Группа учёта" value={m.registration_group} onChange={(v) => set("registration_group", v)} readOnly={readOnly} />
      <Field label="Категория учёта" value={m.registration_category} onChange={(v) => set("registration_category", v)} readOnly={readOnly} />
    </div>
  );
}

export type IntakeDraftFormEditorProps = {
  payload: IntakeDraftPayload;
  onChange: (payload: IntakeDraftPayload) => void;
  readOnly?: boolean;
  stepIndex: number;
  onStepIndexChange: (index: number) => void;
  error?: string | null;
  saveNotice?: string | null;
  saving?: boolean;
  mode?: "public" | "hr-on-behalf";
  onPrimaryAction?: () => void;
  primaryActionBusy?: boolean;
  primaryActionLabel?: string;
  primaryActionDisabled?: boolean;
  reviewNotice?: string | null;
  headerTitle?: string;
  footerHint?: string | null;
  compact?: boolean;
  initialFocusTestId?: string | null;
};

export default function IntakeDraftFormEditor({
  payload,
  onChange,
  readOnly = false,
  stepIndex,
  onStepIndexChange,
  error,
  saveNotice,
  saving = false,
  mode = "public",
  onPrimaryAction,
  primaryActionBusy = false,
  primaryActionLabel,
  primaryActionDisabled = false,
  reviewNotice,
  headerTitle,
  footerHint,
  compact = false,
  initialFocusTestId = null,
}: IntakeDraftFormEditorProps) {
  const currentStep = INTAKE_STEPS[stepIndex];
  const dateValidationIssues = React.useMemo(
    () => collectIntakeDateValidationIssues(payload),
    [payload],
  );
  const hasDateValidationIssues = dateValidationIssues.length > 0;
  const submitBlockedByDates = currentStep.id === "review" && hasDateValidationIssues;
  const [pendingFocusTestId, setPendingFocusTestId] = React.useState<string | null>(initialFocusTestId);

  React.useEffect(() => {
    setPendingFocusTestId(initialFocusTestId ?? null);
  }, [initialFocusTestId]);

  React.useEffect(() => {
    if (!pendingFocusTestId || readOnly) return;
    const element = document.querySelector(
      `[data-testid="${pendingFocusTestId}"]`,
    ) as HTMLInputElement | null;
    if (!element) return;
    element.focus();
    element.scrollIntoView?.({ block: "center", behavior: "smooth" });
    setPendingFocusTestId(null);
  }, [pendingFocusTestId, readOnly, stepIndex]);

  function navigateToDateIssue(issue: IntakeDateValidationIssue) {
    const nextIndex = resolveIntakeDateIssueStepIndex(issue);
    onStepIndexChange(nextIndex);
    onChange({ ...payload, current_step: INTAKE_STEPS[nextIndex].id });
    setPendingFocusTestId(issue.focusTestId);
  }

  function goNext() {
    const nextIndex = Math.min(stepIndex + 1, INTAKE_STEPS.length - 1);
    onStepIndexChange(nextIndex);
    onChange({ ...payload, current_step: INTAKE_STEPS[nextIndex].id });
  }

  function goBack() {
    const nextIndex = Math.max(stepIndex - 1, 0);
    onStepIndexChange(nextIndex);
    onChange({ ...payload, current_step: INTAKE_STEPS[nextIndex].id });
  }

  const title =
    headerTitle ??
    `Анкета сотрудника. Шаг ${stepIndex + 1} из ${INTAKE_STEPS.length} – ${currentStep.title}`;

  return (
    <div className={compact ? "space-y-4" : "min-h-screen bg-zinc-50 dark:bg-zinc-950"}>
      <div className={compact ? "" : "mx-auto max-w-3xl px-4 py-8"}>
        <header className="mb-6">
          <h1 className={compact ? "text-lg font-semibold text-zinc-900 dark:text-zinc-50" : "text-2xl font-semibold text-zinc-900 dark:text-zinc-50"}>
            {title}
          </h1>
          <div className="mt-3 h-2 overflow-hidden rounded-full bg-zinc-200 dark:bg-zinc-800">
            <div
              className="h-full bg-sky-600 transition-all"
              style={{ width: `${((stepIndex + 1) / INTAKE_STEPS.length) * 100}%` }}
            />
          </div>
          {saveNotice ? <p className="mt-2 text-xs text-zinc-500">{saving ? "Сохранение…" : saveNotice}</p> : null}
        </header>

        <main className="rounded-xl border border-zinc-200 bg-white p-6 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
          {error ? <p className="mb-4 text-sm text-red-600">{error}</p> : null}

          {currentStep.id === "personal" ? (
            <StepPersonal payload={payload} onChange={onChange} readOnly={readOnly} />
          ) : null}
          {currentStep.id === "contacts" ? (
            <StepContacts payload={payload} onChange={onChange} readOnly={readOnly} />
          ) : null}
          {currentStep.id === "education" ? (
            <CardListStep<IntakeEducation>
              title="образование"
              items={payload.education}
              emptyItem={{
                education_type: "basic",
                institution: "",
                year_from: "",
                year_to: "",
                specialty: "",
                qualification: "",
                diploma_number: "",
              }}
              fields={[
                {
                  key: "education_type",
                  label: "Вид образования",
                  required: true,
                  options: INTAKE_EDUCATION_TYPE_OPTIONS,
                },
                { key: "institution", label: "Учебное заведение" },
                {
                  key: "year_from",
                  label: "Дата поступления",
                  dateKind: "period",
                  testId: "intake-education-year-from",
                },
                {
                  key: "year_to",
                  label: "Дата окончания",
                  dateKind: "period",
                  testId: "intake-education-year-to",
                },
                { key: "specialty", label: "Специальность" },
                { key: "qualification", label: "Квалификация" },
                { key: "diploma_number", label: "№ диплома" },
              ]}
              readOnly={readOnly}
              onChange={(items) => onChange({ ...payload, education: items })}
            />
          ) : null}
          {currentStep.id === "training" ? (
            <CardListStep
              title="обучение"
              items={payload.training}
              emptyItem={{ institution: "", year: "", course_name: "", hours: "" }}
              fields={[
                { key: "institution", label: "Организация" },
                { key: "year", label: "Дата окончания", dateKind: "period", testId: "intake-training-year" },
                { key: "course_name", label: "Курс" },
              ]}
              readOnly={readOnly}
              onChange={(items) => onChange({ ...payload, training: items })}
            />
          ) : null}
          {currentStep.id === "relatives" ? (
            <CardListStep
              title="родственника"
              items={payload.relatives}
              emptyItem={{ relationship: "", full_name: "", birth_year: "", work_place: "" }}
              fields={[
                { key: "relationship", label: "Степень родства" },
                { key: "full_name", label: "ФИО" },
                { key: "birth_year", label: "Дата рождения", dateKind: "period", testId: "intake-relative-birth-year" },
                { key: "work_place", label: "Место работы" },
              ]}
              readOnly={readOnly}
              onChange={(items) => onChange({ ...payload, relatives: items })}
            />
          ) : null}
          {currentStep.id === "employment_biography" ? (
            <CardListStep
              title="место работы"
              items={payload.employment_biography}
              emptyItem={{ organization: "", position: "", year_from: "", year_to: "", reason_for_leaving: "" }}
              fields={[
                { key: "organization", label: "Организация" },
                { key: "position", label: "Должность" },
                { key: "year_from", label: "Дата начала", dateKind: "period", testId: "intake-employment-year-from" },
                { key: "year_to", label: "Дата окончания", dateKind: "period", testId: "intake-employment-year-to" },
                { key: "reason_for_leaving", label: "Причина увольнения" },
              ]}
              readOnly={readOnly}
              onChange={(items) => onChange({ ...payload, employment_biography: items })}
            />
          ) : null}
          {currentStep.id === "military" ? (
            <StepMilitary payload={payload} onChange={onChange} readOnly={readOnly} />
          ) : null}
          {currentStep.id === "review" ? (
            <div className="space-y-3 text-sm text-zinc-700 dark:text-zinc-300" data-testid="intake-review-summary">
              <p>
                {mode === "hr-on-behalf"
                  ? "Проверьте сведения перед сохранением от имени претендента."
                  : "Проверьте введённые сведения перед отправкой в отдел кадров."}
              </p>
              {mode === "hr-on-behalf" && reviewNotice ? (
                <p className="text-amber-700 dark:text-amber-300" data-testid="intake-on-behalf-review-notice">
                  {reviewNotice}
                </p>
              ) : null}
              <ul className="list-disc space-y-1 pl-5">
                <li>ФИО: {formatIntakeFullName(payload.personal) || "—"}</li>
                <li>Дата рождения: {formatIntakeBirthDateForDisplay(payload.personal.birth_date) || "—"}</li>
                <li>Телефон: {payload.contacts.mobile_phone || "—"}</li>
                <li>Email: {payload.contacts.email || "—"}</li>
                <li>
                  Образование:{" "}
                  {payload.education.length === 0
                    ? "0 зап."
                    : payload.education.map((item, index) => (
                        <span key={`education-${index}`} data-testid={`intake-review-education-${index}`}>
                          {index > 0 ? "; " : ""}
                          {formatIntakeEducationReviewLine(item)}
                        </span>
                      ))}
                </li>
                <li>
                  Обучение:{" "}
                  {payload.training.length === 0
                    ? "0 зап."
                    : payload.training.map((item, index) => (
                        <span key={`training-${index}`} data-testid={`intake-review-training-${index}`}>
                          {index > 0 ? "; " : ""}
                          {formatIntakeTrainingReviewLine(item)}
                        </span>
                      ))}
                </li>
                <li>
                  Родственники:{" "}
                  {payload.relatives.length === 0
                    ? "0 зап."
                    : payload.relatives.map((item, index) => (
                        <span key={`relatives-${index}`} data-testid={`intake-review-relative-${index}`}>
                          {index > 0 ? "; " : ""}
                          {formatIntakeRelativeReviewLine(item)}
                        </span>
                      ))}
                </li>
                <li>
                  Предыдущие места работы:{" "}
                  {payload.employment_biography.length === 0
                    ? "0 зап."
                    : payload.employment_biography.map((item, index) => (
                        <span key={`employment-${index}`} data-testid={`intake-review-employment-${index}`}>
                          {index > 0 ? "; " : ""}
                          {formatIntakeEmploymentReviewLine(item)}
                        </span>
                      ))}
                </li>
              </ul>
              {hasDateValidationIssues ? (
                <div
                  className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-amber-900 dark:border-amber-900 dark:bg-amber-950/40 dark:text-amber-200"
                  data-testid="intake-review-date-issues"
                >
                  <p className="font-medium">Уточните даты перед отправкой:</p>
                  <ul className="mt-1 list-disc pl-5">
                    {dateValidationIssues.map((issue) => (
                      <li key={issue.field}>
                        <button
                          type="button"
                          className="text-left underline decoration-amber-700/60 underline-offset-2 hover:decoration-amber-900 dark:decoration-amber-300/60 dark:hover:decoration-amber-100"
                          data-testid={`intake-review-date-issue-${issue.field}`}
                          onClick={() => navigateToDateIssue(issue)}
                        >
                          {issue.message}
                        </button>
                      </li>
                    ))}
                  </ul>
                </div>
              ) : null}
            </div>
          ) : null}

          <div className="mt-8 flex items-center justify-between gap-3">
            <button
              type="button"
              disabled={stepIndex === 0 || readOnly}
              onClick={goBack}
              className="rounded-lg border border-zinc-300 px-4 py-2 text-sm disabled:opacity-40 dark:border-zinc-700"
            >
              Назад
            </button>
            {currentStep.id === "review" ? (
              <button
                type="button"
                disabled={readOnly || primaryActionDisabled || primaryActionBusy || submitBlockedByDates}
                onClick={() => onPrimaryAction?.()}
                className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-700 disabled:opacity-50"
                data-testid={mode === "hr-on-behalf" ? "intake-on-behalf-save-button" : "intake-submit-button"}
              >
                {primaryActionBusy
                  ? mode === "hr-on-behalf"
                    ? "Сохранение…"
                    : "Отправка…"
                  : primaryActionLabel ??
                    (mode === "hr-on-behalf"
                      ? "Сохранить от имени претендента"
                      : "Отправить в отдел кадров")}
              </button>
            ) : (
              <button
                type="button"
                disabled={readOnly}
                onClick={goNext}
                className="rounded-lg bg-sky-600 px-4 py-2 text-sm font-medium text-white hover:bg-sky-700 disabled:opacity-50"
              >
                Далее
              </button>
            )}
          </div>
        </main>

        {footerHint === null ? null : (
          <p className="mt-4 text-center text-xs text-zinc-500">
            {footerHint ??
              (mode === "hr-on-behalf"
                ? "Изменения сохраняются от имени претендента и фиксируются в audit."
                : "Данные сохраняются автоматически. Вы можете продолжить позже.")}
          </p>
        )}
      </div>
    </div>
  );
}
