"use client";

import * as React from "react";

import IntakeAdditionalStep from "./IntakeAdditionalStep";
import IntakeDictionaryCombobox from "./IntakeDictionaryCombobox";
import IntakeEducationTable from "./IntakeEducationTable";
import IntakeEmploymentBiographyTable from "./IntakeEmploymentBiographyTable";
import { IntakeDateField, IntakeTextField } from "./IntakeFormFields";
import IntakeMilitaryCombobox from "./IntakeMilitaryCombobox";
import IntakeRelativesTable from "./IntakeRelativesTable";
import IntakeTrainingTable from "./IntakeTrainingTable";
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
  INTAKE_STEPS,
  emptyIntakeDraftPayload,
  formatIntakeStepHeaderTitle,
  type IntakeDraftPayload,
} from "../_lib/intakeApi.client";
import { normalizeIntakeAdditionalPayload } from "../_lib/intakeAdditional";
import {
  formatIntakeAcademicDegreeReviewLine,
  formatIntakeAcademicTitleReviewLine,
  formatIntakeAdditionalSubsectionReviewSummary,
  formatIntakeAwardReviewLine,
  formatIntakeForeignLanguageReviewLine,
} from "../_lib/intakeAdditional";
import { normalizeIntakeEducationEntry } from "../_lib/intakeEducation";
import {
  normalizeIntakeTrainingEntry,
  reconcileTrainingEntryHours,
} from "../_lib/intakeTraining";
import {
  applyContactsRegistrationAddressChange,
  applyContactsResidenceMirror,
  contactsMirrorResidence,
  formatIntakeFullName,
} from "../_lib/intakeContactHelpers";
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
  type IntakeDateValidationIssue,
} from "../_lib/intakeDateValidation";
import { sanitizeMilitarySpecialtyCodeInput } from "@/lib/militarySpecialtyCode";

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
      <IntakeTextField label="Фамилия" value={p.last_name} onChange={(v) => set("last_name", v)} readOnly={readOnly} required />
      <IntakeTextField label="Имя" value={p.first_name} onChange={(v) => set("first_name", v)} readOnly={readOnly} required />
      <IntakeTextField label="Отчество" value={p.middle_name} onChange={(v) => set("middle_name", v)} readOnly={readOnly} />
      <IntakeDateField
        label="Дата рождения"
        value={p.birth_date}
        onChange={(v) => set("birth_date", v)}
        readOnly={readOnly}
        kind="birth"
        testId="intake-birth-date"
      />
      <IntakeTextField label="Место рождения" value={p.birth_place} onChange={(v) => set("birth_place", v)} readOnly={readOnly} />
      <IntakeTextField label="Пол" value={p.gender} onChange={(v) => set("gender", v)} readOnly={readOnly} />
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
      <IntakeTextField label="Мобильный телефон" value={c.mobile_phone} onChange={(v) => set("mobile_phone", v)} readOnly={readOnly} required />
      <IntakeTextField label="Email" value={c.email} onChange={(v) => set("email", v)} readOnly={readOnly} type="email" />
      <IntakeTextField
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
      <IntakeTextField
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

export function reconcileIntakeDraftPayload(payload: IntakeDraftPayload): IntakeDraftPayload {
  const military = {
    ...emptyIntakeDraftPayload().military,
    ...payload.military,
    specialty_name: payload.military?.specialty_name ?? "",
  };
  return {
    ...payload,
    education: (payload.education ?? []).map((item) => normalizeIntakeEducationEntry(item)),
    training: (payload.training ?? []).map((item) =>
      reconcileTrainingEntryHours(normalizeIntakeTrainingEntry(item)),
    ),
    additional: normalizeIntakeAdditionalPayload(payload.additional),
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
      <IntakeTextField label="Статус" value={m.status} onChange={(v) => set("status", v)} readOnly={readOnly} />
      <IntakeTextField label="Категория" value={m.category} onChange={(v) => set("category", v)} readOnly={readOnly} />
      <IntakeTextField
        label="Номер ВУС"
        value={m.specialty_code}
        onChange={(v) => set("specialty_code", sanitizeMilitarySpecialtyCodeInput(v))}
        readOnly={readOnly}
        testId="intake-military-specialty-code"
        maxLength={7}
        inputMode="numeric"
      />
      <IntakeTextField label="Категория годности" value={m.fitness_category} onChange={(v) => set("fitness_category", v)} readOnly={readOnly} />
      <IntakeTextField label="Военкомат" value={m.commissariat} onChange={(v) => set("commissariat", v)} readOnly={readOnly} />
      <IntakeTextField label="Группа учёта" value={m.registration_group} onChange={(v) => set("registration_group", v)} readOnly={readOnly} />
      <IntakeTextField label="Категория учёта" value={m.registration_category} onChange={(v) => set("registration_category", v)} readOnly={readOnly} />
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

  const title = headerTitle ?? formatIntakeStepHeaderTitle(stepIndex);

  return (
    <div className={compact ? "space-y-4" : "min-h-screen bg-zinc-50 dark:bg-zinc-950"}>
      <div className={compact ? "" : "mx-auto w-full max-w-[min(96vw,1400px)] px-4 py-8"}>
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
            <IntakeEducationTable
              items={payload.education}
              readOnly={readOnly}
              focusTestId={pendingFocusTestId}
              onChange={(items) => onChange({ ...payload, education: items })}
            />
          ) : null}
          {currentStep.id === "training" ? (
            <IntakeTrainingTable
              items={payload.training}
              readOnly={readOnly}
              focusTestId={pendingFocusTestId}
              onChange={(items) => onChange({ ...payload, training: items })}
            />
          ) : null}
          {currentStep.id === "relatives" ? (
            <IntakeRelativesTable
              items={payload.relatives}
              readOnly={readOnly}
              focusTestId={pendingFocusTestId}
              onChange={(items) => onChange({ ...payload, relatives: items })}
            />
          ) : null}
          {currentStep.id === "employment_biography" ? (
            <IntakeEmploymentBiographyTable
              items={payload.employment_biography}
              readOnly={readOnly}
              onChange={(items) => onChange({ ...payload, employment_biography: items })}
            />
          ) : null}
          {currentStep.id === "military" ? (
            <StepMilitary payload={payload} onChange={onChange} readOnly={readOnly} />
          ) : null}
          {currentStep.id === "additional" ? (
            <IntakeAdditionalStep
              value={payload.additional}
              readOnly={readOnly}
              focusTestId={pendingFocusTestId}
              onChange={(additional) => onChange({ ...payload, additional })}
            />
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
                <li data-testid="intake-review-additional-languages">
                  Иностранные языки:{" "}
                  {formatIntakeAdditionalSubsectionReviewSummary(
                    payload.additional.foreign_languages,
                    payload.additional.foreign_languages_none,
                    (item) => formatIntakeForeignLanguageReviewLine(item),
                  )}
                </li>
                <li data-testid="intake-review-additional-awards">
                  Награды:{" "}
                  {formatIntakeAdditionalSubsectionReviewSummary(
                    payload.additional.awards,
                    payload.additional.awards_none,
                    (item) => formatIntakeAwardReviewLine(item),
                  )}
                </li>
                <li data-testid="intake-review-additional-degrees">
                  Учёные степени:{" "}
                  {formatIntakeAdditionalSubsectionReviewSummary(
                    payload.additional.academic_degrees,
                    payload.additional.academic_degrees_none,
                    (item) => formatIntakeAcademicDegreeReviewLine(item),
                  )}
                </li>
                <li data-testid="intake-review-additional-titles">
                  Учёные звания:{" "}
                  {formatIntakeAdditionalSubsectionReviewSummary(
                    payload.additional.academic_titles,
                    payload.additional.academic_titles_none,
                    (item) => formatIntakeAcademicTitleReviewLine(item),
                  )}
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
              className="rounded-lg bg-sky-600 px-4 py-2 text-sm font-medium text-white hover:bg-sky-700 disabled:opacity-50"
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
