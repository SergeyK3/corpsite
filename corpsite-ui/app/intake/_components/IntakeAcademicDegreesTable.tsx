"use client";

import * as React from "react";

import IntakeDictionaryCombobox from "./IntakeDictionaryCombobox";
import {
  INTAKE_COMPACT_TABLE_EDITOR_ROW_CLASS,
  IntakeCompactTableEditorCell,
} from "./IntakeCompactTableEditor";
import { IntakeDateField, IntakeTextField } from "./IntakeFormFields";
import IntakeListRowActionsMenu from "./IntakeListRowActionsMenu";
import IntakeOptionalListSection from "./IntakeOptionalListSection";
import IntakeSelectWithOtherField from "./IntakeSelectWithOtherField";
import {
  emptyIntakeAcademicDegreeEntry,
  formatIntakeAcademicDegreeDateCell,
  intakeAdditionalCellValue,
  normalizeIntakeAcademicDegreeEntry,
  parseIntakeAcademicDegreeFocusRowIndex,
  resolveIntakeAcademicDegreeDisplay,
  type IntakeAcademicDegreeRow,
} from "../_lib/intakeAdditional";
import {
  INTAKE_ACADEMIC_DEGREE_OPTIONS,
  INTAKE_ACADEMIC_DEGREE_OTHER,
  INTAKE_FIELD_OF_SCIENCE_CATALOG,
  INTAKE_FIELD_OF_SCIENCE_POPULAR,
} from "../_lib/intakeAdditionalDictionary";
import type { IntakeAcademicDegree } from "../_lib/intakeApi.client";

type Props = {
  items: IntakeAcademicDegree[];
  declaredEmpty: boolean;
  onChange: (items: IntakeAcademicDegree[]) => void;
  onDeclaredEmptyChange: (declaredEmpty: boolean) => void;
  readOnly?: boolean;
  focusTestId?: string | null;
};

function patchAcademicDegreeSelection(value: string): Partial<IntakeAcademicDegree> {
  const trimmed = value.trim();
  const known = INTAKE_ACADEMIC_DEGREE_OPTIONS.find(
    (option) => option.value === trimmed && option.value !== INTAKE_ACADEMIC_DEGREE_OTHER,
  );
  if (known) {
    return { degree: known.value, degree_other: "" };
  }
  return { degree: INTAKE_ACADEMIC_DEGREE_OTHER, degree_other: trimmed };
}

function AcademicDegreeFields({
  item,
  index,
  readOnly,
  compact,
  onPatch,
}: {
  item: IntakeAcademicDegree;
  index: number;
  readOnly?: boolean;
  compact?: boolean;
  onPatch: (patch: Partial<IntakeAcademicDegree>) => void;
}) {
  const normalized = normalizeIntakeAcademicDegreeEntry(item);

  return (
    <>
      <IntakeSelectWithOtherField
        label="Учёная степень"
        compact={compact}
        value={
          normalized.degree === INTAKE_ACADEMIC_DEGREE_OTHER
            ? normalized.degree_other
            : normalized.degree
        }
        readOnly={readOnly}
        options={INTAKE_ACADEMIC_DEGREE_OPTIONS}
        otherOptionValue={INTAKE_ACADEMIC_DEGREE_OTHER}
        otherFieldLabel="Уточните учёную степень"
        testId={`intake-academic-degree-degree-${index}`}
        otherTestId={`intake-academic-degree-degree-other-${index}`}
        onChange={(value) => onPatch(patchAcademicDegreeSelection(value))}
      />
      <IntakeDictionaryCombobox
        label="Область наук"
        compact={compact}
        value={normalized.field_of_science}
        readOnly={readOnly}
        allowFreeText
        popular={INTAKE_FIELD_OF_SCIENCE_POPULAR}
        catalog={INTAKE_FIELD_OF_SCIENCE_CATALOG}
        testId={`intake-academic-degree-field-of-science-${index}`}
        onChange={(value) => onPatch({ field_of_science: value })}
      />
      <IntakeDateField
        label="Дата присуждения"
        compact={compact}
        value={normalized.completed_at}
        readOnly={readOnly}
        kind="period"
        testId={`intake-academic-degree-completed-at-${index}`}
        onChange={(value) => onPatch({ completed_at: value })}
      />
      <IntakeTextField
        label="№ документа"
        compact={compact}
        value={normalized.document_number}
        readOnly={readOnly}
        testId={`intake-academic-degree-document-number-${index}`}
        onChange={(value) => onPatch({ document_number: value })}
      />
    </>
  );
}

function AcademicDegreeDesktopRowEditor({
  item,
  index,
  readOnly,
  onEdit,
  onDelete,
  onPatch,
}: {
  item: IntakeAcademicDegree;
  index: number;
  readOnly?: boolean;
  onEdit: () => void;
  onDelete: () => void;
  onPatch: (patch: Partial<IntakeAcademicDegree>) => void;
}) {
  const normalized = normalizeIntakeAcademicDegreeEntry(item);

  return (
    <tr className={INTAKE_COMPACT_TABLE_EDITOR_ROW_CLASS} data-testid={`intake-academic-degree-expanded-${index}`}>
      <IntakeCompactTableEditorCell>
        <IntakeSelectWithOtherField
          label="Учёная степень"
          compact
          value={
            normalized.degree === INTAKE_ACADEMIC_DEGREE_OTHER
              ? normalized.degree_other
              : normalized.degree
          }
          readOnly={readOnly}
          options={INTAKE_ACADEMIC_DEGREE_OPTIONS}
          otherOptionValue={INTAKE_ACADEMIC_DEGREE_OTHER}
          otherFieldLabel="Уточните учёную степень"
          testId={`intake-academic-degree-degree-${index}`}
          otherTestId={`intake-academic-degree-degree-other-${index}`}
          onChange={(value) => onPatch(patchAcademicDegreeSelection(value))}
        />
      </IntakeCompactTableEditorCell>
      <IntakeCompactTableEditorCell>
        <IntakeDictionaryCombobox
          label="Область наук"
          compact
          value={normalized.field_of_science}
          readOnly={readOnly}
          allowFreeText
          popular={INTAKE_FIELD_OF_SCIENCE_POPULAR}
          catalog={INTAKE_FIELD_OF_SCIENCE_CATALOG}
          testId={`intake-academic-degree-field-of-science-${index}`}
          onChange={(value) => onPatch({ field_of_science: value })}
        />
      </IntakeCompactTableEditorCell>
      <IntakeCompactTableEditorCell nowrap>
        <IntakeDateField
          label="Дата присуждения"
          compact
          value={normalized.completed_at}
          readOnly={readOnly}
          kind="period"
          testId={`intake-academic-degree-completed-at-${index}`}
          onChange={(value) => onPatch({ completed_at: value })}
        />
      </IntakeCompactTableEditorCell>
      <IntakeCompactTableEditorCell>
        <IntakeTextField
          label="№ документа"
          compact
          value={normalized.document_number}
          readOnly={readOnly}
          testId={`intake-academic-degree-document-number-${index}`}
          onChange={(value) => onPatch({ document_number: value })}
        />
      </IntakeCompactTableEditorCell>
      <IntakeCompactTableEditorCell className="text-right">
        <IntakeListRowActionsMenu
          index={index}
          readOnly={readOnly}
          testIdPrefix="intake-academic-degree"
          onEdit={onEdit}
          onDelete={onDelete}
        />
      </IntakeCompactTableEditorCell>
    </tr>
  );
}

function AcademicDegreeMobileCard({
  row,
  readOnly,
  expanded,
  onEdit,
  onDelete,
  onPatch,
}: {
  row: IntakeAcademicDegreeRow;
  readOnly?: boolean;
  expanded: boolean;
  onEdit: () => void;
  onDelete: () => void;
  onPatch: (patch: Partial<IntakeAcademicDegree>) => void;
}) {
  const { item, index } = row;

  return (
    <div
      className="rounded-xl border border-zinc-200 dark:border-zinc-800 md:hidden"
      data-testid={`intake-academic-degree-card-${index}`}
    >
      <div className="space-y-2 p-3">
        <div className="text-sm font-medium text-zinc-900 dark:text-zinc-100">
          {resolveIntakeAcademicDegreeDisplay(item)}
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
            testIdPrefix="intake-academic-degree"
            onEdit={onEdit}
            onDelete={onDelete}
          />
        </div>
      </div>
      {expanded ? (
        <div
          className="grid grid-cols-1 gap-3 border-t border-zinc-200 bg-zinc-50 p-4 dark:border-zinc-800 dark:bg-zinc-900/40 sm:grid-cols-2"
          data-testid={`intake-academic-degree-editor-${index}`}
        >
          <AcademicDegreeFields item={item} index={index} readOnly={readOnly} onPatch={onPatch} />
        </div>
      ) : null}
    </div>
  );
}

export default function IntakeAcademicDegreesTable({
  items,
  declaredEmpty,
  onChange,
  onDeclaredEmptyChange,
  readOnly = false,
  focusTestId = null,
}: Props) {
  const [expandedIndex, setExpandedIndex] = React.useState<number | null>(null);
  const normalizedItems = React.useMemo(
    () => items.map((item) => normalizeIntakeAcademicDegreeEntry(item)),
    [items],
  );
  const rows: IntakeAcademicDegreeRow[] = normalizedItems.map((item, index) => ({ item, index }));
  const focusRowIndex = parseIntakeAcademicDegreeFocusRowIndex(focusTestId);
  const visibleExpandedIndex = expandedIndex ?? focusRowIndex;

  React.useEffect(() => {
    if (focusRowIndex !== null) setExpandedIndex(focusRowIndex);
  }, [focusRowIndex]);

  function patchRow(index: number, patch: Partial<IntakeAcademicDegree>) {
    const next = [...items];
    next[index] = { ...normalizeIntakeAcademicDegreeEntry(items[index]), ...patch };
    onChange(next);
  }

  function handleDelete(index: number) {
    const label = resolveIntakeAcademicDegreeDisplay(normalizedItems[index]) || "эту запись";
    if (!window.confirm(`Удалить запись «${label}»?`)) return;
    onChange(items.filter((_, itemIndex) => itemIndex !== index));
    setExpandedIndex((current) => (current === index ? null : current));
  }

  function handleAdd() {
    onDeclaredEmptyChange(false);
    const nextItems = [...items, emptyIntakeAcademicDegreeEntry()];
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
      title="Учёные степени"
      declaredEmpty={declaredEmpty}
      readOnly={readOnly}
      testIdPrefix="intake-academic-degrees"
      onDeclaredEmptyChange={handleDeclaredEmptyChange}
    >
      <div className="space-y-4" data-testid="intake-academic-degrees-table">
        {items.length === 0 ? (
          <p className="text-sm text-zinc-500" data-testid="intake-academic-degrees-empty">
            Записей пока нет.
          </p>
        ) : (
          <>
            <div className="hidden md:block" data-testid="intake-academic-degrees-desktop-view">
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
                        Степень
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
                        <React.Fragment key={`desktop-academic-degree-${index}`}>
                          {expanded ? (
                            <AcademicDegreeDesktopRowEditor
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
                              data-testid={`intake-academic-degree-row-${index}`}
                            >
                              <td className="px-3 py-2 align-top text-sm">
                                {resolveIntakeAcademicDegreeDisplay(item)}
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
                                  testIdPrefix="intake-academic-degree"
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
                <AcademicDegreeMobileCard
                  key={`mobile-academic-degree-${row.index}`}
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
            data-testid="intake-academic-degrees-add-button"
            onClick={handleAdd}
          >
            Добавить степень
          </button>
        ) : null}
      </div>
    </IntakeOptionalListSection>
  );
}
