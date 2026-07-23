"use client";

import * as React from "react";

import {
  filterIntakeDictionaryOptions,
  normalizeIntakeDictionaryQuery,
  resolveIntakeDictionarySelection,
} from "../_lib/intakePersonalDictionary";

const INPUT_CLASS =
  "w-full rounded-lg border border-zinc-300 bg-white py-2 pl-3 pr-9 text-sm read-only:bg-zinc-50 dark:border-zinc-700 dark:bg-zinc-950 dark:read-only:bg-zinc-900";

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
  const [query, setQuery] = React.useState("");
  const [isSearching, setIsSearching] = React.useState(false);
  const [highlightIndex, setHighlightIndex] = React.useState(0);

  const filterQuery = open && !isSearching ? "" : query;
  const options = React.useMemo(
    () => filterIntakeDictionaryOptions(catalog, popular, filterQuery),
    [catalog, popular, filterQuery],
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
    if (readOnly) return;
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

    const resolved = resolveIntakeDictionarySelection(trimmedQuery, catalog);
    if (resolved) {
      if (normalizeIntakeDictionaryQuery(trimmedQuery) === normalizeIntakeDictionaryQuery(value)) {
        closeList();
        return;
      }
      commitSelection(resolved);
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
    if (readOnly) return;

    if (event.key === "ArrowDown") {
      event.preventDefault();
      openDropdown();
      setHighlightIndex((index) => Math.min(index + 1, Math.max(options.length - 1, 0)));
      return;
    }

    if (event.key === "ArrowUp") {
      event.preventDefault();
      openDropdown();
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
      closeList();
      inputRef.current?.blur();
    }
  }

  const showList = open && !readOnly && options.length > 0;
  const inputValue = open && isSearching ? query : value;

  return (
    <label className="block">
      <span className="text-sm font-medium text-zinc-700 dark:text-zinc-300">{label}</span>
      <div
        className={`relative mt-1 ${readOnly ? "" : "cursor-pointer"}`}
        data-testid={testId ? `${testId}-trigger` : undefined}
        onMouseDown={(event) => {
          if (readOnly) return;
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
          readOnly={readOnly}
          autoComplete="off"
          onClick={() => {
            if (readOnly) return;
            openDropdown();
          }}
          onFocus={() => {
            if (readOnly) return;
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
          className="relative z-10 mt-1 max-h-60 overflow-auto rounded-lg border border-zinc-200 bg-white shadow-sm dark:border-zinc-800 dark:bg-zinc-950"
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
