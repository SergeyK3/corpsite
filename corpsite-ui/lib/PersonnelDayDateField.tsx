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
  const pickerRef = React.useRef<HTMLInputElement>(null);
  const display = formatPersonnelDayDateForDisplay(value, mode);
  const incomplete = isIncompletePersonnelDayDate(value, mode);

  React.useEffect(() => {
    if (!focused) setDraft(display);
  }, [display, focused]);

  const formatTypedDate = (raw: string) => {
    const digits = raw.replace(/\D/g, "").slice(0, 8);
    if (digits.length <= 2) return digits;
    if (digits.length <= 4) return `${digits.slice(0, 2)}.${digits.slice(2)}`;
    return `${digits.slice(0, 2)}.${digits.slice(2, 4)}.${digits.slice(4)}`;
  };

  return (
    <label className={className}>
      {label ? (
        <span className="text-sm font-medium text-zinc-700 dark:text-zinc-300">
          {label}
          {required ? " *" : ""}
        </span>
      ) : null}
      <span className="relative mt-1 block">
        <input
          type="text"
          inputMode="numeric"
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
            const nextDraft = formatTypedDate(e.target.value);
            setDraft(nextDraft);
            onChange(parsePersonnelDayDateInput(nextDraft));
          }}
          className={`${inputClassName} pr-11 ${
            incomplete
              ? "border-amber-400 text-amber-900 dark:border-amber-700 dark:text-amber-200"
              : "border-zinc-300 dark:border-zinc-700"
          }`}
        />
        {!readOnly ? <>
          <button
            type="button"
            aria-label={label ? `Открыть календарь для ${label}` : "Открыть календарь"}
            className="absolute right-1 top-1/2 -translate-y-1/2 rounded p-2 text-zinc-500 hover:bg-zinc-100 hover:text-zinc-800 dark:hover:bg-zinc-800 dark:hover:text-zinc-100"
            onClick={() => {
              try { pickerRef.current?.showPicker?.(); } catch { pickerRef.current?.focus(); }
            }}
          >
            <svg aria-hidden="true" viewBox="0 0 24 24" className="h-5 w-5 fill-none stroke-current" strokeWidth="2"><rect x="3" y="5" width="18" height="16" rx="2" /><path d="M16 3v4M8 3v4M3 10h18" /></svg>
          </button>
          <input
            ref={pickerRef}
            type="date"
            tabIndex={-1}
            aria-hidden="true"
            value={isIncompletePersonnelDayDate(value, mode) ? "" : value}
            onChange={(event) => onChange(event.target.value)}
            className="pointer-events-none absolute h-px w-px opacity-0"
          />
        </> : null}
      </span>
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
