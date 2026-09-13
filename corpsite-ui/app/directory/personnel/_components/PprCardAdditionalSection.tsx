"use client";

import {
  formatIntakeAcademicDegreeDateCell,
  formatIntakeAwardDateCell,
  intakeAdditionalCellValue,
  normalizeIntakeAcademicDegreeEntry,
  normalizeIntakeAcademicTitleEntry,
  normalizeIntakeAwardEntry,
  normalizeIntakeForeignLanguageEntry,
  resolveIntakeAcademicDegreeDisplay,
  resolveIntakeAcademicTitleDisplay,
  resolveIntakeAwardCategoryDisplay,
  resolveIntakeAwardNameDisplay,
  resolveIntakeForeignLanguageDisplay,
} from "@/app/intake/_lib/intakeAdditional";
import type {
  PprAdditionalAcademicDegreeResponse,
  PprAdditionalAcademicTitleResponse,
  PprAdditionalAwardResponse,
  PprAdditionalForeignLanguageResponse,
  PprQualificationCategoryRecordResponse,
  PprAdditionalProfileResponse,
} from "../_lib/pprQueryTypes";
import PprAdditionalStatusFactsEditor from "./PprAdditionalStatusFactsEditor";

type Props = {
  additional: PprAdditionalProfileResponse;
  mode?: "languages" | "category" | "notes" | "additional";
  personId?: number;
  editableStatusFacts?: boolean;
  onStatusFactsSaved?: () => void;
};

function NoneDeclaredMessage({ label }: { label: string }) {
  return <p className="text-sm text-zinc-500">{label}: нет сведений.</p>;
}

function EmptyRecordsMessage({ label }: { label: string }) {
  return <p className="text-sm text-zinc-500">{label}: записей пока нет.</p>;
}

function ForeignLanguagesBlock({
  items,
  declaredEmpty,
}: {
  items: PprAdditionalForeignLanguageResponse[];
  declaredEmpty: boolean;
}) {
  if (declaredEmpty) return <NoneDeclaredMessage label="Иностранные языки" />;
  if (items.length === 0) return <EmptyRecordsMessage label="Иностранные языки" />;
  return (
    <div className="overflow-x-auto rounded-xl border border-zinc-200 dark:border-zinc-800">
      <table className="min-w-full divide-y divide-zinc-200 dark:divide-zinc-800" data-testid="ppr-additional-languages-table">
        <thead className="bg-zinc-50 dark:bg-zinc-900/60">
          <tr>
            <th className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-zinc-500">Язык</th>
            <th className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-zinc-500">
              Уровень владения
            </th>
          </tr>
        </thead>
        <tbody>
          {items.map((item, index) => {
            const normalized = normalizeIntakeForeignLanguageEntry(item);
            return (
              <tr key={`ppr-language-${index}`} data-testid={`ppr-additional-language-row-${index}`}>
                <td className="px-3 py-2 text-sm">{resolveIntakeForeignLanguageDisplay(normalized.language)}</td>
                <td className="px-3 py-2 text-sm">{intakeAdditionalCellValue(normalized.proficiency)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function AwardsBlock({
  items,
  declaredEmpty,
}: {
  items: PprAdditionalAwardResponse[];
  declaredEmpty: boolean;
}) {
  if (declaredEmpty) return <NoneDeclaredMessage label="Награды" />;
  if (items.length === 0) return <EmptyRecordsMessage label="Награды" />;
  return (
    <div className="overflow-x-auto rounded-xl border border-zinc-200 dark:border-zinc-800">
      <table className="min-w-full divide-y divide-zinc-200 dark:divide-zinc-800" data-testid="ppr-additional-awards-table">
        <thead className="bg-zinc-50 dark:bg-zinc-900/60">
          <tr>
            <th className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-zinc-500">
              Название награды
            </th>
            <th className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-zinc-500">Кем выдана</th>
            <th className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-zinc-500">Дата</th>
            <th className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-zinc-500">№ документа</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item, index) => {
            const normalized = normalizeIntakeAwardEntry(item);
            return (
              <tr key={`ppr-award-${index}`} data-testid={`ppr-additional-award-row-${index}`}>
                <td className="px-3 py-2 text-sm">
                  <div>{resolveIntakeAwardNameDisplay(normalized)}</div>
                  {normalized.category ? (
                    <div className="mt-0.5 text-xs text-zinc-500">{resolveIntakeAwardCategoryDisplay(normalized)}</div>
                  ) : null}
                </td>
                <td className="px-3 py-2 text-sm">{intakeAdditionalCellValue(normalized.issued_by)}</td>
                <td className="whitespace-nowrap px-3 py-2 text-sm">{formatIntakeAwardDateCell(normalized.awarded_at)}</td>
                <td className="px-3 py-2 text-sm">{intakeAdditionalCellValue(normalized.document_number)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function AcademicDegreesBlock({
  items,
  declaredEmpty,
}: {
  items: PprAdditionalAcademicDegreeResponse[];
  declaredEmpty: boolean;
}) {
  if (declaredEmpty) return <NoneDeclaredMessage label="Учёные степени" />;
  if (items.length === 0) return <EmptyRecordsMessage label="Учёные степени" />;
  return (
    <div className="overflow-x-auto rounded-xl border border-zinc-200 dark:border-zinc-800">
      <table
        className="min-w-full divide-y divide-zinc-200 dark:divide-zinc-800"
        data-testid="ppr-additional-degrees-table"
      >
        <thead className="bg-zinc-50 dark:bg-zinc-900/60">
          <tr>
            <th className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-zinc-500">Степень</th>
            <th className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-zinc-500">
              Область наук
            </th>
            <th className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-zinc-500">Дата</th>
            <th className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-zinc-500">
              № документа
            </th>
          </tr>
        </thead>
        <tbody>
          {items.map((item, index) => {
            const normalized = normalizeIntakeAcademicDegreeEntry({
              ...item,
              label: item.label ?? undefined,
              degree_type: item.degree_type ?? undefined,
            });
            return (
              <tr key={`ppr-degree-${index}`} data-testid={`ppr-additional-degree-row-${index}`}>
                <td className="px-3 py-2 text-sm">{resolveIntakeAcademicDegreeDisplay(normalized)}</td>
                <td className="px-3 py-2 text-sm">{intakeAdditionalCellValue(normalized.field_of_science)}</td>
                <td className="whitespace-nowrap px-3 py-2 text-sm">
                  {formatIntakeAcademicDegreeDateCell(normalized.completed_at)}
                </td>
                <td className="px-3 py-2 text-sm">{intakeAdditionalCellValue(normalized.document_number)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function AcademicTitlesBlock({
  items,
  declaredEmpty,
}: {
  items: PprAdditionalAcademicTitleResponse[];
  declaredEmpty: boolean;
}) {
  if (declaredEmpty) return <NoneDeclaredMessage label="Учёные звания" />;
  if (items.length === 0) return <EmptyRecordsMessage label="Учёные звания" />;
  return (
    <div className="overflow-x-auto rounded-xl border border-zinc-200 dark:border-zinc-800">
      <table
        className="min-w-full divide-y divide-zinc-200 dark:divide-zinc-800"
        data-testid="ppr-additional-titles-table"
      >
        <thead className="bg-zinc-50 dark:bg-zinc-900/60">
          <tr>
            <th className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-zinc-500">Звание</th>
            <th className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-zinc-500">
              Область наук
            </th>
            <th className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-zinc-500">Дата</th>
            <th className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-zinc-500">
              № документа
            </th>
          </tr>
        </thead>
        <tbody>
          {items.map((item, index) => {
            const normalized = normalizeIntakeAcademicTitleEntry({
              ...item,
              label: item.label ?? undefined,
              degree_type: item.degree_type ?? undefined,
            });
            return (
              <tr key={`ppr-title-${index}`} data-testid={`ppr-additional-title-row-${index}`}>
                <td className="px-3 py-2 text-sm">{resolveIntakeAcademicTitleDisplay(normalized)}</td>
                <td className="px-3 py-2 text-sm">{intakeAdditionalCellValue(normalized.field_of_science)}</td>
                <td className="whitespace-nowrap px-3 py-2 text-sm">
                  {formatIntakeAcademicDegreeDateCell(normalized.completed_at)}
                </td>
                <td className="px-3 py-2 text-sm">{intakeAdditionalCellValue(normalized.document_number)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function SourceNoteHint({ value }: { value?: string | null }) {
  if (!value) return null;
  return <aside className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-950 dark:border-amber-900 dark:bg-amber-950/30 dark:text-amber-100" data-testid="ppr-additional-source-note-hint">
    <span className="font-medium">Исходный текст из импорта — подсказка кадровику:</span>{" "}{value}
  </aside>;
}

function StatusFactsBlock({ additional }: { additional: PprAdditionalProfileResponse }) {
  const pension = additional.status_facts.filter((fact) => fact.fact_kind === "PENSION");
  const disability = additional.status_facts.filter((fact) => fact.fact_kind === "DISABILITY");
  return (
    <div className="space-y-5" data-testid="ppr-status-facts-table">
      <SourceNoteHint value={additional.source_note_hint} />
      <div className="space-y-2"><h4 className="text-sm font-semibold">Пенсионный статус</h4><div className="overflow-x-auto rounded-xl border border-zinc-200 dark:border-zinc-800"><table className="min-w-full divide-y divide-zinc-200 dark:divide-zinc-800">
        <thead className="bg-zinc-50 dark:bg-zinc-900/60">
          <tr>
            <th className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-zinc-500">Вид</th>
            <th className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-zinc-500">Дата установления</th>
            <th className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-zinc-500">Статус проверки</th>
          </tr>
        </thead>
        <tbody>
          {pension.length === 0 ? <tr><td colSpan={3} className="px-3 py-2 text-sm text-zinc-500">Записей пока нет.</td></tr> : pension.map((fact) => (
            <tr key={fact.status_fact_id} data-testid={`ppr-status-fact-${fact.status_fact_id}`}>
              <td className="px-3 py-2 text-sm">{fact.pension_kind === "AGE" ? "По возрасту" : fact.pension_kind === "SERVICE" ? "За выслугу лет" : "Не указан"}</td>
              <td className="whitespace-nowrap px-3 py-2 text-sm">{fact.effective_date || "Не указана"}</td>
              <td className="px-3 py-2 text-sm">{fact.review_status === "AUTO_READY" ? "Готово к согласованию" : "Требуется ручная проверка"}</td>
            </tr>
          ))}
        </tbody>
      </table></div></div>
      <div className="space-y-2"><h4 className="text-sm font-semibold">Инвалидность</h4><div className="overflow-x-auto rounded-xl border border-zinc-200 dark:border-zinc-800"><table className="min-w-full divide-y divide-zinc-200 dark:divide-zinc-800">
        <thead className="bg-zinc-50 dark:bg-zinc-900/60"><tr>
          <th className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-zinc-500">Группа</th>
          <th className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-zinc-500">Дата установления</th>
          <th className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-zinc-500">Код заболевания по МКБ-10</th>
          <th className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-zinc-500">Статус проверки</th>
        </tr></thead>
        <tbody>{disability.length === 0 ? <tr><td colSpan={4} className="px-3 py-2 text-sm text-zinc-500">Записей пока нет.</td></tr> : disability.map((fact) => <tr key={fact.status_fact_id} data-testid={`ppr-status-fact-${fact.status_fact_id}`}>
          <td className="px-3 py-2 text-sm">{fact.disability_group || "Не указана"}</td><td className="px-3 py-2 text-sm">{fact.effective_date || "Не указана"}</td><td className="px-3 py-2 text-sm">{fact.icd10_code || "Не указан"}</td><td className="px-3 py-2 text-sm">{fact.review_status === "AUTO_READY" ? "Готово к согласованию" : "Требуется ручная проверка"}</td>
        </tr>)}</tbody>
      </table></div></div>
    </div>
  );
}

const CATEGORY_LABELS: Record<string, string> = {
  highest: "Высшая",
  first: "Первая",
  second: "Вторая",
};

function QualificationCategoriesBlock({ items }: { items: PprQualificationCategoryRecordResponse[] }) {
  if (items.length === 0) return <EmptyRecordsMessage label="Категория" />;
  return (
    <div className="overflow-x-auto rounded-xl border border-zinc-200 dark:border-zinc-800">
      <table className="min-w-full divide-y divide-zinc-200 dark:divide-zinc-800" data-testid="ppr-qualification-categories-table">
        <thead className="bg-zinc-50 dark:bg-zinc-900/60"><tr>
          <th className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-zinc-500">Специальность</th>
          <th className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-zinc-500">Категория</th>
          <th className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-zinc-500">Дата присвоения</th>
        </tr></thead>
        <tbody>{items.map((item, index) => <tr key={`ppr-category-${index}`} data-testid={`ppr-qualification-category-row-${index}`}>
          <td className="px-3 py-2 text-sm">{intakeAdditionalCellValue(item.specialty)}</td>
          <td className="px-3 py-2 text-sm">{CATEGORY_LABELS[item.category] ?? intakeAdditionalCellValue(item.category)}</td>
          <td className="px-3 py-2 text-sm">{intakeAdditionalCellValue(item.assigned_at)}{item.assigned_at_calculated ? " (рассчитана)" : ""}</td>
        </tr>)}</tbody>
      </table>
    </div>
  );
}

export default function PprCardAdditionalSection({ additional, mode = "additional", personId, editableStatusFacts = false, onStatusFactsSaved }: Props) {
  if (mode === "languages") {
    return (
      <div className="space-y-3" data-testid="ppr-foreign-languages-section">
        <ForeignLanguagesBlock items={additional.foreign_languages} declaredEmpty={additional.foreign_languages_none} />
      </div>
    );
  }
  if (mode === "category") {
    return <QualificationCategoriesBlock items={additional.qualification_categories ?? []} />;
  }
  if (mode === "notes") {
    return <StatusFactsBlock additional={additional} />;
  }
  return (
    <div className="space-y-8" data-testid="ppr-additional-section">
      <section className="space-y-3 print:hidden" data-testid="ppr-additional-status-facts-block">
        <h3 className="text-sm font-semibold text-zinc-900 dark:text-zinc-50">Примечание</h3>
        {editableStatusFacts && personId && onStatusFactsSaved ? <><SourceNoteHint value={additional.source_note_hint} /><PprAdditionalStatusFactsEditor personId={personId} facts={additional.status_facts} onSaved={onStatusFactsSaved} /></> : <StatusFactsBlock additional={additional} />}
      </section>

      <section className="space-y-3" data-testid="ppr-additional-awards-block">
        <h3 className="text-sm font-semibold text-zinc-900 dark:text-zinc-50">Награды</h3>
        <AwardsBlock items={additional.awards} declaredEmpty={additional.awards_none} />
      </section>

      <section className="space-y-3" data-testid="ppr-additional-degrees-block">
        <h3 className="text-sm font-semibold text-zinc-900 dark:text-zinc-50">Учёные степени</h3>
        <AcademicDegreesBlock items={additional.academic_degrees} declaredEmpty={additional.academic_degrees_none} />
      </section>

      <section className="space-y-3" data-testid="ppr-additional-titles-block">
        <h3 className="text-sm font-semibold text-zinc-900 dark:text-zinc-50">Учёные звания</h3>
        <AcademicTitlesBlock items={additional.academic_titles} declaredEmpty={additional.academic_titles_none} />
      </section>
    </div>
  );
}
