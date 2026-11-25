"use client";

import * as React from "react";

const IntakeFieldErrorsContext = React.createContext<Record<string, string>>({});

export function IntakeFieldErrorsProvider({ errors, children }: { errors: Record<string, string>; children: React.ReactNode }) {
  return <IntakeFieldErrorsContext.Provider value={errors}>{children}</IntakeFieldErrorsContext.Provider>;
}

export function useIntakeFieldError(testId?: string): string | undefined {
  const errors = React.useContext(IntakeFieldErrorsContext);
  return testId ? errors[testId] : undefined;
}

import PersonnelDayDateField from "@/lib/PersonnelDayDateField";
import {
  formatIntakePeriodForDisplay,
  formatTypedIntakePeriodDate,
  parseIntakePeriodInput,
} from "../_lib/intakePeriodFormat";
import {
  INTAKE_DATE_PLACEHOLDER,
  INTAKE_INCOMPLETE_DATE_HINT,
  isIncompleteIntakePeriodDate,
  type IntakeDateFieldKind,
} from "../_lib/intakeDateValidation";

function isIntakeBirthDateKind(kind: IntakeDateFieldKind): kind is "birth" {
  return kind === "birth";
}

function intakeFieldLabelClass(compact?: boolean) {
  return compact ? "sr-only" : "text-sm font-medium text-zinc-700 dark:text-zinc-300";
}

function intakeFieldControlClass(compact?: boolean, extra = "") {
  const spacing = compact ? "" : "mt-1 ";
  const shape = compact ? "rounded-md px-2 py-1.5" : "rounded-lg px-3 py-2";
  return `${spacing}w-full ${shape} border border-zinc-300 bg-white text-sm disabled:bg-zinc-50 dark:border-zinc-700 dark:bg-zinc-950 dark:disabled:bg-zinc-900 ${extra}`.trim();
}

export function IntakeSelectField<V extends string>({
  label,
  value,
  onChange,
  readOnly,
  required = false,
  options,
  testId,
  compact = false,
}: {
  label: string;
  value: V;
  onChange: (v: V) => void;
  readOnly?: boolean;
  required?: boolean;
  options: ReadonlyArray<{ value: V; label: string }>;
  testId?: string;
  compact?: boolean;
}) {
  const error = useIntakeFieldError(testId);
  return (
    <label className="block">
      <span className={intakeFieldLabelClass(compact)}>
        {label}
        {required ? " *" : ""}
      </span>
      <select
        value={value}
        disabled={readOnly}
        required={required}
        data-testid={testId}
        aria-invalid={Boolean(error) || undefined}
        onChange={(e) => {
          const selected = options.find((option) => option.value === e.target.value);
          if (selected) onChange(selected.value);
        }}
        className={intakeFieldControlClass(compact, `read-only:bg-zinc-50 dark:read-only:bg-zinc-900 ${error ? "border-red-500" : ""}`)}
      >
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
      {error ? <span className="mt-1 block text-xs text-red-700" data-testid={testId ? `${testId}-error` : undefined}>{error}</span> : null}
    </label>
  );
}

export function IntakeTextField({
  label,
  value,
  onChange,
  readOnly,
  type = "text",
  required = false,
  testId,
  maxLength,
  inputMode,
  compact = false,
  hint,
  explicitError,
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
  compact?: boolean;
  hint?: string;
  explicitError?: string;
}) {
  const error = useIntakeFieldError(testId) || explicitError;
  return (
    <label className="block">
      <span className={intakeFieldLabelClass(compact)}>
        {label}
        {required ? " *" : ""}
      </span>
      <input
        type={type}
        value={value}
        readOnly={readOnly}
        required={required}
        data-testid={testId}
        aria-invalid={Boolean(error) || undefined}
        maxLength={maxLength}
        inputMode={inputMode}
        onChange={(e) => onChange(e.target.value)}
        className={intakeFieldControlClass(compact, `read-only:bg-zinc-50 dark:read-only:bg-zinc-900 ${error ? "border-red-500" : ""}`)}
      />
      {hint ? <span className="mt-1 block text-xs text-zinc-500" data-testid={testId ? `${testId}-hint` : undefined}>{hint}</span> : null}
      {error ? <span className="mt-1 block text-xs text-red-700" data-testid={testId ? `${testId}-error` : undefined}>{error}</span> : null}
    </label>
  );
}

export function IntakePeriodDateField({
  label,
  value,
  onChange,
  readOnly,
  required = false,
  testId,
  compact = false,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  readOnly?: boolean;
  required?: boolean;
  testId?: string;
  compact?: boolean;
}) {
  const [focused, setFocused] = React.useState(false);
  const error = useIntakeFieldError(testId);
  const [draft, setDraft] = React.useState("");
  const display = formatIntakePeriodForDisplay(value);
  const incomplete = isIncompleteIntakePeriodDate(value);

  React.useEffect(() => {
    if (!focused) setDraft(display);
  }, [display, focused]);

  return (
    <label className="block">
      <span className={intakeFieldLabelClass(compact)}>
        {label}
        {required ? " *" : ""}
      </span>
      <input
        type="text"
        inputMode="text"
        value={focused ? draft : display}
        readOnly={readOnly}
        data-testid={testId}
        aria-invalid={Boolean(error) || incomplete || undefined}
        placeholder={INTAKE_DATE_PLACEHOLDER}
        onFocus={() => {
          setDraft(display);
          setFocused(true);
        }}
        onBlur={() => {
          setFocused(false);
          if (draft.trim() === display.trim()) return;
          onChange(parseIntakePeriodInput(draft));
        }}
        onChange={(e) => {
          const nextDraft = formatTypedIntakePeriodDate(e.target.value);
          setDraft(nextDraft);
          onChange(parseIntakePeriodInput(nextDraft));
        }}
        className={`${intakeFieldControlClass(compact, "read-only:bg-zinc-50 dark:read-only:bg-zinc-900")} ${
          error
            ? "border-red-500"
            : incomplete
            ? "border-amber-400 text-amber-900 dark:border-amber-700 dark:text-amber-200"
            : ""
        }`.trim()}
      />
      {incomplete ? (
        <span
          className="mt-1 block text-xs text-amber-700 dark:text-amber-300"
          data-testid={testId ? `${testId}-hint` : undefined}
        >
          {INTAKE_INCOMPLETE_DATE_HINT}
        </span>
      ) : null}
      {error ? <span className="mt-1 block text-xs text-red-700" data-testid={testId ? `${testId}-error` : undefined}>{error}</span> : null}
    </label>
  );
}

export function IntakeDateField({
  label,
  value,
  onChange,
  readOnly,
  kind,
  required = false,
  testId,
  compact = false,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  readOnly?: boolean;
  kind: IntakeDateFieldKind;
  required?: boolean;
  testId?: string;
  compact?: boolean;
}) {
  if (isIntakeBirthDateKind(kind)) {
    return (
      <PersonnelDayDateField
        label={label}
        value={value}
        onChange={onChange}
        readOnly={readOnly}
        required={required}
        testId={testId}
        mode="birth"
      />
    );
  }

  return (
    <IntakePeriodDateField
      label={label}
      value={value}
      onChange={onChange}
      readOnly={readOnly}
      required={required}
      testId={testId}
      compact={compact}
    />
  );
}
