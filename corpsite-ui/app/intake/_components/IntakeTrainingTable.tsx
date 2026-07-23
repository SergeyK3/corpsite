"use client";

import * as React from "react";

import { IntakeDateField, IntakeSelectField, IntakeTextField } from "./IntakeFormFields";
import IntakeListRowActionsMenu from "./IntakeListRowActionsMenu";
import { INTAKE_TRAINING_DOCUMENT_TYPE_OPTIONS } from "../_lib/intakeApi.client";
import {
  applyTrainingEntryPatch,
  emptyIntakeTrainingEntry,
  formatIntakeTrainingHoursCell,
  formatIntakeTrainingPeriodCell,
  getIntakeTrainingDocumentTypeLabel,
  intakeTrainingCellValue,
  normalizeIntakeTrainingEntry,
  parseIntakeTrainingFocusRowIndex,
  resolveTrainingHoursState,
  sortIntakeTrainingRows,
  type IntakeTrainingEntry,
  type IntakeTrainingRow,
} from "../_lib/intakeTraining";

type Props = {
  items: IntakeTrainingEntry[];
  onChange: (items: IntakeTrainingEntry[]) => void;
  readOnly?: boolean;
  focusTestId?: string | null;
};


function TrainingRowEditor({
  item,
  index,
  readOnly,
  onPatch,
}: {
  item: IntakeTrainingEntry;
  index: number;
  readOnly?: boolean;
  onPatch: (patch: Partial<IntakeTrainingEntry>) => void;
}) {
  const hoursState = resolveTrainingHoursState(item);

  return (
    <div
      className="grid gap-3 border-t border-zinc-200 bg-zinc-50 p-4 dark:border-zinc-800 dark:bg-zinc-900/40 sm:grid-cols-2"
      data-testid={`intake-training-editor-${index}`}
    >
      <IntakeTextField
        label="Курс"
        value={item.course_name}
        readOnly={readOnly}
        testId={`intake-training-course-name-${index}`}
        onChange={(value) => onPatch({ course_name: value })}
      />
      <IntakeTextField
        label="Организация"
        value={item.institution}
        readOnly={readOnly}
        testId={`intake-training-institution-${index}`}
        onChange={(value) => onPatch({ institution: value })}
      />
      <IntakeDateField
        label="Дата начала"
        value={item.year_from}
        readOnly={readOnly}
        kind="period"
        testId={`intake-training-year-from-${index}`}
        onChange={(value) => onPatch({ year_from: value })}
      />
      <IntakeDateField
        label="Дата окончания"
        value={item.year_to}
        readOnly={readOnly}
        kind="period"
        testId={`intake-training-year-to-${index}`}
        onChange={(value) => onPatch({ year_to: value })}
      />
      <IntakeSelectField
        label="Документ"
        value={item.document_type}
        readOnly={readOnly}
        required
        options={INTAKE_TRAINING_DOCUMENT_TYPE_OPTIONS}
        testId={`intake-training-document-type-${index}`}
        onChange={(value) => onPatch({ document_type: value })}
      />
      <IntakeTextField
        label="№ документа"
        value={item.document_number}
        readOnly={readOnly}
        testId={`intake-training-document-number-${index}`}
        onChange={(value) => onPatch({ document_number: value })}
      />
      <IntakeTextField
        label="Количество часов"
        value={item.hours}
        readOnly={readOnly}
        testId={`intake-training-hours-${index}`}
        onChange={(value) => onPatch({ hours: value })}
      />
      <label className="block sm:col-span-2">
        <span className="text-sm font-medium text-zinc-700 dark:text-zinc-300">Примечание</span>
        <div
          className="mt-1 rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm text-zinc-700 dark:border-zinc-700 dark:bg-zinc-950 dark:text-zinc-300"
          data-testid={`intake-training-hours-note-${index}`}
        >
          {hoursState.note || "—"}
        </div>
        {hoursState.periodError ? (
          <span
            className="mt-1 block text-xs text-amber-700 dark:text-amber-300"
            data-testid={`intake-training-period-error-${index}`}
          >
            {hoursState.periodError}
          </span>
        ) : null}
      </label>
    </div>
  );
}

function TrainingSummaryCells({ item }: { item: IntakeTrainingEntry }) {
  return (
    <>
      <td className="px-3 py-2 align-top text-sm">{intakeTrainingCellValue(item.course_name)}</td>
      <td className="px-3 py-2 align-top text-sm">{intakeTrainingCellValue(item.institution)}</td>
      <td className="whitespace-nowrap px-3 py-2 align-top text-sm">
        {formatIntakeTrainingPeriodCell(item)}
      </td>
      <td className="px-3 py-2 align-top text-sm">{formatIntakeTrainingHoursCell(item.hours)}</td>
      <td className="px-3 py-2 align-top text-sm">
        {getIntakeTrainingDocumentTypeLabel(item.document_type)}
      </td>
      <td className="px-3 py-2 align-top text-sm">{intakeTrainingCellValue(item.document_number)}</td>
    </>
  );
}

function TrainingMobileCard({
  row,
  readOnly,
  expanded,
  onEdit,
  onDelete,
  onPatch,
}: {
  row: IntakeTrainingRow;
  readOnly?: boolean;
  expanded: boolean;
  onEdit: () => void;
  onDelete: () => void;
  onPatch: (patch: Partial<IntakeTrainingEntry>) => void;
}) {
  const { item, index } = row;
  return (
    <div
      className="rounded-xl border border-zinc-200 dark:border-zinc-800"
      data-testid={`intake-training-card-${index}`}
    >
      <div className="space-y-2 p-3">
        <div className="text-sm font-medium text-zinc-900 dark:text-zinc-100">
          {intakeTrainingCellValue(item.course_name)}
        </div>
        <div className="text-sm text-zinc-600 dark:text-zinc-400">
          {intakeTrainingCellValue(item.institution)}
        </div>
        <div className="text-sm text-zinc-600 dark:text-zinc-400">
          {formatIntakeTrainingPeriodCell(item)}
        </div>
        <div className="text-sm text-zinc-600 dark:text-zinc-400">
          {formatIntakeTrainingHoursCell(item.hours)}
        </div>
        <div className="text-sm text-zinc-600 dark:text-zinc-400">
          {getIntakeTrainingDocumentTypeLabel(item.document_type)}
        </div>
        <div className="text-sm text-zinc-600 dark:text-zinc-400">
          {intakeTrainingCellValue(item.document_number)}
        </div>
        <div className="flex justify-end">
          <IntakeListRowActionsMenu
            index={index}
            readOnly={readOnly}
            testIdPrefix="intake-training"
            onEdit={onEdit}
            onDelete={onDelete}
          />
        </div>
      </div>
      {expanded ? (
        <TrainingRowEditor item={item} index={index} readOnly={readOnly} onPatch={onPatch} />
      ) : null}
    </div>
  );
}

export default function IntakeTrainingTable({
  items,
  onChange,
  readOnly = false,
  focusTestId = null,
}: Props) {
  const [expandedIndex, setExpandedIndex] = React.useState<number | null>(null);
  const normalizedItems = React.useMemo(
    () => items.map((item) => normalizeIntakeTrainingEntry(item)),
    [items],
  );
  const rows = React.useMemo(() => sortIntakeTrainingRows(normalizedItems), [normalizedItems]);
  const focusRowIndex = parseIntakeTrainingFocusRowIndex(focusTestId);
  const visibleExpandedIndex = expandedIndex ?? focusRowIndex;

  React.useEffect(() => {
    if (focusRowIndex !== null) setExpandedIndex(focusRowIndex);
  }, [focusRowIndex]);

  function patchRow(index: number, patch: Partial<IntakeTrainingEntry>) {
    const next = [...items];
    next[index] = applyTrainingEntryPatch(normalizeIntakeTrainingEntry(items[index]), patch);
    onChange(next);
  }

  function handleDelete(index: number) {
    const title =
      normalizedItems[index]?.course_name?.trim() ||
      normalizedItems[index]?.institution?.trim() ||
      "эту запись";
    if (!window.confirm(`Удалить обучение «${title}»?`)) return;
    onChange(items.filter((_, itemIndex) => itemIndex !== index));
    setExpandedIndex((current) => (current === index ? null : current));
  }

  function handleAdd() {
    const nextItems = [...items, emptyIntakeTrainingEntry()];
    onChange(nextItems);
    setExpandedIndex(nextItems.length - 1);
  }

  function toggleExpand(index: number) {
    setExpandedIndex((current) => (current === index ? null : index));
  }

  return (
    <div className="space-y-4" data-testid="intake-training-table">
      {items.length === 0 ? (
        <p className="text-sm text-zinc-500" data-testid="intake-training-empty">
          Записей пока нет.
        </p>
      ) : (
        <>
          <div className="hidden md:block" data-testid="intake-training-desktop-view">
            <div className="overflow-x-auto rounded-xl border border-zinc-200 dark:border-zinc-800">
              <table className="min-w-full divide-y divide-zinc-200 dark:divide-zinc-800">
                <thead className="bg-zinc-50 dark:bg-zinc-900/60">
                  <tr>
                    <th className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-zinc-500">
                      Название обучения
                    </th>
                    <th className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-zinc-500">
                      Организация
                    </th>
                    <th className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-zinc-500">
                      Период
                    </th>
                    <th className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-zinc-500">
                      Часы
                    </th>
                    <th className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-zinc-500">
                      Документ
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
                  {rows.map(({ item, index }) => (
                    <React.Fragment key={`desktop-training-${index}`}>
                      <tr
                        className="border-b border-zinc-200 dark:border-zinc-800"
                        data-testid={`intake-training-row-${index}`}
                      >
                        <TrainingSummaryCells item={item} />
                        <td className="px-3 py-2 align-top text-right">
                          <IntakeListRowActionsMenu
                            index={index}
                            readOnly={readOnly}
                            testIdPrefix="intake-training"
                            onEdit={() => toggleExpand(index)}
                            onDelete={() => handleDelete(index)}
                          />
                        </td>
                      </tr>
                      {visibleExpandedIndex === index ? (
                        <tr data-testid={`intake-training-expanded-${index}`}>
                          <td colSpan={7} className="p-0">
                            <TrainingRowEditor
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

          <div className="space-y-3 md:hidden" data-testid="intake-training-mobile-view">
            {rows.map((row) => (
              <TrainingMobileCard
                key={`mobile-training-${row.index}`}
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
          data-testid="intake-training-add-button"
          onClick={handleAdd}
        >
          Добавить обучение
        </button>
      ) : null}
    </div>
  );
}
