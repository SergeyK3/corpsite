"use client";

import * as React from "react";

import { IntakeSelectField } from "./IntakeFormFields";
import IntakeListRowActionsMenu from "./IntakeListRowActionsMenu";
import IntakeOptionalListSection from "./IntakeOptionalListSection";
import IntakeSelectWithOtherField from "./IntakeSelectWithOtherField";
import {
  emptyIntakeForeignLanguageEntry,
  intakeAdditionalCellValue,
  normalizeIntakeForeignLanguageEntry,
  parseIntakeForeignLanguageFocusRowIndex,
  resolveIntakeForeignLanguageDisplay,
  type IntakeForeignLanguageRow,
} from "../_lib/intakeAdditional";
import {
  INTAKE_FOREIGN_LANGUAGE_OPTIONS,
  INTAKE_FOREIGN_LANGUAGE_OTHER,
  INTAKE_FOREIGN_LANGUAGE_PROFICIENCY_OPTIONS,
} from "../_lib/intakeAdditionalDictionary";
import type { IntakeForeignLanguage } from "../_lib/intakeApi.client";

type Props = {
  items: IntakeForeignLanguage[];
  declaredEmpty: boolean;
  onChange: (items: IntakeForeignLanguage[]) => void;
  onDeclaredEmptyChange: (declaredEmpty: boolean) => void;
  readOnly?: boolean;
  focusTestId?: string | null;
};

function ForeignLanguageRowEditor({
  item,
  index,
  readOnly,
  onPatch,
}: {
  item: IntakeForeignLanguage;
  index: number;
  readOnly?: boolean;
  onPatch: (patch: Partial<IntakeForeignLanguage>) => void;
}) {
  return (
    <div
      className="grid gap-3 border-t border-zinc-200 bg-zinc-50 p-4 dark:border-zinc-800 dark:bg-zinc-900/40 sm:grid-cols-2"
      data-testid={`intake-foreign-language-editor-${index}`}
    >
      <IntakeSelectWithOtherField
        label="Язык"
        value={item.language}
        readOnly={readOnly}
        options={INTAKE_FOREIGN_LANGUAGE_OPTIONS}
        otherOptionValue={INTAKE_FOREIGN_LANGUAGE_OTHER}
        otherFieldLabel="Укажите язык"
        testId={`intake-foreign-language-language-${index}`}
        otherTestId={`intake-foreign-language-language-other-${index}`}
        onChange={(value) => onPatch({ language: value })}
      />
      <IntakeSelectField
        label="Уровень владения"
        value={item.proficiency}
        readOnly={readOnly}
        options={[{ value: "", label: "Выберите…" }, ...INTAKE_FOREIGN_LANGUAGE_PROFICIENCY_OPTIONS]}
        testId={`intake-foreign-language-proficiency-${index}`}
        onChange={(value) => onPatch({ proficiency: value })}
      />
    </div>
  );
}

export default function IntakeForeignLanguagesTable({
  items,
  declaredEmpty,
  onChange,
  onDeclaredEmptyChange,
  readOnly = false,
  focusTestId = null,
}: Props) {
  const [expandedIndex, setExpandedIndex] = React.useState<number | null>(null);
  const normalizedItems = React.useMemo(
    () => items.map((item) => normalizeIntakeForeignLanguageEntry(item)),
    [items],
  );
  const rows: IntakeForeignLanguageRow[] = normalizedItems.map((item, index) => ({ item, index }));
  const focusRowIndex = parseIntakeForeignLanguageFocusRowIndex(focusTestId);
  const visibleExpandedIndex = expandedIndex ?? focusRowIndex;

  React.useEffect(() => {
    if (focusRowIndex !== null) setExpandedIndex(focusRowIndex);
  }, [focusRowIndex]);

  function patchRow(index: number, patch: Partial<IntakeForeignLanguage>) {
    const next = [...items];
    next[index] = { ...normalizeIntakeForeignLanguageEntry(items[index]), ...patch };
    onChange(next);
  }

  function handleDelete(index: number) {
    const language = resolveIntakeForeignLanguageDisplay(normalizedItems[index]?.language ?? "") || "эту запись";
    if (!window.confirm(`Удалить язык «${language}»?`)) return;
    onChange(items.filter((_, itemIndex) => itemIndex !== index));
    setExpandedIndex((current) => (current === index ? null : current));
  }

  function handleAdd() {
    onDeclaredEmptyChange(false);
    const nextItems = [...items, emptyIntakeForeignLanguageEntry()];
    onChange(nextItems);
    setExpandedIndex(nextItems.length - 1);
  }

  function handleDeclaredEmptyChange(nextDeclaredEmpty: boolean) {
    onDeclaredEmptyChange(nextDeclaredEmpty);
    if (nextDeclaredEmpty) {
      setExpandedIndex(null);
    }
  }

  return (
    <IntakeOptionalListSection
      title="Знание иностранных языков"
      declaredEmpty={declaredEmpty}
      readOnly={readOnly}
      testIdPrefix="intake-foreign-languages"
      onDeclaredEmptyChange={handleDeclaredEmptyChange}
    >
      <div className="space-y-4" data-testid="intake-foreign-languages-table">
        {items.length === 0 ? (
          <p className="text-sm text-zinc-500" data-testid="intake-foreign-languages-empty">
            Записей пока нет.
          </p>
        ) : (
          <>
            <div className="hidden md:block" data-testid="intake-foreign-languages-desktop-view">
              <div className="overflow-x-auto rounded-xl border border-zinc-200 dark:border-zinc-800">
                <table className="min-w-full divide-y divide-zinc-200 dark:divide-zinc-800">
                  <thead className="bg-zinc-50 dark:bg-zinc-900/60">
                    <tr>
                      <th className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-zinc-500">
                        Язык
                      </th>
                      <th className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-zinc-500">
                        Уровень владения
                      </th>
                      <th className="px-3 py-2 text-right text-xs font-semibold uppercase tracking-wide text-zinc-500">
                        Действие
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map(({ item, index }) => (
                      <React.Fragment key={`desktop-foreign-language-${index}`}>
                        <tr
                          className="border-b border-zinc-200 dark:border-zinc-800"
                          data-testid={`intake-foreign-language-row-${index}`}
                        >
                          <td className="px-3 py-2 align-top text-sm">
                            {resolveIntakeForeignLanguageDisplay(item.language)}
                          </td>
                          <td className="px-3 py-2 align-top text-sm">
                            {intakeAdditionalCellValue(item.proficiency)}
                          </td>
                          <td className="px-3 py-2 align-top text-right">
                            <IntakeListRowActionsMenu
                              index={index}
                              readOnly={readOnly}
                              testIdPrefix="intake-foreign-language"
                              onEdit={() => setExpandedIndex((current) => (current === index ? null : index))}
                              onDelete={() => handleDelete(index)}
                            />
                          </td>
                        </tr>
                        {visibleExpandedIndex === index ? (
                          <tr data-testid={`intake-foreign-language-expanded-${index}`}>
                            <td colSpan={3} className="p-0">
                              <ForeignLanguageRowEditor
                                item={item}
                                index={index}
                                readOnly={readOnly}
                                onPatch={(patch) => patchRow(index, patch)}
                              />
                            </td>
                          </tr>
                        ) : null}
                      </React.Fragment>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </>
        )}

        {!readOnly ? (
          <button
            type="button"
            className="rounded-lg border border-dashed border-zinc-300 px-4 py-2 text-sm text-zinc-700 hover:bg-zinc-50 dark:border-zinc-700 dark:text-zinc-300"
            data-testid="intake-foreign-languages-add-button"
            onClick={handleAdd}
          >
            Добавить язык
          </button>
        ) : null}
      </div>
    </IntakeOptionalListSection>
  );
}
