"use client";

import { IntakeSelectField, IntakeTextField } from "./IntakeFormFields";

type Option = { value: string; label: string };

type Props = {
  label: string;
  value: string;
  onChange: (value: string) => void;
  options: ReadonlyArray<Option>;
  otherOptionValue: string;
  otherFieldLabel: string;
  readOnly?: boolean;
  testId?: string;
  otherTestId?: string;
  compact?: boolean;
};

export function splitIntakeSelectWithOtherValue(
  value: string,
  options: ReadonlyArray<Option>,
  otherOptionValue: string,
): { selected: string; otherText: string } {
  const trimmed = String(value ?? "").trim();
  const known = options.find((option) => option.value === trimmed);
  if (known && known.value !== otherOptionValue) {
    return { selected: known.value, otherText: "" };
  }
  if (trimmed) {
    return { selected: otherOptionValue, otherText: trimmed };
  }
  return { selected: "", otherText: "" };
}

export function mergeIntakeSelectWithOtherValue(
  selected: string,
  otherText: string,
  otherOptionValue: string,
): string {
  if (selected === otherOptionValue) {
    return otherText.trim();
  }
  return selected.trim();
}

export default function IntakeSelectWithOtherField({
  label,
  value,
  onChange,
  options,
  otherOptionValue,
  otherFieldLabel,
  readOnly = false,
  testId,
  otherTestId,
  compact = false,
}: Props) {
  const { selected, otherText } = splitIntakeSelectWithOtherValue(value, options, otherOptionValue);
  const showOther = selected === otherOptionValue;

  function patchSelected(nextSelected: string) {
    onChange(mergeIntakeSelectWithOtherValue(nextSelected, otherText, otherOptionValue));
  }

  function patchOtherText(nextOtherText: string) {
    onChange(mergeIntakeSelectWithOtherValue(otherOptionValue, nextOtherText, otherOptionValue));
  }

  const selectOptions = [{ value: "", label: "Выберите…" }, ...options];

  return (
    <div className={compact ? "space-y-1.5" : "space-y-3"}>
      <IntakeSelectField
        label={label}
        value={selected}
        readOnly={readOnly}
        options={selectOptions}
        testId={testId}
        compact={compact}
        onChange={patchSelected}
      />
      {showOther ? (
        <IntakeTextField
          label={otherFieldLabel}
          value={otherText}
          readOnly={readOnly}
          testId={otherTestId}
          compact={compact}
          onChange={patchOtherText}
        />
      ) : null}
    </div>
  );
}
