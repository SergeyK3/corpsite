"use client";

import * as React from "react";

import {
  filterIntakeMilitaryComboboxOptions,
  intakeMilitaryComboboxDisplayLabel,
  normalizeIntakeDictionaryQuery,
  resolveIntakeMilitaryComboboxSelection,
  type IntakeMilitaryComboboxOption,
} from "@/lib/militaryDictionary";

const INPUT_CLASS =
  "w-full rounded-lg border border-zinc-300 bg-white py-2 pl-3 pr-9 text-sm read-only:bg-zinc-50 dark:border-zinc-700 dark:bg-zinc-950 dark:read-only:bg-zinc-900";

type IntakeMilitaryComboboxProps = {
  label: string;
  value: string;
  onChange: (value: string) => void;
  options: readonly IntakeMilitaryComboboxOption[];
  readOnly?: boolean;
  disabled?: boolean;
  allowFreeText?: boolean;
  emptyHint?: string;
  testId?: string;
};

export default function IntakeMilitaryCombobox({
  label,
  value,
  onChange,
  options,
  readOnly = false,
  disabled = false,
  allowFreeText = false,
  emptyHint,
  testId,
}: IntakeMilitaryComboboxProps) {
  const listId = React.useId();
  const inputRef = React.useRef<HTMLInputElement>(null);

  const [open, setOpen] = React.useState(false);
  const [query, setQuery] = React.useState("");
  const [isSearching, setIsSearching] = React.useState(false);
  const [highlightIndex, setHighlightIndex] = React.useState(0);

  const displayValue = intakeMilitaryComboboxDisplayLabel(value, options);
  const filterQuery = open && !isSearching ? "" : query;
  const filteredOptions = React.useMemo(
    () => filterIntakeMilitaryComboboxOptions(options, filterQuery),
    [options, filterQuery, open, isSearching, query],
  );

  React.useEffect(() => {
    if (!open) return;
    setHighlightIndex(0);
  }, [open, filterQuery]);

  React.useEffect(() => {
    setIsSearching(false);
    setQuery("");
    setOpen(false);
  }, [value]);

  function openDropdown() {
    if (readOnly || disabled) return;
    setIsSearching(false);
    setQuery("");
    setOpen(true);
  }

  function closeList() {
    setOpen(false);
    setIsSearching(false);
    setQuery("");
  }

  function commitSelection(nextValue: string) {
    onChange(nextValue);
    closeList();
  }

  function tryCommitQuery() {
    if (open && !isSearching) {
      closeList();
      return;
    }

    const trimmedQuery = query.trim();
    if (!trimmedQuery) {
      closeList();
      return;
    }

    const resolved = resolveIntakeMilitaryComboboxSelection(trimmedQuery, options);
    if (resolved !== null) {
      if (
        resolved === value ||
        normalizeIntakeDictionaryQuery(trimmedQuery) === normalizeIntakeDictionaryQuery(displayValue)
      ) {
        closeList();
        return;
      }
      commitSelection(resolved);
      return;
    }
    if (allowFreeText) {
      commitSelection(trimmedQuery);
      return;
    }
    closeList();
  }

  function handleInputChange(nextQuery: string) {
    setIsSearching(true);
    setQuery(nextQuery);
    setOpen(true);
  }

  function handleKeyDown(event: React.KeyboardEvent<HTMLInputElement>) {
    if (readOnly || disabled) return;

    if (event.key === "ArrowDown") {
      event.preventDefault();
      openDropdown();
      setHighlightIndex((index) => Math.min(index + 1, Math.max(filteredOptions.length - 1, 0)));
      return;
    }

    if (event.key === "ArrowUp") {
      event.preventDefault();
      openDropdown();
      setHighlightIndex((index) => Math.max(index - 1, 0));
      return;
    }

    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      if (event.key === " " && open && isSearching) {
        return;
      }
      if (!open) {
        openDropdown();
        return;
      }
      if (event.key === "Enter" && filteredOptions[highlightIndex]) {
        commitSelection(filteredOptions[highlightIndex].value);
        return;
      }
      if (event.key === "Enter") {
        tryCommitQuery();
      }
      return;
    }

    if (event.key === "Escape") {
      event.preventDefault();
      closeList();
      inputRef.current?.blur();
    }
  }

  const showList = open && !readOnly && !disabled && filteredOptions.length > 0;
  const inputDisabled = readOnly || disabled;
  const placeholder = inputDisabled && !displayValue ? emptyHint : undefined;
  const inputValue = open && isSearching ? query : displayValue;

  return (
    <label className="block">
      <span className="text-sm font-medium text-zinc-700 dark:text-zinc-300">{label}</span>
      <div
        className={`relative mt-1 ${inputDisabled ? "" : "cursor-pointer"}`}
        data-testid={testId ? `${testId}-trigger` : undefined}
        onMouseDown={(event) => {
          if (inputDisabled) return;
          if (event.target === inputRef.current) return;
          event.preventDefault();
          openDropdown();
          inputRef.current?.focus();
        }}
      >
        <input
          ref={inputRef}
          type="text"
          role="combobox"
          aria-expanded={showList}
          aria-controls={showList ? listId : undefined}
          aria-autocomplete="list"
          aria-label={label}
          data-testid={testId}
          value={inputValue}
          placeholder={placeholder}
          readOnly={readOnly}
          disabled={disabled}
          autoComplete="off"
          onClick={() => {
            if (inputDisabled) return;
            openDropdown();
          }}
          onChange={(event) => handleInputChange(event.target.value)}
          onBlur={() => {
            window.setTimeout(() => {
              tryCommitQuery();
            }, 0);
          }}
          onKeyDown={handleKeyDown}
          className={INPUT_CLASS}
        />
        {!readOnly ? (
          <span
            aria-hidden="true"
            data-testid={testId ? `${testId}-chevron` : undefined}
            className={`pointer-events-none absolute inset-y-0 right-0 flex w-9 items-center justify-center text-xs text-zinc-500 transition-transform dark:text-zinc-400 ${
              showList ? "rotate-180" : ""
            }`}
          >
            ▼
          </span>
        ) : null}
      </div>
      {showList ? (
        <ul
          id={listId}
          role="listbox"
          data-testid={testId ? `${testId}-list` : undefined}
          className="mt-1 max-h-60 overflow-auto rounded-lg border border-zinc-200 bg-white shadow-sm dark:border-zinc-800 dark:bg-zinc-950"
        >
          {filteredOptions.map((option, index) => (
            <li key={`${option.value}-${option.label}`} role="presentation">
              <button
                type="button"
                role="option"
                aria-selected={index === highlightIndex}
                data-testid={testId ? `${testId}-option-${index}` : undefined}
                className={`block w-full px-3 py-1.5 text-left text-sm ${
                  index === highlightIndex
                    ? "bg-sky-50 text-sky-900 dark:bg-sky-950 dark:text-sky-100"
                    : "hover:bg-zinc-50 dark:hover:bg-zinc-900"
                }`}
                onMouseDown={(event) => event.preventDefault()}
                onMouseEnter={() => setHighlightIndex(index)}
                onClick={() => commitSelection(option.value)}
              >
                {option.label}
              </button>
            </li>
          ))}
        </ul>
      ) : null}
    </label>
  );
}
