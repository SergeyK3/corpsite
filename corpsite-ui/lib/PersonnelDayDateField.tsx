"use client";

import * as React from "react";

import {
  formatPersonnelDayDateForDisplay,
  isIncompletePersonnelDayDate,
  parsePersonnelDayDateInput,
  PERSONNEL_DAY_DATE_PLACEHOLDER,
  PERSONNEL_INCOMPLETE_DATE_HINT,
  type PersonnelDayDateMode,
} from "@/lib/personnelDayDate";

export type PersonnelDayDateFieldProps = {
  label?: string;
  value: string;
  onChange: (value: string) => void;
  readOnly?: boolean;
  required?: boolean;
  testId?: string;
  mode?: PersonnelDayDateMode;
  className?: string;
  inputClassName?: string;
};

export default function PersonnelDayDateField({
  label,
  value,
  onChange,
  readOnly = false,
  required = false,
  testId,
  mode = "document",
  className = "block",
  inputClassName = "mt-1 w-full rounded-lg border bg-white px-3 py-2 text-sm read-only:bg-zinc-50 dark:bg-zinc-950 dark:read-only:bg-zinc-900",
}: PersonnelDayDateFieldProps) {
  const [focused, setFocused] = React.useState(false);
  const [draft, setDraft] = React.useState("");
  const display = formatPersonnelDayDateForDisplay(value, mode);
  const incomplete = isIncompletePersonnelDayDate(value, mode);

  React.useEffect(() => {
    if (!focused) setDraft(display);
  }, [display, focused]);

  return (
    <label className={className}>
      {label ? (
        <span className="text-sm font-medium text-zinc-700 dark:text-zinc-300">
          {label}
          {required ? " *" : ""}
        </span>
      ) : null}
      <input
        type="text"
        inputMode="text"
        value={focused ? draft : display}
        readOnly={readOnly}
        data-testid={testId}
        aria-invalid={incomplete || undefined}
        placeholder={PERSONNEL_DAY_DATE_PLACEHOLDER}
        onFocus={() => {
          setDraft(display);
          setFocused(true);
        }}
        onBlur={() => {
          setFocused(false);
          if (draft.trim() === display.trim()) return;
          onChange(parsePersonnelDayDateInput(draft));
        }}
        onChange={(e) => {
          const nextDraft = e.target.value;
          setDraft(nextDraft);
          onChange(parsePersonnelDayDateInput(nextDraft));
        }}
        className={`${inputClassName} ${
          incomplete
            ? "border-amber-400 text-amber-900 dark:border-amber-700 dark:text-amber-200"
            : "border-zinc-300 dark:border-zinc-700"
        }`}
      />
      {incomplete ? (
        <span
          className="mt-1 block text-xs text-amber-700 dark:text-amber-300"
          data-testid={testId ? `${testId}-hint` : undefined}
        >
          {PERSONNEL_INCOMPLETE_DATE_HINT}
        </span>
      ) : null}
    </label>
  );
}
