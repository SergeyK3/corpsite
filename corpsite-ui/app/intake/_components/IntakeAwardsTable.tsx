"use client";

import * as React from "react";

import IntakeDictionaryCombobox from "./IntakeDictionaryCombobox";
import { INTAKE_COMPACT_TABLE_EDITOR_ROW_CLASS, IntakeCompactTableEditorCell } from "./IntakeCompactTableEditor";
import { IntakeDateField, IntakeSelectField, IntakeTextField } from "./IntakeFormFields";
import IntakeListRowActionsMenu from "./IntakeListRowActionsMenu";
import IntakeOptionalListSection from "./IntakeOptionalListSection";
import {
  emptyIntakeAwardEntry,
  formatIntakeAwardDateCell,
  intakeAdditionalCellValue,
  normalizeIntakeAwardEntry,
  parseIntakeAwardFocusRowIndex,
  resolveIntakeAwardCategoryDisplay,
  resolveIntakeAwardNameDisplay,
  type IntakeAwardRow,
} from "../_lib/intakeAdditional";
import {
  INTAKE_AWARD_CATEGORY_OPTIONS,
  INTAKE_AWARD_NAME_CATALOG,
  INTAKE_AWARD_NAME_POPULAR,
} from "../_lib/intakeAdditionalDictionary";
import type { IntakeAward } from "../_lib/intakeApi.client";

type Props = {
  items: IntakeAward[];
  declaredEmpty: boolean;
  onChange: (items: IntakeAward[]) => void;
  onDeclaredEmptyChange: (declaredEmpty: boolean) => void;
  readOnly?: boolean;
  focusTestId?: string | null;
};

function AwardFields({
  item,
  index,
  readOnly,
  compact,
  onPatch,
}: {
  item: IntakeAward;
  index: number;
  readOnly?: boolean;
  compact?: boolean;
  onPatch: (patch: Partial<IntakeAward>) => void;
}) {
  return (
    <>
      <IntakeSelectField
        label="Категория награды"
        compact={compact}
        value={item.category}
        readOnly={readOnly}
        required
        options={[{ value: "", label: "Выберите категорию" }, ...INTAKE_AWARD_CATEGORY_OPTIONS]}
        testId={`intake-award-category-${index}`}
        onChange={(value) => onPatch({ category: value })}
      />
      <IntakeDictionaryCombobox
        label="Название награды"
        compact={compact}
        value={item.name}
        readOnly={readOnly}
        allowFreeText
        popular={INTAKE_AWARD_NAME_POPULAR}
        catalog={INTAKE_AWARD_NAME_CATALOG}
        testId={`intake-award-name-${index}`}
        onChange={(value) => onPatch({ name: value })}
      />
      <IntakeTextField
        label="Кем выдана"
        compact={compact}
        value={item.issued_by}
        readOnly={readOnly}
        testId={`intake-award-issued-by-${index}`}
        onChange={(value) => onPatch({ issued_by: value })}
      />
      <IntakeDateField
        label="Дата награждения"
        compact={compact}
        value={item.awarded_at}
        readOnly={readOnly}
        kind="period"
        testId={`intake-award-awarded-at-${index}`}
        onChange={(value) => onPatch({ awarded_at: value })}
      />
      <IntakeTextField
        label="№ документа"
        compact={compact}
        value={item.document_number}
        readOnly={readOnly}
        testId={`intake-award-document-number-${index}`}
        onChange={(value) => onPatch({ document_number: value })}
      />
    </>
  );
}

function AwardDesktopRowEditor({
  item,
  index,
  readOnly,
  onEdit,
  onDelete,
  onPatch,
}: {
  item: IntakeAward;
  index: number;
  readOnly?: boolean;
  onEdit: () => void;
  onDelete: () => void;
  onPatch: (patch: Partial<IntakeAward>) => void;
}) {
  return (
    <tr className={INTAKE_COMPACT_TABLE_EDITOR_ROW_CLASS} data-testid={`intake-award-expanded-${index}`}>
      <IntakeCompactTableEditorCell>
        <IntakeSelectField
          label="Категория награды"
          compact
          value={item.category}
          readOnly={readOnly}
          required
          options={[{ value: "", label: "Выберите категорию" }, ...INTAKE_AWARD_CATEGORY_OPTIONS]}
          testId={`intake-award-category-${index}`}
          onChange={(value) => onPatch({ category: value })}
        />
      </IntakeCompactTableEditorCell>
      <IntakeCompactTableEditorCell>
        <IntakeDictionaryCombobox
          label="Название награды"
          compact
          value={item.name}
          readOnly={readOnly}
          allowFreeText
          popular={INTAKE_AWARD_NAME_POPULAR}
          catalog={INTAKE_AWARD_NAME_CATALOG}
          testId={`intake-award-name-${index}`}
          onChange={(value) => onPatch({ name: value })}
        />
      </IntakeCompactTableEditorCell>
      <IntakeCompactTableEditorCell>
        <IntakeTextField
          label="Кем выдана"
          compact
          value={item.issued_by}
          readOnly={readOnly}
          testId={`intake-award-issued-by-${index}`}
          onChange={(value) => onPatch({ issued_by: value })}
        />
      </IntakeCompactTableEditorCell>
      <IntakeCompactTableEditorCell nowrap>
        <IntakeDateField
          label="Дата награждения"
          compact
          value={item.awarded_at}
          readOnly={readOnly}
          kind="period"
          testId={`intake-award-awarded-at-${index}`}
          onChange={(value) => onPatch({ awarded_at: value })}
        />
      </IntakeCompactTableEditorCell>
      <IntakeCompactTableEditorCell>
        <IntakeTextField
          label="№ документа"
          compact
          value={item.document_number}
          readOnly={readOnly}
          testId={`intake-award-document-number-${index}`}
          onChange={(value) => onPatch({ document_number: value })}
        />
      </IntakeCompactTableEditorCell>
      <IntakeCompactTableEditorCell className="text-right">
        <IntakeListRowActionsMenu
          index={index}
          readOnly={readOnly}
          testIdPrefix="intake-award"
          onEdit={onEdit}
          onDelete={onDelete}
        />
      </IntakeCompactTableEditorCell>
    </tr>
  );
}

function AwardMobileCard({
  row,
  readOnly,
  expanded,
  onEdit,
  onDelete,
  onPatch,
}: {
  row: IntakeAwardRow;
  readOnly?: boolean;
  expanded: boolean;
  onEdit: () => void;
  onDelete: () => void;
  onPatch: (patch: Partial<IntakeAward>) => void;
}) {
  const { item, index } = row;

  return (
    <div
      className="rounded-xl border border-zinc-200 dark:border-zinc-800 md:hidden"
      data-testid={`intake-award-card-${index}`}
    >
      <div className="space-y-2 p-3">
        <div className="text-sm font-medium text-zinc-900 dark:text-zinc-100">
          {resolveIntakeAwardNameDisplay(item)}
        </div>
        {item.category ? (
          <div className="text-xs text-zinc-500">{resolveIntakeAwardCategoryDisplay(item)}</div>
        ) : null}
        <div className="text-sm text-zinc-600 dark:text-zinc-400">{intakeAdditionalCellValue(item.issued_by)}</div>
        <div className="text-sm text-zinc-600 dark:text-zinc-400">{formatIntakeAwardDateCell(item.awarded_at)}</div>
        <div className="text-sm text-zinc-600 dark:text-zinc-400">
          {intakeAdditionalCellValue(item.document_number)}
        </div>
        <div className="flex justify-end">
          <IntakeListRowActionsMenu
            index={index}
            readOnly={readOnly}
            testIdPrefix="intake-award"
            onEdit={onEdit}
            onDelete={onDelete}
          />
        </div>
      </div>
      {expanded ? (
        <div
          className="grid grid-cols-1 gap-3 border-t border-zinc-200 bg-zinc-50 p-4 dark:border-zinc-800 dark:bg-zinc-900/40 sm:grid-cols-2"
          data-testid={`intake-award-editor-${index}`}
        >
          <AwardFields item={item} index={index} readOnly={readOnly} onPatch={onPatch} />
        </div>
      ) : null}
    </div>
  );
}

export default function IntakeAwardsTable({
  items,
  declaredEmpty,
  onChange,
  onDeclaredEmptyChange,
  readOnly = false,
  focusTestId = null,
}: Props) {
  const [expandedIndex, setExpandedIndex] = React.useState<number | null>(null);
  const normalizedItems = React.useMemo(() => items.map((item) => normalizeIntakeAwardEntry(item)), [items]);
  const rows: IntakeAwardRow[] = normalizedItems.map((item, index) => ({ item, index }));
  const focusRowIndex = parseIntakeAwardFocusRowIndex(focusTestId);
  const visibleExpandedIndex = expandedIndex ?? focusRowIndex;

  React.useEffect(() => {
    if (focusRowIndex !== null) setExpandedIndex(focusRowIndex);
  }, [focusRowIndex]);

  function patchRow(index: number, patch: Partial<IntakeAward>) {
    const next = [...items];
    next[index] = { ...normalizeIntakeAwardEntry(items[index]), ...patch };
    onChange(next);
  }

  function handleDelete(index: number) {
    const label = resolveIntakeAwardNameDisplay(normalizedItems[index]);
    const fallback = resolveIntakeAwardCategoryDisplay(normalizedItems[index]);
    const title = label !== "—" ? label : fallback !== "—" ? fallback : "эту запись";
    if (!window.confirm(`Удалить награду «${title}»?`)) return;
    onChange(items.filter((_, itemIndex) => itemIndex !== index));
    setExpandedIndex((current) => (current === index ? null : current));
  }

  function handleAdd() {
    onDeclaredEmptyChange(false);
    const nextItems = [...items, emptyIntakeAwardEntry()];
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
      title="Награды"
      declaredEmpty={declaredEmpty}
      readOnly={readOnly}
      testIdPrefix="intake-awards"
      onDeclaredEmptyChange={handleDeclaredEmptyChange}
    >
      <div className="space-y-4" data-testid="intake-awards-table">
        {items.length === 0 ? (
          <p className="text-sm text-zinc-500" data-testid="intake-awards-empty">
            Записей пока нет.
          </p>
        ) : (
          <>
            <div className="hidden md:block" data-testid="intake-awards-desktop-view">
              <div className="overflow-x-auto rounded-xl border border-zinc-200 dark:border-zinc-800">
                <table className="min-w-full table-fixed divide-y divide-zinc-200 dark:divide-zinc-800">
                  <colgroup>
                    <col className="w-[14%]" />
                    <col className="w-[26%]" />
                    <col className="w-[26%]" />
                    <col className="w-[14%]" />
                    <col className="w-[12%]" />
                    <col className="w-[8%]" />
                  </colgroup>
                  <thead className="bg-zinc-50 dark:bg-zinc-900/60">
                    <tr>
                      <th className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-zinc-500">
                        Категория
                      </th>
                      <th className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-zinc-500">
                        Название награды
                      </th>
                      <th className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-zinc-500">
                        Кем выдана
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
                        <React.Fragment key={`desktop-award-${index}`}>
                          {expanded ? (
                            <AwardDesktopRowEditor
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
                              data-testid={`intake-award-row-${index}`}
                            >
                              <td className="px-3 py-2 align-top text-sm">
                                {resolveIntakeAwardCategoryDisplay(item)}
                              </td>
                              <td className="px-3 py-2 align-top text-sm">{resolveIntakeAwardNameDisplay(item)}</td>
                              <td className="px-3 py-2 align-top text-sm">{intakeAdditionalCellValue(item.issued_by)}</td>
                              <td className="whitespace-nowrap px-3 py-2 align-top text-sm">
                                {formatIntakeAwardDateCell(item.awarded_at)}
                              </td>
                              <td className="px-3 py-2 align-top text-sm">
                                {intakeAdditionalCellValue(item.document_number)}
                              </td>
                              <td className="px-3 py-2 align-top text-right">
                                <IntakeListRowActionsMenu
                                  index={index}
                                  readOnly={readOnly}
                                  testIdPrefix="intake-award"
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
                <AwardMobileCard
                  key={`mobile-award-${row.index}`}
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
            data-testid="intake-awards-add-button"
            onClick={handleAdd}
          >
            Добавить награду
          </button>
        ) : null}
      </div>
    </IntakeOptionalListSection>
  );
}
