"use client";

import * as React from "react";

import IntakeDictionaryCombobox from "./IntakeDictionaryCombobox";
import { INTAKE_COMPACT_TABLE_EDITOR_ROW_CLASS, IntakeCompactTableEditorCell } from "./IntakeCompactTableEditor";
import { IntakeDateField, IntakeTextField } from "./IntakeFormFields";
import IntakeListRowActionsMenu from "./IntakeListRowActionsMenu";
import IntakeOptionalListSection from "./IntakeOptionalListSection";
import IntakeSelectWithOtherField from "./IntakeSelectWithOtherField";
import {
  emptyIntakeAcademicTitleEntry,
  formatIntakeAcademicDegreeDateCell,
  intakeAdditionalCellValue,
  normalizeIntakeAcademicTitleEntry,
  parseIntakeAcademicTitleFocusRowIndex,
  resolveIntakeAcademicTitleDisplay,
  type IntakeAcademicTitleRow,
} from "../_lib/intakeAdditional";
import {
  INTAKE_ACADEMIC_TITLE_OPTIONS,
  INTAKE_ACADEMIC_TITLE_OTHER,
  INTAKE_FIELD_OF_SCIENCE_CATALOG,
  INTAKE_FIELD_OF_SCIENCE_POPULAR,
} from "../_lib/intakeAdditionalDictionary";
import type { IntakeAcademicTitle } from "../_lib/intakeApi.client";

type Props = {
  items: IntakeAcademicTitle[];
  declaredEmpty: boolean;
  onChange: (items: IntakeAcademicTitle[]) => void;
  onDeclaredEmptyChange: (declaredEmpty: boolean) => void;
  readOnly?: boolean;
  focusTestId?: string | null;
};

function patchAcademicTitleSelection(value: string): Partial<IntakeAcademicTitle> {
  const trimmed = value.trim();
  const known = INTAKE_ACADEMIC_TITLE_OPTIONS.find(
    (option) => option.value === trimmed && option.value !== INTAKE_ACADEMIC_TITLE_OTHER,
  );
  if (known) {
    return { academic_title: known.value, academic_title_other: "" };
  }
  return { academic_title: INTAKE_ACADEMIC_TITLE_OTHER, academic_title_other: trimmed };
}

function AcademicTitleFields({
  item,
  index,
  readOnly,
  compact,
  onPatch,
}: {
  item: IntakeAcademicTitle;
  index: number;
  readOnly?: boolean;
  compact?: boolean;
  onPatch: (patch: Partial<IntakeAcademicTitle>) => void;
}) {
  const normalized = normalizeIntakeAcademicTitleEntry(item);

  return (
    <>
      <IntakeSelectWithOtherField
        label="Учёное звание"
        compact={compact}
        value={
          normalized.academic_title === INTAKE_ACADEMIC_TITLE_OTHER
            ? normalized.academic_title_other
            : normalized.academic_title
        }
        readOnly={readOnly}
        options={INTAKE_ACADEMIC_TITLE_OPTIONS}
        otherOptionValue={INTAKE_ACADEMIC_TITLE_OTHER}
        otherFieldLabel="Уточните учёное звание"
        testId={`intake-academic-title-academic-title-${index}`}
        otherTestId={`intake-academic-title-academic-title-other-${index}`}
        onChange={(value) => onPatch(patchAcademicTitleSelection(value))}
      />
      <IntakeDictionaryCombobox
        label="Область наук (специальность)"
        compact={compact}
        value={normalized.field_of_science}
        readOnly={readOnly}
        allowFreeText
        popular={INTAKE_FIELD_OF_SCIENCE_POPULAR}
        catalog={INTAKE_FIELD_OF_SCIENCE_CATALOG}
        testId={`intake-academic-title-field-of-science-${index}`}
        onChange={(value) => onPatch({ field_of_science: value })}
      />
      <IntakeDateField
        label="Дата присвоения"
        compact={compact}
        value={normalized.completed_at}
        readOnly={readOnly}
        kind="period"
        testId={`intake-academic-title-completed-at-${index}`}
        onChange={(value) => onPatch({ completed_at: value })}
      />
      <IntakeTextField
        label="№ документа"
        compact={compact}
        value={normalized.document_number}
        readOnly={readOnly}
        testId={`intake-academic-title-document-number-${index}`}
        onChange={(value) => onPatch({ document_number: value })}
      />
    </>
  );
}

function AcademicTitleDesktopRowEditor({
  item,
  index,
  readOnly,
  onEdit,
  onDelete,
  onPatch,
}: {
  item: IntakeAcademicTitle;
  index: number;
  readOnly?: boolean;
  onEdit: () => void;
  onDelete: () => void;
  onPatch: (patch: Partial<IntakeAcademicTitle>) => void;
}) {
  const normalized = normalizeIntakeAcademicTitleEntry(item);

  return (
    <tr className={INTAKE_COMPACT_TABLE_EDITOR_ROW_CLASS} data-testid={`intake-academic-title-expanded-${index}`}>
      <IntakeCompactTableEditorCell>
        <IntakeSelectWithOtherField
          label="Учёное звание"
          compact
          value={
            normalized.academic_title === INTAKE_ACADEMIC_TITLE_OTHER
              ? normalized.academic_title_other
              : normalized.academic_title
          }
          readOnly={readOnly}
          options={INTAKE_ACADEMIC_TITLE_OPTIONS}
          otherOptionValue={INTAKE_ACADEMIC_TITLE_OTHER}
          otherFieldLabel="Уточните учёное звание"
          testId={`intake-academic-title-academic-title-${index}`}
          otherTestId={`intake-academic-title-academic-title-other-${index}`}
          onChange={(value) => onPatch(patchAcademicTitleSelection(value))}
        />
      </IntakeCompactTableEditorCell>
      <IntakeCompactTableEditorCell>
        <IntakeDictionaryCombobox
          label="Область наук (специальность)"
          compact
          value={normalized.field_of_science}
          readOnly={readOnly}
          allowFreeText
          popular={INTAKE_FIELD_OF_SCIENCE_POPULAR}
          catalog={INTAKE_FIELD_OF_SCIENCE_CATALOG}
          testId={`intake-academic-title-field-of-science-${index}`}
          onChange={(value) => onPatch({ field_of_science: value })}
        />
      </IntakeCompactTableEditorCell>
      <IntakeCompactTableEditorCell nowrap>
        <IntakeDateField
          label="Дата присвоения"
          compact
          value={normalized.completed_at}
          readOnly={readOnly}
          kind="period"
          testId={`intake-academic-title-completed-at-${index}`}
          onChange={(value) => onPatch({ completed_at: value })}
        />
      </IntakeCompactTableEditorCell>
      <IntakeCompactTableEditorCell>
        <IntakeTextField
          label="№ документа"
          compact
          value={normalized.document_number}
          readOnly={readOnly}
          testId={`intake-academic-title-document-number-${index}`}
          onChange={(value) => onPatch({ document_number: value })}
        />
      </IntakeCompactTableEditorCell>
      <IntakeCompactTableEditorCell className="text-right">
        <IntakeListRowActionsMenu
          index={index}
          readOnly={readOnly}
          testIdPrefix="intake-academic-title"
          onEdit={onEdit}
          onDelete={onDelete}
        />
      </IntakeCompactTableEditorCell>
    </tr>
  );
}

function AcademicTitleMobileCard({
  row,
  readOnly,
  expanded,
  onEdit,
  onDelete,
  onPatch,
}: {
  row: IntakeAcademicTitleRow;
  readOnly?: boolean;
  expanded: boolean;
  onEdit: () => void;
  onDelete: () => void;
  onPatch: (patch: Partial<IntakeAcademicTitle>) => void;
}) {
  const { item, index } = row;

  return (
    <div
      className="rounded-xl border border-zinc-200 dark:border-zinc-800 md:hidden"
      data-testid={`intake-academic-title-card-${index}`}
    >
      <div className="space-y-2 p-3">
        <div className="text-sm font-medium text-zinc-900 dark:text-zinc-100">
          {resolveIntakeAcademicTitleDisplay(item)}
        </div>
        <div className="text-sm text-zinc-600 dark:text-zinc-400">
          {intakeAdditionalCellValue(item.field_of_science)}
        </div>
        <div className="text-sm text-zinc-600 dark:text-zinc-400">
          {formatIntakeAcademicDegreeDateCell(item.completed_at)}
        </div>
        <div className="text-sm text-zinc-600 dark:text-zinc-400">
          {intakeAdditionalCellValue(item.document_number)}
        </div>
        <div className="flex justify-end">
          <IntakeListRowActionsMenu
            index={index}
            readOnly={readOnly}
            testIdPrefix="intake-academic-title"
            onEdit={onEdit}
            onDelete={onDelete}
          />
        </div>
      </div>
      {expanded ? (
        <div
          className="grid grid-cols-1 gap-3 border-t border-zinc-200 bg-zinc-50 p-4 dark:border-zinc-800 dark:bg-zinc-900/40 sm:grid-cols-2"
          data-testid={`intake-academic-title-editor-${index}`}
        >
          <AcademicTitleFields item={item} index={index} readOnly={readOnly} onPatch={onPatch} />
        </div>
      ) : null}
    </div>
  );
}

export default function IntakeAcademicTitlesTable({
  items,
  declaredEmpty,
  onChange,
  onDeclaredEmptyChange,
  readOnly = false,
  focusTestId = null,
}: Props) {
  const [expandedIndex, setExpandedIndex] = React.useState<number | null>(null);
  const normalizedItems = React.useMemo(
    () => items.map((item) => normalizeIntakeAcademicTitleEntry(item)),
    [items],
  );
  const rows: IntakeAcademicTitleRow[] = normalizedItems.map((item, index) => ({ item, index }));
  const focusRowIndex = parseIntakeAcademicTitleFocusRowIndex(focusTestId);
  const visibleExpandedIndex = expandedIndex ?? focusRowIndex;

  React.useEffect(() => {
    if (focusRowIndex !== null) setExpandedIndex(focusRowIndex);
  }, [focusRowIndex]);

  function patchRow(index: number, patch: Partial<IntakeAcademicTitle>) {
    const next = [...items];
    next[index] = { ...normalizeIntakeAcademicTitleEntry(items[index]), ...patch };
    onChange(next);
  }

  function handleDelete(index: number) {
    const label = resolveIntakeAcademicTitleDisplay(normalizedItems[index]) || "эту запись";
    if (!window.confirm(`Удалить запись «${label}»?`)) return;
    onChange(items.filter((_, itemIndex) => itemIndex !== index));
    setExpandedIndex((current) => (current === index ? null : current));
  }

  function handleAdd() {
    onDeclaredEmptyChange(false);
    const nextItems = [...items, emptyIntakeAcademicTitleEntry()];
    onChange(nextItems);
    setExpandedIndex(nextItems.length - 1);
  }

  function handleDeclaredEmptyChange(nextDeclaredEmpty: boolean) {
    onDeclaredEmptyChange(nextDeclaredEmpty);
    if (nextDeclaredEmpty) {
      setExpandedIndex(null);
    }
  }

  function toggleExpand(index: number) {
    setExpandedIndex((current) => (current === index ? null : index));
  }

  return (
    <IntakeOptionalListSection
      title="Учёные звания"
      declaredEmpty={declaredEmpty}
      readOnly={readOnly}
      testIdPrefix="intake-academic-titles"
      onDeclaredEmptyChange={handleDeclaredEmptyChange}
    >
      <div className="space-y-4" data-testid="intake-academic-titles-table">
        {items.length === 0 ? (
          <p className="text-sm text-zinc-500" data-testid="intake-academic-titles-empty">
            Записей пока нет.
          </p>
        ) : (
          <>
            <div className="hidden md:block" data-testid="intake-academic-titles-desktop-view">
              <div className="overflow-x-auto rounded-xl border border-zinc-200 dark:border-zinc-800">
                <table className="min-w-full table-fixed divide-y divide-zinc-200 dark:divide-zinc-800">
                  <colgroup>
                    <col className="w-[22%]" />
                    <col className="w-[34%]" />
                    <col className="w-[18%]" />
                    <col className="w-[18%]" />
                    <col className="w-[8%]" />
                  </colgroup>
                  <thead className="bg-zinc-50 dark:bg-zinc-900/60">
                    <tr>
                      <th className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-zinc-500">
                        Звание
                      </th>
                      <th className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-zinc-500">
                        Область наук
                      </th>
                      <th className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-zinc-500">
                        Дата
                      </th>
                      <th className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-zinc-500">
                        № документа
                      </th>
                      <th className="px-3 py-2 text-right text-xs font-semibold uppercase tracking-wide text-zinc-500">
                        Действие
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map(({ item, index }) => {
                      const expanded = visibleExpandedIndex === index;
                      return (
                        <React.Fragment key={`desktop-academic-title-${index}`}>
                          {expanded ? (
                            <AcademicTitleDesktopRowEditor
                              item={item}
                              index={index}
                              readOnly={readOnly}
                              onEdit={() => toggleExpand(index)}
                              onDelete={() => handleDelete(index)}
                              onPatch={(patch) => patchRow(index, patch)}
                            />
                          ) : (
                            <tr
                              className="border-b border-zinc-200 dark:border-zinc-800"
                              data-testid={`intake-academic-title-row-${index}`}
                            >
                              <td className="px-3 py-2 align-top text-sm">
                                {resolveIntakeAcademicTitleDisplay(item)}
                              </td>
                              <td className="px-3 py-2 align-top text-sm">
                                {intakeAdditionalCellValue(item.field_of_science)}
                              </td>
                              <td className="whitespace-nowrap px-3 py-2 align-top text-sm">
                                {formatIntakeAcademicDegreeDateCell(item.completed_at)}
                              </td>
                              <td className="px-3 py-2 align-top text-sm">
                                {intakeAdditionalCellValue(item.document_number)}
                              </td>
                              <td className="px-3 py-2 align-top text-right">
                                <IntakeListRowActionsMenu
                                  index={index}
                                  readOnly={readOnly}
                                  testIdPrefix="intake-academic-title"
                                  onEdit={() => toggleExpand(index)}
                                  onDelete={() => handleDelete(index)}
                                />
                              </td>
                            </tr>
                          )}
                        </React.Fragment>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>

            <div className="space-y-3 md:hidden">
              {rows.map((row) => (
                <AcademicTitleMobileCard
                  key={`mobile-academic-title-${row.index}`}
                  row={row}
                  readOnly={readOnly}
                  expanded={visibleExpandedIndex === row.index}
                  onEdit={() => toggleExpand(row.index)}
                  onDelete={() => handleDelete(row.index)}
                  onPatch={(patch) => patchRow(row.index, patch)}
                />
              ))}
            </div>
          </>
        )}

        {!readOnly ? (
          <button
            type="button"
            className="rounded-lg border border-dashed border-zinc-300 px-4 py-2 text-sm text-zinc-700 hover:bg-zinc-50 dark:border-zinc-700 dark:text-zinc-300"
            data-testid="intake-academic-titles-add-button"
            onClick={handleAdd}
          >
            Добавить звание
          </button>
        ) : null}
      </div>
    </IntakeOptionalListSection>
  );
}
