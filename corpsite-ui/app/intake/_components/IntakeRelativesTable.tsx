"use client";

import * as React from "react";

import { IntakeDateField, IntakeTextField } from "./IntakeFormFields";
import IntakeListRowActionsMenu from "./IntakeListRowActionsMenu";
import {
  emptyIntakeRelativeEntry,
  formatIntakeRelativeBirthCell,
  intakeRelativeCellValue,
  parseIntakeRelativeFocusRowIndex,
  sortIntakeRelativeRows,
  type IntakeRelativeEntry,
  type IntakeRelativeRow,
} from "../_lib/intakeRelatives";

type Props = {
  items: IntakeRelativeEntry[];
  onChange: (items: IntakeRelativeEntry[]) => void;
  readOnly?: boolean;
  focusTestId?: string | null;
};

function updateItemAt(
  items: IntakeRelativeEntry[],
  index: number,
  patch: Partial<IntakeRelativeEntry>,
): IntakeRelativeEntry[] {
  const next = [...items];
  next[index] = { ...next[index], ...patch };
  return next;
}

function RelativeRowEditor({
  item,
  index,
  readOnly,
  onPatch,
}: {
  item: IntakeRelativeEntry;
  index: number;
  readOnly?: boolean;
  onPatch: (patch: Partial<IntakeRelativeEntry>) => void;
}) {
  return (
    <div
      className="grid gap-3 border-t border-zinc-200 bg-zinc-50 p-4 dark:border-zinc-800 dark:bg-zinc-900/40 sm:grid-cols-2"
      data-testid={`intake-relative-editor-${index}`}
    >
      <IntakeTextField
        label="Степень родства"
        value={item.relationship}
        readOnly={readOnly}
        testId={`intake-relative-relationship-${index}`}
        onChange={(value) => onPatch({ relationship: value })}
      />
      <IntakeTextField
        label="ФИО"
        value={item.full_name}
        readOnly={readOnly}
        testId={`intake-relative-full-name-${index}`}
        onChange={(value) => onPatch({ full_name: value })}
      />
      <IntakeDateField
        label="Дата рождения"
        value={item.birth_year}
        readOnly={readOnly}
        kind="period"
        testId={`intake-relative-birth-year-${index}`}
        onChange={(value) => onPatch({ birth_year: value })}
      />
      <IntakeTextField
        label="Место работы"
        value={item.work_place}
        readOnly={readOnly}
        testId={`intake-relative-work-place-${index}`}
        onChange={(value) => onPatch({ work_place: value })}
      />
    </div>
  );
}

function RelativeSummaryCells({ item }: { item: IntakeRelativeEntry }) {
  return (
    <>
      <td className="px-3 py-2 align-top text-sm">{intakeRelativeCellValue(item.relationship)}</td>
      <td className="px-3 py-2 align-top text-sm">{intakeRelativeCellValue(item.full_name)}</td>
      <td className="whitespace-nowrap px-3 py-2 align-top text-sm">
        {formatIntakeRelativeBirthCell(item.birth_year)}
      </td>
      <td className="px-3 py-2 align-top text-sm">{intakeRelativeCellValue(item.work_place)}</td>
    </>
  );
}

function RelativeMobileCard({
  row,
  readOnly,
  expanded,
  onEdit,
  onDelete,
  onPatch,
}: {
  row: IntakeRelativeRow;
  readOnly?: boolean;
  expanded: boolean;
  onEdit: () => void;
  onDelete: () => void;
  onPatch: (patch: Partial<IntakeRelativeEntry>) => void;
}) {
  const { item, index } = row;
  return (
    <div
      className="rounded-xl border border-zinc-200 dark:border-zinc-800"
      data-testid={`intake-relative-card-${index}`}
    >
      <div className="space-y-2 p-3">
        <div className="text-sm font-medium text-zinc-900 dark:text-zinc-100">
          {intakeRelativeCellValue(item.full_name)}
        </div>
        <div className="text-sm text-zinc-600 dark:text-zinc-400">
          {intakeRelativeCellValue(item.relationship)}
        </div>
        <div className="text-sm text-zinc-600 dark:text-zinc-400">
          {formatIntakeRelativeBirthCell(item.birth_year)}
        </div>
        <div className="text-sm text-zinc-600 dark:text-zinc-400">
          {intakeRelativeCellValue(item.work_place)}
        </div>
        <div className="flex justify-end">
          <IntakeListRowActionsMenu
            index={index}
            readOnly={readOnly}
            testIdPrefix="intake-relative"
            onEdit={onEdit}
            onDelete={onDelete}
          />
        </div>
      </div>
      {expanded ? (
        <RelativeRowEditor item={item} index={index} readOnly={readOnly} onPatch={onPatch} />
      ) : null}
    </div>
  );
}

export default function IntakeRelativesTable({
  items,
  onChange,
  readOnly = false,
  focusTestId = null,
}: Props) {
  const [expandedIndex, setExpandedIndex] = React.useState<number | null>(null);
  const rows = React.useMemo(() => sortIntakeRelativeRows(items), [items]);
  const focusRowIndex = parseIntakeRelativeFocusRowIndex(focusTestId);
  const visibleExpandedIndex = expandedIndex ?? focusRowIndex;

  React.useEffect(() => {
    if (focusRowIndex !== null) setExpandedIndex(focusRowIndex);
  }, [focusRowIndex]);

  function patchRow(index: number, patch: Partial<IntakeRelativeEntry>) {
    onChange(updateItemAt(items, index, patch));
  }

  function handleDelete(index: number) {
    const name = items[index]?.full_name?.trim() || "эту запись";
    if (!window.confirm(`Удалить родственника «${name}»?`)) return;
    onChange(items.filter((_, itemIndex) => itemIndex !== index));
    setExpandedIndex((current) => (current === index ? null : current));
  }

  function handleAdd() {
    const nextItems = [...items, emptyIntakeRelativeEntry()];
    onChange(nextItems);
    setExpandedIndex(nextItems.length - 1);
  }

  function toggleExpand(index: number) {
    setExpandedIndex((current) => (current === index ? null : index));
  }

  return (
    <div className="space-y-4" data-testid="intake-relatives-table">
      {items.length === 0 ? (
        <p className="text-sm text-zinc-500" data-testid="intake-relatives-empty">
          Записей пока нет.
        </p>
      ) : (
        <>
          <div className="hidden md:block" data-testid="intake-relatives-desktop-view">
            <div className="overflow-x-auto rounded-xl border border-zinc-200 dark:border-zinc-800">
              <table className="min-w-full divide-y divide-zinc-200 dark:divide-zinc-800">
                <thead className="bg-zinc-50 dark:bg-zinc-900/60">
                  <tr>
                    <th className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-zinc-500">
                      Степень родства
                    </th>
                    <th className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-zinc-500">
                      ФИО
                    </th>
                    <th className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-zinc-500">
                      Дата рождения
                    </th>
                    <th className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-zinc-500">
                      Место работы
                    </th>
                    <th className="px-3 py-2 text-right text-xs font-semibold uppercase tracking-wide text-zinc-500">
                      Действие
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map(({ item, index }) => (
                    <React.Fragment key={`desktop-relative-${index}`}>
                      <tr
                        className="border-b border-zinc-200 dark:border-zinc-800"
                        data-testid={`intake-relative-row-${index}`}
                      >
                        <RelativeSummaryCells item={item} />
                        <td className="px-3 py-2 align-top text-right">
                          <IntakeListRowActionsMenu
                            index={index}
                            readOnly={readOnly}
                            testIdPrefix="intake-relative"
                            onEdit={() => toggleExpand(index)}
                            onDelete={() => handleDelete(index)}
                          />
                        </td>
                      </tr>
                      {visibleExpandedIndex === index ? (
                        <tr data-testid={`intake-relative-expanded-${index}`}>
                          <td colSpan={5} className="p-0">
                            <RelativeRowEditor
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

          <div className="space-y-3 md:hidden" data-testid="intake-relatives-mobile-view">
            {rows.map((row) => (
              <RelativeMobileCard
                key={`mobile-relative-${row.index}`}
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
          data-testid="intake-relatives-add-button"
          onClick={handleAdd}
        >
          Добавить родственника
        </button>
      ) : null}
    </div>
  );
}
