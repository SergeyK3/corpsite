"use client";

import * as React from "react";

import { isIntakeListRowEmpty } from "../_lib/intakeEmptyRows";
import { focusIntakeListEditor } from "../_lib/intakeListFocus";

import {
  IntakeEducationDateField,
  IntakeSelectField,
  IntakeTextField,
} from "./IntakeFormFields";
import IntakeListRowActionsMenu from "./IntakeListRowActionsMenu";
import {
  emptyIntakeEducationEntry,
  formatIntakeEducationPeriodCell,
  formatIntakeEducationSpecialtyCell,
  getIntakeEducationDocumentTypeLabel,
  intakeEducationCellValue,
  normalizeIntakeEducationEntry,
  parseIntakeEducationFocusRowIndex,
  sortIntakeEducationRows,
  type IntakeEducationRow,
} from "../_lib/intakeEducation";
import {
  INTAKE_EDUCATION_DOCUMENT_TYPE_OPTIONS,
  INTAKE_EDUCATION_TYPE_OPTIONS,
  fetchIntakeEducationLevels,
  type IntakeEducation,
  type IntakeEducationLevel,
} from "../_lib/intakeApi.client";
import { resolveIntakeEducationPeriodError } from "../_lib/intakeEducationDate";

type Props = {
  items: IntakeEducation[];
  onChange: (items: IntakeEducation[]) => void;
  readOnly?: boolean;
  focusTestId?: string | null;
  mode?: "public" | "hr-on-behalf";
  intakeToken?: string;
};


function EducationRowEditor({
  item,
  index,
  readOnly,
  onPatch,
  levels,
}: {
  item: IntakeEducation;
  index: number;
  readOnly?: boolean;
  onPatch: (patch: Partial<IntakeEducation>) => void;
  levels: IntakeEducationLevel[];
}) {
  const periodError = resolveIntakeEducationPeriodError(item.year_from, item.year_to);
  const levelOptions = [
    { value: "", label: "Выберите уровень" },
    ...levels.map((level) => ({ value: level.code, label: level.name_ru })),
  ];
  if (item.education_level_code && !levelOptions.some((level) => level.value === item.education_level_code)) {
    levelOptions.push({ value: item.education_level_code, label: item.education_level_name || item.education_level_code });
  }

  return (
    <div
      className="grid gap-3 border-t border-zinc-200 bg-zinc-50 p-4 dark:border-zinc-800 dark:bg-zinc-900/40 sm:grid-cols-2"
      data-testid={`intake-education-editor-${index}`}
    >
      <IntakeSelectField
        label="Уровень образования"
        value={item.education_level_code ?? ""}
        readOnly={readOnly}
        options={levelOptions}
        testId={`intake-education-level-${index}`}
        onChange={(code) => onPatch({ education_level_code: code, education_level_name: levels.find((level) => level.code === code)?.name_ru ?? "" })}
      />
      <IntakeSelectField
        label="Вид образования"
        value={item.education_type}
        readOnly={readOnly}
        required
        options={INTAKE_EDUCATION_TYPE_OPTIONS}
        testId={`intake-education-type-${index}`}
        onChange={(value) => onPatch({ education_type: value })}
      />
      <IntakeTextField
        label="Учебное заведение"
        value={item.institution}
        readOnly={readOnly}
        testId={`intake-education-institution-${index}`}
        onChange={(value) => onPatch({ institution: value })}
      />
      <IntakeEducationDateField
        label="Дата поступления"
        value={item.year_from}
        readOnly={readOnly}
        testId={`intake-education-year-from-${index}`}
        onChange={(value) => onPatch({ year_from: value })}
      />
      <IntakeEducationDateField
        label="Дата окончания"
        value={item.year_to}
        readOnly={readOnly}
        testId={`intake-education-year-to-${index}`}
        onChange={(value) => onPatch({ year_to: value })}
      />
      <IntakeTextField
        label="Специальность"
        value={item.specialty}
        readOnly={readOnly}
        testId={`intake-education-specialty-${index}`}
        onChange={(value) => onPatch({ specialty: value })}
      />
      <IntakeTextField
        label="Квалификация"
        value={item.qualification}
        readOnly={readOnly}
        testId={`intake-education-qualification-${index}`}
        onChange={(value) => onPatch({ qualification: value })}
      />
      <IntakeSelectField
        label="Документ"
        value={item.document_type}
        readOnly={readOnly}
        required
        options={INTAKE_EDUCATION_DOCUMENT_TYPE_OPTIONS}
        testId={`intake-education-document-type-${index}`}
        onChange={(value) => onPatch({ document_type: value })}
      />
      <IntakeTextField
        label="№ документа"
        value={item.diploma_number}
        readOnly={readOnly}
        testId={`intake-education-diploma-number-${index}`}
        onChange={(value) => onPatch({ diploma_number: value })}
      />
      {periodError ? (
        <p
          className="sm:col-span-2 text-xs text-amber-700 dark:text-amber-300"
          data-testid={`intake-education-period-error-${index}`}
        >
          {periodError}
        </p>
      ) : null}
    </div>
  );
}

function EducationSummaryCells({ item }: { item: IntakeEducation }) {
  return (
    <>
      <td className="px-3 py-2 align-top text-sm">{intakeEducationCellValue(item.education_level_name)}</td>
      <td className="px-3 py-2 align-top text-sm">{intakeEducationCellValue(item.institution)}</td>
      <td className="whitespace-nowrap px-3 py-2 align-top text-sm">
        {formatIntakeEducationPeriodCell(item.year_from, item.year_to)}
      </td>
      <td className="px-3 py-2 align-top text-sm">
        {formatIntakeEducationSpecialtyCell(item.specialty, item.qualification)}
      </td>
      <td className="px-3 py-2 align-top text-sm">
        {getIntakeEducationDocumentTypeLabel(item.document_type)}
      </td>
      <td className="px-3 py-2 align-top text-sm">{intakeEducationCellValue(item.diploma_number)}</td>
    </>
  );
}

function EducationMobileCard({
  row,
  readOnly,
  expanded,
  onEdit,
  onDelete,
  onPatch,
  levels,
}: {
  row: IntakeEducationRow;
  readOnly?: boolean;
  expanded: boolean;
  onEdit: () => void;
  onDelete: () => void;
  onPatch: (patch: Partial<IntakeEducation>) => void;
  levels: IntakeEducationLevel[];
}) {
  const { item, index } = row;
  return (
    <div
      className="rounded-xl border border-zinc-200 dark:border-zinc-800"
      data-testid={`intake-education-card-${index}`}
    >
      <div className="space-y-2 p-3">
        <div className="text-sm font-medium text-zinc-900 dark:text-zinc-100">
          {intakeEducationCellValue(item.institution)}
        </div>
        <div className="text-sm text-zinc-600 dark:text-zinc-400">{intakeEducationCellValue(item.education_level_name)}</div>
        <div className="text-sm text-zinc-600 dark:text-zinc-400">
          {formatIntakeEducationPeriodCell(item.year_from, item.year_to)}
        </div>
        <div className="text-sm text-zinc-600 dark:text-zinc-400">
          {formatIntakeEducationSpecialtyCell(item.specialty, item.qualification)}
        </div>
        <div className="text-sm text-zinc-600 dark:text-zinc-400">
          {getIntakeEducationDocumentTypeLabel(item.document_type)}
        </div>
        <div className="text-sm text-zinc-600 dark:text-zinc-400">
          {intakeEducationCellValue(item.diploma_number)}
        </div>
        <div className="flex justify-end">
          <IntakeListRowActionsMenu
            index={index}
            readOnly={readOnly}
            testIdPrefix="intake-education"
            onEdit={onEdit}
            onDelete={onDelete}
          />
        </div>
      </div>
      {expanded ? (
        <EducationRowEditor item={item} index={index} readOnly={readOnly} onPatch={onPatch} levels={levels} />
      ) : null}
    </div>
  );
}

export default function IntakeEducationTable({
  items,
  onChange,
  readOnly = false,
  focusTestId = null,
  mode = "public",
  intakeToken,
}: Props) {
  const [expandedIndex, setExpandedIndex] = React.useState<number | null>(null);
  const [levels, setLevels] = React.useState<IntakeEducationLevel[]>([]);
  const [levelsError, setLevelsError] = React.useState(false);
  React.useEffect(() => {
    if (mode === "public" && !intakeToken) return;
    let active = true;
    void fetchIntakeEducationLevels(mode, intakeToken)
      .then((items) => { if (active) { setLevels(items); setLevelsError(false); } })
      .catch(() => { if (active) setLevelsError(true); });
    return () => { active = false; };
  }, [mode, intakeToken]);
  const normalizedItems = React.useMemo(
    () => items.map((item) => normalizeIntakeEducationEntry(item)),
    [items],
  );
  const rows = React.useMemo(() => sortIntakeEducationRows(normalizedItems), [normalizedItems]);
  const focusRowIndex = parseIntakeEducationFocusRowIndex(focusTestId);
  const visibleExpandedIndex = expandedIndex ?? focusRowIndex;

  React.useEffect(() => {
    if (focusRowIndex !== null) setExpandedIndex(focusRowIndex);
  }, [focusRowIndex]);

  function patchRow(index: number, patch: Partial<IntakeEducation>) {
    const next = [...items];
    next[index] = { ...normalizeIntakeEducationEntry(items[index]), ...patch };
    onChange(next);
  }

  function handleDelete(index: number) {
    const institution = normalizedItems[index]?.institution?.trim() || "эту запись";
    if (!window.confirm(`Удалить образование «${institution}»?`)) return;
    onChange(items.filter((_, itemIndex) => itemIndex !== index));
    setExpandedIndex((current) => (current === index ? null : current));
  }

  function handleAdd() {
    const emptyIndex = items.findIndex((item) => isIntakeListRowEmpty("education", item));
    if (emptyIndex >= 0) {
      setExpandedIndex(emptyIndex);
      focusIntakeListEditor(`intake-education-editor-${emptyIndex}`);
      return;
    }
    const nextItems = [...items, emptyIntakeEducationEntry()];
    onChange(nextItems);
    setExpandedIndex(nextItems.length - 1);
    focusIntakeListEditor(`intake-education-editor-${nextItems.length - 1}`);
  }

  function toggleExpand(index: number) {
    setExpandedIndex((current) => (current === index ? null : index));
  }

  return (
    <div className="space-y-4" data-testid="intake-education-table">
      {levelsError ? <p role="alert" className="text-sm text-red-600">Не удалось загрузить уровни образования. Обновите страницу и попробуйте снова.</p> : null}
      {items.length === 0 ? (
        <p className="text-sm text-zinc-500" data-testid="intake-education-empty">
          Записей пока нет.
        </p>
      ) : (
        <>
          <div className="hidden md:block" data-testid="intake-education-desktop-view">
            <div className="overflow-x-auto rounded-xl border border-zinc-200 dark:border-zinc-800">
              <table className="min-w-full divide-y divide-zinc-200 dark:divide-zinc-800">
                <thead className="bg-zinc-50 dark:bg-zinc-900/60">
                  <tr>
                    <th className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-zinc-500">Уровень</th>
                    <th className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-zinc-500">
                      Учебное заведение
                    </th>
                    <th className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-zinc-500">
                      Период обучения
                    </th>
                    <th className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-zinc-500">
                      Специальность / квалификация
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
                    <React.Fragment key={`desktop-education-${index}`}>
                      <tr
                        className="border-b border-zinc-200 dark:border-zinc-800"
                        data-testid={`intake-education-row-${index}`}
                      >
                        <EducationSummaryCells item={item} />
                        <td className="px-3 py-2 align-top text-right">
                          <IntakeListRowActionsMenu
                            index={index}
                            readOnly={readOnly}
                            testIdPrefix="intake-education"
                            onEdit={() => toggleExpand(index)}
                            onDelete={() => handleDelete(index)}
                          />
                        </td>
                      </tr>
                      {visibleExpandedIndex === index ? (
                        <tr data-testid={`intake-education-expanded-${index}`}>
                          <td colSpan={7} className="p-0">
                            <EducationRowEditor
                              item={item}
                              index={index}
                              readOnly={readOnly}
                              onPatch={(patch) => patchRow(index, patch)}
                              levels={levels}
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

          <div className="space-y-3 md:hidden" data-testid="intake-education-mobile-view">
            {rows.map((row) => (
              <EducationMobileCard
                key={`mobile-education-${row.index}`}
                row={row}
                readOnly={readOnly}
                expanded={visibleExpandedIndex === row.index}
                onEdit={() => toggleExpand(row.index)}
                onDelete={() => handleDelete(row.index)}
                onPatch={(patch) => patchRow(row.index, patch)}
                levels={levels}
              />
            ))}
          </div>
        </>
      )}

      {!readOnly ? (
        <button
          type="button"
          className="rounded-lg border border-dashed border-zinc-300 px-4 py-2 text-sm text-zinc-700 hover:bg-zinc-50 dark:border-zinc-700 dark:text-zinc-300"
          data-testid="intake-education-add-button"
          onClick={handleAdd}
        >
          Добавить образование
        </button>
      ) : null}
    </div>
  );
}
