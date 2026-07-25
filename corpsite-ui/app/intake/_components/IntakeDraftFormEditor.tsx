"use client";

import * as React from "react";

import IntakeAdditionalStep from "./IntakeAdditionalStep";
import IntakeDictionaryCombobox from "./IntakeDictionaryCombobox";
import IntakeEducationTable from "./IntakeEducationTable";
import IntakeEmploymentBiographyTable from "./IntakeEmploymentBiographyTable";
import { IntakeDateField, IntakeSelectField, IntakeTextField } from "./IntakeFormFields";
import IntakeMilitaryCombobox from "./IntakeMilitaryCombobox";
import IntakePhotoUpload from "./IntakePhotoUpload";
import IntakeRelativesTable from "./IntakeRelativesTable";
import IntakeReviewStep from "./IntakeReviewStep";
import IntakeTrainingTable from "./IntakeTrainingTable";
import {
  INTAKE_CITIZENSHIP_CATALOG,
  INTAKE_CITIZENSHIP_POPULAR,
  INTAKE_GENDER_OPTIONS,
  INTAKE_NATIONALITY_CATALOG,
  INTAKE_NATIONALITY_POPULAR,
  normalizeIntakeGenderValue,
} from "../_lib/intakePersonalDictionary";
import {
  applyIntakeMilitaryCompositionChange,
  getIntakeMilitaryRankOptions,
  INTAKE_MILITARY_COMPOSITION_CATALOG,
  normalizeIntakeMilitaryComposition,
} from "../_lib/intakeMilitaryDictionary";
import {
  INTAKE_STEPS,
  formatIntakeStepHeaderTitle,
  type IntakeDraftPayload,
} from "../_lib/intakeApi.client";
import {
  applyContactsRegistrationAddressChange,
  applyContactsResidenceMirror,
  contactsMirrorResidence,
} from "../_lib/intakeContactHelpers";
import {
  collectIntakeDateValidationIssues,
  resolveIntakeDateIssueStepIndex,
  type IntakeDateValidationIssue,
} from "../_lib/intakeDateValidation";
import { sanitizeMilitarySpecialtyCodeInput } from "@/lib/militarySpecialtyCode";
import {
  deriveIntakeSurnameAlphabet,
  isIntakePersonnelNumberEditable,
  shouldShowIntakePersonnelNumberField,
} from "../_lib/intakePersonalFields";

function StepPersonal({
  payload,
  onChange,
  readOnly,
  mode = "public",
  intakeToken,
  applicationId,
}: {
  payload: IntakeDraftPayload;
  onChange: (p: IntakeDraftPayload) => void;
  readOnly?: boolean;
  mode?: "public" | "hr-on-behalf";
  intakeToken?: string;
  applicationId?: number;
}) {
  const p = payload.personal;
  const set = (key: keyof typeof p, value: string) =>
    onChange({ ...payload, personal: { ...p, [key]: value } });
  const alphabet = deriveIntakeSurnameAlphabet(p.last_name);
  const showPersonnelNumber = shouldShowIntakePersonnelNumberField(mode, p.personnel_number);
  const personnelNumberEditable = isIntakePersonnelNumberEditable(mode, readOnly);
  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start">
        <IntakePhotoUpload
          compact
          mode={mode}
          intakeToken={intakeToken}
          applicationId={applicationId}
          payload={payload}
          readOnly={readOnly}
          onPayloadChange={onChange}
        />
        <div className="grid min-w-0 flex-1 gap-4 sm:grid-cols-2">
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
        </div>
      </div>
      <div className="grid gap-4 sm:grid-cols-2">
      <IntakeTextField label="Место рождения" value={p.birth_place} onChange={(v) => set("birth_place", v)} readOnly={readOnly} testId="intake-birth-place" />
      {showPersonnelNumber ? (
        <IntakeTextField
          label="Табельный номер"
          value={p.personnel_number}
          onChange={(v) => set("personnel_number", v)}
          readOnly={!personnelNumberEditable}
          testId="intake-personnel-number"
        />
      ) : null}
      <IntakeTextField
        label="Алфавит"
        value={alphabet}
        onChange={() => undefined}
        readOnly
        testId="intake-alphabet"
      />
      <IntakeSelectField
        label="Пол"
        value={normalizeIntakeGenderValue(p.gender)}
        onChange={(v) => set("gender", v)}
        readOnly={readOnly}
        options={INTAKE_GENDER_OPTIONS}
        testId="intake-gender"
      />
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
  allowStepNavigation?: boolean;
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
  onSecondaryAction?: () => void;
  secondaryActionBusy?: boolean;
  secondaryActionLabel?: string;
  secondaryActionDisabled?: boolean;
  secondaryActionError?: string | null;
  onGeneratePdf?: () => void;
  pdfGenerating?: boolean;
  reviewNotice?: string | null;
  headerTitle?: string;
  footerHint?: string | null;
  compact?: boolean;
  initialFocusTestId?: string | null;
  intakeToken?: string;
  applicationId?: number;
};

export default function IntakeDraftFormEditor({
  payload,
  onChange,
  readOnly = false,
  allowStepNavigation,
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
  onSecondaryAction,
  secondaryActionBusy = false,
  secondaryActionLabel,
  secondaryActionDisabled = false,
  secondaryActionError = null,
  onGeneratePdf,
  pdfGenerating = false,
  reviewNotice,
  headerTitle,
  footerHint,
  compact = false,
  initialFocusTestId = null,
  intakeToken,
  applicationId,
}: IntakeDraftFormEditorProps) {
  const currentStep = INTAKE_STEPS[stepIndex];
  const blockStepNavigation = readOnly && allowStepNavigation !== true;
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

  function navigateToStep(nextIndex: number) {
    onStepIndexChange(nextIndex);
    onChange({ ...payload, current_step: INTAKE_STEPS[nextIndex].id });
  }

  function navigateToDateIssue(issue: IntakeDateValidationIssue) {
    const nextIndex = resolveIntakeDateIssueStepIndex(issue);
    navigateToStep(nextIndex);
    setPendingFocusTestId(issue.focusTestId);
  }

  function goNext() {
    navigateToStep(Math.min(stepIndex + 1, INTAKE_STEPS.length - 1));
  }

  function goBack() {
    navigateToStep(Math.max(stepIndex - 1, 0));
  }

  function goToStart() {
    navigateToStep(0);
  }

  function goToEnd() {
    navigateToStep(INTAKE_STEPS.length - 1);
  }

  const reviewStepIndex = INTAKE_STEPS.length - 1;
  const navButtonClassName =
    "rounded-lg bg-sky-600 px-3 py-2 text-xs font-medium text-white hover:bg-sky-700 disabled:opacity-50 sm:px-4 sm:text-sm";

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
            <StepPersonal
              payload={payload}
              onChange={onChange}
              readOnly={readOnly}
              mode={mode}
              intakeToken={intakeToken}
              applicationId={applicationId}
            />
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
              focusTestId={pendingFocusTestId}
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
            <IntakeReviewStep
              payload={payload}
              mode={mode}
              reviewNotice={reviewNotice}
              dateValidationIssues={dateValidationIssues}
              onNavigateToStep={navigateToStep}
              onNavigateToDateIssue={navigateToDateIssue}
            />
          ) : null}

          <div className="mt-8 flex flex-wrap items-center justify-between gap-2 sm:gap-3">
            <div className="flex flex-wrap items-center gap-2">
              <button
                type="button"
                disabled={stepIndex === 0 || blockStepNavigation}
                onClick={goToStart}
                className={navButtonClassName}
                data-testid="intake-nav-start"
              >
                Начало
              </button>
              <button
                type="button"
                disabled={stepIndex === 0 || blockStepNavigation}
                onClick={goBack}
                className={navButtonClassName}
                data-testid="intake-nav-back"
              >
                Назад
              </button>
            </div>
            {currentStep.id === "review" ? (
              <div className="flex flex-wrap items-center justify-end gap-2">
                <div className="flex flex-col items-end gap-2">
                  <div className="flex flex-wrap items-center gap-2">
                  {onGeneratePdf ? (
                    <button
                      type="button"
                      disabled={pdfGenerating}
                      onClick={() => onGeneratePdf()}
                      className="rounded-lg border border-zinc-300 bg-white px-3 py-2 text-xs font-medium text-zinc-800 hover:bg-zinc-50 disabled:opacity-50 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-100 dark:hover:bg-zinc-800 sm:px-4 sm:text-sm"
                      data-testid="intake-generate-pdf-button"
                    >
                      {pdfGenerating ? "Формирование PDF…" : "Сформировать PDF"}
                    </button>
                  ) : null}
                  <button
                    type="button"
                    disabled={readOnly || primaryActionDisabled || primaryActionBusy || submitBlockedByDates}
                    onClick={() => onPrimaryAction?.()}
                    className={
                      mode === "hr-on-behalf"
                        ? "rounded-lg border border-emerald-300 bg-white px-3 py-2 text-xs font-medium text-emerald-800 hover:bg-emerald-50 disabled:opacity-50 dark:border-emerald-900 dark:bg-zinc-900 dark:text-emerald-300 dark:hover:bg-zinc-800 sm:px-4 sm:text-sm"
                        : "rounded-lg bg-emerald-600 px-3 py-2 text-xs font-medium text-white hover:bg-emerald-700 disabled:opacity-50 sm:px-4 sm:text-sm"
                    }
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
                  {mode === "hr-on-behalf" && onSecondaryAction ? (
                    <button
                      type="button"
                      disabled={
                        readOnly ||
                        secondaryActionDisabled ||
                        secondaryActionBusy ||
                        primaryActionBusy ||
                        submitBlockedByDates
                      }
                      onClick={() => onSecondaryAction()}
                      className="rounded-lg bg-emerald-600 px-3 py-2 text-xs font-medium text-white hover:bg-emerald-700 disabled:opacity-50 sm:px-4 sm:text-sm"
                      data-testid="intake-on-behalf-submit-button"
                    >
                      {secondaryActionBusy
                        ? "Отправка…"
                        : secondaryActionLabel ?? "Отправить анкету"}
                    </button>
                  ) : null}
                  </div>
                  {secondaryActionError ? (
                    <p
                      className="max-w-xl text-right text-xs text-red-700 dark:text-red-300"
                      data-testid="intake-on-behalf-submit-error"
                    >
                      {secondaryActionError}
                    </p>
                  ) : null}
                </div>
                <button
                  type="button"
                  disabled={stepIndex === reviewStepIndex || blockStepNavigation}
                  onClick={goToEnd}
                  className={navButtonClassName}
                  data-testid="intake-nav-end"
                >
                  Конец
                </button>
              </div>
            ) : (
              <div className="flex flex-wrap items-center gap-2">
                <button
                  type="button"
                  disabled={blockStepNavigation}
                  onClick={goNext}
                  className={navButtonClassName}
                  data-testid="intake-nav-next"
                >
                  Далее
                </button>
                <button
                  type="button"
                  disabled={stepIndex === reviewStepIndex || blockStepNavigation}
                  onClick={goToEnd}
                  className={navButtonClassName}
                  data-testid="intake-nav-end"
                >
                  Конец
                </button>
              </div>
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
