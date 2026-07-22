"use client";

import * as React from "react";

import {
  filterIntakeDictionaryOptions,
  normalizeIntakeDictionaryQuery,
  resolveIntakeDictionarySelection,
} from "../_lib/intakePersonalDictionary";

const INPUT_CLASS =
  "mt-1 w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm read-only:bg-zinc-50 dark:border-zinc-700 dark:bg-zinc-950 dark:read-only:bg-zinc-900";

type IntakeDictionaryComboboxProps = {
  label: string;
  value: string;
  onChange: (value: string) => void;
  readOnly?: boolean;
  popular: readonly string[];
  catalog: readonly string[];
  testId?: string;
};

export default function IntakeDictionaryCombobox({
  label,
  value,
  onChange,
  readOnly = false,
  popular,
  catalog,
  testId,
}: IntakeDictionaryComboboxProps) {
  const listId = React.useId();
  const inputRef = React.useRef<HTMLInputElement>(null);

  const [open, setOpen] = React.useState(false);
  const [query, setQuery] = React.useState(value);
  const [highlightIndex, setHighlightIndex] = React.useState(0);

  const options = React.useMemo(
    () => filterIntakeDictionaryOptions(catalog, popular, query),
    [catalog, popular, query],
  );

  React.useEffect(() => {
    if (!open) return;
    setHighlightIndex(0);
  }, [open, query]);

  React.useEffect(() => {
    if (!open) {
      setQuery(value);
    }
  }, [open, value]);

  function closeList(revertToValue = true) {
    setOpen(false);
    if (revertToValue) {
      setQuery(value);
    }
  }

  function commitSelection(nextValue: string) {
    onChange(nextValue);
    setQuery(nextValue);
    setOpen(false);
  }

  function tryCommitQuery() {
    const resolved = resolveIntakeDictionarySelection(query, catalog);
    if (resolved) {
      if (normalizeIntakeDictionaryQuery(query) === normalizeIntakeDictionaryQuery(value)) {
        setQuery(value);
        setOpen(false);
        return;
      }
      commitSelection(resolved);
      return;
    }
    setQuery(value);
    setOpen(false);
  }

  function handleInputChange(nextQuery: string) {
    setQuery(nextQuery);
    setOpen(true);
  }

  function handleKeyDown(event: React.KeyboardEvent<HTMLInputElement>) {
    if (readOnly) return;

    if (event.key === "ArrowDown") {
      event.preventDefault();
      if (!open) setOpen(true);
      setHighlightIndex((index) => Math.min(index + 1, Math.max(options.length - 1, 0)));
      return;
    }

    if (event.key === "ArrowUp") {
      event.preventDefault();
      if (!open) setOpen(true);
      setHighlightIndex((index) => Math.max(index - 1, 0));
      return;
    }

    if (event.key === "Enter") {
      event.preventDefault();
      if (open && options[highlightIndex]) {
        commitSelection(options[highlightIndex]);
        return;
      }
      tryCommitQuery();
      return;
    }

    if (event.key === "Escape") {
      event.preventDefault();
      closeList(true);
      inputRef.current?.blur();
    }
  }

  const showList = open && !readOnly && options.length > 0;

  return (
    <label className="block">
      <span className="text-sm font-medium text-zinc-700 dark:text-zinc-300">{label}</span>
      <input
        ref={inputRef}
        type="text"
        role="combobox"
        aria-expanded={showList}
        aria-controls={showList ? listId : undefined}
        aria-autocomplete="list"
        aria-label={label}
        data-testid={testId}
        value={query}
        readOnly={readOnly}
        autoComplete="off"
        onFocus={() => {
          if (readOnly) return;
          setQuery(value);
          setOpen(true);
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
      {showList ? (
        <ul
          id={listId}
          role="listbox"
          data-testid={testId ? `${testId}-list` : undefined}
          className="mt-1 max-h-60 overflow-auto rounded-lg border border-zinc-200 bg-white shadow-sm dark:border-zinc-800 dark:bg-zinc-950"
        >
          {options.map((option, index) => (
            <li key={option} role="presentation">
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
                onClick={() => commitSelection(option)}
              >
                {option}
              </button>
            </li>
          ))}
        </ul>
      ) : null}
    </label>
  );
}
